import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, inspect, select, text

from api.services.post_parser import parse_amount, parse_product_post
from bot.handlers import channel_import as channel_handlers
from bot.runtime import ALLOWED_UPDATES
from bot.services.channel_import import (
    STATUS_CREATED,
    STATUS_DUPLICATE,
    STATUS_NO_PHOTO,
    STATUS_NOT_PRODUCT,
    AlbumCollector,
    IncomingPost,
    apply_post_edit,
    import_post,
    result_markup,
    result_text,
)
from db.models import Category, Product, Setting
from db.session import _add_missing_columns

CHANNEL_ID = -1001234567890

# The exact post from the Sakura shop channel screenshot.
BOOTS_POST = (
    "#boots\n\n"
    "🤎Narx: 145.000\n"
    "🤎Razmerlari bor\n"
    "🤎Ranglari: qora, jigarrang, молочный\n"
    "🤎Kargo: 100gr-12.000\n"
    "🤎Yetkazib berish: 10 kunda\n"
    "🤎Dastavka: O'zbekiston bo'ylab\n"
    "🐱Buyurtma berish uchun @fkhrdnvvvva ga yozing"
)

# The caption format the bot itself posts (build_channel_caption).
BOT_POST = (
    "#jempir 🌸\n✨ Pushti jempir\n💰 Narxi: 99.000 so'm\n"
    "📦 Kargo: 12.000 so'm / 100g\n⏳ 10–15 kun\n🚚 Dastavka: O'zbekiston bo'ylab\n"
    "Buyurtma berish uchun @fkhrdnvvvva ga yozing 💌"
)


# ==================== PARSER ====================
def test_parses_real_channel_post():
    p = parse_product_post(BOOTS_POST)
    assert p.is_product
    assert p.category == "boots"
    assert p.price == 145000
    assert p.colors == ("qora", "jigarrang", "молочный")
    assert p.sizes == ()  # "Razmerlari bor" names no sizes
    assert p.title is None  # no title in the post: the importer falls back to the category name
    assert p.description == BOOTS_POST


def test_parses_bot_own_caption_with_title():
    p = parse_product_post(BOT_POST)
    assert (p.category, p.title, p.price) == ("jempir", "Pushti jempir", 99000)


def test_cargo_and_delivery_numbers_are_never_the_price():
    p = parse_product_post("#sumka\nKargo: 100gr-12.000\nYetkazib berish: 10 kunda")
    assert p.price == 0
    assert not p.is_product


def test_non_product_posts_are_ignored():
    assert not parse_product_post("🌸 SAKURA KONKURS 🌸\n🥇 1-o'rin: Jeans pants").is_product
    assert not parse_product_post("").is_product
    assert not parse_product_post(None).is_product
    review = parse_product_post("#отзыв Rahmat, juda zo'r!")
    assert review.is_review and not review.is_product


def test_review_tag_wins_even_with_a_price():
    assert not parse_product_post("#отзыв\nNarx: 145.000 edi, arzimaydi").is_product


@pytest.mark.parametrize(
    "value,expected",
    [
        ("145.000", 145000), ("145 000 so'm", 145000), ("1.250.000", 1250000), ("99000", 99000),
        ("145,000", 145000), ("145k", 145000), ("145 ming", 145000), ("120", 0), ("kelishilgan", 0),
    ],
)
def test_parse_amount(value, expected):
    assert parse_amount(value) == expected


def test_labels_with_variants_and_typographic_apostrophes():
    p = parse_product_post(
        "#sharf\n• Narxi 85 000 so'm\n• Oʻlchamlari: S, M, L\n• Ranglar: oq va qora\n• Vazni: 0,5 kg"
    )
    assert p.price == 85000
    assert p.sizes == ("S", "M", "L")
    assert p.colors == ("oq", "qora")
    assert p.weight_grams == 500


def test_title_label_needs_a_colon():
    assert parse_product_post("#wig\nMahsulot sifati zo'r\nNarx: 200.000").title is None
    assert parse_product_post("#wig\nNomi: Lolita parik\nNarx: 200.000").title == "Lolita parik"


def test_unlabelled_price_only_with_currency_word():
    assert parse_product_post("#aksessuar\nBrelok 35.000 so'm").price == 35000
    assert parse_product_post("#aksessuar\nBrelok 35.000").price == 0


def test_cyrillic_hashtag_becomes_category():
    assert parse_product_post("#сумка\nЦена: 150 000 сум").category == "сумка"


# ==================== ALBUM COLLECTOR ====================
async def _add(collector, handler, message_id, group, photo, caption=None, receiving=CHANNEL_ID):
    await collector.add(
        receiving_chat_id=receiving, source_chat_id=CHANNEL_ID, message_id=message_id,
        media_group_id=group, photo_id=photo, caption=caption, handler=handler,
    )


@pytest.mark.asyncio
async def test_album_parts_become_one_post_with_caption_anchor():
    got = []

    async def handler(post):
        got.append(post)

    collector = AlbumCollector(wait_seconds=0.05)
    # Parts may arrive out of order; the caption sits on the second message here.
    await _add(collector, handler, 12, "g1", "p3")
    await _add(collector, handler, 11, "g1", "p2", caption=BOOTS_POST)
    await _add(collector, handler, 10, "g1", "p1")
    assert got == []
    await asyncio.sleep(0.15)

    assert len(got) == 1
    assert got[0] == IncomingPost(chat_id=CHANNEL_ID, message_id=11, photos=("p1", "p2", "p3"), caption=BOOTS_POST)
    assert collector.pending == 0


@pytest.mark.asyncio
async def test_single_photo_post_is_handled_immediately():
    got = []

    async def handler(post):
        got.append(post)

    collector = AlbumCollector(wait_seconds=10)
    await _add(collector, handler, 5, None, "only", caption=BOOTS_POST)
    assert got == [IncomingPost(chat_id=CHANNEL_ID, message_id=5, photos=("only",), caption=BOOTS_POST)]


@pytest.mark.asyncio
async def test_two_albums_and_two_admins_stay_separate():
    got = []

    async def handler(post):
        got.append(post)

    collector = AlbumCollector(wait_seconds=0.05)
    await _add(collector, handler, 1, "a", "a1", caption="A")
    await _add(collector, handler, 2, "b", "b1", caption="B")
    await _add(collector, handler, 3, "a", "x1", caption="X", receiving=111)
    await asyncio.sleep(0.15)
    assert sorted(p.caption for p in got) == ["A", "B", "X"]


@pytest.mark.asyncio
async def test_handler_error_does_not_break_collector():
    async def broken(post):
        raise RuntimeError("db down")

    collector = AlbumCollector(wait_seconds=0.01)
    await _add(collector, broken, 1, None, "p", caption=BOOTS_POST)  # logged, not raised
    await _add(collector, broken, 2, "g", "p", caption=BOOTS_POST)
    await asyncio.sleep(0.05)
    assert collector.pending == 0


# ==================== IMPORT INTO THE SHOP ====================
def _post(message_id=100, photos=("f1", "f2", "f3"), caption=BOOTS_POST, chat_id=CHANNEL_ID):
    return IncomingPost(chat_id=chat_id, message_id=message_id, photos=tuple(photos), caption=caption)


@pytest.mark.asyncio
async def test_import_creates_product_and_new_category(test_db_session):
    async with test_db_session() as session:
        result = await import_post(session, _post())
        assert result.status == STATUS_CREATED

        prod = (await session.execute(select(Product).where(Product.id == result.product_id))).scalars().one()
        assert prod.title == "Boots"
        assert prod.price == 145000
        assert prod.category == "boots"
        assert prod.photos == ["f1", "f2", "f3"]
        assert prod.colors == ["qora", "jigarrang", "молочный"]
        assert prod.sizes == []
        assert prod.in_stock and prod.is_new
        assert (prod.channel_chat_id, prod.channel_message_id) == (CHANNEL_ID, 100)

        cat = (await session.execute(select(Category).where(Category.slug == "boots"))).scalars().one()
        assert cat.name == "Boots"
        assert cat.sort_order == 4  # after the three seeded categories


@pytest.mark.asyncio
async def test_same_post_is_never_imported_twice(test_db_session):
    async with test_db_session() as session:
        first = await import_post(session, _post())
        again = await import_post(session, _post(photos=("other",)))
        assert again.status == STATUS_DUPLICATE
        assert again.product_id == first.product_id
        # Same message id in another channel is a different post.
        other_channel = await import_post(session, _post(chat_id=-100999))
        assert other_channel.status == STATUS_CREATED
        count = (await session.execute(select(Product).where(Product.channel_message_id == 100))).all()
        assert len(count) == 2


@pytest.mark.asyncio
async def test_post_the_bot_published_itself_is_recognised(test_db_session):
    async with test_db_session() as session:
        bot_made = (await session.execute(select(Product).where(Product.id == 1))).scalars().one()
        bot_made.channel_message_id = 77  # posted before channel_chat_id existed
        await session.commit()

        result = await import_post(session, _post(message_id=77, caption=BOT_POST))
        assert result.status == STATUS_DUPLICATE and result.product_id == 1


@pytest.mark.asyncio
async def test_existing_category_and_title_are_used(test_db_session):
    async with test_db_session() as session:
        result = await import_post(session, _post(caption=BOT_POST))
        prod = (await session.execute(select(Product).where(Product.id == result.product_id))).scalars().one()
        assert (prod.category, prod.title) == ("jempir", "Pushti jempir")
        cats = (await session.execute(select(Category))).scalars().all()
        assert len(cats) == 3


@pytest.mark.asyncio
async def test_post_without_hashtag_goes_to_default_category(test_db_session):
    async with test_db_session() as session:
        result = await import_post(session, _post(caption="Narx: 50.000"))
        assert result.status == STATUS_CREATED
        assert result.category == "boshqa" and result.title == "Boshqa"


@pytest.mark.asyncio
async def test_non_product_and_photo_less_posts_are_skipped(test_db_session):
    async with test_db_session() as session:
        before = len((await session.execute(select(Product))).all())
        assert (await import_post(session, _post(caption="🌸 SAKURA KONKURS"))).status == STATUS_NOT_PRODUCT
        assert (await import_post(session, _post(photos=()))).status == STATUS_NO_PHOTO
        assert len((await session.execute(select(Product))).all()) == before


@pytest.mark.asyncio
async def test_edited_post_updates_product_but_keeps_shop_state(test_db_session):
    async with test_db_session() as session:
        created = await import_post(session, _post())
        prod = (await session.execute(select(Product).where(Product.id == created.product_id))).scalars().one()
        prod.in_stock = False
        prod.is_hit = True
        await session.commit()

        edited = BOOTS_POST.replace("145.000", "129.000").replace("#boots", "#etik")
        assert await apply_post_edit(session, CHANNEL_ID, 100, edited, None) == created.product_id
        await session.refresh(prod)
        assert prod.price == 129000 and prod.category == "etik"
        assert prod.in_stock is False and prod.is_hit is True
        assert prod.photos == ["f1", "f2", "f3"]  # album edit never drops the other photos

        # Price removed: keep the product as it was.
        assert await apply_post_edit(session, CHANNEL_ID, 100, "Sotildi!", None) is None
        await session.refresh(prod)
        assert prod.price == 129000

        assert await apply_post_edit(session, CHANNEL_ID, 555, BOOTS_POST, None) is None


def test_result_texts_and_buttons():
    created = parse_product_post(BOOTS_POST)
    from bot.services.channel_import import ImportResult

    ok = ImportResult(status=STATUS_CREATED, parsed=created, product_id=7, title="Boots", category="boots")
    text_ok = result_text(ok, 3)
    assert "#7" in text_ok and "145.000 so'm" in text_ok and "молочный" in text_ok and "3 ta" in text_ok
    buttons = [b.callback_data for row in result_markup(ok).inline_keyboard for b in row]
    assert buttons == ["admin_prod_manage_7", "admin_confirm_delete_prod_7"]

    skipped = ImportResult(status=STATUS_NOT_PRODUCT, parsed=parse_product_post("salom"))
    assert "narx topilmadi" in result_text(skipped, 0)
    assert result_markup(skipped) is None


# ==================== TELEGRAM WIRING ====================
def test_polling_asks_for_channel_posts():
    assert "channel_post" in ALLOWED_UPDATES
    assert "edited_channel_post" in ALLOWED_UPDATES


def _channel_message(chat_id, message_id, caption, media_group_id=None, bot=None):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        message_id=message_id,
        media_group_id=media_group_id,
        photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id=f"big{message_id}")],
        caption=caption,
        text=None,
        bot=bot or AsyncMock(),
    )


@pytest.mark.asyncio
async def test_live_channel_post_is_imported_and_admins_notified(test_db_session, monkeypatch):
    monkeypatch.setattr(channel_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        ch = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().one()
        ch.value = str(CHANNEL_ID)
        await session.commit()

    bot = AsyncMock()
    await channel_handlers.handle_new_channel_post(_channel_message(CHANNEL_ID, 300, BOOTS_POST, bot=bot))
    # Posts from any other channel are not ours.
    await channel_handlers.handle_new_channel_post(_channel_message(-100555, 301, BOOTS_POST, bot=bot))

    async with test_db_session() as session:
        prods = (await session.execute(select(Product).where(Product.channel_message_id.in_([300, 301])))).scalars().all()
        assert [(p.channel_message_id, p.photos) for p in prods] == [(300, ["big300"])]

    # DEV_ADMIN_ID from the test env receives the notice.
    assert bot.send_message.await_count == 1
    assert bot.send_message.await_args.kwargs["chat_id"] == 999999999


@pytest.mark.asyncio
async def test_live_news_post_stays_silent(test_db_session, monkeypatch):
    monkeypatch.setattr(channel_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        ch = (await session.execute(select(Setting).where(Setting.key == "channel_id"))).scalars().one()
        ch.value = str(CHANNEL_ID)
        await session.commit()

    bot = AsyncMock()
    await channel_handlers.handle_new_channel_post(_channel_message(CHANNEL_ID, 400, "Bugun dam olish kuni 🌸", bot=bot))
    bot.send_message.assert_not_awaited()


def test_missing_column_is_added_to_an_existing_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE contests (id INTEGER PRIMARY KEY, extra_prizes JSON)"))
        conn.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, channel_message_id INTEGER)"))
        _add_missing_columns(conn)
        _add_missing_columns(conn)  # second start-up must be a no-op
        cols = {c["name"] for c in inspect(conn).get_columns("products")}
    assert "channel_chat_id" in cols


def _forwarded_message(origin_message_id, caption, media_group_id=None, photo="fwd", bot=None):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=999999999),  # DEV_ADMIN_ID in the test env
        chat=SimpleNamespace(id=999999999),
        forward_origin=SimpleNamespace(chat=SimpleNamespace(id=CHANNEL_ID), message_id=origin_message_id),
        media_group_id=media_group_id,
        photo=[SimpleNamespace(file_id=f"{photo}{origin_message_id}")] if photo else None,
        caption=caption,
        text=None,
        bot=bot or AsyncMock(),
    )


@pytest.mark.asyncio
async def test_forwarded_old_post_is_imported_once(test_db_session, monkeypatch):
    from bot.handlers import admin as admin_handlers

    monkeypatch.setattr(admin_handlers, "async_session_factory", test_db_session)
    bot = AsyncMock()
    await admin_handlers.handle_forwarded_post(_forwarded_message(900, BOOTS_POST, bot=bot), state=None)
    await admin_handlers.handle_forwarded_post(_forwarded_message(900, BOOTS_POST, bot=bot), state=None)

    async with test_db_session() as session:
        prods = (await session.execute(select(Product).where(Product.channel_message_id == 900))).scalars().all()
    assert len(prods) == 1 and prods[0].photos == ["fwd900"] and prods[0].channel_chat_id == CHANNEL_ID
    replies = [c.kwargs["text"] for c in bot.send_message.await_args_list]
    assert "qo'shildi" in replies[0] and "allaqachon" in replies[1]


@pytest.mark.asyncio
async def test_forwarded_priced_post_saying_rahmat_is_a_product_not_a_review(test_db_session, monkeypatch):
    from bot.handlers import admin as admin_handlers

    monkeypatch.setattr(admin_handlers, "async_session_factory", test_db_session)
    bot = AsyncMock()
    msg = _forwarded_message(901, BOOTS_POST + "\nXaridingiz uchun rahmat!", bot=bot)
    msg.answer = AsyncMock()
    await admin_handlers.handle_forwarded_post(msg, state=None)

    async with test_db_session() as session:
        assert (await session.execute(select(Product).where(Product.channel_message_id == 901))).scalars().first()
    msg.answer.assert_not_awaited()  # the review branch answers via message.answer
