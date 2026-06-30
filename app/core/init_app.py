import os
import shutil

from aerich import Command
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise
from tortoise.exceptions import OperationalError
from tortoise.expressions import Q

from app.api import api_router
from app.controllers.api import api_controller
from app.controllers.user import UserCreate, user_controller
from app.core.exceptions import (
    DoesNotExist,
    DoesNotExistHandle,
    HTTPException,
    HttpExcHandle,
    IntegrityError,
    IntegrityHandle,
    RequestValidationError,
    RequestValidationHandle,
    ResponseValidationError,
    ResponseValidationHandle,
)
from app.log import logger
from app.models.admin import Api, Menu, Role
from app.models.admin import ScheduledTask
from app.models.company import Bank, BankAccount, Company
from app.schemas.menus import MenuType
from app.settings.config import settings

from .middlewares import BackGroundTaskMiddleware, HttpAuditLogMiddleware


def make_middlewares():
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
        ),
        Middleware(BackGroundTaskMiddleware),
        Middleware(
            HttpAuditLogMiddleware,
            methods=["POST", "PUT", "PATCH", "DELETE"],
            exclude_paths=[
                r"^/(?!api/)",
                "/api/v1/base/access_token",
                "/api/v1/vendor/export",
                "/api/v1/vendor/import",
                "/docs",
                "/openapi.json",
            ],
        ),
    ]
    return middleware


def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)


def register_routers(app: FastAPI, prefix: str = "/api"):
    app.include_router(api_router, prefix=prefix)


async def init_superuser():
    user = await user_controller.model.exists()
    if not user:
        await user_controller.create_user(
            UserCreate(
                username="admin",
                email="noc@cn.catixs.com",
                password="Catixs@3202",
                is_active=True,
                is_superuser=True,
            )
        )


async def init_menus():
    menus = await Menu.exists()
    if not menus:
        parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="carbon:gui-management",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )
        children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="用户管理",
                path="user",
                order=1,
                parent_id=parent_menu.id,
                icon="material-symbols:person-outline-rounded",
                is_hidden=False,
                component="/system/user",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="角色管理",
                path="role",
                order=2,
                parent_id=parent_menu.id,
                icon="carbon:user-role",
                is_hidden=False,
                component="/system/role",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="菜单管理",
                path="menu",
                order=3,
                parent_id=parent_menu.id,
                icon="material-symbols:list-alt-outline",
                is_hidden=False,
                component="/system/menu",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="API管理",
                path="api",
                order=4,
                parent_id=parent_menu.id,
                icon="ant-design:api-outlined",
                is_hidden=False,
                component="/system/api",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="部门管理",
                path="dept",
                order=5,
                parent_id=parent_menu.id,
                icon="mingcute:department-line",
                is_hidden=False,
                component="/system/dept",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="审计日志",
                path="auditlog",
                order=6,
                parent_id=parent_menu.id,
                icon="ph:clipboard-text-bold",
                is_hidden=False,
                component="/system/auditlog",
                keepalive=False,
            ),
        ]
        await Menu.bulk_create(children_menu)
        ops_menu, finance_menu = await ensure_service_module_menus()
        ticket_menu = await Menu.create(
            menu_type=MenuType.MENU,
            name="工单管理",
            path="/ticket",
            order=1,
            parent_id=ops_menu.id,
            icon="material-symbols:assignment-globe",
            is_hidden=False,
            component="/ticket",
            keepalive=False,
            redirect="",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="新增工单",
            path="/ticket/create",
            order=1,
            parent_id=ticket_menu.id,
            icon="mdi:file-document-plus-outline",
            is_hidden=True,
            component="/ticket/create",
            keepalive=False,
            redirect="",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="工单详情",
            path="/ticket/detail",
            order=2,
            parent_id=ticket_menu.id,
            icon="mdi:file-document-outline",
            is_hidden=True,
            component="/ticket/detail",
            keepalive=False,
            redirect="",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="编辑工单",
            path="/ticket/edit",
            order=3,
            parent_id=ticket_menu.id,
            icon="mdi:file-document-edit-outline",
            is_hidden=True,
            component="/ticket/edit",
            keepalive=False,
            redirect="",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="客户/供应商",
            path="/vendor",
            order=1,
            parent_id=finance_menu.id,
            icon="mdi:account-group-outline",
            is_hidden=False,
            component="/company",
            keepalive=False,
            redirect="",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="资产管理",
            path="/asset",
            order=2,
            parent_id=0,
            icon="material-symbols:videogame-asset",
            is_hidden=False,
            component="/asset",
            keepalive=False,
            redirect="",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="账单管理",
            path="/bill",
            order=3,
            parent_id=0,
            icon="mdi:file-document-multiple-outline",
            is_hidden=False,
            component="/bill",
            keepalive=False,
            redirect="",
        )
    await ensure_service_module_menus()
    await ensure_ticket_route_menus()
    await ensure_asset_menu()
    await ensure_syslog_menu()
    await ensure_akvorado_menu()
    await ensure_ipam_menu()
    await ensure_business_party_menu()
    await ensure_bill_menu()
    await ensure_inventory_sale_menu()
    await ensure_customer_project_menu()
    await ensure_task_menu()


async def ensure_menu_catalog(name: str, path: str, order: int, icon: str, redirect: str):
    menu = await Menu.filter(path=path).first()
    values = {
        "menu_type": MenuType.CATALOG,
        "name": name,
        "path": path,
        "order": order,
        "parent_id": 0,
        "icon": icon,
        "is_hidden": False,
        "component": "Layout",
        "keepalive": False,
        "redirect": redirect,
    }
    if menu:
        changed = False
        for field, value in values.items():
            if getattr(menu, field) != value:
                setattr(menu, field, value)
                changed = True
        if changed:
            await menu.save()
        return menu

    return await Menu.create(**values)


async def ensure_service_module_menus():
    ops_menu = await ensure_menu_catalog(
        name="\u8fd0\u7ef4\u6a21\u5757",
        path="/ops",
        order=3,
        icon="mdi:tools",
        redirect="/ticket",
    )
    finance_menu = await ensure_menu_catalog(
        name="\u8d22\u52a1\u6a21\u5757",
        path="/finance",
        order=4,
        icon="mdi:finance",
        redirect="/vendor",
    )
    return ops_menu, finance_menu


async def get_service_module_menu(path: str):
    menu = await Menu.filter(path=path).first()
    if menu:
        return menu
    await ensure_service_module_menus()
    return await Menu.filter(path=path).first()


async def ensure_ticket_route_menus():
    ops_menu = await get_service_module_menu("/ops")
    ticket_menu = await Menu.filter(path="/ticket").first()
    if not ticket_menu:
        ticket_menu = await Menu.create(
            menu_type=MenuType.MENU,
            name="工单管理",
            path="/ticket",
            order=1,
            parent_id=ops_menu.id,
            icon="material-symbols:assignment-globe",
            is_hidden=False,
            component="/ticket",
            keepalive=False,
            redirect="",
        )
    else:
        changed = False
        values = {
            "order": 1,
            "parent_id": ops_menu.id,
            "icon": "material-symbols:assignment-globe",
            "is_hidden": False,
            "component": "/ticket",
            "keepalive": False,
        }
        for field, value in values.items():
            if getattr(ticket_menu, field) != value:
                setattr(ticket_menu, field, value)
                changed = True
        if changed:
            await ticket_menu.save()

    ticket_route_menus = [
        {
            "name": "新增工单",
            "path": "/ticket/create",
            "order": 1,
            "icon": "mdi:file-document-plus-outline",
            "component": "/ticket/create",
        },
        {
            "name": "工单详情",
            "path": "/ticket/detail",
            "order": 2,
            "icon": "mdi:file-document-outline",
            "component": "/ticket/detail",
        },
        {
            "name": "编辑工单",
            "path": "/ticket/edit",
            "order": 3,
            "icon": "mdi:file-document-edit-outline",
            "component": "/ticket/edit",
        },
    ]
    for menu_data in ticket_route_menus:
        route_menu = await Menu.filter(component=menu_data["component"]).first()
        if not route_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name=menu_data["name"],
                path=menu_data["path"],
                order=menu_data["order"],
                parent_id=ops_menu.id,
                icon=menu_data["icon"],
                is_hidden=True,
                component=menu_data["component"],
                keepalive=False,
                redirect="",
            )
        elif (
            route_menu.path != menu_data["path"]
            or route_menu.parent_id != ops_menu.id
            or not route_menu.is_hidden
        ):
            route_menu.path = menu_data["path"]
            route_menu.parent_id = ops_menu.id
            route_menu.is_hidden = True
            await route_menu.save()


async def ensure_asset_menu_old():
    ops_menu = await get_service_module_menu("/ops")
    asset_menu = await Menu.filter(path="/asset").first()
    if asset_menu:
        changed = False
        if asset_menu.name != "资产管理":
            asset_menu.name = "资产管理"
            changed = True
        if asset_menu.component != "/asset":
            asset_menu.component = "/asset"
            changed = True
        if asset_menu.is_hidden:
            asset_menu.is_hidden = False
            changed = True
        if asset_menu.parent_id != ops_menu.id:
            asset_menu.parent_id = ops_menu.id
            changed = True
        if asset_menu.order != 2:
            asset_menu.order = 2
            changed = True
        if changed:
            await asset_menu.save()
        return

    await Menu.create(
        menu_type=MenuType.MENU,
        name="资产管理",
        path="/asset",
        order=2,
        parent_id=ops_menu.id,
        icon="material-symbols:videogame-asset",
        is_hidden=False,
        component="/asset",
        keepalive=False,
        redirect="",
    )

async def ensure_asset_menu():
    ops_menu = await get_service_module_menu("/ops")
    legacy_menu = await Menu.filter(path="/asset").first()
    legacy_values = {
        "name": "资产管理",
        "path": "/asset",
        "order": 20,
        "parent_id": ops_menu.id,
        "icon": "material-symbols:videogame-asset",
        "is_hidden": True,
        "component": "/asset",
        "keepalive": False,
        "redirect": "",
    }
    if legacy_menu:
        changed = False
        for field, value in legacy_values.items():
            if getattr(legacy_menu, field) != value:
                setattr(legacy_menu, field, value)
                changed = True
        if changed:
            await legacy_menu.save()
    else:
        await Menu.create(menu_type=MenuType.MENU, **legacy_values)

    asset_menus = [
        {
            "name": "机柜管理",
            "path": "/asset/cabinet",
            "order": 2,
            "icon": "mdi:server-network",
            "component": "/asset/cabinet",
        },
        {
            "name": "库存管理",
            "path": "/asset/inventory",
            "order": 3,
            "icon": "mdi:package-variant-closed",
            "component": "/asset/inventory",
        },
    ]
    for menu_data in asset_menus:
        menu = await Menu.filter(path=menu_data["path"]).first()
        values = {
            "menu_type": MenuType.MENU,
            "name": menu_data["name"],
            "path": menu_data["path"],
            "order": menu_data["order"],
            "parent_id": ops_menu.id,
            "icon": menu_data["icon"],
            "is_hidden": False,
            "component": menu_data["component"],
            "keepalive": False,
            "redirect": "",
        }
        if menu:
            changed = False
            for field, value in values.items():
                if getattr(menu, field) != value:
                    setattr(menu, field, value)
                    changed = True
            if changed:
                await menu.save()
        else:
            await Menu.create(**values)


async def ensure_syslog_menu():
    ops_menu = await get_service_module_menu("/ops")
    syslog_menu = await Menu.filter(path="/syslog").first()
    values = {
        "name": "Syslog日志管理",
        "path": "/syslog",
        "order": 3,
        "parent_id": ops_menu.id,
        "icon": "mdi:text-box-search-outline",
        "is_hidden": False,
        "component": "/ops/syslog",
        "keepalive": False,
        "redirect": "",
    }
    if syslog_menu:
        changed = False
        for field, value in values.items():
            if getattr(syslog_menu, field) != value:
                setattr(syslog_menu, field, value)
                changed = True
        if syslog_menu.menu_type != MenuType.MENU:
            syslog_menu.menu_type = MenuType.MENU
            changed = True
        if changed:
            await syslog_menu.save()
        return

    await Menu.create(menu_type=MenuType.MENU, **values)


async def ensure_akvorado_menu():
    ops_menu = await get_service_module_menu("/ops")
    akvorado_menu = await Menu.filter(path="/akvorado").first()
    values = {
        "name": "Akvorado 流量",
        "path": "/akvorado",
        "order": 4,
        "parent_id": ops_menu.id,
        "icon": "mdi:chart-timeline-variant-shimmer",
        "is_hidden": False,
        "component": "/ops/akvorado",
        "keepalive": False,
        "redirect": "",
    }
    if akvorado_menu:
        changed = False
        for field, value in values.items():
            if getattr(akvorado_menu, field) != value:
                setattr(akvorado_menu, field, value)
                changed = True
        if akvorado_menu.menu_type != MenuType.MENU:
            akvorado_menu.menu_type = MenuType.MENU
            changed = True
        if changed:
            await akvorado_menu.save()
        return

    await Menu.create(menu_type=MenuType.MENU, **values)


async def ensure_ipam_menu():
    ops_menu = await get_service_module_menu("/ops")
    ipam_menu = await Menu.filter(path="/ipam").first()
    values = {
        "name": "IP管理",
        "path": "/ipam",
        "order": 5,
        "parent_id": ops_menu.id,
        "icon": "mdi:ip-network-outline",
        "is_hidden": False,
        "component": "/ops/ipam",
        "keepalive": False,
        "redirect": "",
    }
    if ipam_menu:
        changed = False
        for field, value in values.items():
            if getattr(ipam_menu, field) != value:
                setattr(ipam_menu, field, value)
                changed = True
        if ipam_menu.menu_type != MenuType.MENU:
            ipam_menu.menu_type = MenuType.MENU
            changed = True
        if changed:
            await ipam_menu.save()
        return

    await Menu.create(menu_type=MenuType.MENU, **values)


async def ensure_bill_menu():
    finance_menu = await get_service_module_menu("/finance")
    bill_menu = await Menu.filter(path="/bill").first()
    if bill_menu:
        changed = False
        if bill_menu.name != "账单管理":
            bill_menu.name = "账单管理"
            changed = True
        if bill_menu.component != "/bill":
            bill_menu.component = "/bill"
            changed = True
        if bill_menu.icon != "mdi:file-document-multiple-outline":
            bill_menu.icon = "mdi:file-document-multiple-outline"
            changed = True
        if bill_menu.order != 2:
            bill_menu.order = 2
            changed = True
        if bill_menu.parent_id != finance_menu.id:
            bill_menu.parent_id = finance_menu.id
            changed = True
        if bill_menu.is_hidden:
            bill_menu.is_hidden = False
            changed = True
        if changed:
            await bill_menu.save()
    else:
        bill_menu = await Menu.create(
            menu_type=MenuType.MENU,
            name="账单管理",
            path="/bill",
            order=2,
            parent_id=finance_menu.id,
            icon="mdi:file-document-multiple-outline",
            is_hidden=False,
            component="/bill",
            keepalive=False,
            redirect="",
        )


async def ensure_inventory_sale_menu():
    finance_menu = await get_service_module_menu("/finance")
    sale_menu = await Menu.filter(path="/inventory-sale").first()
    values = {
        "name": "库存售卖",
        "path": "/inventory-sale",
        "order": 3,
        "parent_id": finance_menu.id,
        "icon": "mdi:cart-outline",
        "is_hidden": False,
        "component": "/finance/inventory-sale",
        "keepalive": False,
        "redirect": "",
    }
    if sale_menu:
        changed = False
        for field, value in values.items():
            if getattr(sale_menu, field) != value:
                setattr(sale_menu, field, value)
                changed = True
        if sale_menu.menu_type != MenuType.MENU:
            sale_menu.menu_type = MenuType.MENU
            changed = True
        if changed:
            await sale_menu.save()
        return

    await Menu.create(menu_type=MenuType.MENU, **values)


async def ensure_customer_project_menu():
    project_menu = await Menu.filter(path="/project-board").first()
    values = {
        "name": "\u9879\u76ee\u770b\u677f",
        "path": "/project-board",
        "order": 2,
        "parent_id": 0,
        "icon": "mdi:view-dashboard-outline",
        "is_hidden": False,
        "component": "/project-board",
        "keepalive": False,
        "redirect": "",
    }
    if project_menu:
        changed = False
        for field, value in values.items():
            if getattr(project_menu, field) != value:
                setattr(project_menu, field, value)
                changed = True
        if project_menu.menu_type != MenuType.MENU:
            project_menu.menu_type = MenuType.MENU
            changed = True
        if changed:
            await project_menu.save()
        return

    await Menu.create(menu_type=MenuType.MENU, **values)


async def ensure_task_menu():
    system_menu = await Menu.filter(path="/system").first()
    if not system_menu:
        system_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="carbon:gui-management",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )

    task_menu = await Menu.filter(component="/system/task").first()
    if task_menu:
        changed = False
        values = {
            "name": "定时任务",
            "path": "task",
            "order": 7,
            "parent_id": system_menu.id,
            "icon": "mdi:timer-cog-outline",
            "is_hidden": False,
            "keepalive": False,
        }
        for field, value in values.items():
            if getattr(task_menu, field) != value:
                setattr(task_menu, field, value)
                changed = True
        if changed:
            await task_menu.save()
        return task_menu

    return await Menu.create(
        menu_type=MenuType.MENU,
        name="定时任务",
        path="task",
        order=7,
        parent_id=system_menu.id,
        icon="mdi:timer-cog-outline",
        is_hidden=False,
        component="/system/task",
        keepalive=False,
    )


async def ensure_business_party_menu():
    finance_menu = await get_service_module_menu("/finance")
    company_menu = await Menu.filter(path="/vendor").first()
    if company_menu:
        changed = False
        if company_menu.name != "客户/供应商":
            company_menu.name = "客户/供应商"
            changed = True
        if company_menu.component != "/company":
            company_menu.component = "/company"
            changed = True
        if company_menu.icon != "mdi:account-group-outline":
            company_menu.icon = "mdi:account-group-outline"
            changed = True
        if company_menu.order != 1:
            company_menu.order = 1
            changed = True
        if company_menu.parent_id != finance_menu.id:
            company_menu.parent_id = finance_menu.id
            changed = True
        if company_menu.is_hidden:
            company_menu.is_hidden = False
            changed = True
        if changed:
            await company_menu.save()
    else:
        company_menu = await Menu.create(
            menu_type=MenuType.MENU,
            name="客户/供应商",
            path="/vendor",
            order=1,
            parent_id=finance_menu.id,
            icon="mdi:account-group-outline",
            is_hidden=False,
            component="/company",
            keepalive=False,
            redirect="",
        )

    roles = await Role.all()
    legacy_company_menus = await Menu.filter(path="/company", component="/company")
    for legacy_company_menu in legacy_company_menus:
        if legacy_company_menu.id == company_menu.id:
            continue
        for role in roles:
            has_legacy_menu = await role.menus.filter(id=legacy_company_menu.id).exists()
            if has_legacy_menu:
                await role.menus.remove(legacy_company_menu)
        await Menu.filter(parent_id=legacy_company_menu.id).delete()
        await legacy_company_menu.delete()


async def init_apis():
    await api_controller.refresh_api()


def is_admin_role_name(name: str | None) -> bool:
    role_name = str(name or "").strip().lower()
    return role_name in {"admin", "管理员", "noc"}


async def ensure_business_api_permissions():
    roles = await Role.all()
    if not roles:
        return

    read_apis = await Api.filter(
        Q(method="GET", path="/api/v1/company/list")
        | Q(method="GET", path="/api/v1/company/get")
        | Q(method="GET", path="/api/v1/bill/list")
        | Q(method="GET", path="/api/v1/bill/get")
        | Q(method="GET", path="/api/v1/bank_account/list")
        | Q(method="GET", path="/api/v1/asset/inventory/list")
        | Q(method="GET", path="/api/v1/asset/inventory-category/list")
        | Q(method="GET", path="/api/v1/asset/inventory-sale/list")
        | Q(method="GET", path="/api/v1/asset/inventory-flow/list")
        | Q(method="GET", path="/api/v1/project/list")
        | Q(method="GET", path="/api/v1/project/get")
    )
    manage_apis = await Api.filter(
        Q(path__startswith="/api/v1/company/")
        | Q(path__startswith="/api/v1/bill/")
        | Q(path__startswith="/api/v1/asset/inventory-sale/")
        | Q(path__startswith="/api/v1/project/")
    )
    sale_menu = await Menu.filter(path="/inventory-sale").first()
    project_menu = await Menu.filter(path="/project-board").first()

    for role in roles:
        if read_apis:
            await role.apis.add(*read_apis)
        if is_admin_role_name(role.name):
            if manage_apis:
                await role.apis.add(*manage_apis)
            if sale_menu:
                await role.menus.add(sale_menu)
            if project_menu:
                await role.menus.add(project_menu)


async def ensure_task_permissions():
    task_menu = await Menu.filter(component="/system/task").first()
    task_apis = await Api.filter(Q(path__startswith="/api/v1/task/"))
    if not task_menu and not task_apis:
        return

    for role in await Role.all():
        if not is_admin_role_name(role.name):
            continue
        if task_menu:
            await role.menus.add(task_menu)
        if task_apis:
            await role.apis.add(*task_apis)


async def ensure_virtual_machine_permissions():
    pve_apis = await Api.filter(Q(path__startswith="/api/v1/pve/"))
    if not pve_apis:
        return

    for role in await Role.all():
        if not is_admin_role_name(role.name):
            continue
        await role.apis.add(*pve_apis)


async def ensure_database_backup_task():
    task = await ScheduledTask.filter(name="数据库备份").first()
    values = {
        "task_type": "db_backup",
        "script_path": "scripts/backup_database.py",
        "command": None,
        "schedule_type": "weekly",
        "day_of_week": 6,
        "hour": 2,
        "minute": 0,
        "interval_minutes": None,
        "is_enabled": True,
    }
    if task:
        changed = False
        for field, value in values.items():
            if getattr(task, field) != value:
                setattr(task, field, value)
                changed = True
        if task.next_run_at is None:
            from app.controllers.task import scheduled_task_controller

            task.next_run_at = scheduled_task_controller.calc_next_run_at(task)
            changed = True
        if changed:
            await task.save()
        return

    from app.controllers.task import scheduled_task_controller
    from app.schemas.tasks import ScheduledTaskCreate

    await scheduled_task_controller.create(ScheduledTaskCreate(name="数据库备份", **values))


async def ensure_asset_columns():
    if settings.DB_TYPE == "sqlite":
        conn = Tortoise.get_connection("sqlite")
        columns = [
            ('asset_inventory', 'cost_price_currency', "VARCHAR(10) NOT NULL DEFAULT 'USD'"),
            ('asset_inventory', 'sale_price_currency', "VARCHAR(10) NOT NULL DEFAULT 'USD'"),
            ('asset_inventory_sale_item', 'cost_price_currency', "VARCHAR(10) NOT NULL DEFAULT 'USD'"),
            ('asset_inventory_sale_item', 'unit_price_currency', "VARCHAR(10) NOT NULL DEFAULT 'USD'"),
        ]
        for table, column, column_type in columns:
            try:
                await conn.execute_script(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type};')
            except OperationalError as exc:
                message = str(exc).lower()
                if "duplicate column" not in message and "no such table" not in message:
                    raise
        return

    if settings.DB_TYPE != "postgres":
        return

    conn = Tortoise.get_connection("postgres")
    await conn.execute_script(
        """
        ALTER TABLE IF EXISTS "asset_inventory"
            ADD COLUMN IF NOT EXISTS "subtype" VARCHAR(100),
            ADD COLUMN IF NOT EXISTS "attributes" JSONB NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS "threshold" INT NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS "cost_price" DOUBLE PRECISION NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS "cost_price_currency" VARCHAR(10) NOT NULL DEFAULT 'USD',
            ADD COLUMN IF NOT EXISTS "sale_price" DOUBLE PRECISION NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS "sale_price_currency" VARCHAR(10) NOT NULL DEFAULT 'USD';

        ALTER TABLE IF EXISTS "asset_device"
            ADD COLUMN IF NOT EXISTS "attributes" JSONB NOT NULL DEFAULT '{}';

        ALTER TABLE IF EXISTS "asset_inventory_sale_item"
            ADD COLUMN IF NOT EXISTS "cost_price" DOUBLE PRECISION NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS "cost_price_currency" VARCHAR(10) NOT NULL DEFAULT 'USD',
            ADD COLUMN IF NOT EXISTS "unit_price_currency" VARCHAR(10) NOT NULL DEFAULT 'USD';
        """
    )


async def ensure_bill_columns():
    if settings.DB_TYPE != "postgres":
        return

    conn = Tortoise.get_connection("postgres")
    await conn.execute_script(
        """
        ALTER TABLE IF EXISTS "bill"
            ADD COLUMN IF NOT EXISTS "payment_voucher_url" VARCHAR(255),
            ADD COLUMN IF NOT EXISTS "owner" VARCHAR(100),
            ADD COLUMN IF NOT EXISTS "remark" VARCHAR(500),
            ADD COLUMN IF NOT EXISTS "net_amount" DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS "vat_amount" DOUBLE PRECISION;

        ALTER TABLE IF EXISTS "bill_item"
            ADD COLUMN IF NOT EXISTS "service_id" VARCHAR(100),
            ADD COLUMN IF NOT EXISTS "nrc_amount" DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS "mrc_amount" DOUBLE PRECISION;
        """
    )


async def ensure_project_columns():
    if settings.DB_TYPE == "sqlite":
        conn = Tortoise.get_connection("sqlite")
        columns = [
            ('customer_project_discussion', 'task_id', "BIGINT"),
            ('customer_project_discussion', 'attachment_id', "BIGINT"),
            ('customer_project_attachment', 'task_id', "BIGINT"),
        ]
        for table, column, column_type in columns:
            try:
                await conn.execute_script(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type};')
            except OperationalError as exc:
                message = str(exc).lower()
                if "duplicate column" not in message and "no such table" not in message:
                    raise
        return

    if settings.DB_TYPE != "postgres":
        return

    conn = Tortoise.get_connection("postgres")
    await conn.execute_script(
        """
        ALTER TABLE IF EXISTS "customer_project_discussion"
            ADD COLUMN IF NOT EXISTS "task_id" BIGINT,
            ADD COLUMN IF NOT EXISTS "attachment_id" BIGINT;

        ALTER TABLE IF EXISTS "customer_project_attachment"
            ADD COLUMN IF NOT EXISTS "task_id" BIGINT;
        """
    )


async def ensure_ticket_columns():
    if settings.DB_TYPE == "sqlite":
        conn = Tortoise.get_connection("sqlite")
        try:
            await conn.execute_script('ALTER TABLE "ticket" ADD COLUMN "completion_note" TEXT;')
        except OperationalError as exc:
            message = str(exc).lower()
            if "duplicate column" not in message and "no such table" not in message:
                raise
        await conn.execute_script(
            """
            CREATE TABLE IF NOT EXISTS "ticket_reply" (
                "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                "ticket_id" BIGINT NOT NULL,
                "user_id" BIGINT,
                "parent_id" BIGINT,
                "reply_to_user_id" BIGINT,
                "content" TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS "idx_ticket_reply_ticket_id" ON "ticket_reply" ("ticket_id");
            CREATE INDEX IF NOT EXISTS "idx_ticket_reply_user_id" ON "ticket_reply" ("user_id");
            CREATE INDEX IF NOT EXISTS "idx_ticket_reply_parent_id" ON "ticket_reply" ("parent_id");
            """
        )
        for column in [
            ('parent_id', "BIGINT"),
            ('reply_to_user_id', "BIGINT"),
        ]:
            try:
                await conn.execute_script(f'ALTER TABLE "ticket_reply" ADD COLUMN "{column[0]}" {column[1]};')
            except OperationalError as exc:
                message = str(exc).lower()
                if "duplicate column" not in message and "no such table" not in message:
                    raise
        return

    if settings.DB_TYPE != "postgres":
        return

    conn = Tortoise.get_connection("postgres")
    await conn.execute_script(
        """
        ALTER TABLE IF EXISTS "ticket"
            ADD COLUMN IF NOT EXISTS "completion_note" TEXT;

        CREATE TABLE IF NOT EXISTS "ticket_reply" (
            "id" BIGSERIAL NOT NULL PRIMARY KEY,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "ticket_id" BIGINT NOT NULL,
            "user_id" BIGINT,
            "parent_id" BIGINT,
            "reply_to_user_id" BIGINT,
            "content" TEXT NOT NULL
        );
        ALTER TABLE IF EXISTS "ticket_reply"
            ADD COLUMN IF NOT EXISTS "parent_id" BIGINT,
            ADD COLUMN IF NOT EXISTS "reply_to_user_id" BIGINT;
        CREATE INDEX IF NOT EXISTS "idx_ticket_reply_ticket_id" ON "ticket_reply" ("ticket_id");
        CREATE INDEX IF NOT EXISTS "idx_ticket_reply_user_id" ON "ticket_reply" ("user_id");
        CREATE INDEX IF NOT EXISTS "idx_ticket_reply_parent_id" ON "ticket_reply" ("parent_id");
        """
    )


async def ensure_company_columns():
    if settings.DB_TYPE != "postgres":
        return

    conn = Tortoise.get_connection("postgres")
    await conn.execute_script(
        """
        ALTER TABLE IF EXISTS "company"
            ADD COLUMN IF NOT EXISTS "legal_name" VARCHAR(200),
            ADD COLUMN IF NOT EXISTS "logo_url" VARCHAR(255),
            ADD COLUMN IF NOT EXISTS "bill_email" VARCHAR(100),
            ADD COLUMN IF NOT EXISTS "contact_person" VARCHAR(100);
        """
    )


async def ensure_company_branding():
    companies = [
        ("Catixs Ltd", {"logo_url": "/logos/catixs.png", "legal_name": "Catixs Ltd"}),
        ("77 Telecom Ltd", {"logo_url": "/logos/77-telecom.png", "legal_name": "77 Telecom Ltd"}),
        ("深圳市科特思网络科技有限公司", {"logo_url": "/logos/catixs.png", "legal_name": "深圳市科特思网络科技有限公司"}),
    ]
    for name, values in companies:
        company = await Company.filter(name=name, role=0).first()
        if not company:
            continue
        changed = False
        for field, value in values.items():
            if getattr(company, field, None) != value:
                setattr(company, field, value)
                changed = True
        if changed:
            await company.save()


async def ensure_user_columns():
    if settings.DB_TYPE != "postgres":
        return

    conn = Tortoise.get_connection("postgres")
    await conn.execute_script(
        """
        ALTER TABLE IF EXISTS "user"
            ADD COLUMN IF NOT EXISTS "avatar" VARCHAR(255);
        """
    )


def is_ignorable_asset_migration_error(exc: Exception) -> bool:
    message = str(exc)
    is_duplicate_column = (
        "already exists" in message
        or "已经存在" in message
        or "DuplicateColumnError" in message
    )
    inventory_columns = [
        "item_name",
        "subtype",
        "brand",
        "unit",
        "min_quantity",
        "threshold",
        "cost_price",
        "cost_price_currency",
        "sale_price",
        "sale_price_currency",
        "attributes",
    ]
    return is_duplicate_column and any(column in message for column in inventory_columns)


async def init_db():
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    try:
        await command.init_db(safe=True)
    except FileExistsError:
        pass

    await command.init()
    await ensure_user_columns()
    await ensure_company_columns()
    await ensure_asset_columns()
    await ensure_bill_columns()
    await ensure_project_columns()
    await ensure_ticket_columns()
    await Tortoise.generate_schemas(safe=True)
    if os.getenv("AUTO_DB_MIGRATE", "false").lower() in {"1", "true", "yes", "on"}:
        try:
            await command.migrate()
        except AttributeError:
            logger.warning("unable to retrieve model history from database, model history will be created from scratch")
            shutil.rmtree("migrations")
            await command.init_db(safe=True)

    try:
        await command.upgrade(run_in_transaction=True)
    except OperationalError as exc:
        if not is_ignorable_asset_migration_error(exc):
            raise
        logger.warning("asset compatibility columns already exist, skipped duplicate migration")
    logger.info("database schema checked, missing tables have been created")


async def init_roles():
    roles = await Role.exists()
    if not roles:
        admin_role = await Role.create(
            name="管理员",
            desc="管理员角色",
        )
        user_role = await Role.create(
            name="普通用户",
            desc="普通用户角色",
        )

        # 分配所有API给管理员角色
        all_apis = await Api.all()
        await admin_role.apis.add(*all_apis)
        # 分配所有菜单给管理员和普通用户
        all_menus = await Menu.all()
        await admin_role.menus.add(*all_menus)
        await user_role.menus.add(*all_menus)

        # 为普通用户分配基本API
        basic_apis = await Api.filter(Q(method__in=["GET"]) | Q(tags="基础模块"))
        await user_role.apis.add(*basic_apis)


async def init_companies():
    """初始化签约主体公司（role=0）和银行账户"""
    # 检查是否已存在签约主体公司
    existing = await Company.filter(role=0).first()
    if existing:
        logger.debug("签约主体公司已存在，跳过初始化")
        return
    
    # 1. 77 Telecom Ltd (香港)
    company_77 = await Company.create(
        name="77 Telecom Ltd",
        legal_name="77 Telecom Ltd",
        logo_url="/logos/77-telecom.png",
        code="H",
        role=0,
        country="Hong Kong",
        address="RM B, 10/F, LEE MAY BUILDING, 788-790 NATHAN ROAD, MONGKOK, KOWLOON, HONG KONG",
        noc_email="billing@77tel.com",
        noc_phone="+44 020 4600 7777",
        registration_no="78687939",
        company_email="billing@77tel.com",
        company_phone="+44 020 4600 7777",
        status=True,
    )
    
    # 创建77 Telecom的银行账户
    bank_dbs_hk = await Bank.create(
        name="DBS Bank (Hong Kong) Limited",
        country="Hong Kong",
        swift_code="DHBKHKHH",
        bank_code="016",
        branch_code="478",
    )
    await BankAccount.create(
        company=company_77,
        bank=bank_dbs_hk,
        account_name="77 Telecom Limited",
        account_number="7950193007",
        currency="USD",
    )
    
    # 2. 深圳市科特思网络科技有限公司 (中国)
    company_cn = await Company.create(
        name="深圳市科特思网络科技有限公司",
        legal_name="深圳市科特思网络科技有限公司",
        logo_url="/logos/catixs.png",
        code="C",
        role=0,
        country="China",
        address="深圳市南山区粤海街道科技园社区科发路222号康泰集团大厦3202",
        noc_email="",
        noc_phone="",
        tax_no="91440300MAEAJ4CP7U",
        registration_no="91440300MAEAJ4CP7U",
        company_email="fapiao@cn.catixs.com",
        company_phone="+0755-86638006",
        status=True,
    )
    
    # 创建中国银行账户
    bank_boc_sz = await Bank.create(
        name="中国银行深圳石岩支行",
        country="China",
    )
    await BankAccount.create(
        company=company_cn,
        bank=bank_boc_sz,
        account_name="深圳市科特思网络科技有限公司",
        account_number="758879546570",
        currency="CNY",
    )
    
    # 3. Catixs Ltd (英国)
    company_uk = await Company.create(
        name="Catixs Ltd",
        legal_name="Catixs Ltd",
        logo_url="/logos/catixs.png",
        code="U",
        role=0,
        country="United Kingdom",
        address="6 Watergate Walk, London, E14 9XH, United Kingdom",
        noc_email="",
        noc_phone="",
        registration_no="13745695",
        company_email="billing@catixs.com",
        company_phone="+44 020 4600 7777",
        status=True,
    )
    
    # 创建Catixs Ltd的银行账户
    # GBP账户
    bank_mod = await Bank.create(
        name="Airwallex",
        country="United Kingdom",
        swift_code="MODRGB21",
        bank_address="58 Wood Ln",
    )
    await BankAccount.create(
        company=company_uk,
        bank=bank_mod,
        sort_code="040085",
        account_name="Catixs Ltd",
        account_number="06520111",
        iban="GB54MODR04008506520111",
        currency="GBP",
    )
    
    # HKD账户
    bank_sc_hk = await Bank.create(
        name="Standard Chartered Bank (Hong Kong) Ltd",
        country="Hong Kong",
        swift_code="SCBLHKHH",
        bank_code="003",
        branch_code="474",
    )
    await BankAccount.create(
        company=company_uk,
        bank=bank_sc_hk,
        account_name="Catixs Ltd",
        account_number="47412321804",
        currency="HKD",
    )
    
    # USD账户
    await BankAccount.create(
        company=company_uk,
        bank=bank_sc_hk,
        account_name="Catixs Ltd",
        account_number="47412485947",
        currency="USD",
    )
    
    logger.info("签约主体公司和银行账户初始化完成")


async def init_data():
    await init_db()
    await init_superuser()
    await init_menus()
    await init_apis()
    await ensure_business_api_permissions()
    await init_roles()
    await ensure_task_permissions()
    await ensure_virtual_machine_permissions()
    await ensure_database_backup_task()
    await init_companies()
    await ensure_company_branding()
