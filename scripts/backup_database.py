import os
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path

from app.settings.config import settings

REMOTE_BACKUP_HOST = os.getenv("BACKUP_REMOTE_HOST", "10.4.10.11")
REMOTE_BACKUP_USER = os.getenv("BACKUP_REMOTE_USER", "root")
REMOTE_BACKUP_DIR = os.getenv("BACKUP_REMOTE_DIR", "/log/backup/finwork")


def is_local_host(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        local_ips = set(socket.gethostbyname_ex(socket.gethostname())[2])
        host_ips = set(socket.gethostbyname_ex(host)[2])
        return bool(local_ips & host_ips)
    except socket.gaierror:
        return False


def remote_target() -> str:
    host = f"{REMOTE_BACKUP_USER}@{REMOTE_BACKUP_HOST}" if REMOTE_BACKUP_USER else REMOTE_BACKUP_HOST
    return f"{host}:{REMOTE_BACKUP_DIR.rstrip('/')}/"


def backup_sqlite(output_dir: Path) -> Path:
    source = Path(settings.SQLITE_DB_PATH)
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")

    target = output_dir / f"{source.stem}_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
    shutil.copy2(source, target)
    return target


def backup_postgres(output_dir: Path) -> Path:
    target = output_dir / f"{settings.POSTGRES_DATABASE}_{datetime.now():%Y%m%d_%H%M%S}.dump"
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("pg_dump not found. Please install PostgreSQL client tools on the server.")

    command = [
        pg_dump,
        "--host",
        settings.POSTGRES_HOST,
        "--port",
        str(settings.POSTGRES_PORT),
        "--username",
        settings.POSTGRES_USER,
        "--dbname",
        settings.POSTGRES_DATABASE,
        "--format",
        "custom",
        "--file",
        str(target),
    ]
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.POSTGRES_PASSWORD
    subprocess.run(command, check=True, env=env)
    return target


def upload_to_remote(local_file: Path) -> None:
    ssh = shutil.which("ssh")
    scp = shutil.which("scp")
    if not ssh or not scp:
        raise RuntimeError("ssh/scp not found. Please install OpenSSH client on the server.")

    host = f"{REMOTE_BACKUP_USER}@{REMOTE_BACKUP_HOST}" if REMOTE_BACKUP_USER else REMOTE_BACKUP_HOST
    subprocess.run([ssh, host, "mkdir", "-p", REMOTE_BACKUP_DIR], check=True)
    subprocess.run([scp, str(local_file), remote_target()], check=True)


def main() -> None:
    output_dir = Path(REMOTE_BACKUP_DIR) if is_local_host(REMOTE_BACKUP_HOST) else Path(settings.BASE_DIR) / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)

    if settings.DB_TYPE == "sqlite":
        target = backup_sqlite(output_dir)
    elif settings.DB_TYPE == "postgres":
        target = backup_postgres(output_dir)
    else:
        raise ValueError(f"Unsupported DB_TYPE: {settings.DB_TYPE}")

    if is_local_host(REMOTE_BACKUP_HOST):
        print(f"Database backup created: {target}")
        return

    upload_to_remote(target)
    target.unlink(missing_ok=True)
    print(f"Database backup uploaded: {remote_target()}{target.name}")


if __name__ == "__main__":
    main()
