"""Contest admin menu refresh: one callback answer, and photo messages get a new menu message."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from bot.handlers import admin_contest
from db.models import Contest
from tests.test_contest import seed_active_contest


def make_call(data="admin_contest_menu", text="⚠️ DIQQAT: Konkursni bekor qilmoqchimisiz?"):
    message = SimpleNamespace(text=text, edit_text=AsyncMock(), answer=AsyncMock())
    return SimpleNamespace(data=data, from_user=SimpleNamespace(id=1), answer=AsyncMock(), message=message)


@pytest.fixture
def admin_db(test_db_session, monkeypatch):
    monkeypatch.setattr(admin_contest, "async_session_factory", test_db_session)
    monkeypatch.setattr(admin_contest, "check_admin", AsyncMock(return_value=True))
    return test_db_session


@pytest.mark.asyncio
async def test_cancel_answers_once_and_refreshes_menu(admin_db):
    async with admin_db() as session:
        contest = await seed_active_contest(session)
    call = make_call(data=f"adm_c_cancel_exec:{contest.id}")

    await admin_contest.handle_cancel_execute(call, AsyncMock())

    call.answer.assert_awaited_once_with("Konkurs bekor qilindi.", show_alert=True)
    call.message.edit_text.assert_awaited_once()
    assert "Hozirda faol konkurs mavjud emas" in call.message.edit_text.await_args.args[0]
    async with admin_db() as session:
        status = (await session.execute(select(Contest.status).where(Contest.id == contest.id))).scalar_one()
    assert status == "cancelled"


@pytest.mark.asyncio
async def test_menu_after_photo_preview_sends_new_message(admin_db):
    call = make_call(text=None)  # launch preview is a photo with a caption

    await admin_contest.handle_admin_contest_menu(call, AsyncMock(), notice="Konkurs muvaffaqiyatli boshlandi! 🌸")

    call.answer.assert_awaited_once_with("Konkurs muvaffaqiyatli boshlandi! 🌸", show_alert=True)
    call.message.edit_text.assert_not_awaited()
    call.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_plain_menu_open_answers_silently(admin_db):
    call = make_call(text="👑 Admin menyusi")

    await admin_contest.handle_admin_contest_menu(call, AsyncMock())

    call.answer.assert_awaited_once_with(None, show_alert=False)
    call.message.edit_text.assert_awaited_once()
