"""Tests that need a real server process: crash (I7) and hang (client-timeout shape)."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(log_dir: Path) -> tuple[subprocess.Popen, str]:
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "faultline"],
        env=os.environ
        | {"HOST": "127.0.0.1", "PORT": str(port), "FAULTLINE_LOG_DIR": str(log_dir)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=1).status_code == 200:
                return process, base_url
        except httpx.HTTPError:
            time.sleep(0.1)
        if process.poll() is not None:
            break
    process.kill()
    raise RuntimeError("server failed to become healthy")


def test_i7_crash_logs_critical_then_exits_1(tmp_path):
    process, base_url = _start_server(tmp_path)
    try:
        response = httpx.get(f"{base_url}/simulate/crash?delay=0.2", timeout=5)
        assert response.status_code == 200
        assert response.json()["crashing_in_seconds"] == 0.2
        assert process.wait(timeout=10) == 1

        log_lines = [
            json.loads(line)
            for line in (tmp_path / "app.log").read_text().splitlines()
            if line.strip()
        ]
        crash_lines = [line for line in log_lines if line.get("event") == "crash"]
        assert len(crash_lines) == 1
        assert crash_lines[0]["level"] == "CRITICAL"
    finally:
        if process.poll() is None:
            process.kill()


def test_hang_never_responds_and_leaves_service_alive(tmp_path):
    process, base_url = _start_server(tmp_path)
    try:
        with pytest.raises(httpx.ReadTimeout):
            httpx.get(f"{base_url}/simulate/hang", timeout=1.5)
        # The held connection must not wedge the rest of the service.
        assert httpx.get(f"{base_url}/health", timeout=5).status_code == 200
        log_text = (tmp_path / "app.log").read_text()
        assert '"event": "hang"' in log_text
    finally:
        process.kill()
        process.wait(timeout=10)


def test_startup_event_logged_and_health_green(tmp_path):
    process, base_url = _start_server(tmp_path)
    try:
        log_lines = [
            json.loads(line)
            for line in (tmp_path / "app.log").read_text().splitlines()
            if line.strip()
        ]
        assert any(line.get("event") == "startup" for line in log_lines)
    finally:
        process.kill()
        process.wait(timeout=10)
