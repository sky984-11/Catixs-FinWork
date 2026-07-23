import os
import typing
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    VERSION: str = "0.1.0"
    APP_TITLE: str = "Catixs FinWork"
    PROJECT_NAME: str = "Catixs FinWork"
    APP_DESCRIPTION: str = "Description"

    CORS_ORIGINS: typing.List = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: typing.List = ["*"]
    CORS_ALLOW_HEADERS: typing.List = ["*"]

    DEBUG: Optional[bool] = True

    PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    BASE_DIR: str = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir))
    LOGS_ROOT: str = os.path.join(BASE_DIR, "app/logs")
    SECRET_KEY: str = "3488a63e1765035d386f05409663f55c83bfae3b3c61a932744b20ad14244dcf"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DB_TYPE: str = "postgres"
    SQLITE_DB_PATH: str = os.path.join(BASE_DIR, "db.sqlite3")
    POSTGRES_DSN: Optional[str] = None
    POSTGRES_HOST: str = "10.4.10.11"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "Catixs@3202"
    POSTGRES_DATABASE: str = "finwork"
    POSTGRES_SSL: bool = False

    PDM_API_URL: str = "https://10.4.10.51:8443"
    PDM_TOKEN_ID: str = "root@pam!Finwork"
    PDM_TOKEN_SECRET: str = "86973c29-6466-4fba-bc97-b5942f235007"
    PDM_API_TOKEN: str = ""
    PDM_REMOTES: str = ""
    PDM_TIMEOUT: float = 15
    PVE_CREATE_SSH_USER: str = "root"
    PVE_CREATE_SSH_PASSWORD: str = "Catixs@3202"
    PVE_CREATE_SSH_TIMEOUT: float = 10
    PVE_GUEST_AGENT_IP_TIMEOUT: float = 2
    PVE_GUEST_AGENT_IP_CACHE_TTL: float = 60
    ZABBIX_URL: str = ""
    ZABBIX_TOKEN: str = ""
    ZABBIX_PVE_REFERENCE_HOSTID: str = "10777"
    NETBOX_URL: str = "https://10.4.10.100"
    NETBOX_TOKEN: str = ""
    GRAFANA_URL: str = "http://10.4.10.11:3000"
    GRAFANA_API_TOKEN: str = "glsa_sPkzKo8z4RCQX30C3kgr3iv3lJoacD19_e082c65a"
    DATACENTER_PARTS_API_URL: str = "https://datacenter-parts-management.catixs.workers.dev"
    DATACENTER_PARTS_API_TOKEN: str = ""
    DATACENTER_PARTS_API_USERNAME: str = "admin"
    DATACENTER_PARTS_API_PASSWORD: str = "Catixs@3202"
    DATACENTER_PARTS_API_TIMEOUT: float = 20
    PROJECT_DAILY_SUMMARY_HOUR: int = 8
    PROJECT_DAILY_SUMMARY_MINUTE: int = 30
    PROJECT_DAILY_SUMMARY_OWNER_FILTER: str = ""
    PROJECT_FEISHU_USER_MAP: str = ""
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    WEB_BASE_URL: str = ""
    WEB_DEV_BASE_URL: str = "http://127.0.0.1:3100"
    WEB_DOMAIN: str = "finwork.catixs.net"

    TORTOISE_ORM: dict[str, Any] = {}
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() not in ("false", "0", "no", "off", "release")
        return bool(v)

    @field_validator("DB_TYPE", mode="before")
    @classmethod
    def normalize_db_type(cls, v):
        db_type = (v or "sqlite").lower()
        aliases = {
            "postgresql": "postgres",
            "pg": "postgres",
        }
        db_type = aliases.get(db_type, db_type)
        if db_type not in {"sqlite", "postgres"}:
            raise ValueError("DB_TYPE must be either 'sqlite' or 'postgres'")
        return db_type

    def model_post_init(self, __context):
        self.TORTOISE_ORM = self.build_tortoise_orm()

    def get_web_base_url(self) -> str:
        explicit_url = str(self.WEB_BASE_URL or "").strip()
        if explicit_url:
            return explicit_url.rstrip("/")
        from app.core.runtime_context import get_last_frontend_origin, get_last_request_origin

        request_origin = get_last_request_origin()
        if request_origin:
            return request_origin.rstrip("/")
        frontend_origin = get_last_frontend_origin()
        if frontend_origin:
            return frontend_origin.rstrip("/")
        if self.DEBUG:
            return str(self.WEB_DEV_BASE_URL or "http://127.0.0.1:3100").strip().rstrip("/")
        domain = str(self.WEB_DOMAIN or "").strip().rstrip("/")
        if not domain:
            return ""
        if domain.startswith(("http://", "https://")):
            return domain
        return f"https://{domain}"

    def build_tortoise_orm(self, default_connection: str | None = None) -> dict[str, Any]:
        connection = default_connection or self.DB_TYPE
        if connection == "postgresql":
            connection = "postgres"

        if connection not in {"sqlite", "postgres"}:
            raise ValueError("default_connection must be either 'sqlite' or 'postgres'")

        if connection == "sqlite":
            db_connection: str | dict[str, Any] = {
                "engine": "tortoise.backends.sqlite",
                "credentials": {"file_path": self.SQLITE_DB_PATH},
            }
        elif self.POSTGRES_DSN:
            db_connection = self.POSTGRES_DSN
        else:
            credentials: dict[str, Any] = {
                "host": self.POSTGRES_HOST,
                "port": self.POSTGRES_PORT,
                "user": self.POSTGRES_USER,
                "password": self.POSTGRES_PASSWORD,
                "database": self.POSTGRES_DATABASE,
            }
            if self.POSTGRES_SSL:
                credentials["ssl"] = True
            db_connection = {
                "engine": "tortoise.backends.asyncpg",
                "credentials": credentials,
            }

        return {
            "connections": {connection: db_connection},
            "apps": {
                "models": {
                    "models": ["app.models", "aerich.models"],
                    "default_connection": connection,
                },
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }


settings = Settings()
