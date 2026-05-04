from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_UID = 10001
DEFAULT_GID = 10001


def main() -> None:
    data_dir = Path("/data")
    command = sys.argv[1:] or ["serve"]

    if os.geteuid() == 0:
        uid, gid = prepare_data_dir(data_dir)
        drop_privileges(uid, gid)
    else:
        data_dir.mkdir(parents=True, exist_ok=True)

    if command == ["serve"]:
        command = uvicorn_command()

    os.execvp(command[0], command)


def prepare_data_dir(data_dir: Path) -> tuple[int, int]:
    data_dir.mkdir(parents=True, exist_ok=True)
    uid, gid = runtime_identity_for(data_dir)
    try:
        chown_tree(data_dir, uid, gid)
    except OSError as exc:
        print(
            f"warning: could not adjust ownership for {data_dir}: {exc}",
            file=sys.stderr,
        )
        return os.geteuid(), os.getegid()
    return uid, gid


def runtime_identity_for(data_dir: Path) -> tuple[int, int]:
    stat_result = data_dir.stat()
    if stat_result.st_uid != 0:
        return stat_result.st_uid, stat_result.st_gid
    return DEFAULT_UID, DEFAULT_GID


def chown_tree(path: Path, uid: int, gid: int) -> None:
    chown_path(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for name in dirs:
            chown_path(Path(root) / name, uid, gid)
        for name in files:
            chown_path(Path(root) / name, uid, gid)


def chown_path(path: Path, uid: int, gid: int) -> None:
    os.chown(path, uid, gid, follow_symlinks=False)


def drop_privileges(uid: int, gid: int) -> None:
    try:
        os.setgroups([])
    except OSError:
        pass
    os.setgid(gid)
    os.setuid(uid)
    os.environ["HOME"] = "/tmp"


def uvicorn_command() -> list[str]:
    return [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        os.getenv("WARPARTY_PORT", "8080"),
        "--proxy-headers",
        "--forwarded-allow-ips",
        os.getenv("WARPARTY_FORWARDED_ALLOW_IPS", "*"),
        "--log-level",
        os.getenv("WARPARTY_LOG_LEVEL", "info"),
    ]


if __name__ == "__main__":
    main()
