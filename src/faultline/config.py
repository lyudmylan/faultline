"""Environment-driven configuration (read at call time so tests can override)."""

import os


def host() -> str:
    return os.environ.get("HOST", "127.0.0.1")


def port() -> int:
    return int(os.environ.get("PORT", "8000"))


def log_dir() -> str:
    return os.environ.get("FAULTLINE_LOG_DIR", "./logs")
