import asyncio
import sys
from pathlib import Path

from tortoise import Tortoise

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.company import Company
from app.settings.config import settings


async def main() -> None:
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        issuer = await Company.filter(name="Catixs Ltd", role=0).first()
        if not issuer:
            issuer = await Company.filter(legal_name="Catixs Ltd", role=0).first()
        if not issuer:
            print("issuer_not_found")
            return

        updated = await Company.filter(
            role=1,
            code__gte="U00000",
            code__lte="U00030",
        ).update(contract_company_id=issuer.id)
        verified = await Company.filter(
            role=1,
            code__gte="U00000",
            code__lte="U00030",
            contract_company_id=issuer.id,
        ).count()
        print(f"issuer_id={issuer.id} issuer_name={issuer.name}")
        print(f"updated={updated} verified={verified}")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
