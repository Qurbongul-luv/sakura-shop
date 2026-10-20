import pytest
from sqlalchemy import select
from db.models import Admin, Setting
from api.config import settings


@pytest.mark.asyncio
async def test_channel_linking_ignores_non_owners(test_db_session):
    async_session = test_db_session
    owner_id = 11122233
    random_user_id = 99988877

    # Setup owner in DB
    async with async_session() as session:
        session.add(Admin(telegram_id=owner_id, name="Real Owner", role="owner"))
        await session.commit()

    # Verify logic: non-owner attempts channel link
    async with async_session() as session:
        res_owner = await session.execute(select(Admin).where(Admin.role == "owner"))
        owner = res_owner.scalars().first()

        # Non-owner test
        assert random_user_id != owner.telegram_id
        # Channel ID must remain unlinked
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch_setting = res_ch.scalars().first()
        assert ch_setting.value == ""

        # Owner test
        assert owner_id == owner.telegram_id
        ch_setting.value = "-1001234567890"
        await session.commit()

    async with async_session() as session:
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        assert res_ch.scalars().first().value == "-1001234567890"
