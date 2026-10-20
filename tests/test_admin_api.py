import pytest
from tests.conftest import generate_test_init_data
from db.models import Admin


@pytest.mark.asyncio
async def test_admin_endpoints_reject_non_admins(client, test_db_session):
    # 1. No header -> 401 Unauthorized
    resp = await client.get("/api/admin/orders")
    assert resp.status_code == 401

    # 2. Regular customer user initData (not admin in DB) -> 403 Forbidden
    customer_init = generate_test_init_data(user_id=123456, first_name="RegularUser")
    resp2 = await client.get("/api/admin/orders", headers={"X-Telegram-Init-Data": customer_init})
    assert resp2.status_code == 403
    assert "admin huquqi" in resp2.json()["detail"].lower() or "administrator" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_endpoints_allow_verified_admin(client, test_db_session):
    async_session = test_db_session
    admin_id = 55566677

    # Add admin to DB
    async with async_session() as session:
        session.add(Admin(telegram_id=admin_id, name="Chief Admin", role="admin"))
        await session.commit()

    admin_init = generate_test_init_data(user_id=admin_id, first_name="Chief Admin")
    resp = await client.get("/api/admin/orders", headers={"X-Telegram-Init-Data": admin_init})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
