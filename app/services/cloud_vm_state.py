"""Refresh one guest without scheduling a fleet inventory scan."""

import asyncio

from tortoise.transactions import in_transaction

from app.models.asset import CloudResourceSnapshot
from app.services.cloud_resource_snapshot import spawn, vm_key


async def refresh_vm_state(remote, vmid):
    from app.api.v1.pve import pve

    row = await CloudResourceSnapshot.get_or_none(key="fleet")
    key = (str(remote), str(vmid))
    vm = next((item for item in (row.payload or {}).get("items", []) if vm_key(item) == key), None) if row else None
    if vm is None:
        raise LookupError("VM not found")
    kind = pve.guest_kind(vm.get("type"))
    status = await pve.pdm_get(f"/pve/remotes/{remote}/{kind}/{vmid}/status", timeout=5)
    if not isinstance(status, dict) or status.get("status") not in {"running", "stopped", "paused", "suspended"}:
        raise RuntimeError("VM status unavailable")
    changes = {
        "status": status["status"],
        **{field: None for field in ("uptime", "cpu", "mem", "disk", "maxcpu", "maxmem", "maxdisk")},
    }
    for field in ("uptime", "mem", "disk", "maxmem", "maxdisk"):
        if field in status:
            changes[field] = max(0, int(status[field] or 0))
    if "cpus" in status or "maxcpu" in status:
        changes["maxcpu"] = max(0, int(status.get("cpus", status.get("maxcpu")) or 0))
    if "cpu" in status:
        changes["cpu"] = pve.percent(status["cpu"])
    if status["status"] == "stopped":
        changes.update(uptime=0, cpu=0, mem=0)
    async with in_transaction() as connection:
        latest = await CloudResourceSnapshot.filter(key="fleet").using_db(connection).select_for_update().first()
        payload = latest.payload if latest else None
        current = next((item for item in (payload or {}).get("items", []) if vm_key(item) == key), None)
        if current is None:
            raise LookupError("VM removed during refresh")
        current.update(changes)
        await CloudResourceSnapshot.filter(id=latest.id).using_db(connection).update(payload=payload)
        return dict(current)


async def after_vm_power(remote, vmid, task_id):
    async def followup():
        from app.api.v1.pve import pve

        try:
            async with asyncio.timeout(120):
                if task_id:
                    while True:
                        state = pve.task_state(await pve.pdm_task_request(remote, str(task_id), "status"))
                        if state["finished"]:
                            break
                        await asyncio.sleep(2)
                await refresh_vm_state(remote, vmid)
        except Exception:
            pve.logger.warning("Targeted VM power status refresh failed for remote=%s vmid=%s", remote, vmid)

    spawn(followup())


async def live_vm_list(remote):
    """Read both live guest inventories, retaining only local business metadata."""
    from app.api.v1.pve import pve

    row = await CloudResourceSnapshot.get_or_none(key="fleet")
    payload = row.payload or {} if row else {}
    if not any(item.get("remote") == remote for item in [*payload.get("nodes", []), *payload.get("items", [])]):
        raise LookupError("Remote not found")

    async def guests(kind):
        raw = await pve.pdm_get(f"/pve/remotes/{remote}/{kind}", timeout=5)
        if not isinstance(raw, list) and not (
            isinstance(raw, dict) and any(isinstance(raw.get(key), list) for key in ("data", "items"))
        ):
            raise RuntimeError("Incomplete live inventory")
        return pve.normalize_remote_items(raw, remote, f"pve-{kind}")

    results = await asyncio.gather(guests("qemu"), guests("lxc"))
    previous = {vm_key(vm): vm for vm in payload.get("items", [])}
    items = []
    runtime = {}
    for resource in [*results[0], *results[1]]:
        resource = {**resource, "maxcpu": resource.get("maxcpu", resource.get("cpus"))}
        vm = pve.normalize_vm(resource, remote)
        old = previous.get(vm_key(vm), {})
        for field in ("ips", "ip_addresses", "primary_ip", "os_type", "created_at", "remark", "region_name"):
            if field in old:
                vm[field] = old[field]
        # Missing live measurements remain unknown, never fall back to old specs.
        for field in ("cpu", "maxcpu", "mem", "maxmem", "disk", "maxdisk", "uptime"):
            if resource.get(field) is None:
                vm[field] = None
        if vm["status"] == "stopped":
            vm.update(cpu=0, mem=0, uptime=0)
        runtime[vm_key(vm)] = {key: vm[key] for key in ("maxcpu", "maxmem", "maxdisk")}
        items.append(vm)
    await pve.apply_vm_metadata(items)
    for vm in items:
        vm.update(runtime[vm_key(vm)])
    async with in_transaction() as connection:
        latest = await CloudResourceSnapshot.filter(key="fleet").using_db(connection).select_for_update().first()
        if latest:
            payload = latest.payload or {}
            deleted = {vm_key(vm) for vm in payload.get("pending_deletions", [])}
            items = [vm for vm in items if vm_key(vm) not in deleted]
            payload["items"] = [vm for vm in payload.get("items", []) if vm.get("remote") != remote] + items
            await CloudResourceSnapshot.filter(id=latest.id).using_db(connection).update(payload=payload)
    return items
