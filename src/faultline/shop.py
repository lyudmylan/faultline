"""The business API: a tiny in-memory store, scenery for realistic failures.

Two deliberate, data-dependent defects (see docs/SPEC.md section 4.1):
D1 — product 3 ships with zero stock, so its turnover_score divides by zero.
D2 — product 4 ships with a null price, so total_price arithmetic raises TypeError.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["shop"])


def seed_products() -> dict[int, dict]:
    return {
        1: {"id": 1, "name": "Anvil", "price": 49.5, "units_in_stock": 120},
        2: {"id": 2, "name": "Toaster", "price": 23.0, "units_in_stock": 40},
        3: {"id": 3, "name": "Unobtainium Ingot", "price": 999.0, "units_in_stock": 0},
        4: {"id": 4, "name": "Mystery Box", "price": None, "units_in_stock": 75},
        5: {"id": 5, "name": "Rubber Duck", "price": 6.25, "units_in_stock": 500},
    }


products: dict[int, dict] = seed_products()
orders: list[dict] = []


def reset() -> None:
    """Restore seed state (test hook; the service itself resets on restart)."""
    products.clear()
    products.update(seed_products())
    orders.clear()


class OrderRequest(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=1000)


def _units_ordered(product_id: int) -> int:
    return sum(o["quantity"] for o in orders if o["product_id"] == product_id)


@router.get("/products")
def list_products() -> list[dict]:
    return list(products.values())


@router.get("/products/{product_id}")
def get_product(product_id: int) -> dict:
    product = products.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"no such product: {product_id}")
    units_ordered = _units_ordered(product_id)
    return {
        **product,
        "units_ordered": units_ordered,
        # D1: divides by zero for the seed row with units_in_stock == 0.
        "turnover_score": units_ordered / product["units_in_stock"],
    }


@router.post("/orders", status_code=201)
def create_order(order: OrderRequest) -> dict:
    product = products.get(order.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"no such product: {order.product_id}")
    if order.quantity > product["units_in_stock"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"insufficient stock for product {order.product_id}: "
                f"{product['units_in_stock']} available, {order.quantity} requested"
            ),
        )
    # D2: raises TypeError for the seed row with a null price.
    total_price = round(product["price"] * order.quantity, 2)
    record = {
        "id": len(orders) + 1,
        "product_id": order.product_id,
        "quantity": order.quantity,
        "total_price": total_price,
        "created_at": datetime.now(tz=UTC).isoformat(timespec="milliseconds"),
    }
    product["units_in_stock"] -= order.quantity
    orders.append(record)
    logger.info(
        "order created",
        extra={
            "event": "order_created",
            "order_id": record["id"],
            "product_id": record["product_id"],
            "quantity": record["quantity"],
            "total_price": record["total_price"],
        },
    )
    return record


@router.get("/orders")
def list_orders() -> list[dict]:
    return orders


@router.get("/orders/{order_id}")
def get_order(order_id: int) -> dict:
    if 1 <= order_id <= len(orders):
        return orders[order_id - 1]
    raise HTTPException(status_code=404, detail=f"no such order: {order_id}")
