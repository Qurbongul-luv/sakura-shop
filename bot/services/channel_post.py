import logging
from typing import Dict, Any, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, FSInputFile
from pathlib import Path
from sqlalchemy import select

from api.config import settings
from api.services.formatters import build_channel_caption
from bot.loader import bot
from db.models import Product, Setting
from db.session import async_session_factory

logger = logging.getLogger(__name__)


async def post_product_to_channel(product: Product) -> Dict[str, Any]:
    if not bot:
        return {"success": False, "error": "Bot is not running"}

    async with async_session_factory() as session:
        # Get channel settings
        res_ch = await session.execute(select(Setting).where(Setting.key == "channel_id"))
        ch_setting = res_ch.scalars().first()
        channel_id = ch_setting.value if ch_setting else ""

        if not channel_id:
            return {"success": False, "error": "Kanal ulanmagan. Avval botni kanalingizga admin qiling."}

        # Get delivery terms & contact
        res_settings = await session.execute(select(Setting))
        settings_map = {s.key: s.value for s in res_settings.scalars().all()}

        cargo_rate = int(settings_map.get("cargo_rate", 12000))
        delivery_days = settings_map.get("delivery_days", "10–15 kun")
        delivery_scope = settings_map.get("delivery_scope", "O'zbekiston bo'ylab")
        contact_username = settings_map.get("contact_username", "fkhrdnvvvva")

        caption = build_channel_caption(
            category_slug=product.category,
            price=product.price,
            cargo_rate=cargo_rate,
            delivery_days=delivery_days,
            delivery_scope=delivery_scope,
            contact_username=contact_username,
            title=product.title,
        )

        # Get bot username for deep link
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        product_webapp_url = f"https://t.me/{bot_username}?startapp=product_{product.id}"

        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛍️ Do'konda ko'rish",
                        url=product_webapp_url,
                    )
                ]
            ]
        )

        media_dir = Path(settings.MEDIA_CACHE_DIR)
        photos = product.photos or []

        try:
            sent_msg_id = None
            if photos and len(photos) > 1:
                # Media album
                media_group: List[InputMediaPhoto] = []
                for idx, photo_id in enumerate(photos[:10]):
                    local_file = media_dir / photo_id
                    media_obj = FSInputFile(str(local_file)) if local_file.is_file() else photo_id
                    media_group.append(
                        InputMediaPhoto(
                            media=media_obj,
                            caption=caption if idx == 0 else None,
                        )
                    )
                messages = await bot.send_media_group(chat_id=channel_id, media=media_group)
                sent_msg_id = messages[0].message_id
                # Send follow-up button
                await bot.send_message(
                    chat_id=channel_id,
                    text="🌸 Mahsulotni Mini App orqali tomosha qilish va savatga qo'shish:",
                    reply_markup=reply_markup,
                )
            elif photos and len(photos) == 1:
                photo_id = photos[0]
                local_file = media_dir / photo_id
                photo_obj = FSInputFile(str(local_file)) if local_file.is_file() else photo_id
                msg = await bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_obj,
                    caption=caption,
                    reply_markup=reply_markup,
                )
                sent_msg_id = msg.message_id
            else:
                msg = await bot.send_message(
                    chat_id=channel_id,
                    text=caption,
                    reply_markup=reply_markup,
                )
                sent_msg_id = msg.message_id

            # Save message ID
            p_res = await session.execute(select(Product).where(Product.id == product.id))
            p_obj = p_res.scalars().first()
            if p_obj and sent_msg_id:
                p_obj.channel_message_id = sent_msg_id
                await session.commit()

            return {"success": True, "channel_message_id": sent_msg_id}

        except Exception as e:
            logger.error(f"Failed to post product #{product.id} to channel: {e}")
            return {"success": False, "error": str(e)}
