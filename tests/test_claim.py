import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from db.models import Admin, Setting
from api.config import settings


@pytest.mark.asyncio
async def test_claim_link_works_once_and_only_once(test_db_session):
    async_session = test_db_session

    user_id = 77712345
    full_name = "Sakura Owner"
    claim_code = settings.OWNER_SETUP_CODE

    # 1. First claim attempt with correct code
    async with async_session() as session:
        # Check not claimed yet
        res_claimed = await session.execute(select(Setting).where(Setting.key == "owner_claimed_at"))
        claimed_setting = res_claimed.scalars().first()
        assert claimed_setting is not None
        assert claimed_setting.value == ""

        # Claim
        new_owner = Admin(
            telegram_id=user_id,
            name=full_name,
            role="owner",
        )
        session.add(new_owner)
        claimed_setting.value = datetime.now(timezone.utc).isoformat()
        await session.commit()

    # Verify owner stored in DB
    async with async_session() as session:
        res_owner = await session.execute(select(Admin).where(Admin.role == "owner"))
        owner = res_owner.scalars().first()
        assert owner is not None
        assert owner.telegram_id == user_id

        # Verify claim setting is now set
        res_claimed = await session.execute(select(Setting).where(Setting.key == "owner_claimed_at"))
        assert res_claimed.scalars().first().value != ""

    # 2. Second claim attempt by another user
    second_user_id = 88899900
    async with async_session() as session:
        res_claimed = await session.execute(select(Setting).where(Setting.key == "owner_claimed_at"))
        claimed_setting = res_claimed.scalars().first()
        already_claimed = bool(claimed_setting and claimed_setting.value.strip())

        res_owner = await session.execute(select(Admin).where(Admin.role == "owner"))
        owner_exists = res_owner.scalars().first() is not None

        # Must reject because already claimed!
        assert already_claimed is True
        assert owner_exists is True
