from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.runtime import BotRuntime


def prepare_startup(monkeypatch, main, backend="sqlite"):
    monkeypatch.setattr(main, "engine", SimpleNamespace(
        dialect=SimpleNamespace(name=backend), dispose=AsyncMock()))
    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main, "seed_database", AsyncMock())
    monkeypatch.setattr(main, "generate_demo_images", MagicMock())
    monkeypatch.setattr(main, "bot_polling_task", None)
    monkeypatch.setattr(main, "contest_scheduler_task", None)
    monkeypatch.setattr(main, "bot", None)
    monkeypatch.setattr(main, "dp", None)
    monkeypatch.setattr(main, "bot_runtime", BotRuntime(mode="disabled"))


@pytest.mark.asyncio
async def test_render_sqlite_fails_before_creating_or_seeding_data(monkeypatch):
    import api.main as main
    prepare_startup(monkeypatch, main)
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        async with main.lifespan(main.app):
            pass
    main.init_db.assert_not_awaited()
    main.seed_database.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend,is_render", [("sqlite", False), ("postgresql", True)])
async def test_valid_backend_starts_and_is_disposed(monkeypatch, caplog, backend, is_render):
    import api.main as main
    prepare_startup(monkeypatch, main, backend)
    monkeypatch.setenv("RENDER", "true" if is_render else "false")
    caplog.set_level("INFO")
    async with main.lifespan(main.app):
        main.init_db.assert_awaited_once()
    assert f"Database backend: {backend}" in caplog.text
    main.engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_local_preview_switch_starts_no_polling_or_scheduler(monkeypatch):
    import api.main as main
    prepare_startup(monkeypatch, main)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(main.settings, "BOT_POLLING_ENABLED", False)
    monkeypatch.setattr(main, "bot", SimpleNamespace(session=SimpleNamespace(close=AsyncMock())))
    monkeypatch.setattr(main, "dp", object())
    starter = AsyncMock()
    monkeypatch.setattr(main.bot_runtime, "start", starter)
    async with main.lifespan(main.app):
        assert main.bot_polling_task is None
        assert main.contest_scheduler_task is None
    starter.assert_not_awaited()
    main.bot.session.close.assert_awaited_once()
