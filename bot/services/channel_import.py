"""
Turns channel posts into shop products.

Two entry points share this module:
- a new post in the linked channel (channel_post update) is imported automatically;
- an old post forwarded to the bot by an admin is imported the same way.

A Telegram album arrives as one message per photo with a shared media_group_id, and only one
of them carries the caption, so parts are collected for a moment before the product is built.
The caption-bearing message id is what the product remembers: it is what an edit or a second
forward of the same post refers to, so a post is never imported twice.
"""
import asyncio
import logging
from dataclasses import dataclass
from html import escape
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.services.formatters import format_price
from api.services.post_parser import ParsedPost, parse_product_post
from db.models import Admin, Category, Product

logger = logging.getLogger(__name__)

# Telegram delivers album parts within a second or two of each other.
ALBUM_WAIT_SECONDS = 2.5
MAX_PHOTOS = 10
DEFAULT_CATEGORY_SLUG = "boshqa"
DEFAULT_CATEGORY_NAME = "Boshqa"
NEW_CATEGORY_EMOJI = "🌸"

STATUS_CREATED = "created"
STATUS_DUPLICATE = "duplicate"
STATUS_NOT_PRODUCT = "not_product"
STATUS_NO_PHOTO = "no_photo"


@dataclass(frozen=True)
class IncomingPost:
    chat_id: int  # channel the post belongs to
    message_id: int  # id of the caption-bearing message inside that channel
    photos: Tuple[str, ...]
    caption: str


@dataclass(frozen=True)
class ImportResult:
    status: str
    parsed: ParsedPost
    product_id: Optional[int] = None
    title: Optional[str] = None
    category: Optional[str] = None


PostHandler = Callable[[IncomingPost], Awaitable[None]]


@dataclass(frozen=True)
class _Part:
    message_id: int
    photo_id: Optional[str]
    caption: str


def build_post(chat_id: int, parts: List[_Part]) -> IncomingPost:
    ordered = sorted(parts, key=lambda p: p.message_id)
    captioned = next((p for p in ordered if p.caption.strip()), None)
    anchor = captioned or ordered[0]
    return IncomingPost(
        chat_id=chat_id,
        message_id=anchor.message_id,
        photos=tuple(p.photo_id for p in ordered if p.photo_id)[:MAX_PHOTOS],
        caption=anchor.caption if captioned else "",
    )


class AlbumCollector:
    """Groups album parts by (receiving chat, media_group_id) and hands over one post per album."""

    def __init__(self, wait_seconds: float = ALBUM_WAIT_SECONDS) -> None:
        self._wait = wait_seconds
        self._parts: Dict[Tuple[int, str], List[_Part]] = {}
        self._sources: Dict[Tuple[int, str], int] = {}
        self._handlers: Dict[Tuple[int, str], PostHandler] = {}
        self._timers: Dict[Tuple[int, str], asyncio.Task] = {}

    @property
    def pending(self) -> int:
        return len(self._parts)

    async def add(
        self,
        *,
        receiving_chat_id: int,
        source_chat_id: int,
        message_id: int,
        media_group_id: Optional[str],
        photo_id: Optional[str],
        caption: Optional[str],
        handler: PostHandler,
    ) -> None:
        part = _Part(message_id=message_id, photo_id=photo_id, caption=caption or "")
        if not media_group_id:
            await self._run(handler, build_post(source_chat_id, [part]))
            return

        key = (receiving_chat_id, media_group_id)
        self._parts.setdefault(key, []).append(part)
        self._sources[key] = source_chat_id
        self._handlers[key] = handler
        previous = self._timers.get(key)
        if previous is not None:
            previous.cancel()  # still sleeping: the album is still arriving
        self._timers[key] = asyncio.create_task(self._flush_later(key))

    async def _flush_later(self, key: Tuple[int, str]) -> None:
        await asyncio.sleep(self._wait)
        # Taken out synchronously right after the sleep: a part arriving from now on starts a
        # new group instead of cancelling an import that is already running.
        parts = self._parts.pop(key, [])
        source = self._sources.pop(key, None)
        handler = self._handlers.pop(key, None)
        self._timers.pop(key, None)
        if parts and source is not None and handler is not None:
            await self._run(handler, build_post(source, parts))

    @staticmethod
    async def _run(handler: PostHandler, post: IncomingPost) -> None:
        try:
            await handler(post)
        except Exception:
            logger.exception(f"Channel post import failed for message {post.message_id} in {post.chat_id}")


async def ensure_category(session: AsyncSession, slug: Optional[str]) -> Category:
    """Existing category for the hashtag, or a new one so a new hashtag never blocks an import."""
    slug = slug or DEFAULT_CATEGORY_SLUG
    found = (await session.execute(select(Category).where(Category.slug == slug))).scalars().first()
    if found:
        return found

    max_order = (await session.execute(select(func.max(Category.sort_order)))).scalar() or 0
    name = DEFAULT_CATEGORY_NAME if slug == DEFAULT_CATEGORY_SLUG else slug.capitalize()
    try:
        async with session.begin_nested():
            created = Category(slug=slug, name=name, emoji=NEW_CATEGORY_EMOJI, sort_order=max_order + 1)
            session.add(created)
        return created
    except IntegrityError:
        # Another album created the same hashtag a moment ago.
        return (await session.execute(select(Category).where(Category.slug == slug))).scalars().one()


async def find_imported_product(session: AsyncSession, chat_id: int, message_id: int) -> Optional[Product]:
    # NULL chat: products the bot itself posted before channel_chat_id existed (one linked channel).
    stmt = select(Product).where(
        Product.channel_message_id == message_id,
        or_(Product.channel_chat_id == chat_id, Product.channel_chat_id.is_(None)),
    )
    return (await session.execute(stmt)).scalars().first()


async def import_post(session: AsyncSession, post: IncomingPost) -> ImportResult:
    parsed = parse_product_post(post.caption)
    if not parsed.is_product:
        return ImportResult(status=STATUS_NOT_PRODUCT, parsed=parsed)
    if not post.photos:
        return ImportResult(status=STATUS_NO_PHOTO, parsed=parsed)

    existing = await find_imported_product(session, post.chat_id, post.message_id)
    if existing:
        return ImportResult(
            status=STATUS_DUPLICATE, parsed=parsed, product_id=existing.id,
            title=existing.title, category=existing.category,
        )

    category = await ensure_category(session, parsed.category)
    product = Product(
        title=parsed.title or category.name,
        description=parsed.description,
        price=parsed.price,
        category=category.slug,
        photos=list(post.photos),
        sizes=list(parsed.sizes),
        colors=list(parsed.colors),
        weight_grams=parsed.weight_grams,
        in_stock=True,
        is_new=True,
        channel_chat_id=post.chat_id,
        channel_message_id=post.message_id,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    logger.info(f"Imported product #{product.id} from channel {post.chat_id} message {post.message_id}")
    return ImportResult(
        status=STATUS_CREATED, parsed=parsed, product_id=product.id,
        title=product.title, category=product.category,
    )


async def apply_post_edit(
    session: AsyncSession,
    chat_id: int,
    message_id: int,
    caption: Optional[str],
    single_photo_id: Optional[str],
) -> Optional[int]:
    """
    Keeps an imported product in step with an edited post. Stock state, badges and views stay;
    photos are replaced only for a single-photo post, since an album edit carries one photo.
    """
    product = await find_imported_product(session, chat_id, message_id)
    if product is None:
        return None
    parsed = parse_product_post(caption)
    if not parsed.is_product:
        return None  # price removed or post turned into something else: keep the product as is

    category = await ensure_category(session, parsed.category or product.category)
    product.title = parsed.title or category.name
    product.description = parsed.description
    product.price = parsed.price
    product.category = category.slug
    product.sizes = list(parsed.sizes)
    product.colors = list(parsed.colors)
    product.weight_grams = parsed.weight_grams
    if single_photo_id:
        product.photos = [single_photo_id]
    await session.commit()
    return product.id


def result_text(result: ImportResult, photo_count: int) -> str:
    parsed = result.parsed
    if result.status == STATUS_DUPLICATE:
        return f"♻️ Bu post allaqachon do'konda bor: <b>#{result.product_id}</b> {escape(result.title or '')}"
    if result.status == STATUS_NO_PHOTO:
        return "⚠️ Postda rasm yo'q, mahsulot qo'shilmadi."
    if result.status == STATUS_NOT_PRODUCT:
        if parsed.is_review:
            return "⭐ Bu fikr (#отзыв) posti, mahsulot emas."
        return "⚠️ Postda narx topilmadi (masalan: <code>Narx: 145.000</code>), mahsulot qo'shilmadi."

    sizes = ", ".join(parsed.sizes) or "—"
    colors = ", ".join(parsed.colors) or "—"
    return (
        f"🛍 <b>Kanal postidan mahsulot qo'shildi! (#{result.product_id})</b> 🌸\n\n"
        f"🏷️ <b>Kategoriya:</b> #{escape(result.category or '')}\n"
        f"🎀 <b>Nomi:</b> {escape(result.title or '')}\n"
        f"💰 <b>Narxi:</b> {format_price(parsed.price)}\n"
        f"📏 <b>O'lchamlar:</b> {escape(sizes)}\n"
        f"🎨 <b>Ranglar:</b> {escape(colors)}\n"
        f"📸 <b>Rasmlar:</b> {photo_count} ta\n\n"
        "<i>Xato bo'lsa, quyidan boshqaring yoki o'chiring.</i>"
    )


def result_markup(result: ImportResult) -> Optional[InlineKeyboardMarkup]:
    if result.status not in (STATUS_CREATED, STATUS_DUPLICATE) or result.product_id is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Boshqarish", callback_data=f"admin_prod_manage_{result.product_id}"),
                InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"admin_confirm_delete_prod_{result.product_id}"),
            ]
        ]
    )


async def admin_chat_ids(session: AsyncSession) -> List[int]:
    ids = [a.telegram_id for a in (await session.execute(select(Admin))).scalars().all()]
    if settings.DEV_ADMIN_ID and settings.DEV_ADMIN_ID not in ids:
        ids.append(settings.DEV_ADMIN_ID)
    return ids


async def notify_admins(bot: Bot, session: AsyncSession, result: ImportResult, photo_count: int) -> None:
    text = result_text(result, photo_count)
    markup = result_markup(result)
    for chat_id in await admin_chat_ids(session):
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        except Exception as e:
            logger.info(f"Could not notify admin {chat_id} about imported product: {e}")
