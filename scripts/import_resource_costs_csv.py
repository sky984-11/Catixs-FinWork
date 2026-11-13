"""Import a resource cost CSV locally; dry-run by default, using system audit actor 0."""

# ruff: noqa: E402 -- standalone script adds the repository root before app imports.

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tortoise import Tortoise
from tortoise.transactions import in_transaction

from app.api.v1.resource_costs import save_cost
from app.models import Company, ResourceCost, ResourceCostVersion
from app.schemas.resource_cost import CostPayload
from app.settings.config import settings

HEADERS = {
    "Service Resource": "service_resource",
    "Service": "service",
    "Vendor": "vendor_id",
    "B/W": "bandwidth",
    "Site A": "site_a",
    "Protection": "protection",
    "XC/Cabling": "xc_cabling",
    "Contract Terms": "contract_months",
    "Currency": "currency",
    "NRC": "nrc",
    "MRC": "mrc",
    "Note": "note",
}


def parse_rows(path, category="colo"):
    mapping = dict(HEADERS)
    if category == "ipt_dia":
        mapping.update({"Burst": "burst", "Price/Mbps MRC": "price_per_mbps", "Burst Price/M": "burst_price"})
    elif category == "ptp":
        mapping.update({"Site B": "site_b", "Price/Mbps MRC": "price_per_mbps"})
    elif category == "retail":
        mapping.update({"Burst": "burst", "Site B": "site_b", "USD/Mbps MRC": "price_per_mbps"})
    elif category == "xc":
        mapping = {
            "DC Name": "dc_name",
            "Site Address": "site_address",
            "Currency": "currency",
            "Tax Rate": "tax_rate",
            "NRC": "nrc",
            "MRC": "mrc",
            "Remarks": "note",
        }
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        for header_row, raw_header in enumerate(reader, 1):
            headers = [h.strip() for h in raw_header]
            if ("DC Name" if category == "xc" else "Service Resource") in headers:
                break
            if header_row >= 20:
                raise ValueError("No recognized header in first 20 records")
        else:
            raise ValueError("No recognized header")
        named = [h for h in headers if h]
        if set(named) != set(mapping) or len(named) != len(mapping):
            raise ValueError("CSV headers do not match selected category export")
        for row_number, row in enumerate(reader, header_row + 1):
            if not any(v.strip() for v in row):
                continue
            if len(row) != len(headers):
                raise ValueError(f"Unexpected columns at row {row_number}")
            data = {mapping[h]: v.strip() or None for h, v in zip(headers, row) if h}
            extras = [
                f"column {i}: {v.strip()}" for i, (h, v) in enumerate(zip(headers, row), 1) if not h and v.strip()
            ]
            if extras:
                data["note"] = (data["note"] or "") + "\n[CSV unnamed columns] " + "; ".join(extras)
            digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:24].upper()
            data.update(category=category, code=f"{category.upper()}-CSV-{digest}")
            vendor_name = data.pop("vendor_id", None)
            if data.get("contract_months"):
                data["contract_months"] = re.sub(r"\s+Months?$", "", data["contract_months"], flags=re.I)
            for key in ("nrc", "mrc", "price_per_mbps", "burst_price"):
                raw = data.get(key)
                if not raw:
                    continue
                if raw in ("NA", "N/A"):
                    data[key] = None
                    continue
                for symbol, currency in (("€", "EUR"), ("£", "GBP"), ("$", "USD")):
                    if raw.startswith(symbol) and data.get("currency") == currency:
                        raw = raw[len(symbol) :].strip()
                match = re.fullmatch(r"([\d,]+(?:\.\d+)?)\s*([A-Z]{3})?(?:/(.+))?", raw)
                if not match:
                    continue  # Leave nonnumeric quotes intact for schema rejection.
                amount, currency, unit = match.groups()
                if currency and currency != data["currency"]:
                    continue  # Preserve the full raw value for review instead of guessing currency.
                if unit and key != "mrc":
                    continue
                data[key] = amount.replace(",", "")
                if unit:
                    data["mrc_unit"] = unit
            yield row_number, vendor_name, data


def prepare_incomplete(data, vendor_name):
    """Preserve unrepresentable values as notes; never invent prices or required fields."""
    data = dict(data)
    notes = [data.get("note") or ""]
    if vendor_name:
        notes.append(f"原表供应商（未关联）：{vendor_name}")
    try:
        CostPayload.model_validate(data)
    except ValidationError as exc:
        data["enabled"] = False
        notes.append("导入待核对：原表存在缺失或非标准字段，补全核对后方可启用。")
        for error in exc.errors():
            if not error["loc"]:
                continue
            key = error["loc"][0]
            if key not in {"nrc", "mrc", "price_per_mbps", "burst_price", "protection", "contract_months", "tax_rate"}:
                raise
            notes.append(f"原表 {key}：{data[key]}")
            data[key] = None
    data["note"] = "\n".join(filter(None, notes)) or None
    return data


async def run(args):
    rows = list(parse_rows(args.file, args.category))
    currency_overrides = dict(value.split("=", 1) for value in args.currency_by_row)
    vendor_overrides = dict(value.split("=", 1) for value in args.vendor)
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        vendors = await Company.filter(role__in=[2, 3], status=True)
        pending, errors, skipped = [], [], 0
        excluded = []
        duplicate_rows = []
        seen_codes = set()
        for number, original_vendor, data in rows:
            if original_vendor in args.skip_vendor:
                excluded.append(number)
                continue
            if data["code"] in seen_codes:
                duplicate_rows.append(number)
                continue
            if await ResourceCost.filter(code=data["code"]).exists():
                skipped += 1
                continue
            if str(number) in currency_overrides:
                if data["currency"]:
                    errors.append(f"row {number}: cannot override existing currency")
                    continue
                data["currency"] = currency_overrides[str(number)]
            matches = [
                v
                for v in vendors
                if original_vendor
                and original_vendor.casefold() in ((v.name or "").casefold(), (v.legal_name or "").casefold())
            ]
            if original_vendor in vendor_overrides:
                matches = [v for v in vendors if vendor_overrides[original_vendor] in (str(v.id), v.code)]
                if len(matches) != 1:
                    errors.append(f"row {number}: invalid vendor override")
                    continue
            if args.no_vendor_links:
                matches = []
            if len(matches) == 1:
                data["vendor_id"] = matches[0].id
            elif original_vendor and not (args.allow_unlinked or args.no_vendor_links):
                errors.append(f"row {number}: vendor requires mapping")
                continue
            try:
                if args.preserve_incomplete:
                    data = prepare_incomplete(data, original_vendor if not data.get("vendor_id") else None)
                pending.append((CostPayload.model_validate(data), original_vendor))
                seen_codes.add(data["code"])
            except ValueError as exc:
                fields = [".".join(map(str, e["loc"])) or "required fields" for e in exc.errors()]
                errors.append(f"row {number}: invalid or missing fields: {', '.join(fields)}")
        print(
            json.dumps(
                {
                    "source_rows": len(rows),
                    "ready": len(pending),
                    "disabled": sum(not p.enabled for p, _ in pending),
                    "already_imported": skipped,
                    "excluded_rows": excluded,
                    "duplicate_rows": duplicate_rows,
                    "errors": errors,
                },
                ensure_ascii=False,
            )
        )
        if errors and not args.skip_invalid:
            raise ValueError("No rows written; resolve validation errors first")
        if args.commit:
            async with in_transaction():
                for payload, original_vendor in pending:
                    result = await save_cost(payload, SimpleNamespace(id=0))
                    if original_vendor:
                        version = await ResourceCostVersion.get(id=result["version_id"])
                        version.data["source_vendor_name"] = original_vendor
                        if not payload.vendor_id:
                            version.data["vendor_name"] = original_vendor
                        await version.save(update_fields=["data"])
            count = await ResourceCost.filter(code__in=[p.code for p, _ in pending]).count()
            print(json.dumps({"inserted_and_verified": count, "category": args.category, "audit_actor": 0}))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--category", choices=["colo", "ipt_dia", "ptp", "retail", "xc"], default="colo")
    parser.add_argument(
        "--skip-invalid", action="store_true", help="Explicitly skip and report invalid/unmatched records"
    )
    parser.add_argument("--allow-unlinked", action="store_true")
    parser.add_argument(
        "--no-vendor-links", action="store_true", help="Preserve source vendor name without any supplier link"
    )
    parser.add_argument(
        "--preserve-incomplete", action="store_true", help="Store incomplete rows disabled with raw values in notes"
    )
    parser.add_argument("--vendor", action="append", default=[], help="CSV vendor name=existing supplier ID or code")
    parser.add_argument(
        "--skip-vendor", action="append", default=[], help="Skip records for this exact CSV vendor name"
    )
    parser.add_argument("--currency-by-row", action="append", default=[], help="CSV record number=currency")
    asyncio.run(run(parser.parse_args()))
