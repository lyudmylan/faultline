"""Seeded defects D1 and D2 (SPEC 4.1): deterministic, logged with stacks, counted."""

from conftest import metric_value


def test_d1_zero_stock_product_detail_is_500_zero_division(client, log_capture):
    response = client.get("/products/3")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal server error"
    assert body["exception_type"] == "ZeroDivisionError"
    assert body["request_id"] == response.headers["X-Request-ID"]

    errors = [line for line in log_capture.new_lines() if line["level"] == "ERROR"]
    assert len(errors) == 1
    assert errors[0]["exception_type"] == "ZeroDivisionError"
    assert "ZeroDivisionError" in errors[0]["stack"]


def test_d2_null_price_order_is_500_type_error(client, log_capture):
    response = client.post("/orders", json={"product_id": 4, "quantity": 2})
    assert response.status_code == 500
    assert response.json()["exception_type"] == "TypeError"

    errors = [line for line in log_capture.new_lines() if line["level"] == "ERROR"]
    assert len(errors) == 1
    assert "TypeError" in errors[0]["stack"]


def test_defects_are_deterministic(client):
    for _ in range(3):
        assert client.get("/products/3").status_code == 500
        assert client.post("/orders", json={"product_id": 4, "quantity": 1}).status_code == 500


def test_d2_does_not_create_an_order(client):
    client.post("/orders", json={"product_id": 4, "quantity": 1})
    assert client.get("/orders").json() == []


def test_defects_increment_exception_metrics(client):
    def scrape(exception_type):
        return metric_value(
            client.get("/metrics").text, "http_exceptions_total", f'type="{exception_type}"'
        )

    zero_before = scrape("ZeroDivisionError") or 0
    type_before = scrape("TypeError") or 0
    client.get("/products/3")
    client.post("/orders", json={"product_id": 4, "quantity": 1})
    assert scrape("ZeroDivisionError") == zero_before + 1
    assert scrape("TypeError") == type_before + 1
