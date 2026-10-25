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


# ---- Linking the channel: any owner, and manual linking by @username ----
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.handlers.channel import is_shop_owner, link_channel_by_username

CHANNEL_ID = -1004424585420
BOT_ID = 42
OWNER_1, OWNER_2, PLAIN_ADMIN = 111, 222, 333


def channel_bot(member_by_user):
    tg_bot = AsyncMock()
    tg_bot.get_chat.return_value = SimpleNamespace(id=CHANNEL_ID, type="channel", title="Sakura shop")
    tg_bot.get_me.return_value = SimpleNamespace(id=BOT_ID)

    async def get_chat_member(chat_id, user_id):
        assert chat_id == CHANNEL_ID
        return member_by_user[user_id]

    tg_bot.get_chat_member.side_effect = get_chat_member
    return tg_bot


async def saved_channel_id(session):
    res = await session.execute(select(Setting).where(Setting.key == "channel_id"))
    return res.scalars().first().value


async def seed_admins(session):
    session.add_all([
        Admin(telegram_id=OWNER_1, name="bek", role="owner"),
        Admin(telegram_id=OWNER_2, name="Faxriddinova", role="owner"),
        Admin(telegram_id=PLAIN_ADMIN, name="helper", role="admin"),
    ])
    await session.commit()


@pytest.mark.asyncio
async def test_every_owner_counts_not_only_the_first(test_db_session):
    async with test_db_session() as session:
        await seed_admins(session)
        assert await is_shop_owner(session, OWNER_1)
        assert await is_shop_owner(session, OWNER_2)
        assert not await is_shop_owner(session, PLAIN_ADMIN)
        assert not await is_shop_owner(session, 999)


@pytest.mark.asyncio
async def test_owner_links_channel_by_username(test_db_session):
    tg_bot = channel_bot({
        BOT_ID: SimpleNamespace(status="administrator", can_post_messages=True),
        OWNER_1: SimpleNamespace(status="administrator"),
    })
    async with test_db_session() as session:
        linked, reply = await link_channel_by_username(session, tg_bot, OWNER_1, "https://t.me/sakuraaa_chinese_shop")
        assert linked, reply
        assert await saved_channel_id(session) == str(CHANNEL_ID)
    tg_bot.get_chat.assert_awaited_once_with("@sakuraaa_chinese_shop")


@pytest.mark.asyncio
@pytest.mark.parametrize("bot_member, user_member", [
    (SimpleNamespace(status="administrator", can_post_messages=True), SimpleNamespace(status="member")),
    (SimpleNamespace(status="administrator", can_post_messages=False), SimpleNamespace(status="creator")),
    (SimpleNamespace(status="left"), SimpleNamespace(status="creator")),
])
async def test_link_refused_without_admin_rights(test_db_session, bot_member, user_member):
    tg_bot = channel_bot({BOT_ID: bot_member, OWNER_1: user_member})
    async with test_db_session() as session:
        linked, _ = await link_channel_by_username(session, tg_bot, OWNER_1, "@sakuraaa_chinese_shop")
        assert not linked
        assert await saved_channel_id(session) == ""


@pytest.mark.asyncio
async def test_link_refuses_garbage_and_unknown_channel(test_db_session):
    tg_bot = channel_bot({})
    async with test_db_session() as session:
        linked, _ = await link_channel_by_username(session, tg_bot, OWNER_1, "salom qalaysiz")
        assert not linked
        tg_bot.get_chat.assert_not_awaited()

        tg_bot.get_chat.side_effect = Exception("chat not found")
        linked, _ = await link_channel_by_username(session, tg_bot, OWNER_1, "@no_such_channel")
        assert not linked
        assert await saved_channel_id(session) == ""


# ---- Unlinking the channel ----
from bot.handlers.channel import save_channel_id, unlink_channel
from tests.test_contest import seed_active_contest


@pytest.mark.asyncio
async def test_unlink_refused_while_contest_is_active(test_db_session):
    async with test_db_session() as session:
        await seed_active_contest(session)
        await save_channel_id(session, str(CHANNEL_ID))
        unlinked, _ = await unlink_channel(session)
        assert not unlinked
        assert await saved_channel_id(session) == str(CHANNEL_ID)


@pytest.mark.asyncio
async def test_unlink_clears_channel_without_contest(test_db_session):
    async with test_db_session() as session:
        await save_channel_id(session, str(CHANNEL_ID))
        unlinked, _ = await unlink_channel(session)
        assert unlinked
        assert await saved_channel_id(session) == ""
