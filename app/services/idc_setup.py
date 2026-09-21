"""Idempotent catalog/menu setup; no customer mappings are guessed or auto-created."""

from app.models.admin import Api, Menu, Role
from app.services.idc_workflow import catalog_products


async def setup_idc():
    from app.core.init_app import ensure_menu_catalog
    from app.schemas.menus import MenuType

    await catalog_products()
    parent = await ensure_menu_catalog("IDC业务", "/idc", 6, "mdi:transit-connection-variant", "/idc/orders")
    menus = [parent]
    for index, (name, path, icon) in enumerate(
        [
            ("IDC工单", "orders", "mdi:clipboard-flow-outline"),
            ("客户产品", "services", "mdi:server-network"),
            ("IDC账单", "billing", "mdi:receipt-text-outline"),
        ]
    ):
        row, _ = await Menu.get_or_create(
            path=f"/idc/{path}",
            defaults={
                "name": name,
                "parent_id": parent.id,
                "menu_type": MenuType.MENU,
                "component": f"/idc/{path}",
                "icon": icon,
                "order": index,
                "keepalive": False,
                "is_hidden": False,
            },
        )
        menus.append(row)
    apis = await Api.filter(path__startswith="/api/v1/idc/")
    for role in await Role.all():
        name = str(role.name or "").lower().strip()
        if name in {"admin", "管理员"}:
            selected = apis
        elif name in {"sales", "销售", "商务"}:
            selected = [
                api
                for api in apis
                if api.method == "GET"
                or api.path.endswith(("/orders", "/lines/{line_id}", "/quotes", "/decision", "/accept"))
                and "/billing" not in api.path
            ]
        elif name in {"noc", "运维", "技术"}:
            selected = [
                api
                for api in apis
                if (api.method == "GET" and "/billing" not in api.path and "account-options" not in api.path)
                or api.path.endswith(("/delivery", "/support-complete", "/resources/reconcile"))
                or "/tasks/" in api.path
            ]
        elif name in {"finance", "财务"}:
            selected = [
                api
                for api in apis
                if api.method == "GET" or "/billing" in api.path or api.path.endswith(("/accounts", "/usage"))
            ]
        else:
            continue
        await role.apis.add(*selected)
        visible_menus = menus if name in {"admin", "管理员", "finance", "财务"} else menus[:3]
        await role.menus.add(*visible_menus)
