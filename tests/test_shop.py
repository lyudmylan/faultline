"""Business API behavior (SPEC 4.1)."""


def test_list_products_returns_seed_catalog(client):
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 5
    assert {p["id"] for p in products} == {1, 2, 3, 4, 5}


def test_product_detail_includes_derived_fields(client):
    response = client.get("/products/1")
    assert response.status_code == 200
    product = response.json()
    assert product["units_ordered"] == 0
    assert product["turnover_score"] == 0


def test_product_detail_reflects_orders_in_derived_fields(client):
    client.post("/orders", json={"product_id": 1, "quantity": 10})
    product = client.get("/products/1").json()
    assert product["units_ordered"] == 10
    assert product["turnover_score"] == 10 / product["units_in_stock"]


def test_unknown_product_is_404_with_detail(client):
    response = client.get("/products/999")
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_create_order_returns_201_with_total_price(client):
    response = client.post("/orders", json={"product_id": 1, "quantity": 3})
    assert response.status_code == 201
    order = response.json()
    assert order["total_price"] == 3 * 49.5
    assert order["product_id"] == 1
    assert order["quantity"] == 3


def test_order_for_unknown_product_is_404(client):
    response = client.post("/orders", json={"product_id": 999, "quantity": 1})
    assert response.status_code == 404


def test_order_exceeding_stock_is_409(client):
    response = client.post("/orders", json={"product_id": 2, "quantity": 41})
    assert response.status_code == 409
    assert "insufficient stock" in response.json()["detail"]


def test_successful_order_decrements_stock(client):
    before = client.get("/products/2").json()["units_in_stock"]
    client.post("/orders", json={"product_id": 2, "quantity": 5})
    after = client.get("/products/2").json()["units_in_stock"]
    assert after == before - 5


def test_orders_listing_and_detail(client):
    assert client.get("/orders").json() == []
    created = client.post("/orders", json={"product_id": 5, "quantity": 2}).json()
    listed = client.get("/orders").json()
    assert listed == [created]
    assert client.get(f"/orders/{created['id']}").json() == created


def test_unknown_order_is_404(client):
    assert client.get("/orders/42").status_code == 404


def test_order_creation_logs_order_created_event(client, log_capture):
    client.post("/orders", json={"product_id": 1, "quantity": 2})
    events = [line for line in log_capture.new_lines() if line.get("event") == "order_created"]
    assert len(events) == 1
    assert events[0]["order_id"] == 1
