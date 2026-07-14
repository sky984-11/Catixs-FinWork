from fastapi import APIRouter

from app.core.dependency import DependPermission

from .apis import api_docs_router, apis_router
from .akvorado import router as akvorado_router
from .assets import assets_router
from .auditlog import auditlog_router
from .banks import banks_router
from .bank_accounts import bank_accounts_router
from .base import base_router
from .bills import bills_router
from .companies import companies_router
from .depts import depts_router
from .finance_quotes import finance_quotes_router
from .dashboard import router as dashboard_router
from .menus import menus_router
from .netbox import netbox_router
from .projects import projects_router
from .pve import grafana_router as pve_grafana_router
from .pve import pve_router
from .pve.novnc import ws_router as pve_novnc_ws_router
from .roles import roles_router
from .syslog import syslog_router
from .tasks import tasks_router
from .users import users_router
from .vendors import vendors_router
from .tickets import ticket_router

v1_router = APIRouter()

v1_router.include_router(base_router, prefix="/base")
v1_router.include_router(users_router, prefix="/user", dependencies=[DependPermission])
v1_router.include_router(roles_router, prefix="/role", dependencies=[DependPermission])
v1_router.include_router(menus_router, prefix="/menu", dependencies=[DependPermission])
v1_router.include_router(api_docs_router, prefix="/api")
v1_router.include_router(apis_router, prefix="/api", dependencies=[DependPermission])
v1_router.include_router(depts_router, prefix="/dept", dependencies=[DependPermission])
v1_router.include_router(auditlog_router, prefix="/auditlog", dependencies=[DependPermission])
v1_router.include_router(tasks_router, prefix="/task", dependencies=[DependPermission])
v1_router.include_router(vendors_router, prefix="/vendor", dependencies=[DependPermission])
v1_router.include_router(dashboard_router, prefix="/ticket", tags=["仪表盘模块"])
v1_router.include_router(ticket_router, prefix="/ticket", tags=["工单模块"])
v1_router.include_router(assets_router, prefix="/asset", dependencies=[DependPermission], tags=["资产管理模块"])
v1_router.include_router(syslog_router, prefix="/syslog", dependencies=[DependPermission], tags=["Syslog日志管理模块"])
v1_router.include_router(netbox_router, prefix="/netbox", dependencies=[DependPermission], tags=["NetBox IPAM"])
v1_router.include_router(pve_novnc_ws_router, prefix="/pve", tags=["PVE noVNC模块"])
v1_router.include_router(pve_router, prefix="/pve", dependencies=[DependPermission], tags=["PVE Datacenter模块"])
v1_router.include_router(banks_router, prefix="/bank", dependencies=[DependPermission])
v1_router.include_router(pve_grafana_router, prefix="/pve", tags=["PVE Grafana"])
v1_router.include_router(bank_accounts_router, prefix="/bank_account", dependencies=[DependPermission])
v1_router.include_router(bills_router, prefix="/bill", dependencies=[DependPermission])
v1_router.include_router(finance_quotes_router, prefix="/finance/quote", dependencies=[DependPermission])
v1_router.include_router(companies_router, prefix="/company", dependencies=[DependPermission])
v1_router.include_router(projects_router, prefix="/project", dependencies=[DependPermission])
v1_router.include_router(akvorado_router, prefix="/akvorado", tags=["Akvorado"])
