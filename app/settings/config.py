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

    DB_TYPE: str = "sqlite"
    SQLITE_DB_PATH: str = os.path.join(BASE_DIR, "db.sqlite3")
    POSTGRES_DSN: Optional[str] = None
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DATABASE: str = "catixs_finwork"
    POSTGRES_SSL: bool = False

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

    def build_tortoise_orm(self, default_connection: str | None = None) -> dict[str, Any]:
        connection = default_connection or self.DB_TYPE
        if connection == "postgresql":
            connection = "postgres"

        if connection not in {"sqlite", "postgres"}:
            raise ValueError("default_connection must be either 'sqlite' or 'postgres'")

        postgres_connection: str | dict[str, Any]
        if self.POSTGRES_DSN:
            postgres_connection = self.POSTGRES_DSN
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
            postgres_connection = {
                "engine": "tortoise.backends.asyncpg",
                "credentials": credentials,
            }

        return {
            "connections": {
                "sqlite": {
                    "engine": "tortoise.backends.sqlite",
                    "credentials": {"file_path": self.SQLITE_DB_PATH},
                },
                "postgres": postgres_connection,
            },
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
