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


DEFAULT_CSV_PATH = Path(r"C:\Users\LiuPeng\Downloads\77Tel(Catixs HK).csv")
ISSUER_NAME = "77 Telecom Ltd"
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def clean(value: str | None) -> str:
    return (value or "").replace("\ufeff", "").strip()


def limit(value: str, max_length: int) -> str:
    value = clean(value)
    return value[:max_length] if len(value) > max_length else value


def first_email(value: str) -> str:
    match = EMAIL_RE.search(value or "")
    return match.group(0) if match else ""


def note_line(label: str, value: str) -> str:
    value = clean(value)
    return f"{label}: {value}" if value else ""


def build_remark(row: dict[str, str]) -> str:
    parts = [
        note_line("账期", row.get("Payment Terms", "")),
        note_line("销售联系人", row.get("Sales Contact (Name, Email, Tel)", "")),
        note_line("财务联系人", row.get("Billing Contact (Name; Email, Tel)", "")),
        note_line("技术联系人", row.get("Tech Contact (Name; Email, Tel)", "")),
        note_line("NOC联系人", row.get("NOC Contact", "")),
        note_line("客户资料链接", row.get("Customer Info Folder", "")),
        note_line("备注", row.get("Note", "")),
    ]
    return "\n".join(part for part in parts if part)


def normalize_row(row: dict[str, str]) -> dict[str, str] | None:
    code = clean(row.get("Customer Account# (CAN)", ""))
    legal_name = clean(row.get("Customer Name", ""))
    name = legal_name
    if not code or not legal_name:
        return None

    billing_contact = clean(row.get("Billing Contact (Name; Email, Tel)", ""))
    tech_contact = clean(row.get("Tech Contact (Name; Email, Tel)", ""))
    noc_contact = clean(row.get("NOC Contact", ""))

    return {
        "role": 1,
        "code": limit(code, 50),
        "name": limit(name, 100),
        "legal_name": limit(legal_name, 200),
        "address": limit(row.get("Customer Address ", ""), 255),
        "company_email": limit(first_email(tech_contact), 100),
        "company_phone": "",
        "bill_email": limit(first_email(billing_contact), 100),
        "noc_email": limit(first_email(noc_contact), 100),
        "noc_phone": "",
        "remark": limit(build_remark(row), 500),
        "status": True,
    }


def load_customers(csv_path: Path) -> tuple[list[dict[str, str]], int]:
    customers = []
    skipped = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            payload = normalize_row(row)
            if payload:
                customers.append(payload)
            else:
                skipped += 1
    return customers, skipped


async def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV_PATH
    await Tortoise.init(config=settings.TORTOISE_ORM)
    created = 0
    updated = 0
    try:
        issuer = await Company.filter(name=ISSUER_NAME, role=0).first()
        if not issuer:
            issuer = await Company.filter(legal_name=ISSUER_NAME, role=0).first()
        if not issuer:
            print("issuer_not_found")
            return

        customers, skipped = load_customers(csv_path)
        for payload in customers:
            payload["contract_company_id"] = issuer.id
            existing = await Company.filter(code=payload["code"]).first()
            if existing:
                for field, value in payload.items():
                    setattr(existing, field, value)
                await existing.save()
                updated += 1
            else:
                await Company.create(**payload)
                created += 1

        verified = await Company.filter(
            role=1,
            contract_company_id=issuer.id,
            code__in=[item["code"] for item in customers],
        ).count()
        print(f"csv_path={csv_path}")
        print(f"issuer_id={issuer.id} issuer_name={issuer.name}")
        print(f"loaded={len(customers)} created={created} updated={updated} skipped={skipped} verified={verified}")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
