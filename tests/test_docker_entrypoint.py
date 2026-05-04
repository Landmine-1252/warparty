from __future__ import annotations

import os

import scripts.docker_entrypoint as entrypoint
from scripts.docker_entrypoint import prepare_data_dir, runtime_identity_for, uvicorn_command


def test_runtime_identity_uses_existing_data_dir_owner(tmp_path) -> None:
    uid, gid = runtime_identity_for(tmp_path)

    assert uid == tmp_path.stat().st_uid
    assert gid == tmp_path.stat().st_gid


def test_prepare_data_dir_keeps_current_identity_when_chown_fails(monkeypatch, tmp_path) -> None:
    def fail_chown(path, uid, gid) -> None:
        raise OSError("no chown")

    monkeypatch.setattr(entrypoint, "runtime_identity_for", lambda path: (10001, 10001))
    monkeypatch.setattr(entrypoint, "chown_tree", fail_chown)
    monkeypatch.setattr(entrypoint.os, "geteuid", lambda: 0)
    monkeypatch.setattr(entrypoint.os, "getegid", lambda: 0)

    assert prepare_data_dir(tmp_path) == (0, 0)


def test_uvicorn_command_uses_runtime_environment(monkeypatch) -> None:
    monkeypatch.setenv("WARPARTY_PORT", "5150")
    monkeypatch.setenv("WARPARTY_FORWARDED_ALLOW_IPS", "127.0.0.1")
    monkeypatch.setenv("WARPARTY_LOG_LEVEL", "debug")

    command = uvicorn_command()

    assert command[:2] == ["uvicorn", "app.main:app"]
    assert command[command.index("--port") + 1] == "5150"
    assert command[command.index("--forwarded-allow-ips") + 1] == "127.0.0.1"
    assert command[command.index("--log-level") + 1] == "debug"


def test_uvicorn_command_defaults_are_container_friendly(monkeypatch) -> None:
    monkeypatch.delenv("WARPARTY_PORT", raising=False)
    monkeypatch.delenv("WARPARTY_FORWARDED_ALLOW_IPS", raising=False)
    monkeypatch.delenv("WARPARTY_LOG_LEVEL", raising=False)

    command = uvicorn_command()

    assert command[command.index("--host") + 1] == "0.0.0.0"
    assert command[command.index("--port") + 1] == "8080"
    assert command[command.index("--forwarded-allow-ips") + 1] == "*"
    assert command[command.index("--log-level") + 1] == "info"
    assert os.getenv("WARPARTY_PORT") is None
