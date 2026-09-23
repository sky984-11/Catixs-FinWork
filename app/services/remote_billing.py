"""Maintenance estimates. Naive input is always Beijing time; locale only determines rate windows."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

import pytz

from app.schemas.remote_billing import (
    BillingContext,
    CustomerMaintenancePrice,
    GeneralBillingRules,
    validate_billing_timezone,
)

BEIJING = timezone(timedelta(hours=8))


def normalize_rules(source: dict) -> dict:
    if source.get("mode") == "general":
        return source
    if source.get("mode") != "package":
        return {
            "mode": "general",
            "currency": source["currency"],
            "pricing": "tiered_hourly",
            "hourly_tiers": source["tiers"],
        }
    return {
        "mode": "general",
        "currency": source["currency"],
        "pricing": "package",
        "tiers": source["tiers"],
        "overtime_enabled": True,
        "overtime_hourly_rate": source["overtime_hourly_rate"],
        "overtime_threshold_minutes": source["overtime_threshold_minutes"],
        "overtime_rounding": source["overtime_rounding"],
        "night_enabled": Decimal(str(source["night_multiplier"])) > 1,
        "night_multiplier": source["night_multiplier"],
        "night_applies_to_emergency": source["night_applies_to_emergency"],
        "emergency_fee": source["emergency_fee"],
        "emergency_response_minutes": source["emergency_response_minutes"],
        "emergency_regions": [source["emergency_region"]],
        "emergency_confirmation_regions": [source["emergency_confirmation_region"]],
        "transport_mode": "reimburse",
        "transport_included_regions": [source["transport_included_region"]],
        "project_services": source["project_services"],
        "settlement_cycles": source["settlement_cycles"],
        "payment_methods": [
            {"name": "原国内收款", "note": source["domestic_payment"]},
            {"name": "原日本收款", "tax_mode": "confirm", "note": source["japan_payment"]},
        ],
        "note": "由旧固定档位转换；当地夜班起止时段需确认。",
    }


def beijing_time(value: str | datetime) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING)
    return value.astimezone(BEIJING)


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_fixed_fee(pricing, context, source=None):
    result = {"status": "pending", "total": None, "currency": pricing.currency, "lines": [], "notices": []}
    amounts = {}

    def add(label, amount, currency):
        if amount is None:
            result["notices"].append(f"金额待确认：{label}")
            return
        result["lines"].append({"label": label, "amount": money(amount), "currency": currency})
        amounts[currency] = amounts.get(currency, Decimal(0)) + amount

    add("本次施工一口价", pricing.fixed_fee, pricing.currency)
    if not pricing.expenses_included:
        if context.reimbursed_transport is not None:
            add("报销交通费", context.reimbursed_transport, (source or {}).get("currency", pricing.currency))
        for expense in context.expenses:
            add(f"实报实销：{expense.name}", expense.amount, expense.currency)
    totals = {currency: money(amount) for currency, amount in amounts.items()}
    result.update(subtotals=totals, subtotal=totals.get(pricing.currency, "0.00"))
    if not result["notices"]:
        result.update(
            status="calculated", totals=totals, total=totals.get(pricing.currency) if len(totals) == 1 else None
        )
    return result


def calculate_record_fee(
    source, arrived_at, left_at, zone="Asia/Shanghai", region="", context=None, customer_pricing=None
):
    result = {"status": "pending", "total": None, "lines": [], "notices": [], "currency": None}
    try:
        pricing = CustomerMaintenancePrice.model_validate(customer_pricing) if customer_pricing else None
        ctx = BillingContext.model_validate(context or {})
        if pricing and pricing.kind == "fixed":
            return calculate_fixed_fee(pricing, ctx, source)
    except (ValueError, TypeError) as exc:
        return result | {"notices": [f"无法计费：{exc}"]}
    if not source:
        return result | {"notices": ["工程师尚未配置计费规则"]}
    try:
        rules = GeneralBillingRules.model_validate(normalize_rules(source))
        original_currency = rules.currency
        if pricing and pricing.kind == "hourly" and pricing.hourly_rate is not None:
            rules = rules.model_copy(
                update={"pricing": "hourly", "hourly_rate": pricing.hourly_rate, "currency": pricing.currency}
            )
        result["currency"] = rules.currency
        tz = pytz.timezone(validate_billing_timezone(zone))
        if not arrived_at or not left_at:
            return result | {"notices": ["到场、离场时间齐全后计算费用"]}
        start, end = beijing_time(arrived_at), beijing_time(left_at)
        if end < start:
            raise ValueError("离场时间不能早于到场时间")
        minutes = int((end - start).total_seconds() // 60)
        if minutes > 44640:
            raise ValueError("单次工时超过31天，请拆分记录后计费")
    except (ValueError, TypeError, KeyError) as exc:
        return result | {"notices": [f"无法计费：{exc}"]}
    result.update(
        work_minutes=minutes,
        timezone=zone,
        local_arrived_at=start.astimezone(tz).isoformat(),
        local_left_at=end.astimezone(tz).isoformat(),
    )
    if ctx.service_type == "project":
        return result | {"notices": ["此服务按项目内容单独报价"]}
    if minutes == 0 and not ctx.expenses and not ctx.actual_commute_minutes and not rules.additional_fees:
        return result | {"status": "calculated", "total": "0.00", "night_minutes": 0}
    notices = result["notices"]
    if pricing and (pricing.kind == "pending" or (pricing.kind == "hourly" and pricing.hourly_rate is None)):
        return result | {"notices": ["本次施工报价待确认，请填写小时单价或一口价"]}
    if rules.night_enabled and not rules.night_start:
        notices.append("当地夜班起止时段未确认")
    night_flags = []
    if rules.night_enabled and rules.night_start:
        for minute in range(minutes):
            local_clock = (start + timedelta(minutes=minute)).astimezone(tz).strftime("%H:%M")
            night_flags.append(
                rules.night_start <= local_clock < rules.night_end
                if rules.night_start < rules.night_end
                else local_clock >= rules.night_start or local_clock < rules.night_end
            )
    result["night_minutes"] = None if rules.night_enabled and not rules.night_start else sum(night_flags)

    def night_extra(amount, begin, finish):
        night = sum(night_flags[begin:finish])
        fraction = (
            Decimal(bool(night)) if rules.night_basis == "any_overlap" else Decimal(night) / max(finish - begin, 1)
        )
        return amount * (rules.night_multiplier - 1) * fraction

    lines = result["lines"]

    def add(label, amount, currency=None):
        lines.append({"label": label, "amount": money(amount), "currency": currency or rules.currency})

    billed = max(minutes, rules.minimum_minutes)
    billed = (
        (billed + rules.billing_increment_minutes - 1) // rules.billing_increment_minutes
    ) * rules.billing_increment_minutes
    result["billable_minutes"] = billed
    base, extra_night = Decimal(0), Decimal(0)
    if minutes == 0:
        result["billable_minutes"] = 0
    elif rules.pricing == "hourly":
        if rules.hourly_rate is None:
            notices.append("小时单价未确认")
        else:
            base = rules.hourly_rate * billed / 60
            extra_night = night_extra(base, 0, minutes)
            add(f"人工费（计费{billed}分钟）", base)
    elif rules.pricing == "tiered_hourly":
        previous = 0
        for tier in rules.hourly_tiers:
            stop = min(billed, tier.up_to_minutes or billed)
            part = Decimal(max(0, stop - previous)) * tier.hourly_rate / 60
            base += part
            extra_night += night_extra(part, min(previous, minutes), min(stop, minutes))
            previous = stop
            if stop >= billed:
                break
        add(f"分段人工费（计费{billed}分钟）", base)
    else:
        tier = next((tier for tier in rules.tiers if billed <= tier.up_to_minutes), rules.tiers[-1])
        base = tier.total_fee
        boundary = rules.tiers[-1].up_to_minutes
        extra_night = night_extra(base, 0, min(minutes, boundary))
        add(f"档位总价（{tier.up_to_minutes}分钟以内）", base)
        overtime = max(0, billed - boundary)
        if overtime:
            if not rules.overtime_enabled or rules.overtime_hourly_rate is None:
                notices.append("超出档位的加班费未配置或未确认")
            else:
                threshold = rules.overtime_threshold_minutes
                if rules.overtime_rounding == "half_hour_round":
                    units = Decimal(overtime // 60 + (overtime % 60 >= threshold))
                elif overtime < threshold:
                    units = Decimal(0)
                elif rules.overtime_rounding == "ceil_after_threshold":
                    units = Decimal((overtime + 59) // 60)
                else:
                    units = Decimal(overtime) / 60
                fee = units * rules.overtime_hourly_rate
                base += fee
                extra_night += night_extra(fee, min(minutes, boundary), minutes)
                add(f"加班费（计费{money(units * 60)}分钟）", fee)
    if ctx.emergency:
        if region in rules.emergency_confirmation_regions or (
            rules.emergency_regions and region not in rules.emergency_regions
        ):
            notices.append("此区域紧急维护费用及到场时间需确认")
        elif rules.emergency_fee is None:
            notices.append("紧急维护加收金额未确认")
        else:
            add("紧急维护加收", rules.emergency_fee, original_currency)
            if rules.night_applies_to_emergency:
                add("紧急维护夜班附加费", night_extra(rules.emergency_fee, 0, minutes), original_currency)
    if rules.night_enabled and rules.night_start:
        add(f"夜班附加费（当地夜班{result['night_minutes']}分钟）", extra_night)
    labor_lines = list(lines)
    transport_due = (
        (minutes > 0 or bool(ctx.actual_commute_minutes))
        and rules.transport_mode != "none"
        and (not rules.transport_included_regions or region not in rules.transport_included_regions)
    )
    if transport_due:
        if rules.transport_included_regions and not region:
            notices.append("服务地区未填写，交通费适用范围待确认")
        elif rules.transport_mode == "fixed":
            if rules.transport_fee is None:
                notices.append("每次固定交通费未确认")
            else:
                add("每次固定交通费", rules.transport_fee, original_currency)
        elif rules.transport_mode == "hourly":
            rate = (
                rules.commute_hourly_rate
                if rules.commute_hourly_rate is not None
                else rules.hourly_rate if rules.pricing == "hourly" else None
            )
            commute = rules.commute_minutes if rules.commute_mode == "fixed" else ctx.actual_commute_minutes
            if commute is None:
                notices.append("往返实际通勤时长待填写")
            elif rate is None:
                notices.append("通勤小时单价未确认")
            else:
                if rules.commute_mode == "actual":
                    step = rules.commute_increment_minutes
                    commute = (commute + step - 1) // step * step
                result["commute_billable_minutes"] = commute
                add(
                    f"每次通勤费（{commute}分钟）",
                    rate * commute / 60,
                    original_currency if rules.commute_hourly_rate is not None else rules.currency,
                )
        elif ctx.reimbursed_transport is None:
            notices.append("实报实销交通费待确认")
        else:
            add("报销交通费", ctx.reimbursed_transport, original_currency)
    for fee in rules.additional_fees:
        if fee.id in ctx.excluded_fee_ids or region in fee.excluded_regions:
            continue
        if fee.excluded_regions and not region:
            notices.append(f"{fee.name}适用地区待确认")
            continue
        if fee.amount is None:
            notices.append(f"{fee.name}金额待确认")
            continue
        if fee.mode == "fixed":
            add(fee.name, fee.amount, original_currency)
            continue
        duration = (
            fee.minutes
            if fee.minutes_source == "fixed"
            else (
                minutes
                if fee.minutes_source == "work"
                else ctx.additional_fee_minutes.get(
                    fee.id, ctx.actual_commute_minutes if fee.id == "legacy-transport" else None
                )
            )
        )
        if duration is None:
            notices.append(f"{fee.name}实际时长待填写")
            continue
        billed_duration = (duration + fee.increment_minutes - 1) // fee.increment_minutes * fee.increment_minutes
        add(f"{fee.name}（计费{billed_duration}分钟）", fee.amount * billed_duration / 60, original_currency)
    for expense in ctx.expenses:
        if expense.amount is None:
            notices.append(f"实报实销待确认：{expense.name}")
        else:
            add(f"实报实销：{expense.name}", expense.amount, expense.currency)

    def totals(items):
        amounts = {}
        for line in items:
            amounts[line["currency"]] = amounts.get(line["currency"], Decimal(0)) + Decimal(line["amount"])
        return amounts

    subtotals = totals(lines)
    if rules.payment_methods:
        method = next((item for item in rules.payment_methods if item.name == ctx.payment_method), None)
        if method is None:
            notices.append("请选择本次收款方式以确定税费")
        elif method.tax_mode == "confirm" or (method.tax_mode == "extra" and method.tax_rate is None):
            notices.append("此收款方式的税率或税额待确认")
        elif method.tax_mode == "extra":
            for currency, amount in (totals(labor_lines) if method.tax_base == "labor" else subtotals).items():
                add("另加税费", amount * method.tax_rate / 100, currency)
    result["subtotal"] = money(subtotals.get(rules.currency, Decimal(0)))
    result["subtotals"] = {currency: money(amount) for currency, amount in subtotals.items()}
    if not notices:
        amounts = {currency: money(amount) for currency, amount in totals(lines).items()}
        result.update(
            status="calculated",
            totals=amounts,
            total=amounts.get(rules.currency, "0.00") if len(amounts) <= 1 else None,
        )
    return result
