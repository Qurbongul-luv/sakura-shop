import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonWebApp, WebAppInfo
from sqlalchemy import select

from api.config import settings
from bot.loader import bot, dp
from bot.handlers import start, channel, admin, inline, orders, contest, admin_contest, channel_member
from db.models import Admin
from db.session import async_session_factory

logger = logging.getLogger(__name__)


def setup_routers(dp: Dispatcher):
    dp.include_router(start.router)
    dp.include_router(contest.router)
    dp.include_router(admin_contest.router)
    dp.include_router(channel_member.router)
    dp.include_router(channel.router)
    dp.include_router(admin.router)
    dp.include_router(inline.router)
    dp.include_router(orders.router)


async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Do'konni ochish 🌸"),
        BotCommand(command="admin", description="Admin paneli 👑"),
        BotCommand(command="cancel", description="Amalni bekor qilish ❌"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        # Set Menu Button to open Mini App directly
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🌸 Do'kon",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        )
    except Exception as e:
        logger.warning(f"Failed to configure bot commands or menu button: {e}")


async def notify_admins_of_error(error_message: str):
    """
    Sends admins a short DM when an unhandled error happens.
    """
    if not bot:
        return
    try:
        async with async_session_factory() as session:
            res = await session.execute(select(Admin))
            admins = res.scalars().all()
            for a in admins:
                try:
                    await bot.send_message(
                        chat_id=a.telegram_id,
                        text=f"⚠️ <b>Tizimda kutilmagan xatolik yuz berdi:</b>\n\n<code>{error_message[:3000]}</code>"
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Failed to notify admins of error: {e}")
