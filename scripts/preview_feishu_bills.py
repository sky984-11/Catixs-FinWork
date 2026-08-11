import argparse
import asyncio
import os
import sys

from tortoise import Tortoise

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.api.v1.bills.bills import sync_feishu_bills
from app.schemas.bills import FeishuBillSyncPayload
from app.settings.config import settings


async def ensure_feishu_bill_columns() -> None:
    connection = Tortoise.get_connection("postgres")
    await connection.execute_script(
        """
        ALTER TABLE IF EXISTS "bill"
            ADD COLUMN IF NOT EXISTS "source" VARCHAR(50),
            ADD COLUMN IF NOT EXISTS "source_record_id" VARCHAR(100);
        CREATE INDEX IF NOT EXISTS "idx_bill_source" ON "bill" ("source");
        CREATE INDEX IF NOT EXISTS "idx_bill_source_record_id" ON "bill" ("source_record_id");
        """
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or sync Feishu bitable bill records.")
    parser.add_argument("--url", default="")
    parser.add_argument("--app-token", default="TbyPbBZJWafmcgsIyEocRorTnxh")
    parser.add_argument("--table-id", default="tblaU90ppqwjOfta")
    parser.add_argument("--view-id", default="vew8xyI8DE")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--replace-source", action="store_true")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--raw", action="store_true")
    args = parser.parse_args()

    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        await ensure_feishu_bill_columns()
        if args.raw:
            from app.api.v1.bills.bills import fetch_feishu_bitable_records

            records = await fetch_feishu_bitable_records(args.app_token, args.table_id, args.view_id)
            for record in records[:5]:
                print({"record_id": record.get("record_id"), "fields": record.get("fields")})
            return
        if args.replace_source:
            from app.models.company import Bill

            deleted = await Bill.filter(source="feishu_bitable").delete()
            print({"deleted_feishu_bills": deleted})
        result = await sync_feishu_bills(
            FeishuBillSyncPayload(
                url=args.url,
                app_token=args.app_token,
                table_id=args.table_id,
                view_id=args.view_id,
                dry_run=not args.apply,
            )
        )
        data = result.body
        import json

        data = (json.loads(data.decode("utf-8")).get("data") or {}) if data else {}
        print({key: (len(value) if isinstance(value, list) else value) for key, value in data.items()})
        if args.details:
            currency_summary = {}
            for item in data.get("previews") or []:
                currency = item.get("currency") or "-"
                bucket = currency_summary.setdefault(currency, {"total": 0, "paid": 0, "unpaid": 0, "count": 0})
                bucket["total"] += float(item.get("total_amount") or 0)
                bucket["paid"] += float(item.get("paid_amount") or 0)
                bucket["unpaid"] += float(item.get("unpaid_amount") or 0)
                bucket["count"] += 1
            print({"summary": currency_summary})
            for item in (data.get("previews") or [])[:3]:
                print(
                    {
                        "invoice_no": item.get("invoice_no"),
                        "customer_name": item.get("customer_name"),
                        "bill_month": item.get("bill_month"),
                        "currency": item.get("currency"),
                        "total_amount": item.get("total_amount"),
                        "item": (item.get("items") or [{}])[0].get("item"),
                    }
                )
            for item in data.get("skipped") or []:
                print({"skipped": item.get("record_id"), "reason": item.get("reason")})
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
