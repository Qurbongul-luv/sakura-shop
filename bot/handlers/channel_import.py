import logging

from aiogram import Bot, F, Router
from aiogram.types import Message

from bot.services.channel_import import (
    STATUS_CREATED,
    AlbumCollector,
    IncomingPost,
    apply_post_edit,
    import_post,
    notify_admins,
)
from bot.services.contest_service import get_channel_info
from db.session import async_session_factory

router = Router(name="channel_import")
logger = logging.getLogger(__name__)

# One collector for the process: album parts of a channel post arrive as separate updates.
channel_albums = AlbumCollector()


async def is_linked_channel(chat_id: int) -> bool:
    async with async_session_factory() as session:
        linked, _ = await get_channel_info(session)
    return linked is not None and str(chat_id) == str(linked)


async def import_channel_post_and_notify(bot: Bot, post: IncomingPost) -> None:
    async with async_session_factory() as session:
        result = await import_post(session, post)
        # Only new products are worth a DM; every other channel post (news, contests) stays silent.
        if result.status == STATUS_CREATED:
            await notify_admins(bot, session, result, len(post.photos))


@router.channel_post(F.photo)
async def handle_new_channel_post(message: Message):
    if not await is_linked_channel(message.chat.id):
        return
    bot = message.bot

    async def handler(post: IncomingPost) -> None:
        await import_channel_post_and_notify(bot, post)

    await channel_albums.add(
        receiving_chat_id=message.chat.id,
        source_chat_id=message.chat.id,
        message_id=message.message_id,
        media_group_id=message.media_group_id,
        photo_id=message.photo[-1].file_id,
        caption=message.caption,
        handler=handler,
    )


@router.edited_channel_post()
async def handle_edited_channel_post(message: Message):
    if not await is_linked_channel(message.chat.id):
        return
    single_photo = message.photo[-1].file_id if message.photo and not message.media_group_id else None
    async with async_session_factory() as session:
        product_id = await apply_post_edit(
            session, message.chat.id, message.message_id, message.caption or message.text, single_photo
        )
    if product_id is not None:
        logger.info(f"Product #{product_id} updated from edited channel post {message.message_id}")
        return
    # A single-photo post that only now got its price becomes a product; album edits carry one
    # photo, so those are left for a forward instead of importing an incomplete product.
    if single_photo:
        await import_channel_post_and_notify(
            message.bot,
            IncomingPost(
                chat_id=message.chat.id,
                message_id=message.message_id,
                photos=(single_photo,),
                caption=message.caption or "",
            )
        )
