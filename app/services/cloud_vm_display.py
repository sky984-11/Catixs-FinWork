"""Non-sensitive VM display fields; never substitute discovery time for creation time."""

import asyncio
import re
import time
from datetime import datetime, timezone

_cache = {}


def display_metadata(config):
    metadata = str(config.get("meta") or "")
    match = re.search(r"(?:^|,)ctime=(\d+)(?:,|$)", metadata)
    raw = match.group(1) if match else config.get("creation_time") or config.get("ctime")
    created_at = None
    if raw:
        try:
            timestamp = float(raw)
            if 0 < timestamp <= time.time() + 86400:
                created_at = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            pass
    return {"os_type": str(config.get("ostype") or config.get("os_type") or ""), "created_at": created_at}


async def enrich_display_metadata(vms):
    from app.api.v1.pve.pve import guest_kind, pdm_get

    semaphore = asyncio.Semaphore(6)
    now = time.monotonic()
    # Remove expired entries, including guests no longer present in the fleet.
    for key in list(_cache):
        if _cache[key][0] <= now:
            _cache.pop(key, None)

    async def load(vm):
        key = (vm.get("remote"), vm.get("vmid"), vm.get("type"))
        if not key[0] or not key[1]:
            return
        cached = _cache.get(key)
        if cached:
            vm.update(cached[1])
            return
        kind = guest_kind(str(vm.get("type") or ""))
        paths = [f"/pve/remotes/{key[0]}/{kind}/{int(key[1])}/config"]
        if vm.get("node"):
            paths.append(f"/pve/remotes/{key[0]}/nodes/{vm['node']}/{kind}/{int(key[1])}/config")
        async with semaphore:
            for path in paths:
                try:
                    config = await pdm_get(path, timeout=3)
                    if not isinstance(config, dict):
                        continue
                    fields = display_metadata(config)
                    _cache[key] = (time.monotonic() + 900, fields)
                    vm.update(fields)
                    return
                except Exception:
                    continue
            # Unknown stays unknown and failed reads are retried on the next minute.
            fields = {"os_type": vm.get("os_type") or "", "created_at": vm.get("created_at")}
            _cache[key] = (time.monotonic() + 60, fields)
            vm.update(fields)

    jobs = [asyncio.create_task(load(vm)) for vm in vms]
    if not jobs:
        return
    try:
        await asyncio.wait(jobs, timeout=30)
    finally:
        for job in jobs:
            if not job.done():
                job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
