from app.models import Api, Menu, Role
from app.schemas.menus import MenuType


async def ensure_monitor_event_menu():
    menu, _ = await Menu.update_or_create(
        path="/ops/events",
        defaults={
            "name": "事件管理",
            "order": 8,
            "parent_id": 0,
            "icon": "mdi:alert-circle-check-outline",
            "component": "/ops/events",
            "is_hidden": False,
            "keepalive": False,
            "redirect": "",
            "menu_type": MenuType.MENU,
        },
    )
    apis = await Api.filter(path__startswith="/api/v1/monitor-events")
    for role in await Role.all():
        if str(role.name or "").strip().lower() in {"admin", "管理员"}:
            if apis:
                await role.apis.add(*apis)
            await role.menus.add(menu)
