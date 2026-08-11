import logging
import os
import re
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from tortoise.expressions import Q

from app.controllers.bill import bill_controller, bill_item_controller
from app.models.company import BillAuditLog, BillPayment, BillingProductTemplate, BillingSubscription, Company
from app.schemas.base import Success, SuccessExtra
from app.schemas.bills import (
    BillCreate,
    BillGeneratePayload,
    BillPaymentPayload,
    BillStatusPayload,
    BillUpdate,
    BillingSubscriptionPayload,
    BillingTemplatePayload,
    FeishuBillSyncPayload,
)
from app.utils.feishu_app import FEISHU_API_BASE, get_tenant_access_token

logger = logging.getLogger(__name__)

router = APIRouter()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads", "bills")
os.makedirs(UPLOAD_DIR, exist_ok=True)

SORTABLE_FIELDS = {
    "customer_name",
    "bill_month",
    "is_settled",
    "invoice_no",
    "invoice_date",
    "due_date",
    "billing_start_date",
    "billing_end_date",
    "currency",
    "total_amount",
    "paid_amount",
    "unpaid_amount",
    "owner",
    "status",
}

BILL_STATUS_LABELS = {
    "issued": "已开具",
    "pending_approval": "待审批",
    "pending_send": "待发送",
    "sent": "已发送",
    "paid": "已付款",
    "overdue": "未付款",
}

BILL_TRANSITIONS = {
    "submit": {"from": {"issued", "pending_approval"}, "to": "pending_approval"},
    "approve": {"from": {"pending_approval"}, "to": "pending_send"},
    "reject": {"from": {"pending_approval", "pending_send"}, "to": "pending_approval"},
    "send": {"from": {"pending_send"}, "to": "sent"},
    "mark_paid": {"from": {"issued", "pending_approval", "pending_send", "sent", "overdue"}, "to": "paid"},
    "mark_overdue": {"from": {"issued", "pending_approval", "pending_send", "sent"}, "to": "overdue"},
}

FEISHU_BILL_FIELD_ALIASES = {
    "company_name": ["客户", "客户名称", "客户名", "供应商", "供应商名称", "公司", "公司名称", "Customer", "Vendor", "Company"],
    "invoice_no": ["账单编号", "发票编号", "Invoice ID", "Invoice No", "Invoice Number", "Bill No", "编号"],
    "bill_month": ["账单月份", "月份", "计费月份", "Billing Month", "Month"],
    "invoice_date": ["账单日期", "开票日期", "发票日期", "Invoice Date", "Bill Date"],
    "due_date": ["到期日", "截止日期", "付款截止日", "Due Date"],
    "billing_start_date": ["计费开始", "计费开始日期", "服务开始", "Billing Start Date", "Start Date"],
    "billing_end_date": ["计费结束", "计费结束日期", "服务结束", "Billing End Date", "End Date"],
    "currency": ["币种", "Currency"],
    "net_amount": ["Net Amount", "净额", "不含税金额", "小计"],
    "vat_amount": ["VAT Amount", "VAT", "税额", "增值税"],
    "total_amount": ["Total Amount", "总金额", "账单金额", "应收金额", "Amount"],
    "paid_amount": ["Paid Amount", "已付金额", "已收金额", "已付款", "已收款"],
    "unpaid_amount": ["Unpaid Amount", "未付金额", "未收金额", "欠费金额", "欠款"],
    "owner": ["负责人", "Owner", "Sales", "AM"],
    "term": ["账期", "付款账期", "Payment Term", "Term"],
    "status": ["状态", "账单状态", "Status"],
    "remark": ["备注", "说明", "Remark", "Notes"],
    "bill_link": ["账单链接", "账单文件", "账单附件", "Invoice Link", "Bill Link"],
    "payment_voucher_url": ["付款凭证", "支付凭证", "Payment Voucher", "Voucher"],
    "local_currency": ["本地币种", "记账币种", "Local Currency"],
    "fx_rate": ["汇率", "FX Rate", "Exchange Rate"],
    "local_amount": ["本地金额", "记账金额", "Local Amount"],
    "service_id": ["服务ID", "Service ID", "Circuit ID", "资源ID"],
    "service": ["服务", "服务类型", "Service", "Service Type"],
    "item": ["项目", "产品", "产品名称", "Item", "Product"],
    "location": ["位置", "POP", "机房", "Location"],
    "nrc_amount": ["NRC", "NRC Amount", "一次性费用"],
    "mrc_amount": ["MRC", "MRC Amount", "月费"],
}

FEISHU_STATUS_MAP = {
    "已开具": "issued",
    "已开票": "issued",
    "待审批": "pending_approval",
    "待发送": "pending_send",
    "已发送": "sent",
    "已付款": "paid",
    "已收款": "paid",
    "已结清": "paid",
    "逾期": "overdue",
    "未付款": "overdue",
    "未收款": "overdue",
}

FEISHU_COMPANY_ALIASES = {
    "263": "263 Global Communications Limited",
    "AKILE": "AK",
    "AOFEI奥飞": "Aofei",
    "BACKWAVES": "BACK WAVES LIMITED",
    "BACKWAVES HKD": "BACK WAVES LIMITED",
    "BACKWAVES SG": "BACK WAVES LIMITED",
    "CMI": "China Mobile International Limited",
    "CMI UK": "China Mobile International Limited",
    "CUG UK": "China Unicom (Europe) Operations Limited",
    "CIELOCOM": "Cielocom Hongkong Limited",
    "CORNSEED": "Cornseed Limited",
    "DEEPINSIGHT强尼": "DeepInsight Inc.",
    "DODO KK": "DODO K.K.",
    "EONS": "Eons Data Communications Limited",
    "FLARESPEED": "Flarespeed HK Co., Limited",
    "FLARESPEED大姚": "Flarespeed HK Co., Limited",
    "GCC 无忧云": "GCC CLOUD TECHNOLOGY LIMITED",
    "GEELINX 安锐普世": "Geelinx",
    "H POP 肖总": "H POP Technology Limited",
    "HKBRI": "Hong Kong Bridge Info-tech Limited",
    "LIASAIL": "Liasail Global HongKong Limited",
    "LINKSPEED": "上海灵肃数据科技有限公司",
    "MOECHUANG": "Moechuang",
    "NETTOP": "NETTOP LTD",
    "ONEESWORLD": "ONEESWORLD PTE.LTD",
    "PBS": "Telstra PBS limited",
    "QUICKFOX科臻赛": "Quickfox",
    "XBXZ": "XIAOBAIXUEZHANG",
    "XIYE": "Futurex investment company limited",
    "飞牛": "Awesomecloud Limited",
    "高诺": "GOALNOW NETWORK TECHNOLOGY COMPANY LIMITED",
    "荔枝云": "CloudSDWan Limited",
    "六六云": "CloudSDWan Limited",
    "萌创网络": "Moechuang",
    "南凌": "Nova",
    "瑞技": "瑞技BBT",
    "王菠萝": "Fountainhead Technologies Limited",
    "心海": "STARCLOUD INFORMATION LIMITED",
    "云端": "Cloud Hong Kong East Asia Telecom Co., Limited",
    "智联": "Zhilian Technology CO., LTD.",
    "智盈": "Guangzhou Tieren Intelligent Manufacturing Technology Co., Ltd. (广州铁刃智造技术有限公司)",
    "紫电": "Gadgets Lab Ltd",
}


def build_invoice_no(customer_name: str | None, owner: str | None, bill_month) -> str:
    if not customer_name or not owner or not bill_month:
        return ""
    month_text = str(bill_month)
    if len(month_text) < 7:
        return ""
    return f"{customer_name}_INV{owner}_{month_text[2:4]}.{month_text[5:7]}"


def month_start(value: date | None = None) -> date:
    source = value or date.today()
    return date(source.year, source.month, 1)


def month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def date_overlap(start: date, end: date, left: date | None, right: date | None) -> tuple[date, date] | None:
    effective_start = max(start, left) if left else start
    effective_end = min(end, right) if right else end
    if effective_end < effective_start:
        return None
    return effective_start, effective_end


def sync_settled_status(payload: dict):
    if "unpaid_amount" not in payload:
        return
    try:
        payload["is_settled"] = float(payload.get("unpaid_amount") or 0) <= 0
    except (TypeError, ValueError):
        payload["is_settled"] = False


def sync_local_amount(payload: dict):
    fx_rate = payload.get("fx_rate")
    local_currency = payload.get("local_currency")
    if not fx_rate or not local_currency:
        return
    payload["local_amount"] = round(float(payload.get("total_amount") or 0) * float(fx_rate), 2)


def sync_bill_amounts(payload: dict, items: list):
    item_total = sum((item.nrc_amount or 0) + (item.mrc_amount or 0) for item in items)
    net_amount = float(payload.get("net_amount") or item_total or 0)
    vat_amount = float(payload.get("vat_amount") or 0)
    paid_amount = float(payload.get("paid_amount") or 0)
    if abs(net_amount - item_total) >= 0.01:
        raise HTTPException(status_code=400, detail="Net Amount must equal Invoice Summary NRC + MRC total")
    total_amount = item_total + vat_amount
    payload["net_amount"] = item_total
    payload["total_amount"] = total_amount
    payload["unpaid_amount"] = max(total_amount - paid_amount, 0)
    sync_local_amount(payload)


def build_bill_order(sort_field: str = "", sort_order: str = "") -> list[str]:
    if sort_field in SORTABLE_FIELDS and sort_order in {"ascend", "descend"}:
        prefix = "-" if sort_order == "descend" else ""
        return [f"{prefix}{sort_field}", "customer_name", "-bill_month", "-id"]
    return ["customer_name", "-bill_month", "-id"]


async def build_bill_summary(q: Q) -> dict:
    rows = await bill_controller.model.filter(q).values(
        "total_amount",
        "paid_amount",
        "unpaid_amount",
        "currency",
        "status",
    )
    by_currency = {}
    by_status = {}
    for row in rows:
        currency = row.get("currency") or "-"
        bucket = by_currency.setdefault(currency, {"currency": currency, "total": 0, "paid": 0, "unpaid": 0, "count": 0})
        total_amount = float(row.get("total_amount") or 0)
        paid_amount = float(row.get("paid_amount") or 0)
        unpaid_amount = float(row.get("unpaid_amount") or 0)
        bucket["total"] += total_amount
        bucket["paid"] += paid_amount
        bucket["unpaid"] += unpaid_amount
        bucket["count"] += 1
        status = row.get("status") or "issued"
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "count": len(rows),
        "by_currency": sorted(by_currency.values(), key=lambda item: item["currency"]),
        "by_status": [
            {"status": key, "label": BILL_STATUS_LABELS.get(key, key), "count": value}
            for key, value in sorted(by_status.items())
        ],
    }


async def bill_to_dict(obj, include_items: bool = False):
    data = await obj.to_dict()
    data["status_label"] = BILL_STATUS_LABELS.get(data.get("status") or "issued", data.get("status") or "issued")
    if include_items:
        items = await bill_item_controller.model.filter(bill_id=obj.id).order_by("id")
        data["items"] = [await item.to_dict() for item in items]
        data["payments"] = [await item.to_dict() for item in await BillPayment.filter(bill_id=obj.id).order_by("-payment_date", "-id")]
        data["audit_logs"] = [await item.to_dict() for item in await BillAuditLog.filter(bill_id=obj.id).order_by("-created_at", "-id")]
    return data


async def write_bill_audit(bill_id: int, action: str, before: dict | None = None, after: dict | None = None, comment: str = "", operator: str = ""):
    await BillAuditLog.create(
        bill_id=bill_id,
        action=action,
        operator=operator or None,
        comment=comment or None,
        before=before or {},
        after=after or {},
    )


async def replace_bill_items(bill_id: int, items: list):
    await bill_item_controller.model.filter(bill_id=bill_id).delete()
    if not items:
        return
    await bill_item_controller.model.bulk_create(
        [
            bill_item_controller.model(
                bill_id=bill_id,
                service_id=item.service_id or str(index + 1),
                service=item.service or "",
                item=item.item or "",
                location=item.location or "",
                start_date=item.start_date,
                end_date=item.end_date,
                nrc_amount=item.nrc_amount or 0,
                mrc_amount=item.mrc_amount or 0,
                amount=(item.nrc_amount or 0) + (item.mrc_amount or 0),
            )
            for index, item in enumerate(items)
        ]
    )


async def template_to_dict(obj: BillingProductTemplate) -> dict[str, Any]:
    return await obj.to_dict()


async def subscription_to_dict(obj: BillingSubscription) -> dict[str, Any]:
    data = await obj.to_dict()
    company = await Company.get_or_none(id=obj.company_id)
    template = await BillingProductTemplate.get_or_none(id=obj.template_id) if obj.template_id else None
    data["company_name"] = company.name if company else ""
    data["template_name"] = template.name if template else ""
    return data


def template_payload_data(payload: BillingTemplatePayload) -> dict[str, Any]:
    return {
        "name": payload.name.strip(),
        "product_code": payload.product_code.strip() or None,
        "service_type": payload.service_type.strip() or None,
        "billing_rule": payload.billing_rule.strip() or "monthly",
        "unit_price": float(payload.unit_price or 0),
        "currency": payload.currency.strip() or "USD",
        "unit": payload.unit.strip() or None,
        "default_contract_months": int(payload.default_contract_months or 12),
        "status": bool(payload.status),
        "remark": payload.remark.strip() or None,
    }


def clean(value: Any) -> str:
    return str(value or "").strip()


def parse_feishu_bitable_url(url: str) -> dict[str, str]:
    parsed = urlparse(clean(url))
    params = parse_qs(parsed.query)
    parts = [part for part in parsed.path.split("/") if part]
    app_token = ""
    if "base" in parts:
        index = parts.index("base")
        if len(parts) > index + 1:
            app_token = parts[index + 1]
    return {
        "app_token": app_token,
        "table_id": (params.get("table") or [""])[0],
        "view_id": (params.get("view") or [""])[0],
    }


def feishu_plain_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        parts = [feishu_plain_value(item) for item in value]
        parts = [str(item) for item in parts if item not in (None, "")]
        return ", ".join(parts)
    if isinstance(value, dict):
        for key in ("text", "name", "en_name", "email", "link", "url"):
            if value.get(key):
                return value.get(key)
        if "value" in value:
            return feishu_plain_value(value.get("value"))
        return ", ".join(str(item) for item in value.values() if item not in (None, ""))
    return value


def feishu_url_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        for item in value:
            link = feishu_url_value(item)
            if link:
                return link
        return clean(feishu_plain_value(value))
    if isinstance(value, dict):
        for key in ("tmp_url", "url", "link"):
            if value.get(key):
                return clean(value.get(key))
        return clean(feishu_plain_value(value))
    return clean(value)


def pick_feishu_field(fields: dict[str, Any], key: str) -> Any:
    normalized = {name.strip().lower(): value for name, value in fields.items()}
    for alias in FEISHU_BILL_FIELD_ALIASES.get(key, []):
        if alias.strip().lower() in normalized:
            return feishu_plain_value(normalized[alias.strip().lower()])
    return None


def pick_feishu_url_field(fields: dict[str, Any], key: str) -> str:
    normalized = {name.strip().lower(): value for name, value in fields.items()}
    for alias in FEISHU_BILL_FIELD_ALIASES.get(key, []):
        if alias.strip().lower() in normalized:
            return feishu_url_value(normalized[alias.strip().lower()])
    return ""


def parse_feishu_date(value: Any) -> date | None:
    value = feishu_plain_value(value)
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp).date()
    text = clean(value)
    if not text:
        return None
    compact = re.sub(r"\D", "", text)
    if len(compact) == 8:
        try:
            return date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))
        except ValueError:
            pass
    if len(compact) == 6:
        try:
            return date(int(compact[:4]), int(compact[4:6]), 1)
        except ValueError:
            pass
    for pattern in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y-%m",
        "%Y/%m",
        "%Y.%m",
        "%y-%m-%d",
        "%y/%m/%d",
        "%y.%m.%d",
        "%y-%m",
        "%y/%m",
        "%y.%m",
    ):
        try:
            parsed = datetime.strptime(text, pattern)
            return date(parsed.year, parsed.month, parsed.day)
        except ValueError:
            continue
    match = re.search(r"(\d{4})[-/.年](\d{1,2})(?:[-/.月](\d{1,2}))?", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3) or 1))
        except ValueError:
            return None
    return None


def parse_feishu_float(value: Any) -> float | None:
    value = feishu_plain_value(value)
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def normalize_feishu_status(value: Any, unpaid_amount: float | None = None) -> str:
    text = clean(feishu_plain_value(value))
    if text in BILL_STATUS_LABELS:
        return text
    if text in FEISHU_STATUS_MAP:
        return FEISHU_STATUS_MAP[text]
    if unpaid_amount is not None and unpaid_amount <= 0:
        return "paid"
    return "issued"


async def get_or_create_billing_company(name: str, bill_type: int, create_missing: bool) -> Company | None:
    name = clean(name)
    if not name:
        return None
    target_name = FEISHU_COMPANY_ALIASES.get(name.upper(), name)
    company = await Company.filter(Q(name=target_name) | Q(legal_name=target_name)).first()
    if not company and target_name != name:
        company = await Company.filter(Q(name=name) | Q(legal_name=name)).first()
    if not company:
        company = await Company.filter(Q(name=name) | Q(legal_name=name)).first()
    if company or not create_missing:
        return company
    return await Company.create(role=2 if bill_type == 2 else 1, name=name, legal_name=name, status=True)


def feishu_record_to_bill_payload(record: dict[str, Any], company_id: int, bill_type: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fields = record.get("fields") or {}
    total_amount = parse_feishu_float(pick_feishu_field(fields, "total_amount"))
    net_amount = parse_feishu_float(pick_feishu_field(fields, "net_amount"))
    vat_amount = parse_feishu_float(pick_feishu_field(fields, "vat_amount")) or 0
    paid_amount = parse_feishu_float(pick_feishu_field(fields, "paid_amount")) or 0
    unpaid_amount = parse_feishu_float(pick_feishu_field(fields, "unpaid_amount"))
    if net_amount is None:
        net_amount = total_amount if total_amount is not None else 0
    if total_amount is None:
        total_amount = float(net_amount or 0) + float(vat_amount or 0)
    if unpaid_amount is None:
        unpaid_amount = max(float(total_amount or 0) - float(paid_amount or 0), 0)

    bill_month = parse_feishu_date(pick_feishu_field(fields, "bill_month"))
    if bill_month:
        bill_month = month_start(bill_month)
    invoice_date = parse_feishu_date(pick_feishu_field(fields, "invoice_date"))
    billing_start = parse_feishu_date(pick_feishu_field(fields, "billing_start_date")) or bill_month
    billing_end = parse_feishu_date(pick_feishu_field(fields, "billing_end_date")) or (month_end(bill_month) if bill_month else None)
    customer_name = clean(pick_feishu_field(fields, "company_name"))
    currency = clean(pick_feishu_field(fields, "currency")) or "USD"
    status = normalize_feishu_status(pick_feishu_field(fields, "status"), unpaid_amount)
    bill_link = pick_feishu_url_field(fields, "bill_link")
    payment_voucher_url = pick_feishu_url_field(fields, "payment_voucher_url")
    remark = clean(pick_feishu_field(fields, "remark"))
    if bill_link:
        remark = f"{remark}\n账单链接: {bill_link}".strip()
    item = {
        "service_id": clean(pick_feishu_field(fields, "service_id")) or record.get("record_id") or "",
        "service": clean(pick_feishu_field(fields, "service")) or "Billing",
        "item": clean(pick_feishu_field(fields, "item")) or clean(pick_feishu_field(fields, "invoice_no")) or "Billing record",
        "location": clean(pick_feishu_field(fields, "location")),
        "start_date": billing_start,
        "end_date": billing_end,
        "nrc_amount": parse_feishu_float(pick_feishu_field(fields, "nrc_amount")) or 0,
        "mrc_amount": parse_feishu_float(pick_feishu_field(fields, "mrc_amount")) or float(net_amount or 0),
    }
    item["amount"] = float(item["nrc_amount"] or 0) + float(item["mrc_amount"] or 0)
    payload = {
        "company_id": company_id,
        "invoice_no": clean(pick_feishu_field(fields, "invoice_no")),
        "customer_name": customer_name,
        "bill_month": bill_month,
        "invoice_date": invoice_date,
        "due_date": parse_feishu_date(pick_feishu_field(fields, "due_date")),
        "billing_start_date": billing_start,
        "billing_end_date": billing_end,
        "currency": currency,
        "net_amount": float(item["amount"] or 0),
        "vat_amount": vat_amount,
        "total_amount": float(item["amount"] or 0) + float(vat_amount or 0),
        "paid_amount": paid_amount,
        "unpaid_amount": max(float(item["amount"] or 0) + float(vat_amount or 0) - float(paid_amount or 0), 0),
        "is_settled": status == "paid",
        "payment_voucher_url": payment_voucher_url or "",
        "owner": clean(pick_feishu_field(fields, "owner")),
        "remark": remark,
        "bill_type": bill_type,
        "status": status,
        "term": clean(pick_feishu_field(fields, "term")),
        "approval_comment": "",
        "local_currency": clean(pick_feishu_field(fields, "local_currency")) or None,
        "fx_rate": parse_feishu_float(pick_feishu_field(fields, "fx_rate")),
        "local_amount": parse_feishu_float(pick_feishu_field(fields, "local_amount")),
        "source": "feishu_bitable",
        "source_record_id": record.get("record_id"),
    }
    if not payload["invoice_no"]:
        payload["invoice_no"] = build_invoice_no(customer_name, payload["owner"], bill_month)
    if not payload["local_amount"]:
        sync_local_amount(payload)
    return payload, [item]


async def fetch_feishu_bitable_records(app_token: str, table_id: str, view_id: str = "") -> list[dict[str, Any]]:
    token = await get_tenant_access_token()
    if not token:
        raise HTTPException(status_code=400, detail="飞书应用凭证未配置或获取 tenant_access_token 失败")
    records = []
    page_token = ""
    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            params = {"page_size": 500}
            if view_id:
                params["view_id"] = view_id
            if page_token:
                params["page_token"] = page_token
            response = await client.get(
                f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                data = response.json()
            except ValueError:
                raise HTTPException(status_code=502, detail=f"飞书多维表返回非 JSON：{response.text[:200]}")
            if response.status_code != 200 or data.get("code") != 0:
                raise HTTPException(status_code=502, detail=f"读取飞书多维表失败：{data.get('msg') or data}")
            payload = data.get("data") or {}
            records.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token") or ""
            if not page_token:
                break
    return records


async def subscription_payload_data(payload: BillingSubscriptionPayload) -> dict[str, Any]:
    template = await BillingProductTemplate.get_or_none(id=payload.template_id) if payload.template_id else None
    return {
        "company_id": payload.company_id,
        "template_id": template.id if template else None,
        "product_code": clean((payload.product_code or template.product_code) if template else payload.product_code),
        "service_type": clean((payload.service_type or template.service_type) if template else payload.service_type) or None,
        "service_name": clean((payload.service_name or template.name) if template else payload.service_name) or None,
        "service_location": clean(payload.service_location) or None,
        "billing_start_date": payload.billing_start_date,
        "billing_end_date": payload.billing_end_date,
        "contract_months": int(payload.contract_months or (template.default_contract_months if template else 12)),
        "unit_price": float(payload.unit_price or (template.unit_price if template else 0)),
        "quantity": float(payload.quantity or 1),
        "currency": clean((payload.currency or template.currency) if template else payload.currency) or "USD",
        "unit": clean((payload.unit or template.unit) if template else payload.unit) or None,
        "vat_rate": float(payload.vat_rate or 0),
        "is_active": bool(payload.is_active),
        "last_billed_month": payload.last_billed_month,
        "remark": clean(payload.remark) or None,
    }


async def bill_exists_for_subscription(subscription_id: int, bill_month: date) -> bool:
    marker = f"subscription:{subscription_id}"
    return await bill_item_controller.model.filter(
        service_id=marker,
        bill__bill_month=bill_month,
    ).exists()


def generated_invoice_no(company: Company, owner: str, bill_month: date, sequence: int, location: str = "") -> str:
    customer_code = (company.code or company.name or company.legal_name or "CUSTOMER").replace(" ", "")
    suffix = "".join(ch for ch in (location or "") if ch.isalnum()).upper()[:4] or "AUTO"
    return f"{customer_code}_INV{owner or 'AUTO'}_{bill_month:%y.%m}_{sequence:03d}_{suffix}"


async def build_generated_bill_payload(
    company: Company,
    subscriptions: list[BillingSubscription],
    payload: BillGeneratePayload,
    bill_month: date,
    sequence: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    start = month_start(bill_month)
    end = month_end(start)
    days_in_month = (end - start).days + 1
    items = []
    vat_amount = 0.0
    for subscription in subscriptions:
        overlap = date_overlap(start, end, subscription.billing_start_date, subscription.billing_end_date)
        if not overlap:
            continue
        item_start, item_end = overlap
        bill_days = (item_end - item_start).days + 1
        mrc_amount = round(float(subscription.unit_price or 0) * float(subscription.quantity or 1) * bill_days / days_in_month, 2)
        vat_amount += round(mrc_amount * float(subscription.vat_rate or 0), 2)
        items.append(
            {
                "service_id": f"subscription:{subscription.id}",
                "service": subscription.service_type or subscription.product_code,
                "item": subscription.service_name or subscription.product_code,
                "location": subscription.service_location or "",
                "start_date": item_start,
                "end_date": item_end,
                "nrc_amount": 0,
                "mrc_amount": mrc_amount,
                "amount": mrc_amount,
            }
        )
    item_total = round(sum(item["mrc_amount"] for item in items), 2)
    invoice_date = date.today()
    due_days = max(int(payload.due_days or 30), 0)
    bill_data = {
        "company_id": company.id,
        "invoice_no": generated_invoice_no(company, payload.owner, bill_month, sequence, subscriptions[0].service_location if subscriptions else ""),
        "customer_name": company.name or company.legal_name or "",
        "bill_month": start,
        "invoice_date": invoice_date,
        "due_date": invoice_date + timedelta(days=due_days),
        "billing_start_date": start,
        "billing_end_date": end,
        "currency": subscriptions[0].currency if subscriptions else "USD",
        "net_amount": item_total,
        "vat_amount": round(vat_amount, 2),
        "total_amount": round(item_total + vat_amount, 2),
        "paid_amount": 0,
        "unpaid_amount": round(item_total + vat_amount, 2),
        "is_settled": False,
        "payment_voucher_url": "",
        "owner": payload.owner or "",
        "remark": "自动生成账单",
        "bill_type": 1,
        "status": "pending_approval",
        "term": payload.term or f"Net {due_days}",
        "local_currency": payload.local_currency or None,
        "fx_rate": payload.fx_rate,
    }
    sync_local_amount(bill_data)
    return bill_data, items


async def create_bill_items_from_dicts(bill_id: int, items: list[dict[str, Any]]):
    await bill_item_controller.model.bulk_create(
        [
            bill_item_controller.model(
                bill_id=bill_id,
                service_id=item.get("service_id") or str(index + 1),
                service=item.get("service") or "",
                item=item.get("item") or "",
                location=item.get("location") or "",
                start_date=item.get("start_date"),
                end_date=item.get("end_date"),
                nrc_amount=item.get("nrc_amount") or 0,
                mrc_amount=item.get("mrc_amount") or 0,
                amount=item.get("amount") or 0,
            )
            for index, item in enumerate(items)
        ]
    )


@router.get("/automation/options", summary="账单自动化选项")
async def automation_options():
    return Success(
        data={
            "statuses": [{"label": label, "value": value} for value, label in BILL_STATUS_LABELS.items()],
            "templates": [await template_to_dict(item) for item in await BillingProductTemplate.all().order_by("name")],
        }
    )


@router.get("/templates", summary="产品配置模板列表")
async def list_templates(status: bool | None = Query(None, description="状态")):
    q = Q()
    if status is not None:
        q &= Q(status=status)
    rows = await BillingProductTemplate.filter(q).order_by("-status", "name")
    return Success(data=[await template_to_dict(item) for item in rows])


@router.post("/templates", summary="保存产品配置模板")
async def save_template(payload: BillingTemplatePayload):
    data = template_payload_data(payload)
    if not data["name"]:
        raise HTTPException(status_code=400, detail="请填写模板名")
    if payload.id:
        obj = await BillingProductTemplate.get_or_none(id=payload.id)
        if not obj:
            raise HTTPException(status_code=404, detail="产品模板不存在")
        for key, value in data.items():
            setattr(obj, key, value)
        await obj.save()
    else:
        obj = await BillingProductTemplate.create(**data)
    return Success(msg="Saved Successfully", data=await template_to_dict(obj))


@router.delete("/templates/{template_id}", summary="删除产品配置模板")
async def delete_template(template_id: int):
    deleted = await BillingProductTemplate.filter(id=template_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="产品模板不存在")
    return Success(msg="Deleted Successfully")


@router.get("/subscriptions", summary="产品订阅列表")
async def list_subscriptions(
    company_id: int | None = Query(None, description="公司ID"),
    is_active: bool | None = Query(None, description="是否激活"),
):
    q = Q()
    if company_id is not None:
        q &= Q(company_id=company_id)
    if is_active is not None:
        q &= Q(is_active=is_active)
    rows = await BillingSubscription.filter(q).order_by("company_id", "product_code", "id")
    return Success(data=[await subscription_to_dict(item) for item in rows])


@router.post("/subscriptions", summary="保存产品订阅")
async def save_subscription(payload: BillingSubscriptionPayload):
    if not await Company.filter(id=payload.company_id).exists():
        raise HTTPException(status_code=400, detail="客户不存在")
    data = await subscription_payload_data(payload)
    if not data["product_code"]:
        raise HTTPException(status_code=400, detail="请填写产品Code")
    if payload.id:
        obj = await BillingSubscription.get_or_none(id=payload.id)
        if not obj:
            raise HTTPException(status_code=404, detail="产品订阅不存在")
        for key, value in data.items():
            setattr(obj, key, value)
        await obj.save()
    else:
        obj = await BillingSubscription.create(**data)
    return Success(msg="Saved Successfully", data=await subscription_to_dict(obj))


@router.delete("/subscriptions/{subscription_id}", summary="删除产品订阅")
async def delete_subscription(subscription_id: int):
    deleted = await BillingSubscription.filter(id=subscription_id).delete()
    if not deleted:
        raise HTTPException(status_code=404, detail="产品订阅不存在")
    return Success(msg="Deleted Successfully")


@router.post("/feishu/sync", summary="同步飞书多维表账单记录")
async def sync_feishu_bills(payload: FeishuBillSyncPayload):
    parsed = parse_feishu_bitable_url(payload.url)
    app_token = clean(payload.app_token) or parsed["app_token"]
    table_id = clean(payload.table_id) or parsed["table_id"]
    view_id = clean(payload.view_id) or parsed["view_id"]
    if not app_token or not table_id:
        raise HTTPException(status_code=400, detail="请填写飞书多维表链接，或提供 app_token/table_id")

    records = await fetch_feishu_bitable_records(app_token, table_id, view_id)
    previews = []
    created = []
    updated = []
    skipped = []
    for record in records:
        record_id = record.get("record_id") or ""
        fields = record.get("fields") or {}
        company_name = clean(pick_feishu_field(fields, "company_name"))
        company = await get_or_create_billing_company(company_name, payload.bill_type, payload.create_missing_companies)
        if not company:
            skipped.append({"record_id": record_id, "reason": "客户/供应商为空或不存在", "fields": fields})
            continue
        bill_data, items = feishu_record_to_bill_payload(record, company.id, payload.bill_type)
        bill_data["customer_name"] = company.name or company.legal_name or company_name
        preview = {**bill_data, "items": items}
        if payload.dry_run:
            previews.append(preview)
            continue

        existing = None
        if record_id:
            existing = await bill_controller.model.filter(source="feishu_bitable", source_record_id=record_id).first()
        if not existing and not record_id and bill_data.get("invoice_no"):
            existing = await bill_controller.model.filter(invoice_no=bill_data["invoice_no"]).first()

        if existing:
            if not payload.update_existing:
                skipped.append({"record_id": record_id, "invoice_no": bill_data.get("invoice_no"), "reason": "账单已存在"})
                continue
            before = await bill_to_dict(existing, include_items=True)
            for key, value in bill_data.items():
                setattr(existing, key, value)
            await existing.save()
            await bill_item_controller.model.filter(bill_id=existing.id).delete()
            await create_bill_items_from_dicts(existing.id, items)
            after = await bill_to_dict(existing, include_items=True)
            await write_bill_audit(existing.id, "feishu_sync_update", before=before, after=after, comment=f"飞书记录 {record_id}")
            updated.append(after)
        else:
            obj = await bill_controller.model.create(**bill_data)
            await create_bill_items_from_dicts(obj.id, items)
            after = await bill_to_dict(obj, include_items=True)
            await write_bill_audit(obj.id, "feishu_sync_create", after=after, comment=f"飞书记录 {record_id}")
            created.append(after)

    return Success(
        data=jsonable_encoder({
            "total": len(records),
            "created": created,
            "updated": updated,
            "previews": previews,
            "skipped": skipped,
        })
    )


@router.post("/generate", summary="自动生成账单")
async def generate_bills(payload: BillGeneratePayload):
    bill_month = month_start(payload.bill_month)
    q = Q(is_active=True)
    if payload.company_id is not None:
        q &= Q(company_id=payload.company_id)
    if payload.subscription_ids:
        q &= Q(id__in=payload.subscription_ids)
    subscriptions = await BillingSubscription.filter(q).order_by("company_id", "currency", "id")

    grouped: dict[tuple[int, str], list[BillingSubscription]] = {}
    skipped = []
    for subscription in subscriptions:
        if await bill_exists_for_subscription(subscription.id, bill_month):
            skipped.append({"subscription_id": subscription.id, "reason": "已生成当月账单"})
            continue
        if not date_overlap(month_start(bill_month), month_end(bill_month), subscription.billing_start_date, subscription.billing_end_date):
            skipped.append({"subscription_id": subscription.id, "reason": "订阅不在本月计费区间"})
            continue
        grouped.setdefault((subscription.company_id, subscription.currency or "USD"), []).append(subscription)

    previews = []
    created = []
    sequence = 1
    for (company_id, _currency), group in grouped.items():
        company = await Company.get(id=company_id)
        bill_data, items = await build_generated_bill_payload(company, group, payload, bill_month, sequence)
        if not items:
            continue
        preview = {**bill_data, "items": items}
        if payload.dry_run:
            previews.append(preview)
        else:
            bill = await bill_controller.model.create(**bill_data)
            await create_bill_items_from_dicts(bill.id, items)
            for subscription in group:
                subscription.last_billed_month = bill_month
                await subscription.save(update_fields=["last_billed_month", "updated_at"])
            await write_bill_audit(bill.id, "auto_generate", after=preview, comment=f"{bill_month:%Y-%m} 自动生成")
            created.append(await bill_to_dict(bill, include_items=True))
        sequence += 1

    return Success(data={"created": created, "previews": previews, "skipped": skipped})


@router.post("/{bill_id}/status", summary="账单状态流转")
async def update_bill_status(bill_id: int, payload: BillStatusPayload):
    bill = await bill_controller.model.get_or_none(id=bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    action = payload.action.strip()
    transition = BILL_TRANSITIONS.get(action)
    if not transition:
        raise HTTPException(status_code=400, detail="不支持的状态动作")
    current_status = bill.status or "issued"
    if current_status not in transition["from"]:
        raise HTTPException(status_code=400, detail=f"当前状态不允许执行 {action}")
    before = await bill_to_dict(bill)
    bill.status = transition["to"]
    bill.approval_comment = payload.comment or bill.approval_comment
    if action == "approve":
        bill.approved_at = datetime.now()
    if action == "send":
        bill.sent_at = datetime.now()
    if action == "mark_paid":
        bill.is_settled = True
        bill.unpaid_amount = 0
    await bill.save()
    after = await bill_to_dict(bill)
    await write_bill_audit(bill.id, action, before=before, after=after, comment=payload.comment, operator=payload.operator)
    return Success(msg="Updated Successfully", data=after)


@router.post("/{bill_id}/payments", summary="登记付款")
async def create_payment(bill_id: int, payload: BillPaymentPayload):
    bill = await bill_controller.model.get_or_none(id=bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="账单不存在")
    before = await bill_to_dict(bill)
    payment = await BillPayment.create(
        bill_id=bill.id,
        payment_id=payload.payment_id.strip() or f"PAY{datetime.now():%Y%m%d%H%M%S}",
        payment_date=payload.payment_date or date.today(),
        amount=float(payload.amount or 0),
        currency=payload.currency.strip() or bill.currency or "USD",
        method=payload.method.strip() or None,
        fx_rate=payload.fx_rate,
        voucher_url=payload.voucher_url.strip() or None,
        remark=payload.remark.strip() or None,
    )
    bill.paid_amount = float(bill.paid_amount or 0) + float(payment.amount or 0)
    bill.unpaid_amount = max(float(bill.total_amount or 0) - bill.paid_amount, 0)
    bill.is_settled = bill.unpaid_amount <= 0
    if bill.is_settled:
        bill.status = "paid"
    await bill.save()
    after = await bill_to_dict(bill)
    await write_bill_audit(bill.id, "payment", before=before, after=after, comment=payload.remark)
    return Success(msg="Payment Saved", data={"bill": after, "payment": await payment.to_dict()})


@router.get("/list", summary="查看账单列表")
async def list_bill(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    company_id: int | None = Query(None, description="公司ID"),
    bill_type: int | None = Query(None, description="账单类型(1客户/2供应商)"),
    bill_month: date | None = Query(None, description="账单月份"),
    invoice_no: str = Query("", description="账单编号"),
    customer_name: str = Query("", description="客户/供应商名称"),
    is_settled: bool | None = Query(None, description="是否结清"),
    status: str = Query("", description="账单状态"),
    sort_field: str = Query("", description="排序字段"),
    sort_order: str = Query("", description="排序方向"),
):
    q = Q()
    if company_id is not None:
        q &= Q(company_id=company_id)
    if bill_type is not None:
        q &= Q(bill_type=bill_type)
    if bill_month is not None:
        q &= Q(bill_month=bill_month)
    if invoice_no:
        q &= Q(invoice_no__contains=invoice_no)
    if customer_name:
        q &= Q(customer_name__contains=customer_name)
    if is_settled is not None:
        q &= Q(is_settled=is_settled)
    if status:
        q &= Q(status=status)

    total, objs = await bill_controller.list(
        page=page,
        page_size=page_size,
        search=q,
        order=build_bill_order(sort_field, sort_order),
    )
    data = [await bill_to_dict(obj) for obj in objs]
    summary = await build_bill_summary(q)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size, summary=summary)


@router.get("/get", summary="查看账单")
async def get_bill(
    bill_id: int = Query(..., description="账单ID"),
):
    obj = await bill_controller.get(id=bill_id)
    return Success(data=await bill_to_dict(obj, include_items=True))


@router.post("/create", summary="创建账单")
async def create_bill(
    obj_in: BillCreate,
):
    payload = obj_in.model_dump(exclude={"items"})
    if not payload.get("invoice_no"):
        payload["invoice_no"] = build_invoice_no(
            payload.get("customer_name"), payload.get("owner"), payload.get("bill_month")
        )
    payload["status"] = payload.get("status") or "issued"
    sync_bill_amounts(payload, obj_in.items)
    sync_settled_status(payload)
    obj = await bill_controller.create(payload)
    await replace_bill_items(obj.id, obj_in.items)
    await write_bill_audit(obj.id, "create", after=await bill_to_dict(obj, include_items=True))
    return Success(msg="Created Successfully", data=await bill_to_dict(obj, include_items=True))


@router.post("/update", summary="更新账单")
async def update_bill(
    obj_in: BillUpdate,
):
    existing = await bill_controller.get(id=obj_in.id)
    before = await bill_to_dict(existing, include_items=True)
    if (existing.status or "issued") != "pending_approval":
        locked_fields = {"invoice_no", "invoice_date", "company_id", "customer_name"}
        changed_locked = [
            field for field in locked_fields
            if getattr(existing, field, None) != getattr(obj_in, field, None)
        ]
        if changed_locked:
            raise HTTPException(status_code=400, detail="Invoice ID、Invoice Date 和客户主体信息生成后不可直接编辑")
    payload = obj_in.model_dump(exclude_unset=True, exclude={"id", "items"})
    if not payload.get("invoice_no"):
        payload["invoice_no"] = build_invoice_no(
            payload.get("customer_name"), payload.get("owner"), payload.get("bill_month")
        )
    sync_bill_amounts(payload, obj_in.items)
    sync_settled_status(payload)
    obj = await bill_controller.update(id=obj_in.id, obj_in=payload)
    await replace_bill_items(obj.id, obj_in.items)
    await write_bill_audit(obj.id, "update", before=before, after=await bill_to_dict(obj, include_items=True))
    return Success(msg="Updated Successfully", data=await bill_to_dict(obj, include_items=True))


@router.delete("/delete", summary="删除账单")
async def delete_bill(
    bill_id: int = Query(..., description="账单ID"),
):
    await bill_controller.remove(id=bill_id)
    return Success(msg="Deleted Successfully")


async def save_bill_file(file: UploadFile):
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return f"/uploads/bills/{unique_filename}"


@router.post("/upload_voucher", summary="上传付款凭证")
async def upload_payment_voucher(
    bill_id: int = Query(..., description="账单ID"),
    file: UploadFile = File(..., description="付款凭证"),
):
    if not str(file.content_type or "").startswith("image/"):
        return Success(msg="Only image files are allowed", code=400)

    payment_voucher_url = await save_bill_file(file)
    await bill_controller.update(id=bill_id, obj_in={"payment_voucher_url": payment_voucher_url})
    return Success(msg="Upload Successfully", data={"payment_voucher_url": payment_voucher_url})
