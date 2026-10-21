"""Owner claim must never be possible for strangers."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from api.config import settings
from bot.handlers import admin
from bot.services.ownership import (
    DEFAULT_SETUP_CODE,
    claim_ownership,
    create_owner_invite,
)
from db.models import Admin


async def _owners(session):
    return [a.telegram_id for a in (await session.execute(select(Admin).where(Admin.role == "owner"))).scalars()]


@pytest.mark.asyncio
async def test_setup_code_claims_only_the_first_owner(test_db_session):
    async with test_db_session() as session:
        assert await claim_ownership(session, settings.OWNER_SETUP_CODE, 1, "Me", None) == "claimed"
    async with test_db_session() as session:
        # The same code is useless once the shop has an owner.
        assert await claim_ownership(session, settings.OWNER_SETUP_CODE, 2, "Stranger", None) == "invalid"
        assert await claim_ownership(session, settings.OWNER_SETUP_CODE, 1, "Me", None) == "already_owner"
        assert await _owners(session) == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize("unsafe_code", [DEFAULT_SETUP_CODE, "short", ""])
async def test_unsafe_setup_code_never_claims(test_db_session, monkeypatch, unsafe_code):
    monkeypatch.setattr(settings, "OWNER_SETUP_CODE", unsafe_code)
    async with test_db_session() as session:
        assert await claim_ownership(session, unsafe_code, 1, "Hacker", None) == "invalid"
        assert await _owners(session) == []


@pytest.mark.asyncio
async def test_owner_invite_is_single_use(test_db_session):
    async with test_db_session() as session:
        await claim_ownership(session, settings.OWNER_SETUP_CODE, 1, "Me", None)
        token = await create_owner_invite(session)
    async with test_db_session() as session:
        assert await claim_ownership(session, token, 2, "Her", "her") == "claimed"
    async with test_db_session() as session:
        assert await claim_ownership(session, token, 3, "Stranger", None) == "invalid"
        assert sorted(await _owners(session)) == [1, 2]


@pytest.mark.asyncio
async def test_new_invite_replaces_old_one(test_db_session):
    async with test_db_session() as session:
        await claim_ownership(session, settings.OWNER_SETUP_CODE, 1, "Me", None)
        old = await create_owner_invite(session)
        new = await create_owner_invite(session)
    async with test_db_session() as session:
        assert await claim_ownership(session, old, 2, "Stranger", None) == "invalid"
        assert await claim_ownership(session, new, 3, "Her", None) == "claimed"


@pytest.mark.asyncio
async def test_admin_command_never_reveals_setup_code(test_db_session, monkeypatch):
    monkeypatch.setattr(admin, "async_session_factory", test_db_session)
    message = MagicMock()
    message.from_user = SimpleNamespace(id=555, full_name="Stranger", username=None)
    message.answer = AsyncMock()

    await admin.handle_admin_command(message, AsyncMock(), SimpleNamespace(args=None))

    sent = " ".join(str(call.args[0]) for call in message.answer.await_args_list)
    assert settings.OWNER_SETUP_CODE not in sent
    async with test_db_session() as session:
        assert await _owners(session) == []
