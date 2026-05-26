import os
import shutil
import shlex
import socket
import subprocess
from datetime import datetime
from pathlib import Path

from app.settings.config import settings

REMOTE_BACKUP_HOST = os.getenv("BACKUP_REMOTE_HOST", "10.4.10.11")
REMOTE_BACKUP_USER = os.getenv("BACKUP_REMOTE_USER", "root")
REMOTE_BACKUP_DIR = os.getenv("BACKUP_REMOTE_DIR", "/log/backup/finwork")
REMOTE_PG_HOST = os.getenv("BACKUP_REMOTE_PG_HOST", "10.4.10.11")
SSH_CONNECT_TIMEOUT = int(os.getenv("BACKUP_SSH_CONNECT_TIMEOUT", "15"))
SSH_COMMAND_TIMEOUT = int(os.getenv("BACKUP_SSH_COMMAND_TIMEOUT", "300"))


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


def ssh_host() -> str:
    return f"{REMOTE_BACKUP_USER}@{REMOTE_BACKUP_HOST}" if REMOTE_BACKUP_USER else REMOTE_BACKUP_HOST


def ssh_options() -> list[str]:
    return [
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]


def run_checked(command: list[str], timeout: int | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        check=False,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
    )
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Command failed ({result.returncode}): {shlex.join(command)}\n{output}")
    return result


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
        raise FileNotFoundError("pg_dump not found")

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
    run_checked(command, env=env)
    return target


def backup_postgres_on_remote() -> str:
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("pg_dump not found locally and ssh is not available.")

    host = ssh_host()
    remote_dir = REMOTE_BACKUP_DIR.rstrip("/")
    remote_file = f"{settings.POSTGRES_DATABASE}_{datetime.now():%Y%m%d_%H%M%S}.dump"
    remote_path = f"{remote_dir}/{remote_file}"
    remote_command = " ".join(
        [
            "mkdir",
            "-p",
            shlex.quote(remote_dir),
            "&&",
            f"PGPASSWORD={shlex.quote(settings.POSTGRES_PASSWORD)}",
            "pg_dump",
            "--host",
            shlex.quote(REMOTE_PG_HOST),
            "--port",
            shlex.quote(str(settings.POSTGRES_PORT)),
            "--username",
            shlex.quote(settings.POSTGRES_USER),
            "--dbname",
            shlex.quote(settings.POSTGRES_DATABASE),
            "--format",
            "custom",
            "--file",
            shlex.quote(remote_path),
        ]
    )
    run_checked([ssh, *ssh_options(), host, remote_command], timeout=SSH_COMMAND_TIMEOUT)
    return f"{host}:{remote_path}"


def upload_to_remote(local_file: Path) -> None:
    ssh = shutil.which("ssh")
    scp = shutil.which("scp")
    if not ssh or not scp:
        raise RuntimeError("ssh/scp not found. Please install OpenSSH client on the server.")

    host = ssh_host()
    run_checked([ssh, *ssh_options(), host, "mkdir", "-p", REMOTE_BACKUP_DIR], timeout=SSH_CONNECT_TIMEOUT)
    run_checked([scp, *ssh_options(), str(local_file), remote_target()], timeout=SSH_COMMAND_TIMEOUT)


def main() -> None:
    output_dir = Path(REMOTE_BACKUP_DIR) if is_local_host(REMOTE_BACKUP_HOST) else Path(settings.BASE_DIR) / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)

    if settings.DB_TYPE == "sqlite":
        target = backup_sqlite(output_dir)
    elif settings.DB_TYPE == "postgres":
        try:
            target = backup_postgres(output_dir)
        except FileNotFoundError:
            remote_path = backup_postgres_on_remote()
            print(f"Database backup created on remote: {remote_path}")
            return
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
