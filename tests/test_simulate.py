"""Simulation API behavior (SPEC 4.2). Crash and hang need a real server: test_live_server.py."""

import time

import pytest

from faultline import simulate


def test_status_echoes_requested_code(client):
    for code in (200, 301, 404, 503, 599):
        response = client.get(f"/simulate/status/{code}")
        assert response.status_code == code


def test_status_204_and_304_have_no_body(client):
    for code in (204, 304):
        response = client.get(f"/simulate/status/{code}")
        assert response.status_code == code
        assert response.content == b""


@pytest.mark.parametrize(
    ("kind", "exception_type"),
    [
        ("runtime", "RuntimeError"),
        ("key", "KeyError"),
        ("zero", "ZeroDivisionError"),
        ("type", "TypeError"),
        ("index", "IndexError"),
    ],
)
def test_exception_kinds_produce_genuine_500s(client, kind, exception_type):
    response = client.get(f"/simulate/exception?kind={kind}")
    assert response.status_code == 500
    assert response.json()["exception_type"] == exception_type


def test_exception_default_kind_is_runtime(client):
    assert client.get("/simulate/exception").json()["exception_type"] == "RuntimeError"


def test_exception_logs_simulated_exception_event(client, log_capture):
    client.get("/simulate/exception?kind=key")
    assert any(line.get("event") == "simulated_exception" for line in log_capture.new_lines())


def test_slow_delays_then_succeeds(client):
    start = time.perf_counter()
    response = client.get("/simulate/slow?seconds=0.3")
    assert response.status_code == 200
    assert time.perf_counter() - start >= 0.3
    assert response.json()["delayed_seconds"] == 0.3


def test_memory_ballast_allocates_and_releases(client, log_capture):
    assert client.get("/simulate/memory?mb=2").json() == {"allocated_mb": 2, "held_mb": 2}
    assert client.get("/simulate/memory?mb=1").json() == {"allocated_mb": 1, "held_mb": 3}
    released = client.get("/simulate/memory/release").json()
    assert released == {"released_mb": 3, "held_mb": 0}
    events = {line.get("event") for line in log_capture.new_lines()}
    assert {"memory_ballast", "memory_released"} <= events


def test_memory_over_cap_is_409(client, monkeypatch):
    monkeypatch.setattr(simulate, "MEMORY_CAP_MB", 3)
    assert client.get("/simulate/memory?mb=2").status_code == 200
    response = client.get("/simulate/memory?mb=2")
    assert response.status_code == 409
    assert simulate.held_mb() == 2


def test_cpu_burn_returns_immediately(client):
    start = time.perf_counter()
    response = client.get("/simulate/cpu?seconds=1")
    assert response.status_code == 200
    assert time.perf_counter() - start < 1
    assert response.json()["burning_seconds"] == 1
