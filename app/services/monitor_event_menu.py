from tortoise.transactions import atomic

from app.models import Api, Menu, Role
from app.schemas.menus import MenuType


@atomic()
async def ensure_monitor_event_menu():
    root, _ = await Menu.update_or_create(
        path="/events",
        defaults={
            "name": "事件管理",
            "order": 8,
            "parent_id": 0,
            "icon": "mdi:alert-circle-check-outline",
            "component": "Layout",
            "is_hidden": False,
            "keepalive": False,
            "redirect": "/ops/events",
            "menu_type": MenuType.CATALOG,
        },
    )
    menu, _ = await Menu.update_or_create(
        path="/ops/events",
        defaults={
            "name": "事件列表",
            "order": 1,
            "parent_id": root.id,
            "icon": "mdi:alert-circle-check-outline",
            "component": "/ops/events",
            "is_hidden": False,
            "keepalive": False,
            "redirect": "",
            "menu_type": MenuType.MENU,
        },
    )
    children = []
    for order, key, name, icon in [
        (2, "history", "历史事件", "mdi:history"),
        (3, "hosts", "监控主机", "mdi:server-network"),
        (4, "categories", "分类管理", "mdi:tag-multiple-outline"),
    ]:
        child, _ = await Menu.update_or_create(
            path=f"/events/{key}",
            defaults={
                "name": name,
                "order": order,
                "parent_id": root.id,
                "icon": icon,
                "component": f"/ops/events/{key}",
                "is_hidden": False,
                "keepalive": False,
                "redirect": "",
                "menu_type": MenuType.MENU,
            },
        )
        children.append(child)
    apis = await Api.filter(path__startswith="/api/v1/monitor-events")
    for role in await Role.all():
        if str(role.name or "").strip().lower() in {"admin", "管理员"}:
            if apis:
                await role.apis.add(*apis)
            await role.menus.add(root, menu, *children)
        elif await role.menus.filter(id=menu.id).exists():
            # Preserve existing event readers without granting new API permissions.
            await role.menus.add(root, children[0])
            if await role.apis.filter(path="/api/v1/monitor-events/settings", method="GET").exists():
                await role.menus.add(*children[1:])
