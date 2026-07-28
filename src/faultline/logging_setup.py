"""Structured JSON logging: one object per line, to stdout and a rotating file."""

import contextvars
import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path

from faultline import config

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

# Attributes present on every LogRecord; anything else was passed via `extra=`.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[
                :-3
            ]
            + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_var.get()
        if request_id is not None:
            line["request_id"] = request_id
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and key != "request_id":
                line[key] = value
        if record.exc_info:
            line["stack"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


_configured = False


def setup_logging() -> None:
    """Configure the root logger once per process."""
    global _configured
    if _configured:
        return
    _configured = True

    log_path = Path(config.log_dir())
    log_path.mkdir(parents=True, exist_ok=True)

    formatter = JsonFormatter()
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    rotating = logging.handlers.RotatingFileHandler(
        log_path / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    rotating.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [stream, rotating]
