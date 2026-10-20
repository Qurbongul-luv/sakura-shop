from html import escape
import logging
from aiogram import Router, F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import select, or_

from api.config import settings
from api.services.formatters import format_price, calculate_cargo
from bot.loader import bot
from db.models import Product
from db.session import async_session_factory

router = Router(name="inline")
logger = logging.getLogger(__name__)


@router.inline_query()
async def handle_inline_search(inline_query: InlineQuery):
    query_text = inline_query.query.strip().lower()
    clean_search = query_text.replace("#", "")

    async with async_session_factory() as session:
        query = select(Product).where(Product.in_stock == True)
        if clean_search:
            term = f"%{clean_search}%"
            query = query.where(
                or_(
                    Product.title.ilike(term),
                    Product.description.ilike(term),
                    Product.category.ilike(term),
                )
            )
        query = query.limit(15)
        res = await session.execute(query)
        products = res.scalars().all()

    bot_info = await bot.get_me() if bot else None
    bot_username = bot_info.username if bot_info else "sakura_shop_bot"

    results = []
    for prod in products:
        cargo = calculate_cargo(prod.weight_grams)
        caption = (
            f"🌸 <b>{escape(prod.title)}</b>\n"
            f"💰 Narxi: <b>{format_price(prod.price)}</b>\n"
            f"📦 Kargo: ~{format_price(cargo)}\n\n"
            f"💌 Buyurtma berish uchun @fkhrdnvvvva ga yozing"
        )

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛍️ Do'konda ko'rish",
                        url=f"https://t.me/{bot_username}?startapp=product_{prod.id}",
                    )
                ]
            ]
        )

        results.append(
            InlineQueryResultArticle(
                id=str(prod.id),
                title=f"{prod.title} — {format_price(prod.price)}",
                description=f"#{prod.category} | {prod.description[:60] if prod.description else 'Sakura shop'}",
                input_message_content=InputTextMessageContent(
                    message_text=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        )

    await inline_query.answer(results=results, cache_time=30, is_personal=False)
