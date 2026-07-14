import argparse
import asyncio
import csv
import sys
from pathlib import Path

from tortoise import Tortoise

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.finance import FinanceQuote
from app.settings.config import settings


TEXT_FIELDS = [
    "service_resource",
    "service_name",
    "provider",
    "bandwidth",
    "burst",
    "site_a",
    "protection",
    "xc_cabling",
    "contract_terms",
    "currency",
    "usd_per_mbps_nrc",
    "note",
]


def clean_key(value: str) -> str:
    return str(value or "").strip().replace("\ufeff", "")


def clean_text(value) -> str:
    return str(value or "").strip()


def parse_money(value) -> tuple[float, str]:
    text = clean_text(value)
    if not text:
        return 0.0, ""
    normalized = text.replace(",", "")
    try:
        return float(normalized), ""
    except ValueError:
        return 0.0, text


def parse_rate(value) -> float:
    text = clean_text(value).replace(",", "")
    if not text:
        return 0.0
    import re

    decimal_match = re.search(r"\d+\.\d+", text)
    if decimal_match:
        return float(decimal_match.group(0))
    integer_match = re.search(r"\d+", text)
    if integer_match:
        return float(integer_match.group(0))
    return 0.0


def quote_type_from_service(service: str) -> str:
    text = service.strip().lower()
    if text == "dia":
        return "dia"
    if text in {"ip transit", "ip"}:
        return "ipt"
    return "transport"


def build_payload(row: dict) -> dict:
    normalized = {clean_key(key): clean_text(value) for key, value in row.items() if clean_key(key)}
    service_name = normalized.get("Service", "")
    nrc, raw_nrc = parse_money(normalized.get("NRC", ""))
    mrc, raw_mrc = parse_money(normalized.get("MRC", ""))
    note_parts = [normalized.get("Note", "")]
    if raw_nrc:
        note_parts.append(f"NRC原值: {raw_nrc}")
    if raw_mrc:
        note_parts.append(f"MRC原值: {raw_mrc}")
    note = "；".join(part for part in note_parts if part)

    return {
        "quote_type": quote_type_from_service(service_name),
        "service_resource": normalized.get("Service Resource", ""),
        "region": normalized.get("Site A", ""),
        "service_name": service_name,
        "provider": normalized.get("Vendor", ""),
        "bandwidth": normalized.get("B/W", ""),
        "burst": normalized.get("Burst", ""),
        "site_a": normalized.get("Site A", ""),
        "protection": normalized.get("Protection", ""),
        "xc_cabling": normalized.get("XC/Cabling", normalized.get("XC/Cabling ", "")),
        "contract_terms": normalized.get("Contract Terms", ""),
        "currency": normalized.get("Currency", "USD") or "USD",
        "nrc": nrc,
        "mrc": mrc,
        "usd_per_mbps_nrc": normalized.get("USD/Mbps NRC", ""),
        "usd_per_mbps_mrc": parse_rate(normalized.get("USD/Mbps MRC", "")),
        "cost_price": mrc,
        "target_price": mrc,
        "sale_price": mrc,
        "status": 1,
        "sort": 0,
        "note": note,
        "remark": note,
    }


def is_empty_payload(payload: dict) -> bool:
    return not any(clean_text(payload.get(field)) for field in TEXT_FIELDS) and not payload.get("nrc") and not payload.get("mrc")


async def ensure_schema():
    await Tortoise.generate_schemas(safe=True)
    if settings.DB_TYPE != "postgres":
        return
    conn = Tortoise.get_connection("postgres")
    await conn.execute_script(
        """
        ALTER TABLE IF EXISTS "finance_quote"
            ADD COLUMN IF NOT EXISTS "service_resource" VARCHAR(80),
            ADD COLUMN IF NOT EXISTS "burst" VARCHAR(80),
            ADD COLUMN IF NOT EXISTS "site_a" VARCHAR(120),
            ADD COLUMN IF NOT EXISTS "protection" VARCHAR(80),
            ADD COLUMN IF NOT EXISTS "xc_cabling" VARCHAR(80),
            ADD COLUMN IF NOT EXISTS "contract_terms" VARCHAR(80),
            ADD COLUMN IF NOT EXISTS "nrc" DOUBLE PRECISION DEFAULT 0,
            ADD COLUMN IF NOT EXISTS "mrc" DOUBLE PRECISION DEFAULT 0,
            ADD COLUMN IF NOT EXISTS "usd_per_mbps_nrc" VARCHAR(80),
            ADD COLUMN IF NOT EXISTS "usd_per_mbps_mrc" DOUBLE PRECISION DEFAULT 0,
            ADD COLUMN IF NOT EXISTS "note" VARCHAR(500);

        DO $$
        DECLARE
            column_type TEXT;
        BEGIN
            SELECT data_type INTO column_type
            FROM information_schema.columns
            WHERE table_name = 'finance_quote'
              AND column_name = 'usd_per_mbps_mrc';

            IF column_type IS NOT NULL AND column_type <> 'double precision' THEN
                ALTER TABLE "finance_quote"
                    ADD COLUMN IF NOT EXISTS "usd_per_mbps_mrc_num" DOUBLE PRECISION DEFAULT 0;

                UPDATE "finance_quote"
                SET "usd_per_mbps_mrc_num" = COALESCE(
                    NULLIF((regexp_match(COALESCE("usd_per_mbps_mrc"::TEXT, ''), '[0-9]+\\.[0-9]+'))[1], '')::DOUBLE PRECISION,
                    NULLIF((regexp_match(COALESCE("usd_per_mbps_mrc"::TEXT, ''), '[0-9]+'))[1], '')::DOUBLE PRECISION,
                    0
                );

                ALTER TABLE "finance_quote" DROP COLUMN "usd_per_mbps_mrc";
                ALTER TABLE "finance_quote" RENAME COLUMN "usd_per_mbps_mrc_num" TO "usd_per_mbps_mrc";
            END IF;
        END $$;
        """
    )


async def import_quotes(path: Path) -> tuple[int, int, int]:
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        await ensure_schema()
        created = 0
        skipped = 0
        invalid = 0
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                payload = build_payload(row)
                if is_empty_payload(payload):
                    invalid += 1
                    continue
                exists = await FinanceQuote.filter(**payload).exists()
                if exists:
                    skipped += 1
                    continue
                await FinanceQuote.create(**payload)
                created += 1
        return created, skipped, invalid
    finally:
        await Tortoise.close_connections()


def main():
    parser = argparse.ArgumentParser(description="Import IPT/DIA finance quotes from CSV")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    created, skipped, invalid = asyncio.run(import_quotes(args.path))
    print(f"created={created}")
    print(f"skipped={skipped}")
    print(f"invalid={invalid}")


if __name__ == "__main__":
    main()
