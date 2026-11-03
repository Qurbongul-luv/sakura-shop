from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from api.routes import orders as order_routes
from db.models import CartItem, Order, Product
from tests.conftest import generate_test_init_data

CUSTOMER = 31337


@pytest.fixture
def headers(monkeypatch):
    monkeypatch.setattr(order_routes, "notify_new_order", AsyncMock())
    init = generate_test_init_data(user_id=CUSTOMER, first_name="Real", username="real_buyer")
    return {"X-Telegram-Init-Data": init}


async def _cart(session, qty=2):
    session.add(CartItem(user_id=CUSTOMER, product_id=1, size="M", color="Pushti", qty=qty))
    await session.commit()


@pytest.mark.asyncio
async def test_client_prices_and_identity_are_ignored(client, test_db_session, headers):
    async with test_db_session() as session:
        await _cart(session)

    forged = {
        "customer_name": "Boshqa odam",
        "customer_username": "victim_account",
        "items": [{"product_id": 1, "title": "Arzon", "price": 1, "qty": 50}],
    }
    resp = await client.post("/api/orders", json=forged, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 198000  # 99.000 × 2 from the database, not 1 × 50
    assert body["customer_username"] == "real_buyer" and body["customer_name"] == "Real"
    assert body["items_snapshot"] == [{
        "product_id": 1, "title": "Aesthetic Jempir 🌸", "price": 99000, "size": "M", "color": "Pushti",
        "qty": 2, "weight_grams": 350, "photo": "test_jempir.png",
    }]
    order_routes.notify_new_order.assert_called_once()
    assert order_routes.notify_new_order.call_args.kwargs["customer_username"] == "real_buyer"


@pytest.mark.asyncio
async def test_items_without_a_cart_cannot_create_an_order(client, test_db_session, headers):
    resp = await client.post(
        "/api/orders", json={"items": [{"product_id": 1, "price": 1, "qty": 1}]}, headers=headers
    )
    assert resp.status_code == 400
    async with test_db_session() as session:
        assert (await session.execute(select(Order))).scalars().first() is None


@pytest.mark.asyncio
async def test_normal_mini_app_checkout_still_works(client, test_db_session, headers):
    async with test_db_session() as session:
        await _cart(session, qty=1)
    resp = await client.post("/api/orders", json={}, headers=headers)  # exactly what BagPage sends
    assert resp.status_code == 200 and resp.json()["total"] == 99000
    async with test_db_session() as session:
        assert (await session.execute(select(CartItem).where(CartItem.user_id == CUSTOMER))).first() is None


@pytest.mark.asyncio
async def test_price_change_after_adding_to_cart_uses_current_price(client, test_db_session, headers):
    async with test_db_session() as session:
        await _cart(session, qty=1)
        prod = (await session.execute(select(Product).where(Product.id == 1))).scalars().one()
        prod.price = 120000
        await session.commit()
    resp = await client.post("/api/orders", json={}, headers=headers)
    assert resp.json()["total"] == 120000


@pytest.mark.asyncio
async def test_unsigned_request_is_rejected(client):
    assert (await client.post("/api/orders", json={})).status_code == 401


@pytest.mark.asyncio
async def test_customer_sees_only_own_orders_newest_first(client, test_db_session, headers):
    async with test_db_session() as session:
        for uid, status in ((CUSTOMER, "new"), (999, "accepted"), (CUSTOMER, "shipping")):
            session.add(Order(
                user_id=uid, customer_name="X", items_snapshot=[], total=1000, estimated_cargo=0, status=status,
            ))
        await session.commit()
    resp = await client.get("/api/orders", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [o["status"] for o in body] == ["shipping", "new"]
    assert all(o["user_id"] == CUSTOMER for o in body)
    assert "status_updated_at" in body[0]


@pytest.mark.asyncio
async def test_order_list_requires_signed_init_data(client):
    assert (await client.get("/api/orders")).status_code == 401
