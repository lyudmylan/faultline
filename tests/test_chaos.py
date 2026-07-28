"""Chaos mode semantics (SPEC 4.3)."""

import time

from conftest import metric_value


def test_chaos_defaults_and_status(client):
    state = client.get("/chaos").json()
    assert state == {
        "enabled": False,
        "failure_rate": 0.3,
        "error_status": 503,
        "extra_latency_ms": 0,
    }


def test_enable_without_body_uses_defaults(client):
    state = client.post("/chaos/enable").json()
    assert state["enabled"] is True
    assert state["failure_rate"] == 0.3
    assert state["error_status"] == 503


def test_chaos_failure_uses_degraded_envelope_and_configured_status(client):
    client.post("/chaos/enable", json={"failure_rate": 1.0, "error_status": 418})
    response = client.get("/products")
    assert response.status_code == 418
    body = response.json()
    assert body["error"] == "service temporarily degraded"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_chaos_failure_rate_zero_never_fails(client):
    client.post("/chaos/enable", json={"failure_rate": 0.0})
    assert all(client.get("/products").status_code == 200 for _ in range(20))


def test_chaos_adds_latency(client):
    client.post("/chaos/enable", json={"failure_rate": 0.0, "extra_latency_ms": 150})
    start = time.perf_counter()
    for _ in range(5):
        client.get("/products")
    elapsed = time.perf_counter() - start
    # Five draws from uniform[0, 150ms]; all five landing under 20ms total is implausible.
    assert elapsed > 0.02


def test_transitions_are_logged_at_warning(client, log_capture):
    client.post("/chaos/enable")
    client.post("/chaos/disable")
    lines = log_capture.new_lines()
    enabled = [line for line in lines if line.get("event") == "chaos_enabled"]
    disabled = [line for line in lines if line.get("event") == "chaos_disabled"]
    assert enabled[0]["level"] == "WARNING" and disabled[0]["level"] == "WARNING"


def test_chaos_failures_are_logged(client, log_capture):
    client.post("/chaos/enable", json={"failure_rate": 1.0})
    client.get("/products")
    assert any(line.get("event") == "chaos_failure" for line in log_capture.new_lines())


def test_chaos_gauge_tracks_state(client):
    assert metric_value(client.get("/metrics").text, "faultline_chaos_enabled") == 0
    client.post("/chaos/enable")
    assert metric_value(client.get("/metrics").text, "faultline_chaos_enabled") == 1
    client.post("/chaos/disable")
    assert metric_value(client.get("/metrics").text, "faultline_chaos_enabled") == 0
