import asyncio
import json

from app.api.v1.netbox.ipam import sync_pve_ips_summary


async def main() -> None:
    data = await sync_pve_ips_summary()
    summary = {
        "vm_count": data.get("vm_count", 0),
        "ip_count": data.get("ip_count", 0),
        "created": data.get("created", 0),
        "updated": data.get("updated", 0),
        "unchanged": data.get("unchanged", 0),
        "skipped": data.get("skipped", 0),
        "failed": data.get("failed", 0),
    }
    print(json.dumps(summary, ensure_ascii=False))
    failures = data.get("failures") or []
    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
