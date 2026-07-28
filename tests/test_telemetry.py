"""Health, metrics exposition, and log schema (SPEC 4.4)."""

import json
import re

from conftest import LOG_FILE, metric_value

TS_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
LEVELS = {"INFO", "WARNING", "ERROR", "CRITICAL"}


def test_health_reports_ok_and_uptime(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["uptime_seconds"], float) and body["uptime_seconds"] > 0


def test_metrics_families_present(client):
    client.get("/products")
    text = client.get("/metrics").text
    for family in (
        "http_requests_total",
        "http_request_duration_seconds_sum",
        "http_request_duration_seconds_count",
        "faultline_chaos_enabled",
        "process_uptime_seconds",
        "process_max_rss_bytes",
    ):
        assert family in text


def test_request_counter_uses_route_template_and_status(client):
    before = (
        metric_value(
            client.get("/metrics").text,
            "http_requests_total",
            'method="GET",path="/products/{product_id}",status="404"',
        )
        or 0
    )
    client.get("/products/999")
    after = metric_value(
        client.get("/metrics").text,
        "http_requests_total",
        'method="GET",path="/products/{product_id}",status="404"',
    )
    assert after == before + 1


def test_duration_summary_counts_requests(client):
    client.get("/products")
    text = client.get("/metrics").text
    count = metric_value(
        text, "http_request_duration_seconds_count", 'method="GET",path="/products"'
    )
    total = metric_value(text, "http_request_duration_seconds_sum", 'method="GET",path="/products"')
    assert count >= 1 and total > 0


def test_max_rss_metric_is_plausible(client):
    rss = metric_value(client.get("/metrics").text, "process_max_rss_bytes")
    # A Python process is comfortably above 10 MB and below 100 GB.
    assert 10 * 1024 * 1024 < rss < 100 * 1024 * 1024 * 1024


def test_every_log_line_is_json_with_base_fields(client, log_capture):
    client.get("/products")
    client.get("/products/3")
    client.post("/chaos/enable")
    client.post("/chaos/disable")

    with open(LOG_FILE) as handle:
        lines = [line for line in handle.read().splitlines() if line.strip()]
    assert lines, "log file is empty"
    for raw in lines:
        parsed = json.loads(raw)
        assert TS_PATTERN.fullmatch(parsed["ts"]), parsed["ts"]
        assert parsed["level"] in LEVELS
        assert parsed["logger"]
        assert "message" in parsed


def test_request_scoped_lines_carry_request_id(client, log_capture):
    client.get("/products", headers={"X-Request-ID": "corr-check"})
    lines = [line for line in log_capture.new_lines() if line.get("event") == "request"]
    assert lines and all(line["request_id"] == "corr-check" for line in lines)


def test_stack_only_on_unhandled_exceptions(client, log_capture):
    client.get("/products")
    client.get("/products/3")
    lines = log_capture.new_lines()
    with_stack = [line for line in lines if "stack" in line]
    assert all(line.get("event") == "unhandled_exception" for line in with_stack)
    assert len(with_stack) == 1
