import argparse
import asyncio
import csv
import re
import sys
from pathlib import Path

from tortoise import Tortoise

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.company import Company
from app.settings.config import settings


EMAIL_RE = re.compile(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{5,}\d)")


def clean(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\ufeff", " ")).strip().strip('"')


def limit(value: str, max_length: int) -> str:
    value = clean(value)
    return value[:max_length] if len(value) > max_length else value


def first_email(value: str) -> str:
    matches = EMAIL_RE.findall(value or "")
    return matches[0] if matches else ""


def first_phone(value: str) -> str:
    matches = PHONE_RE.findall(value or "")
    return clean(matches[0]) if matches else ""


def contact_name(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    text = EMAIL_RE.sub("", text)
    text = PHONE_RE.sub("", text)
    return limit(text.strip(" ;,+-"), 100)


def compact_note(label: str, value: str) -> str:
    value = clean(value)
    return f"{label}: {value}" if value else ""


def get_value(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def parse_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    first_line = text.splitlines()[0] if text else ""
    sample = text[:4096]
    if "\t" in first_line:
        dialect = csv.excel_tab
    else:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        except csv.Error:
            dialect = csv.excel

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, dialect=dialect)
        return [{clean(key): clean(value) for key, value in row.items()} for row in reader]


def build_payload(row: dict[str, str]) -> dict:
    full_name = clean(row.get("Name"))
    nickname = clean(row.get("Nickname"))
    sales_contact = get_value(row, "Sales Contact (Name, Email, Tel)")
    billing_contact = get_value(
        row,
        "Billing Contact (Name; Email, Tel)",
        "Billing Contact \r\n(Name; Email, Tel)",
        "Billing Contact \n(Name; Email, Tel)",
    )
    tech_contact = get_value(
        row,
        "Tech Contact (Name; Email, Tel)",
        "Tech Contact \r\n(Name; Email, Tel)",
        "Tech Contact \n(Name; Email, Tel)",
    )
    noc_contact = get_value(row, "NOC Contact")
    note = get_value(row, "Note")
    terms = get_value(row, "Billing/Payment Terms")

    remark_parts = [
        compact_note("账期", terms),
        compact_note("销售联系人", sales_contact),
        compact_note("账务联系人", billing_contact),
        compact_note("技术联系人", tech_contact),
        compact_note("NOC联系人", noc_contact),
        compact_note("备注", note),
    ]

    return {
        "role": 1,
        "code": limit(row.get("Customer Account# (CAN)", ""), 50),
        "name": limit(nickname or full_name, 100),
        "legal_name": limit(full_name, 200),
        "address": limit(row.get("Address", ""), 255),
        "company_email": limit(first_email(sales_contact) or first_email(tech_contact) or first_email(noc_contact), 100),
        "company_phone": limit(first_phone(sales_contact) or first_phone(tech_contact) or first_phone(noc_contact), 50),
        "bill_email": limit(first_email(billing_contact), 100),
        "contact_person": contact_name(billing_contact),
        "noc_email": limit(first_email(noc_contact), 100),
        "noc_phone": limit(first_phone(noc_contact), 50),
        "remark": limit("\n".join(part for part in remark_parts if part), 500),
        "status": True,
    }


async def import_customers(path: Path) -> tuple[int, int, int]:
    await Tortoise.init(config=settings.TORTOISE_ORM)
    created = 0
    updated = 0
    skipped = 0
    try:
        for row in parse_rows(path):
            payload = build_payload(row)
            if not payload["code"] or not payload["legal_name"]:
                skipped += 1
                continue

            existing = await Company.filter(code=payload["code"]).first()
            if existing:
                for field, value in payload.items():
                    setattr(existing, field, value)
                await existing.save()
                updated += 1
            else:
                await Company.create(**payload)
                created += 1
    finally:
        await Tortoise.close_connections()
    return created, updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Import pasted TSV customers into company table.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    created, updated, skipped = asyncio.run(import_customers(args.path))
    print(f"created={created} updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()
