"""Database snapshots refreshed on access and after resource operations, without a timer loop."""

import asyncio
from datetime import datetime, timedelta, timezone

from tortoise.expressions import Q

from app.log import logger
from app.models.asset import CloudResourceSnapshot

MAX_AGE = timedelta(minutes=5)
_tasks: set[asyncio.Task] = set()


def spawn(coroutine):
    task = asyncio.create_task(coroutine)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


async def read_snapshot(force=False):
    row, _ = await CloudResourceSnapshot.get_or_create(key="fleet")
    now = datetime.now(timezone.utc)
    stale = row.dirty or row.synced_at is None or now - row.synced_at >= MAX_AGE
    retry_due = row.attempted_at is None or now - row.attempted_at >= timedelta(seconds=30)
    if force or (stale and retry_due):
        # Atomic lease coordinates requests and multiple application workers.
        claimed = (
            await CloudResourceSnapshot.filter(id=row.id)
            .filter(Q(lease_until=None) | Q(lease_until__lt=now))
            .update(lease_until=now + timedelta(minutes=3), attempted_at=now)
        )
        if claimed:
            spawn(refresh_snapshot(row.id))
            row.lease_until = now + timedelta(minutes=3)
    return row.payload or {}, {
        "synced_at": row.synced_at.isoformat() if row.synced_at else None,
        "refreshing": bool(row.lease_until and row.lease_until > now),
        "stale": stale,
        "error": row.error,
    }


async def collect_snapshot(previous):
    from app.api.v1.pve import pve

    remotes = await pve.pdm_remote_list()
    bindings = await pve.pve_node_binding_map(remotes)
    details = await pve.pdm_remote_config_detail_map()
    addresses = {remote: str(value.get("address") or "") for remote, value in details.items()}
    old_nodes = {item["remote"]: item for item in previous.get("nodes", [])}
    try:
        live_groups = {group["remote"]: group for group in await pve.pdm_live_resources_list(timeout=10)}
    except Exception:
        live_groups = {}
    semaphore = asyncio.Semaphore(4)

    async def fetch(remote):
        async with semaphore:
            group = live_groups.get(remote)
            if group and not group.get("error") and (group.get("resources") or group.get("queried")):
                return group.get("resources") or []
            # Only a successful complete resource endpoint is authoritative for removals.
            # The interactive helper tolerates partial failures and must not be used here.
            for suffix in ("resources", "cluster/resources", "resources/list"):
                try:
                    raw = await pve.pdm_get(f"/pve/remotes/{remote}/{suffix}", timeout=10)
                    resources = pve.pdm_resource_items(raw, remote)
                    if resources or raw == []:
                        return resources
                except Exception:
                    continue
            raise RuntimeError("Cannot obtain a complete resource list")

    results = await asyncio.gather(*(fetch(remote) for remote in remotes), return_exceptions=True)
    nodes, vms, failures = [], [], []
    for remote, result in zip(remotes, results):
        if isinstance(result, BaseException):
            failures.append(remote)
            nodes.append(
                {
                    **old_nodes.get(remote, {"remote": remote, "value": remote, "label": remote}),
                    **bindings.get(remote, {}),
                    "error": "节点同步失败，保留上次数据",
                }
            )
            vms.extend(item for item in previous.get("items", []) if item.get("remote") == remote)
            continue
        group = {"remote": remote, "resources": result, "queried": True}
        node = pve.resource_groups([group], addresses, remote_details=details)[0]
        node.update(bindings.get(remote, {}))
        # Preserve connection display fields that aren't part of resource responses.
        for key in ("ip", "address", "fingerprint"):
            node[key] = node.get(key) or old_nodes.get(remote, {}).get(key, "")
        nodes.append(node)
        current = pve.all_vms([group])
        await pve.sync_vm_spec_metadata_from_list(current)
        for vm in current:
            vm["region_name"] = node.get("region_name") or ""
        vms.extend(current)
    await pve.apply_vm_metadata(vms)
    return {"nodes": nodes, "items": vms}, (f"同步失败的节点：{'、'.join(failures)}" if failures else "")


async def refresh_snapshot(row_id):
    try:
        row = await CloudResourceSnapshot.get(id=row_id)
        payload, error = await asyncio.wait_for(collect_snapshot(row.payload or {}), timeout=150)
        values = {"payload": payload, "error": error}
        if not error:
            values["synced_at"] = datetime.now(timezone.utc)
            values["dirty"] = False
        await CloudResourceSnapshot.filter(id=row_id).update(**values)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Cloud resource snapshot refresh failed")
        await CloudResourceSnapshot.filter(id=row_id).update(error="云资源同步失败，保留上次成功数据")
    finally:
        await CloudResourceSnapshot.filter(id=row_id).update(lease_until=None)


async def after_resource_change(remote="", task_id=None):
    """Keep the HTTP action independent of cloud polling; observe async task completion."""

    async def followup():
        try:
            from app.api.v1.pve import pve

            await CloudResourceSnapshot.filter(key="fleet").update(dirty=True)
            if task_id:
                for _ in range(120):
                    state = pve.task_state(await pve.pdm_task_request(remote, str(task_id), "status"))
                    if state["finished"]:
                        break
                    await asyncio.sleep(2)
                else:
                    return
            else:
                await asyncio.sleep(2)
            # Wait for an earlier read refresh, then take a fresh snapshot after this operation.
            for _ in range(90):
                row = await CloudResourceSnapshot.get_or_none(key="fleet")
                if not row or not row.lease_until or row.lease_until <= datetime.now(timezone.utc):
                    await read_snapshot(force=True)
                    return
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Post-operation cloud snapshot refresh failed")
            await CloudResourceSnapshot.filter(key="fleet").update(dirty=True)

    spawn(followup())


async def stop_snapshot_tasks():
    tasks = list(_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
