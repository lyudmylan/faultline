"""Shared fixtures. FAULTLINE_LOG_DIR must be set before faultline.app is imported."""

import json
import os
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / ".logs"
os.environ["FAULTLINE_LOG_DIR"] = str(LOG_DIR)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from faultline import chaos, shop, simulate  # noqa: E402
from faultline.app import app  # noqa: E402

LOG_FILE = LOG_DIR / "app.log"


@pytest.fixture(autouse=True)
def reset_state():
    shop.reset()
    chaos.state.enabled = False
    chaos.state.failure_rate = 0.3
    chaos.state.error_status = 503
    chaos.state.extra_latency_ms = 0
    simulate._ballast.clear()
    yield
    chaos.state.enabled = False
    simulate._ballast.clear()


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class LogCapture:
    """Reads only the log lines written after the fixture was created."""

    def __init__(self, path: Path):
        self.path = path
        self.offset = path.stat().st_size

    def new_lines(self) -> list[dict]:
        with open(self.path) as handle:
            handle.seek(self.offset)
            return [json.loads(line) for line in handle.read().splitlines() if line.strip()]


@pytest.fixture
def log_capture() -> LogCapture:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch()
    return LogCapture(LOG_FILE)


def metric_value(metrics_text: str, name: str, labels: str = "") -> float | None:
    """Extract a single metric sample from Prometheus text exposition."""
    target = f"{name}{{{labels}}}" if labels else name
    for line in metrics_text.splitlines():
        if line.startswith("#"):
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) == 2 and parts[0] == target:
            return float(parts[1])
    return None
