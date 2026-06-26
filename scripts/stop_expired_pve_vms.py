import asyncio
import re
from datetime import datetime, timezone, timedelta

from app.api.v1.pve.pve import all_vms, enrich_vm_remarks, guest_kind, pdm_post, pdm_resources_list


TIMEZONE = timezone(timedelta(hours=8))
EXPIRE_PATTERN = re.compile(
    r"有效期至[:：]\s*"
    r"(?P<year>20\d{2})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})(?:日)?"
    r"(?:\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{1,2}))?)?"
)


def parse_expire_at(remark: str) -> datetime | None:
    match = EXPIRE_PATTERN.search((remark or "").strip())
    if not match:
        return None

    values = match.groupdict()
    try:
        return datetime(
            int(values["year"]),
            int(values["month"]),
            int(values["day"]),
            int(values.get("hour") or 0),
            int(values.get("minute") or 0),
            tzinfo=TIMEZONE,
        )
    except ValueError:
        return None


async def stop_expired_vm(vm: dict, expire_at: datetime) -> tuple[bool, str]:
    remote = str(vm.get("remote") or "")
    vmid = vm.get("vmid")
    if not remote or not vmid:
        return False, "missing remote or vmid"

    payload: dict = {}
    if vm.get("node"):
        payload["node"] = vm.get("node")

    await pdm_post(f"/pve/remotes/{remote}/{guest_kind(vm.get('type'))}/{int(vmid)}/stop", payload)
    return True, f"expired at {expire_at:%Y-%m-%d %H:%M}"


async def main() -> None:
    now = datetime.now(TIMEZONE)
    print(f"[start] stop expired PVE VMs at {now:%Y-%m-%d %H:%M:%S}")

    data = await pdm_resources_list()
    vms = all_vms(data)
    await enrich_vm_remarks(vms)

    checked = 0
    skipped = 0
    stopped = 0
    failed = 0

    for vm in vms:
        name = str(vm.get("name") or f"VM {vm.get('vmid')}")
        remote = str(vm.get("remote") or "")
        remark = str(vm.get("remark") or "").strip()
        expire_at = parse_expire_at(remark)

        if not expire_at:
            skipped += 1
            continue

        checked += 1
        if expire_at > now:
            print(f"[skip] {remote}/{name}: not expired, expire_at={expire_at:%Y-%m-%d %H:%M}")
            continue

        if vm.get("status") != "running":
            print(f"[skip] {remote}/{name}: expired but status={vm.get('status')}")
            continue

        try:
            ok, detail = await stop_expired_vm(vm, expire_at)
        except Exception as exc:
            failed += 1
            print(f"[fail] {remote}/{name}: {type(exc).__name__}: {exc}")
            continue

        if ok:
            stopped += 1
            print(f"[stop] {remote}/{name}: {detail}")

    print(
        "[done] "
        f"total={len(vms)} checked_with_expire={checked} skipped_no_valid_expire={skipped} "
        f"stopped={stopped} failed={failed}"
    )


if __name__ == "__main__":
    asyncio.run(main())
