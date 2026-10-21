"""Telegram transport lifecycle and health; business handlers stay unchanged."""
import asyncio
import logging
from datetime import datetime, timezone
from time import monotonic

from aiogram.methods import GetUpdates
from aiogram.exceptions import TelegramConflictError

logger = logging.getLogger(__name__)
ALLOWED_UPDATES = ["message", "callback_query", "inline_query", "my_chat_member", "chat_member"]


class WebhookConfiguredError(RuntimeError):
    """Polling must never silently remove a production webhook."""


class BotRuntime:
    def __init__(self, bot=None, dispatcher=None, mode="polling", *, retry_delay=2.0):
        self.bot = bot
        self.dispatcher = dispatcher
        self.mode = mode
        self.retry_delay = retry_delay
        self.task = None
        self.started_at = None
        self.last_poll_success_at = None
        self.last_update_at = None
        self.last_update_processed_at = None
        self.last_handler_error = None
        self.last_transport_error = None
        self.restart_count = 0
        self.conflict_count = 0
        self._last_poll_tick = None
        self._stopping = False
        self._hooks_installed = False

    async def observe_request(self, make_request, bot, method):
        if not isinstance(method, GetUpdates):
            return await make_request(bot, method)
        try:
            result = await make_request(bot, method)
        except Exception as exc:
            self.last_transport_error = type(exc).__name__
            if isinstance(exc, TelegramConflictError):
                self.conflict_count += 1
                logger.error("Telegram polling Conflict: stop the other process using this bot token")
            raise
        self.last_poll_success_at = datetime.now(timezone.utc).isoformat()
        self._last_poll_tick = monotonic()
        self.last_transport_error = None
        return result

    async def observe_update(self, handler, event, data):
        self.last_update_at = datetime.now(timezone.utc).isoformat()
        try:
            result = await handler(event, data)
        except Exception as exc:
            self.last_handler_error = type(exc).__name__
            raise
        self.last_update_processed_at = datetime.now(timezone.utc).isoformat()
        self.last_handler_error = None
        return result

    def install_hooks(self):
        if not self._hooks_installed:
            self.bot.session.middleware(self.observe_request)
            self.dispatcher.update.outer_middleware(self.observe_update)
            self._hooks_installed = True

    async def start(self):
        self.started_at = datetime.now(timezone.utc).isoformat()
        if self.mode == "disabled":
            return
        if not self.bot or not self.dispatcher:
            self.last_transport_error = "BotNotConfigured"
            return
        self.install_hooks()
        self._stopping = False
        self.task = asyncio.create_task(self._supervise_polling(), name="telegram-polling-supervisor")

    async def _supervise_polling(self):
        delay = self.retry_delay
        while not self._stopping:
            try:
                info = await asyncio.wait_for(self.bot.get_webhook_info(), timeout=20)
                if info.url:
                    raise WebhookConfiguredError("Remove webhook deliberately before switching to polling")
                logger.info("Starting Telegram polling; chat_member updates enabled")
                await self.dispatcher.start_polling(
                    self.bot, allowed_updates=ALLOWED_UPDATES,
                    handle_signals=False, close_bot_session=False,
                )
                if self._stopping:
                    return
                self.last_transport_error = "PollingStopped"
                logger.error("Telegram polling returned unexpectedly; restarting")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_transport_error = type(exc).__name__
                logger.error("Telegram polling stopped (%s); retrying in %.1fs", type(exc).__name__, delay)
            self.restart_count += 1
            await asyncio.sleep(delay)
            delay = min(max(delay * 2, self.retry_delay), 30)

    def health(self):
        running = self.task is not None and not self.task.done()
        age = None if self._last_poll_tick is None else max(0, monotonic() - self._last_poll_tick)
        if self.mode == "disabled":
            healthy = False
        else:
            # Empty getUpdates responses count as success; a quiet shop is healthy.
            healthy = running and age is not None and age < 120 and not self.last_transport_error
        healthy = healthy and not self.last_handler_error
        return {
            "healthy": bool(healthy), "mode": self.mode,
            "polling_task_alive": running,
            "started_at": self.started_at,
            "last_poll_success_at": self.last_poll_success_at,
            "last_update_at": self.last_update_at,
            "last_update_processed_at": self.last_update_processed_at,
            "last_transport_error": self.last_transport_error,
            "last_handler_error": self.last_handler_error,
            "restart_count": self.restart_count,
            "conflict_count": self.conflict_count,
        }

    async def stop(self):
        self._stopping = True
        if self.task:
            # Let aiogram cancel its own getUpdates/handler tasks before cancelling
            # the supervisor. Cancelling start_polling alone can orphan its children.
            stop_polling = getattr(self.dispatcher, "stop_polling", None)
            if stop_polling and not self.task.done():
                try:
                    await asyncio.wait_for(stop_polling(), timeout=10)
                except RuntimeError:
                    pass  # Still checking webhook state or waiting between attempts.
                except asyncio.TimeoutError:
                    logger.warning("Timed out waiting for Telegram polling shutdown")
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
