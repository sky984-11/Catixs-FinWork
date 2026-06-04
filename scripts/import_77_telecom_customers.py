import asyncio
import sys
from pathlib import Path

from tortoise import Tortoise

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.company import Company
from app.settings.config import settings


CUSTOMERS = [
    {
        "code": "H00000",
        "name": "ABC",
        "legal_name": "ABCDEFG",
        "address": "",
        "noc_email": "NOC@ABC.com",
        "remark": "账期: '1/30\n备注: Demo",
    },
    {
        "code": "H00001",
        "name": "智盈",
        "legal_name": "SPEED CLOUD",
        "address": "RM 509 5/F THE CLOUD, 111 TUNG CHAU STREET, TAI KOK TSUI, KL HongKong China",
        "bill_email": "songyao.ma@scloud.ac.cn",
        "noc_email": "noc@scloud.ac.cn",
        "remark": "账期: '1/10",
    },
    {
        "code": "H00002",
        "name": "奥飞",
        "legal_name": "AOFEI DATA",
        "address": "701, 7/F",
        "bill_email": "billing@ofidc.com",
        "company_email": "tanzm@aofidc.com",
        "company_phone": "+86 18928942465",
        "noc_email": "monitor@ofidc.com",
        "remark": "账期: '1/30\n技术联系人: Zhangmin Tan tanzm@aofidc.com +86 18928942465",
    },
    {
        "code": "H00003",
        "name": "Cielocom Hongkong",
        "legal_name": "Cielocom Hongkong",
        "address": "253-261 HENNESSY ROAD HongKong China",
        "bill_email": "commercial@cielocom.cc",
        "company_email": "noc@cielocom.cc",
        "company_phone": "+86 151 5625 5048",
        "noc_email": "noc@cielocom.cc",
        "remark": "账期: '1/30\n账务联系人: Summer Li\n技术联系人: Felix Zhu",
    },
    {
        "code": "H00004",
        "name": "南凌",
        "legal_name": "NOVA TECHNOLOGY",
        "address": "43/FAIA TOWER 183 ELECTRIC ROAD NORTH POINT HongKong China",
        "company_email": "gaodonghong@nova.net.cn",
        "company_phone": "+86 15815583391",
        "noc_email": "Service@nova.net.cn",
        "remark": (
            "账期: '1/30\n"
            "销售联系人: Lydia Gao; Tony Zhang; 林萌; 毛舞阳; Patrick; 陈超; 鲁子奕; 卢赛平; "
            "gaodonghong@nova.net.cn; tonyzhang@novaglobalnet.com; Tony M: +86 15815583391\n"
            "备注: 发起割接提前一周通知"
        ),
    },
    {
        "code": "H00005",
        "name": "EPBS",
        "legal_name": "Telstra EPBS",
        "address": "19/F Telecom House 3 Gloucester Road Wanchai, Hong Kong HongKong China",
        "bill_email": "summer.xiao@telstra-pbs.cn",
        "company_email": "jenny.wu@telstra-pbs.cn",
        "company_phone": "181 3884 2805",
        "noc_email": "noc@telstra-pbs.cn",
        "noc_phone": "4007002800",
        "remark": (
            "账期: '1/30\n"
            "销售联系人: Jocelyne Simon; lilian; Mars; jocelyne 18610490878; 彭贤明 18688966275; "
            "Lilian 18610490878; Alex 18610490878\n"
            "账务联系人: Summer Xiao 肖夏君 summer.xiao@telstra-pbs.cn 18816793668\n"
            "技术联系人: Jenny Wu jenny.wu@telstra-pbs.cn 181 3884 2805\n"
            "NOC联系人: 4007002800; noc@telstra-pbs.cn; tra-pbs.cn; na@telstra-pbs.cn\n"
            "备注: 有任何涉及到线路调整割接，需提前16天（或者两周）通知PBS售后部门"
        ),
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
        issuer = await Company.filter(name="77 Telecom Ltd", role=0).first()
        if not issuer:
            issuer = await Company.filter(legal_name="77 Telecom Ltd", role=0).first()
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
            code__gte="H00000",
            code__lte="H00005",
            contract_company_id=issuer.id,
        ).count()
        print(f"issuer_id={issuer.id} issuer_name={issuer.name}")
        print(f"created={created} updated={updated} verified={verified}")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
