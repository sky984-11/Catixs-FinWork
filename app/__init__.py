import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tortoise import Tortoise

from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    init_data,
    make_middlewares,
    register_exceptions,
    register_routers,
)

try:
    from app.settings.config import settings
except ImportError:
    raise SettingNotFound("Can not import settings")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(
        "Starting backend with "
        f"DB_TYPE={settings.DB_TYPE}, "
        f"POSTGRES_HOST={settings.POSTGRES_HOST}, "
        f"POSTGRES_PORT={settings.POSTGRES_PORT}, "
        f"POSTGRES_DATABASE={settings.POSTGRES_DATABASE}",
        flush=True,
    )
    await init_data()
    yield
    await Tortoise.close_connections()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        openapi_url="/openapi.json",
        middleware=make_middlewares(),
        lifespan=lifespan,
    )
    register_exceptions(app)
    register_routers(app, prefix="/api")

    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    if os.path.exists(uploads_dir):
        app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    web_dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dist")
    assets_dir = os.path.join(web_dist_dir, "assets")
    index_file = os.path.join(web_dist_dir, "index.html")

    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    if os.path.exists(index_file):
        @app.get("/")
        async def spa_index():
            return FileResponse(index_file)

        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            file_path = os.path.abspath(os.path.join(web_dist_dir, path))
            web_dist_root = os.path.abspath(web_dist_dir)
            if file_path.startswith(web_dist_root) and os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(index_file)
    
    return app


app = create_app()
