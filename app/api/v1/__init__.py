from fastapi import APIRouter

from app.core.dependency import DependPermission

from .apis import apis_router
from .assets import assets_router
from .auditlog import auditlog_router
from .banks import banks_router
from .bank_accounts import bank_accounts_router
from .base import base_router
from .bills import bills_router
from .companies import companies_router
from .depts import depts_router
from .dashboard import router as dashboard_router
from .menus import menus_router
from .roles import roles_router
from .tasks import tasks_router
from .users import users_router
from .vendors import vendors_router
from .tickets import ticket_router

v1_router = APIRouter()

v1_router.include_router(base_router, prefix="/base")
v1_router.include_router(users_router, prefix="/user", dependencies=[DependPermission])
v1_router.include_router(roles_router, prefix="/role", dependencies=[DependPermission])
v1_router.include_router(menus_router, prefix="/menu", dependencies=[DependPermission])
v1_router.include_router(apis_router, prefix="/api", dependencies=[DependPermission])
v1_router.include_router(depts_router, prefix="/dept", dependencies=[DependPermission])
v1_router.include_router(auditlog_router, prefix="/auditlog", dependencies=[DependPermission])
v1_router.include_router(tasks_router, prefix="/task", dependencies=[DependPermission])
v1_router.include_router(vendors_router, prefix="/vendor", dependencies=[DependPermission])
v1_router.include_router(dashboard_router, prefix="/ticket", tags=["仪表盘模块"])
v1_router.include_router(ticket_router, prefix="/ticket", tags=["工单模块"])
v1_router.include_router(assets_router, prefix="/asset", dependencies=[DependPermission], tags=["资产管理模块"])
v1_router.include_router(banks_router, prefix="/bank", dependencies=[DependPermission])
v1_router.include_router(bank_accounts_router, prefix="/bank_account", dependencies=[DependPermission])
v1_router.include_router(bills_router, prefix="/bill", dependencies=[DependPermission])
v1_router.include_router(companies_router, prefix="/company", dependencies=[DependPermission])
