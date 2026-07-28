"""One dedicated test per behavioral invariant (SPEC 5).

I7 (crash) and the hang half of client-timeout behavior live in
test_live_server.py because they need a real subprocess.
"""

import re
import threading
import time

from conftest import metric_value

from faultline import chaos


def test_i1_request_id_generated_and_echoed(client):
    generated = client.get("/products").headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{12}", generated)

    echoed = client.get("/products", headers={"X-Request-ID": "trace-me-42"})
    assert echoed.headers["X-Request-ID"] == "trace-me-42"


def test_i1_error_responses_also_carry_request_id(client):
    for path in ("/products/3", "/products/999", "/nonexistent"):
        assert "X-Request-ID" in client.get(path).headers


def test_i2_unhandled_exception_produces_exactly_one_of_each(client, log_capture):
    before = (
        metric_value(client.get("/metrics").text, "http_exceptions_total", 'type="IndexError"') or 0
    )

    response = client.get("/simulate/exception?kind=index")

    assert response.status_code == 500
    assert response.json() == {
        "error": "internal server error",
        "exception_type": "IndexError",
        "request_id": response.headers["X-Request-ID"],
    }
    errors = [line for line in log_capture.new_lines() if line["level"] == "ERROR"]
    assert len(errors) == 1
    assert "Traceback" in errors[0]["stack"]
    after = metric_value(client.get("/metrics").text, "http_exceptions_total", 'type="IndexError"')
    assert after == before + 1


def test_i3_chaos_never_alters_exempt_paths(client):
    client.post("/chaos/enable", json={"failure_rate": 1.0, "extra_latency_ms": 60000})
    exempt_expectations = {
        "/health": 200,
        "/metrics": 200,
        "/chaos": 200,
        "/simulate/status/201": 201,
        "/docs": 200,
        "/openapi.json": 200,
        "/redoc": 200,
    }
    for path, expected_status in exempt_expectations.items():
        start = time.perf_counter()
        response = client.get(path)
        elapsed = time.perf_counter() - start
        assert response.status_code == expected_status, path
        assert "temporarily degraded" not in response.text, path
        assert elapsed < 5, f"{path} appears to have received chaos latency"


def test_i4_disable_restores_normal_behavior_immediately(client):
    client.post("/chaos/enable", json={"failure_rate": 1.0})
    assert client.get("/products").status_code == 503
    client.post("/chaos/disable")
    assert all(client.get("/products").status_code == 200 for _ in range(10))


def test_i5_health_and_metrics_green_under_chaos_and_cpu_burn(client):
    client.post("/chaos/enable", json={"failure_rate": 1.0})
    client.get("/simulate/cpu?seconds=1")
    for _ in range(3):
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert client.get("/metrics").status_code == 200


def test_i6_ballast_cap_is_2048_and_enforced(client, monkeypatch):
    from faultline import simulate

    assert simulate.MEMORY_CAP_MB == 2048
    monkeypatch.setattr(simulate, "MEMORY_CAP_MB", 2)
    assert client.get("/simulate/memory?mb=2").status_code == 200
    assert client.get("/simulate/memory?mb=1").status_code == 409
    assert simulate.held_mb() <= 2


def _access_lines(log_capture):
    return [line for line in log_capture.new_lines() if line.get("event") == "request"]


def test_i8_exactly_one_access_line_per_request(client, log_capture):
    client.get("/products")
    client.get("/products/999")
    client.get("/products/3")
    client.post("/orders", json={"product_id": 1, "quantity": 0})
    client.post("/chaos/enable", json={"failure_rate": 1.0})
    client.get("/products")
    client.post("/chaos/disable")

    lines = _access_lines(log_capture)
    assert len(lines) == 7
    assert [line["status"] for line in lines] == [200, 404, 500, 422, 200, 503, 200]
    assert all(line["method"] and line["path"] and "duration_ms" in line for line in lines)


def test_i8_access_lines_under_concurrency(client, log_capture):
    def hit():
        client.get("/products")

    threads = [threading.Thread(target=hit) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(_access_lines(log_capture)) == 8


def test_chaos_state_reset_between_tests(client):
    assert chaos.state.enabled is False
