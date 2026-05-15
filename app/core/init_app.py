import shutil

from aerich import Command
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
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
            methods=["GET", "POST", "PUT", "DELETE"],
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
        ticket_menu = await Menu.create(
            menu_type=MenuType.MENU,
            name="工单管理",
            path="/ticket",
            order=2,
            parent_id=0,
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
            parent_id=0,
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
            parent_id=0,
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
            parent_id=0,
            icon="mdi:file-document-edit-outline",
            is_hidden=True,
            component="/ticket/edit",
            keepalive=False,
            redirect="",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="供应商管理",
            path="/vendor",
            order=2,
            parent_id=0,
            icon="material-symbols:assured-workload-outline",
            is_hidden=False,
            component="/vendor",
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
    await ensure_ticket_route_menus()


async def ensure_ticket_route_menus():
    ticket_menu = await Menu.filter(path="/ticket").first()
    if not ticket_menu:
        await Menu.create(
            menu_type=MenuType.MENU,
            name="工单管理",
            path="/ticket",
            order=2,
            parent_id=0,
            icon="material-symbols:assignment-globe",
            is_hidden=False,
            component="/ticket",
            keepalive=False,
            redirect="",
        )

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
                parent_id=0,
                icon=menu_data["icon"],
                is_hidden=True,
                component=menu_data["component"],
                keepalive=False,
                redirect="",
            )
        elif route_menu.path != menu_data["path"] or route_menu.parent_id != 0 or not route_menu.is_hidden:
            route_menu.path = menu_data["path"]
            route_menu.parent_id = 0
            route_menu.is_hidden = True
            await route_menu.save()


async def init_apis():
    apis = await api_controller.model.exists()
    if not apis:
        await api_controller.refresh_api()


async def init_db():
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    try:
        await command.init_db(safe=True)
    except FileExistsError:
        pass

    await command.init()
    try:
        await command.migrate()
    except AttributeError:
        logger.warning("unable to retrieve model history from database, model history will be created from scratch")
        shutil.rmtree("migrations")
        await command.init_db(safe=True)

    await command.upgrade(run_in_transaction=True)


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
    await init_roles()
    await init_companies()
