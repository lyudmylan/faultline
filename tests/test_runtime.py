"""Configuration defaults and entry points (SPEC 3)."""

import json

import uvicorn

from faultline import config, export_openapi
from faultline.__main__ import main as run_main


def test_config_defaults(monkeypatch):
    for variable in ("HOST", "PORT", "FAULTLINE_LOG_DIR"):
        monkeypatch.delenv(variable, raising=False)
    assert config.host() == "127.0.0.1"
    assert config.port() == 8000
    assert config.log_dir() == "./logs"


def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("FAULTLINE_LOG_DIR", "/var/log/faultline")
    assert (config.host(), config.port(), config.log_dir()) == (
        "0.0.0.0",
        9999,
        "/var/log/faultline",
    )


def test_main_runs_uvicorn_with_configured_bind(monkeypatch):
    captured = {}

    def fake_run(app_ref, **kwargs):
        captured["app"] = app_ref
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8123")
    run_main()
    assert captured["app"] == "faultline.app:app"
    assert (captured["host"], captured["port"]) == ("127.0.0.1", 8123)
    assert captured["access_log"] is False


def test_export_openapi_writes_schema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    export_openapi.main()
    written = json.loads((tmp_path / "docs" / "openapi.json").read_text())
    assert written["info"]["title"] == "faultline"
    assert "/products" in written["paths"]
