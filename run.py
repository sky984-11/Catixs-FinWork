import os

import uvicorn
from uvicorn.config import LOGGING_CONFIG

def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    # 修改默认日志配置
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    port = int(os.getenv("PORT", "9999"))
    reload = parse_bool(os.getenv("UVICORN_RELOAD"), default=True)

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        reload_excludes=["migrations/*", "**/__pycache__/*"],
        log_config=LOGGING_CONFIG,
    )
