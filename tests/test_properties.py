"""Property-based coverage of parameter bounds (SPEC 7.4)."""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

common = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@common
@given(code=st.integers(min_value=200, max_value=599))
def test_status_endpoint_echoes_any_code_in_range(client, code):
    response = client.get(f"/simulate/status/{code}")
    assert response.status_code == code
    assert "X-Request-ID" in response.headers


@common
@given(code=st.one_of(st.integers(min_value=0, max_value=199), st.integers(600, 10_000)))
def test_status_codes_outside_bounds_are_rejected(client, code):
    assert client.get(f"/simulate/status/{code}").status_code == 422


def test_flaky_rate_zero_always_succeeds(client):
    assert all(client.get("/simulate/flaky?rate=0").status_code == 200 for _ in range(25))


def test_flaky_rate_one_always_fails_502(client):
    assert all(client.get("/simulate/flaky?rate=1").status_code == 502 for _ in range(25))


@common
@given(rate=st.one_of(st.floats(max_value=-0.001), st.floats(min_value=1.001)))
def test_flaky_rate_outside_bounds_rejected(client, rate):
    assert client.get(f"/simulate/flaky?rate={rate}").status_code == 422


@common
@given(quantity=st.one_of(st.integers(max_value=0), st.integers(min_value=1001)))
def test_order_quantity_outside_bounds_rejected(client, quantity):
    response = client.post("/orders", json={"product_id": 1, "quantity": quantity})
    assert response.status_code == 422


@common
@given(quantity=st.integers(min_value=1, max_value=1000))
def test_order_quantity_within_bounds_never_422(client, quantity):
    response = client.post("/orders", json={"product_id": 5, "quantity": quantity})
    assert response.status_code in (201, 409)


@common
@given(
    failure_rate=st.one_of(
        st.floats(min_value=-9, max_value=-0.01), st.floats(min_value=1.01, max_value=9)
    ),
)
def test_chaos_failure_rate_bounds_rejected(client, failure_rate):
    response = client.post("/chaos/enable", json={"failure_rate": failure_rate})
    assert response.status_code == 422


@common
@given(error_status=st.one_of(st.integers(0, 399), st.integers(600, 5000)))
def test_chaos_error_status_bounds_rejected(client, error_status):
    assert client.post("/chaos/enable", json={"error_status": error_status}).status_code == 422


@common
@given(seconds=st.one_of(st.floats(max_value=-0.01), st.floats(min_value=120.01, max_value=1e6)))
def test_slow_seconds_bounds_rejected(client, seconds):
    assert client.get(f"/simulate/slow?seconds={seconds}").status_code == 422


@common
@given(mb=st.one_of(st.integers(max_value=0), st.integers(min_value=513)))
def test_memory_mb_bounds_rejected(client, mb):
    assert client.get(f"/simulate/memory?mb={mb}").status_code == 422
