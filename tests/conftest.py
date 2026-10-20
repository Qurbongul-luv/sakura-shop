import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import json
import hashlib
import hmac
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Set test environment
os.environ["BOT_TOKEN"] = "123456789:TEST_BOT_TOKEN_SECRET"
os.environ["OWNER_SETUP_CODE"] = "test_owner_secret_token_123"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEV_ADMIN_ID"] = "999999999"

from api.config import settings
from api.main import app
from db.models import Base, Admin, Setting, Product, Category
from db.session import get_db

TEST_BOT_TOKEN = "123456789:TEST_BOT_TOKEN_SECRET"
settings.BOT_TOKEN = TEST_BOT_TOKEN
settings.OWNER_SETUP_CODE = "test_owner_secret_token_123"


def generate_test_init_data(
    user_id: int = 12345678,
    first_name: str = "TestUser",
    username: str = "test_sakura",
    auth_date_offset: int = 0,
    tampered: bool = False,
    secret_token: str = TEST_BOT_TOKEN,
) -> str:
    auth_date = int(time.time()) + auth_date_offset
    user_json = json.dumps({
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "language_code": "uz",
    }, separators=(',', ':'))

    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohD9w7uJ",
        "user": user_json,
    }

    # Data check string: alphabetically sorted key=value lines
    data_check_list = [f"{k}={v}" for k, v in sorted(params.items())]
    data_check_string = "\n".join(data_check_list)

    # Compute HMAC
    secret_key = hmac.new(b"WebAppData", secret_token.encode("utf-8"), hashlib.sha256).digest()
    sig_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if tampered:
        # Alter user data after signature calculation
        params["user"] = json.dumps({"id": 9999999, "first_name": "Hacker"}, separators=(',', ':'))

    query_parts = [f"{k}={v}" for k, v in params.items()]
    query_parts.append(f"hash={sig_hash}")
    return "&".join(query_parts)


@pytest_asyncio.fixture(scope="function")
async def test_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed basic settings
    async with async_session() as session:
        session.add_all([
            Setting(key="cargo_rate", value="12000"),
            Setting(key="delivery_days", value="10–15 kun"),
            Setting(key="delivery_scope", value="O'zbekiston bo'ylab"),
            Setting(key="contact_username", value="fkhrdnvvvva"),
            Setting(key="channel_id", value=""),
            Setting(key="owner_claimed_at", value=""),
            Category(slug="jempir", name="Jempir", emoji="🧶", sort_order=1),
            Category(slug="wig", name="Wig", emoji="💇‍♀️", sort_order=2),
            Category(slug="scarf", name="Scarf", emoji="🧣", sort_order=3),
            Product(
                id=1,
                title="Aesthetic Jempir 🌸",
                description="Test jempir",
                price=99000,
                category="jempir",
                photos=["test_jempir.png"],
                sizes=["S", "M"],
                colors=["Pushti 🌸"],
                weight_grams=350,
                in_stock=True,
                is_new=True,
            ),
        ])
        await session.commit()

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield async_session

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
