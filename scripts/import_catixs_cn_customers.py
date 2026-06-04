import asyncio
import sys
from pathlib import Path

from tortoise import Tortoise

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.company import Company
from app.settings.config import settings


ISSUER_NAME = "深圳市科特思网络科技有限公司"

CUSTOMERS = [
    {
        "code": "C00000",
        "name": "ABC",
        "legal_name": "ABCDEFG",
        "noc_email": "NOC@ABC.com",
        "remark": "账期: '1/30\n备注: Demo",
    },
    {
        "code": "C00001",
        "name": "AK",
        "legal_name": "武汉很大",
        "address": "湖北省武汉市洪山区",
        "bill_email": "fp@bigwuhan.cn",
    },
    {
        "code": "C00002",
        "name": "Geelinx",
        "legal_name": "安锐普世",
        "address": "北京市延庆",
        "bill_email": "master@aoripus.com",
        "remark": "账期: '1/30\n销售联系人: 陈紫阳\n备注: Geelinx",
    },
    {
        "code": "C00003",
        "name": "Quickfox",
        "legal_name": "厦门科臻",
        "address": "福建区金海街道鸿翔西路1888号1号楼10层1007单元 厦门市 中国",
        "remark": "账期: '1/30\n销售联系人: 李莉莉",
    },
    {
        "code": "C00004",
        "name": "Moechuang",
        "legal_name": "广州市萌创",
        "address": "广州大道中1268号803A 6385室 广州市天河区 中国",
        "remark": "账期: '1/12",
    },
    {
        "code": "C00005",
        "name": "米连",
        "legal_name": "米连网络科技",
        "address": "深圳市南山",
        "bill_email": "finance@link-technology.com",
        "remark": "账期: '1/15\n销售联系人: alextyang",
    },
    {
        "code": "C00006",
        "name": "Nova",
        "legal_name": "南凌科技",
        "address": "深圳市福田",
        "bill_email": "Gaodonghong@nova.net.cn",
        "remark": "账期: '1/30\n账务联系人: 富东红",
    },
]


def limit(value: str, max_length: int) -> str:
    value = value or ""
    return value[:max_length] if len(value) > max_length else value


async def main() -> None:
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

        for item in CUSTOMERS:
            payload = {
                "role": 1,
                "code": item["code"],
                "name": limit(item["name"], 100),
                "legal_name": limit(item["legal_name"], 200),
                "address": limit(item.get("address", ""), 255),
                "company_email": limit(item.get("company_email", ""), 100),
                "company_phone": limit(item.get("company_phone", ""), 50),
                "bill_email": limit(item.get("bill_email", ""), 100),
                "noc_email": limit(item.get("noc_email", ""), 100),
                "noc_phone": limit(item.get("noc_phone", ""), 50),
                "remark": limit(item.get("remark", ""), 500),
                "contract_company_id": issuer.id,
                "status": True,
            }
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
            code__gte="C00000",
            code__lte="C00006",
            contract_company_id=issuer.id,
        ).count()
        print(f"issuer_id={issuer.id} issuer_name={issuer.name}")
        print(f"created={created} updated={updated} verified={verified}")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
