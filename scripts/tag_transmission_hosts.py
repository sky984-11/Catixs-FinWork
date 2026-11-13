"""Apply the reviewed transmission host tags; dry-run unless --apply is supplied.

Run from the repository root: python -m scripts.tag_transmission_hosts [--apply]
Only direct host tags are changed. Existing unrelated tags are preserved;
conflicting values or changed host identities stop the entire preflight.
"""

import argparse
import asyncio
import json
import sys

from app.services.monitor_events import ZabbixClient

# hostid, reviewed name prefix, line type, site A, site B, provider
PLAN = [
    ("10881", "DE_DE1 -- Colt -- DE_FRA15", "德国境内互联", "DE1", "FRA15", "Colt"),
    ("10882", "DE_FRA15 -- CUG -- DE_FRA7", "德国境内互联", "FRA15", "FRA7", "CUG"),
    ("10883", "HK -- Zenlayer --- USA", "跨太平洋互联", "HK2", "LA1", "Zenlayer"),
    ("10887", "HK -- CTG -- JPN", "亚太跨境互联", "HK2", "JPN", "CTG"),
    ("10888", "HK -- Zenlayer -- SG", "亚太跨境互联", "HK2", "SG", "Zenlayer"),
    ("10890", "HK -- Zenlayer -- TW", "香港与台湾互联", "HK2", "TW", "Zenlayer"),
    ("10891", "JPN -- 263 -- SH", "内地国际互联", "JPN", "SH", "263"),
    ("10893", "UK_LD8 -- Colt -- UK_UK1", "英国境内互联", "LD8", "UK1", "Colt"),
    ("10894", "UK_LD8 -- RETN -- DE_FRA7", "欧洲跨国互联", "LD8", "FRA7", "RETN"),
    ("10932", "USA_LA3 --- Cogent -- USA_LA1", "美国本地互联", "LA3", "LA1", "Cogent"),
    ("10933", "HK -- gaonuo -- SZ", "内地与香港互联", "HK2", "SZBWX", "gaonuo"),
    ("10949", "external UK_LD8 -- RETN -- DE_FRA7", "欧洲跨国互联", "LD8", "FRA7", "RETN"),
    ("11056", "SG_EQ_SG1 -- Sarhub -- SG_CMI_SG1", "新加坡本地互联", "SG_EQ_SG1", "SG_CMI_SG1", "Sarhub"),
    ("11057", "SG_EQ_SG1 -- Zenlayer -- SG_CMI_SG1", "新加坡本地互联", "SG_EQ_SG1", "SG_CMI_SG1", "Zenlayer"),
    ("11069", "SZ -- gaonuo -- HK", "内地与香港互联", "SZBWX", "HK2", "gaonuo"),
    ("11077", "SZ -- kuandu -- SH", "内地跨城互联", "SZBWX", "SH", "kuandu"),
    ("11082", "SH --- yinghe --- KR", "内地国际互联", "SH", "KR", "yinghe"),
    ("11088", "HK -- Equinix -- AUS", "亚太跨境互联", "HK2", "SY2", "Equinix"),
]


def pairs(tags):
    return {(tag["tag"], tag["value"]) for tag in tags}


async def run(apply=False):
    async with ZabbixClient() as client:
        groups = await client.call(
            "hostgroup.get", {"output": ["groupid"], "filter": {"name": ["传输 PING监控"]}}
        )
        if len(groups) != 1:
            raise RuntimeError("Expected transmission group not found uniquely")
        params = {
            "groupids": [groups[0]["groupid"]],
            "hostids": [row[0] for row in PLAN],
            "output": ["hostid", "name"],
            "selectTags": "extend",
        }
        hosts = {host["hostid"]: host for host in await client.call("host.get", params)}
        if len(hosts) != len(PLAN):
            raise RuntimeError("Some reviewed hosts are missing or no longer in the expected group")
        updates, expected = [], {}
        for hostid, prefix, line_type, site_a, site_b, provider in PLAN:
            host = hosts[hostid]
            if host["name"].split("PATH", 1)[0].strip() != prefix:
                raise RuntimeError(f"Host identity changed: {hostid}")
            desired = {
                "business_category": "传输线路",
                "line_type": line_type,
                "site_a": site_a,
                "site_b": site_b,
                "provider": provider,
            }
            existing = pairs(host["tags"])
            for key, value in existing:
                if key in desired and desired[key] != value:
                    raise RuntimeError(f"Conflicting existing tag on host {hostid}: {key}")
            expected[hostid] = existing | set(desired.items())
            if expected[hostid] != existing:
                updates.append({
                    "hostid": hostid,
                    "tags": [{"tag": key, "value": value} for key, value in sorted(expected[hostid])],
                })
        print(json.dumps({"reviewed": len(hosts), "pending": len(updates), "apply": apply}))
        if not apply:
            return
        # Recheck before writing: do not overwrite edits made during preflight.
        fresh = await client.call("host.get", params)
        if {h["hostid"]: (h["name"], pairs(h["tags"])) for h in fresh} != {
            hid: (h["name"], pairs(h["tags"])) for hid, h in hosts.items()
        }:
            raise RuntimeError("Host names/tags changed during preflight; rerun to review")
        if updates:
            await client.call("host.update", updates)
        verified = await client.call("host.get", params)
        if {h["hostid"]: pairs(h["tags"]) for h in verified} != expected:
            raise RuntimeError("Tag read-back mismatch; inspect current tags before retrying")
        print(json.dumps({"updated": len(updates), "verified": len(verified)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run(args.apply))
