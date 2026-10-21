"""Polling recovery, health semantics, and aiogram/FastAPI lifecycle integration."""
import asyncio
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Dispatcher
from aiogram.exceptions import TelegramConflictError
from aiogram.methods import GetUpdates
from httpx import ASGITransport, AsyncClient

from bot.runtime import BotRuntime


@pytest.mark.asyncio
async def test_empty_poll_is_healthy_and_clears_transport_error():
    runtime = BotRuntime()
    runtime.task = SimpleNamespace(done=lambda: False)
    runtime.last_transport_error = "TelegramNetworkError"
    assert await runtime.observe_request(AsyncMock(return_value=[]), object(), GetUpdates()) == []
    assert runtime.last_poll_success_at
    assert runtime.last_update_at is None  # A quiet shop is healthy too.
    assert runtime.health()["healthy"] is True


@pytest.mark.asyncio
async def test_conflict_is_counted_even_for_subclasses():
    class Conflict(TelegramConflictError):
        pass
    runtime = BotRuntime()
    with pytest.raises(TelegramConflictError):
        await runtime.observe_request(
            AsyncMock(side_effect=Conflict(GetUpdates(), "another poller")), object(), GetUpdates())
    assert runtime.conflict_count == 1
    assert runtime.health()["healthy"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("temporary"), None])
async def test_supervisor_restarts_after_exception_or_normal_exit(failure):
    restarted = asyncio.Event()
    class FakeDispatcher:
        def __init__(self):
            self.calls = 0
        async def start_polling(self, *args, **kwargs):
            self.calls += 1
            assert kwargs["handle_signals"] is False
            assert kwargs["close_bot_session"] is False
            assert "chat_member" in kwargs["allowed_updates"]
            if self.calls == 1:
                if failure:
                    raise failure
                return
            restarted.set()
            await asyncio.Future()
    dispatcher = FakeDispatcher()
    bot = SimpleNamespace(get_webhook_info=AsyncMock(return_value=SimpleNamespace(url="")))
    runtime = BotRuntime(bot, dispatcher, retry_delay=0)
    runtime.task = asyncio.create_task(runtime._supervise_polling())
    try:
        await asyncio.wait_for(restarted.wait(), timeout=2)
        assert dispatcher.calls == 2
        assert runtime.restart_count == 1
    finally:
        await runtime.stop()
    assert runtime.task.cancelled()


@pytest.mark.asyncio
async def test_existing_webhook_is_never_removed_automatically():
    checked = asyncio.Event()
    async def info():
        checked.set()
        return SimpleNamespace(url="https://example.com/telegram")
    bot = SimpleNamespace(get_webhook_info=info, delete_webhook=AsyncMock())
    dispatcher = SimpleNamespace(start_polling=AsyncMock())
    runtime = BotRuntime(bot, dispatcher)
    runtime.task = asyncio.create_task(runtime._supervise_polling())
    try:
        await asyncio.wait_for(checked.wait(), timeout=2)
        # Yield until the response has been consumed by the supervisor.
        while runtime.last_transport_error is None:
            await asyncio.sleep(0)
        assert runtime.last_transport_error == "WebhookConfiguredError"
        dispatcher.start_polling.assert_not_awaited()
        bot.delete_webhook.assert_not_awaited()
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_stop_uses_aiogram_to_cancel_its_polling_child(monkeypatch):
    started, cancelled = asyncio.Event(), asyncio.Event()
    dispatcher = Dispatcher()
    async def polling(**kwargs):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    monkeypatch.setattr(dispatcher, "_polling", polling)
    bot = SimpleNamespace(
        get_webhook_info=AsyncMock(return_value=SimpleNamespace(url="")),
        session=SimpleNamespace(middleware=MagicMock(), close=AsyncMock()),
    )
    runtime = BotRuntime(bot, dispatcher)
    await runtime.start()
    await asyncio.wait_for(started.wait(), timeout=2)
    await runtime.stop()
    assert cancelled.is_set()
    assert runtime.task.done()
    bot.session.close.assert_not_awaited()  # The FastAPI lifespan owns the shared session.


def test_alive_supervisor_alone_does_not_mean_healthy():
    runtime = BotRuntime()
    runtime.task = SimpleNamespace(done=lambda: False)
    assert runtime.health()["healthy"] is False
    runtime._last_poll_tick = monotonic() - 121
    assert runtime.health()["healthy"] is False
    runtime._last_poll_tick = monotonic()
    assert runtime.health()["healthy"] is True
    runtime.task = SimpleNamespace(done=lambda: True)
    assert runtime.health()["healthy"] is False


@pytest.mark.asyncio
async def test_handler_error_is_visible_until_next_success():
    runtime = BotRuntime()
    runtime.task = SimpleNamespace(done=lambda: False)
    runtime._last_poll_tick = monotonic()
    with pytest.raises(RuntimeError):
        await runtime.observe_update(AsyncMock(side_effect=RuntimeError("DB unavailable")), object(), {})
    assert runtime.last_update_at
    assert runtime.health()["healthy"] is False
    await runtime.observe_update(AsyncMock(return_value=True), object(), {})
    assert runtime.last_update_processed_at
    assert runtime.health()["healthy"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/api/health"])
@pytest.mark.parametrize("healthy", [False, True])
async def test_health_get_and_head_report_bot_state(monkeypatch, path, healthy):
    import api.main as main
    runtime = BotRuntime()
    runtime.task = SimpleNamespace(done=lambda: False)
    if healthy:
        runtime._last_poll_tick = monotonic()
    monkeypatch.setattr(main, "bot_runtime", runtime)
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(path)
        assert response.status_code == (200 if healthy else 503)
        assert response.json()["bot"]["healthy"] is healthy
        response = await client.head(path)
        assert response.status_code == (200 if healthy else 503)
        assert response.content == b""
        assert (await client.get("/health/live")).status_code == 200


@pytest.mark.asyncio
async def test_disabled_polling_does_not_claim_bot_is_healthy():
    runtime = BotRuntime(mode="disabled")
    await runtime.start()
    assert runtime.task is None
    assert runtime.health()["healthy"] is False
