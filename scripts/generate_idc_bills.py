"""IDC billing batch entry point for an external scheduler. Preview by default."""

import argparse
import asyncio
import json
from datetime import date

from fastapi import HTTPException
from tortoise import Tortoise

from app.core.dependency import has_admin_role
from app.models.admin import User
from app.schemas.idc import BillingInput
from app.services.idc_billing import generate
from app.services.idc_workflow import allowed_accounts
from app.settings import settings


async def run(args):
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        user = await User.get_or_none(id=args.operator_id, is_active=True)
        if not user:
            raise ValueError("Operator must be an active application user")
        permitted = user.is_superuser or await has_admin_role(user)
        if not permitted:
            permitted = any(
                api.method == "POST" and api.path == "/api/v1/idc/billing/generate"
                for role in await user.roles
                for api in await role.apis
            )
        if not permitted:
            raise ValueError("Operator has no IDC billing permission")
        failed = False
        for account in await allowed_accounts(user):
            if not account.active or args.account_id and account.id != args.account_id:
                continue
            try:
                result = await generate(
                    BillingInput(account_id=account.id, month=args.month, dry_run=not args.apply), user
                )
                failed |= bool(result["blocked"])
                print(json.dumps({"account_id": account.id, "result": result}, ensure_ascii=False))
            except HTTPException as exc:
                failed = True
                print(
                    json.dumps(
                        {"account_id": account.id, "error": exc.detail, "status": exc.status_code}, ensure_ascii=False
                    )
                )
        return 1 if failed else 0
    finally:
        await Tortoise.close_connections()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", type=date.fromisoformat, required=True, help="Billing month, YYYY-MM-01")
    parser.add_argument("--operator-id", type=int, required=True, help="User attributed in the audit trail")
    parser.add_argument("--account-id", type=int, help="Limit to one IDC account")
    parser.add_argument("--apply", action="store_true", help="Save pending-approval drafts; default is preview")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
