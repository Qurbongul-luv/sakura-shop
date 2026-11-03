import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select

from api.config import settings
from api.services.taobao import (
    PriceRule,
    TaobaoItem,
    calculate_price,
    find_taobao_link,
    normalize_image_url,
    parse_item,
    parse_rule_input,
    rule_from_settings,
    rule_to_settings,
)
from bot.handlers import taobao_import as tb
from bot.services import taobao_client
from bot.services.taobao_client import TaobaoFetchError, download_image, fetch_item, resolve_short_link
from db.models import Product, Setting

IMG = "https://img.alicdn.com/imgextra/i3/1/O1CN01abc_!!1.jpg"


# ==================== LINKS ====================
@pytest.mark.parametrize(
    "text,item_id",
    [
        ("https://item.taobao.com/item.htm?id=730344766230", "730344766230"),
        ("qarang https://item.taobao.com/item.htm?spm=a1z10&id=730344766230&ns=1 shu", "730344766230"),
        ("https://detail.tmall.com/item.htm?id=612345678901&skuId=1", "612345678901"),
        ("https://world.taobao.com/item/730344766230.htm", "730344766230"),
        ("https://h5.m.taobao.com/awp/core/detail.htm?id=700000000001", "700000000001"),
    ],
)
def test_full_links_give_item_id(text, item_id):
    link = find_taobao_link(text)
    assert link is not None and link.item_id == item_id and not link.is_short


def test_app_share_text_gives_short_link():
    share = "【淘宝】假一赔四 https://m.tb.cn/h.5xYzAbC?tk=abc CZ0001 「女士短靴」点击链接直接打开"
    link = find_taobao_link(share)
    assert link is not None and link.is_short and link.url == "https://m.tb.cn/h.5xYzAbC?tk=abc"


@pytest.mark.parametrize(
    "text",
    [
        "salom", "", None, "https://google.com/?id=730344766230",
        "https://item.taobao.com.evil.com/item.htm?id=730344766230",  # look-alike host
        "https://item.taobao.com/item.htm",  # no id
    ],
)
def test_non_taobao_text_is_ignored(text):
    assert find_taobao_link(text) is None


# ==================== PRICE ====================
def test_price_formula_rounds_up():
    rule = PriceRule(yuan_rate=1800, markup_percent=30, markup_fixed=20000, round_to=1000)
    assert calculate_price(100, rule) == 254000  # 100*1800*1.3 + 20000
    assert calculate_price(89.5, PriceRule(yuan_rate=1800)) == 162000  # 161100 → up to 162000
    assert calculate_price(10, PriceRule(yuan_rate=1800, round_to=5000)) == 20000
    assert calculate_price(100, PriceRule(yuan_rate=0)) == 0  # not configured
    assert calculate_price(0, rule) == 0


def test_exact_step_is_not_bumped_by_float_noise():
    assert 15.0 * 1800 * (1 + 10 / 100) > 29700  # float noise: 29700.000000000004
    assert calculate_price(15.0, PriceRule(yuan_rate=1800, markup_percent=10, round_to=100)) == 29700


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1800 30 20000 1000", PriceRule(1800, 30, 20000, 1000)),
        ("1800 30", PriceRule(1800, 30, 0, 1000)),
        ("kurs 1800, foiz 25", PriceRule(1800, 25, 0, 1000)),
        ("1800 12,5 20.000", PriceRule(1800, 12.5, 20000, 1000)),
        ("1.800 30", PriceRule(1800, 30, 0, 1000)),
    ],
)
def test_rule_input(text, expected):
    assert parse_rule_input(text) == expected


@pytest.mark.parametrize("text", ["", "salom", "1800", "1 800 30", "1800 30 1 2 3", "0 30", "1800 5000"])
def test_rule_input_rejects_unclear_text(text):
    assert parse_rule_input(text) is None


def test_rule_settings_round_trip_and_bad_values():
    rule = PriceRule(1800, 12.5, 20000, 500)
    assert rule_from_settings(rule_to_settings(rule)) == rule
    assert rule_from_settings({}) == PriceRule(0, 0.0, 0, 1000)
    assert rule_from_settings({"taobao_yuan_rate": "abc", "taobao_round_to": "0"}).round_to == 1000


# ==================== SCRAPER ROW ====================
def test_parse_item_prefers_promo_and_cleans_images():
    row = {
        "itemId": "730344766230", "title": "女士短靴", "price": 129, "promoPrice": 99.5,
        "imageUrl": "//img.alicdn.com/a.jpg",
        "images": ["//img.alicdn.com/a.jpg", "http://gw.alicdn.com/b.jpg", "https://evil.com/c.jpg", None, 5],
        "categoryPath": ["女鞋", "靴子"],
    }
    item = parse_item(row)
    assert item == TaobaoItem(
        item_id="730344766230", title="女士短靴", price_yuan=99.5,
        images=("https://img.alicdn.com/a.jpg", "https://gw.alicdn.com/b.jpg"),
        url="https://item.taobao.com/item.htm?id=730344766230", category_path=("女鞋", "靴子"),
    )


@pytest.mark.parametrize(
    "row",
    [
        {"itemId": "1234567", "price": None, "imageUrl": IMG},
        {"itemId": "1234567", "price": 0, "imageUrl": IMG},
        {"itemId": "1234567", "price": 50, "imageUrl": "https://evil.com/x.jpg"},
        {"itemId": "abc", "price": 50, "imageUrl": IMG},
        "not a dict",
    ],
)
def test_parse_item_rejects_unusable_rows(row):
    assert parse_item(row) is None


def test_normalize_image_url_only_allows_taobao_cdn():
    assert normalize_image_url("//img.alicdn.com/x.jpg") == "https://img.alicdn.com/x.jpg"
    assert normalize_image_url("https://alicdn.com.evil.net/x.jpg") is None
    assert normalize_image_url("ftp://img.alicdn.com/x.jpg") is None


# ==================== APIFY CLIENT ====================
def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def apify_token(monkeypatch):
    monkeypatch.setattr(settings, "APIFY_TOKEN", "test-token")
    monkeypatch.setattr(taobao_client, "RETRY_BACKOFF_SECONDS", 0)


@pytest.mark.asyncio
async def test_fetch_item_success_sends_token_in_header(apify_token):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[{"itemId": "730344766230", "title": "t", "price": 49.9, "imageUrl": IMG}])

    async with _client(handler) as client:
        item = await fetch_item("730344766230", client=client)
    assert item.price_yuan == 49.9 and item.images == (IMG,)
    assert seen["auth"] == "Bearer test-token"
    assert "token=" not in seen["url"]  # never in the URL, where it would end up in logs
    assert seen["body"] == {"productUrls": ["730344766230"], "maxConcurrency": 1}


@pytest.mark.asyncio
async def test_fetch_item_retries_server_errors(apify_token):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(502)
        return httpx.Response(200, json=[{"itemId": "123456789", "price": 10, "imageUrl": IMG}])

    async with _client(handler) as client:
        assert (await fetch_item("123456789", client=client)).item_id == "123456789"
    assert calls["n"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,needle", [(401, "token"), (402, "krediti"), (404, "actor"), (408, "sekin"), (400, "400")]
)
async def test_fetch_item_explains_errors(apify_token, status, needle):
    async with _client(lambda r: httpx.Response(status, json={"error": "x"})) as client:
        with pytest.raises(TaobaoFetchError) as err:
            await fetch_item("123456789", client=client)
    assert needle in str(err.value)


@pytest.mark.asyncio
async def test_fetch_item_unreadable_and_network_failure(apify_token):
    async with _client(lambda r: httpx.Response(200, json=[])) as client:
        with pytest.raises(TaobaoFetchError, match="o'qib bo'lmadi"):
            await fetch_item("123456789", client=client)

    def boom(request):
        raise httpx.ConnectError("down")

    async with _client(boom) as client:
        with pytest.raises(TaobaoFetchError, match="ulanib"):
            await fetch_item("123456789", client=client)


@pytest.mark.asyncio
async def test_fetch_item_without_token_says_how_to_enable(monkeypatch):
    monkeypatch.setattr(settings, "APIFY_TOKEN", None)
    with pytest.raises(TaobaoFetchError, match="APIFY_TOKEN"):
        await fetch_item("123456789")


# ==================== SHORT LINKS & IMAGES ====================
@pytest.mark.asyncio
async def test_short_link_follows_redirect_to_product():
    def handler(request):
        if request.url.host == "m.tb.cn":
            return httpx.Response(302, headers={"location": "https://item.taobao.com/item.htm?id=730344766230"})
        raise AssertionError("product page must not be fetched once the id is known")

    async with _client(handler) as client:
        assert await resolve_short_link("https://m.tb.cn/h.abc", client=client) == "730344766230"


@pytest.mark.asyncio
async def test_short_link_reads_id_from_share_page():
    body = "<script>var url = 'https://a.m.taobao.com/i700000000002.htm?price=1';</script>"
    async with _client(lambda r: httpx.Response(200, text=body)) as client:
        assert await resolve_short_link("https://m.tb.cn/h.abc", client=client) == "700000000002"


@pytest.mark.asyncio
async def test_short_link_never_follows_foreign_hosts():
    hits = []

    def handler(request):
        hits.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://evil.com/?id=730344766230"})

    async with _client(handler) as client:
        with pytest.raises(TaobaoFetchError):
            await resolve_short_link("https://m.tb.cn/h.abc", client=client)
    assert hits == ["m.tb.cn"]


@pytest.mark.asyncio
async def test_download_image_checks_host_type_and_size(monkeypatch):
    monkeypatch.setattr(taobao_client, "MAX_IMAGE_BYTES", 10)

    def handler(request):
        if request.url.path == "/ok.jpg":
            return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"12345")
        if request.url.path == "/big.jpg":
            return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"x" * 50)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>")

    async with _client(handler) as client:
        assert await download_image("https://img.alicdn.com/ok.jpg", client=client) == b"12345"
        assert await download_image("https://img.alicdn.com/big.jpg", client=client) is None
        assert await download_image("https://img.alicdn.com/page", client=client) is None
        assert await download_image("https://evil.com/ok.jpg", client=client) is None


# ==================== BOT FLOW ====================
def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=999999999, user_id=999999999))


def _message(text, bot):
    status = SimpleNamespace(edit_text=AsyncMock())
    msg = SimpleNamespace(
        text=text, caption=None, chat=SimpleNamespace(id=999999999), from_user=SimpleNamespace(id=999999999),
        bot=bot, answer=AsyncMock(return_value=status),
    )
    return msg, status


def _bot():
    bot = MagicMock()
    sent = [SimpleNamespace(photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id=f"tg{i}")]) for i in range(2)]
    bot.send_media_group = AsyncMock(return_value=sent)
    return bot


@pytest.fixture
def flow(test_db_session, monkeypatch):
    monkeypatch.setattr(tb, "async_session_factory", test_db_session)
    item = TaobaoItem("730344766230", "女士短靴", 100.0, (IMG, IMG + "2"), "https://item.taobao.com/x", ())
    monkeypatch.setattr(tb, "fetch_item", AsyncMock(return_value=item))
    monkeypatch.setattr(tb, "download_image", AsyncMock(return_value=b"jpegbytes"))
    monkeypatch.setattr(tb, "post_product_to_channel", AsyncMock(return_value={"success": True}))
    return test_db_session


def _callback(data, message):
    return SimpleNamespace(data=data, message=message, answer=AsyncMock(), from_user=SimpleNamespace(id=999999999))


@pytest.mark.asyncio
async def test_full_flow_asks_formula_once_then_saves(flow):
    bot, state = _bot(), _state()
    link = find_taobao_link("https://item.taobao.com/item.htm?id=730344766230")

    msg, _ = _message(link.url, bot)
    await tb.handle_taobao_link(msg, state, link)
    assert await state.get_state() == tb.TaobaoPricing.waiting_rule.state  # formula first

    msg, status = _message("1800 30 20000 1000", bot)
    await tb.handle_rule_input(msg, state)
    assert await state.get_state() == tb.TaobaoImport.title.state  # pending link continued
    data = await state.get_data()
    assert data["price"] == 254000 and data["photos"] == ["tg0", "tg1"]
    assert "254.000 so'm" in status.edit_text.await_args.args[0]

    await tb.step_title(_message("Ayollar etigi", bot)[0], state)
    reply_target, _ = _message("", bot)
    await tb.step_category(_callback("tb_cat:jempir", reply_target), state)
    await tb.step_colors(_message("qora, jigarrang", bot)[0], state)
    await tb.step_sizes(_message("36, 37, 38", bot)[0], state)
    assert await state.get_state() == tb.TaobaoImport.confirm.state

    await tb.step_save(_callback("tb_save_post", reply_target), state)
    assert await state.get_state() is None
    tb.post_product_to_channel.assert_awaited_once()

    async with flow() as session:
        prod = (await session.execute(select(Product).where(Product.taobao_item_id == "730344766230"))).scalars().one()
        assert (prod.title, prod.price, prod.category) == ("Ayollar etigi", 254000, "jempir")
        assert (prod.colors, prod.sizes, prod.photos) == (["qora", "jigarrang"], ["36", "37", "38"], ["tg0", "tg1"])
        assert prod.description == ""  # the Taobao source is never shown to customers
        rate = (await session.execute(select(Setting).where(Setting.key == "taobao_yuan_rate"))).scalars().one()
        assert rate.value == "1800"


@pytest.mark.asyncio
async def test_same_taobao_item_is_not_imported_twice(flow):
    async with flow() as session:
        session.add(Setting(key="taobao_yuan_rate", value="1800"))
        prod = (await session.execute(select(Product).where(Product.id == 1))).scalars().one()
        prod.taobao_item_id = "730344766230"
        await session.commit()

    bot, state = _bot(), _state()
    link = find_taobao_link("https://item.taobao.com/item.htm?id=730344766230")
    msg, status = _message(link.url, bot)
    await tb.handle_taobao_link(msg, state, link)
    assert "allaqachon" in status.edit_text.await_args.args[0]
    tb.fetch_item.assert_not_awaited()  # no Apify credit spent on a repeat
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_fetch_error_is_shown_and_nothing_is_saved(flow, monkeypatch):
    async with flow() as session:
        session.add(Setting(key="taobao_yuan_rate", value="1800"))
        await session.commit()
    monkeypatch.setattr(tb, "fetch_item", AsyncMock(side_effect=TaobaoFetchError("💳 kredit tugadi")))

    bot, state = _bot(), _state()
    link = find_taobao_link("https://item.taobao.com/item.htm?id=730344766230")
    msg, status = _message(link.url, bot)
    await tb.handle_taobao_link(msg, state, link)
    assert status.edit_text.await_args.args[0] == "💳 kredit tugadi"
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_skip_keeps_chinese_title_and_empty_lists(flow):
    bot, state = _bot(), _state()
    await state.set_state(tb.TaobaoImport.title)
    await state.update_data(title_cn="女士短靴", price=100000, photos=["tg0"], colors=[], sizes=[])
    target, _ = _message("", bot)
    await tb.step_skip(_callback("tb_skip", target), state)
    assert (await state.get_data())["title"] == "女士短靴"
    assert await state.get_state() == tb.TaobaoImport.category.state


@pytest.mark.asyncio
async def test_manual_price_must_be_a_real_amount(flow):
    bot, state = _bot(), _state()
    await state.set_state(tb.TaobaoImport.price)
    await state.update_data(price=1, photos=["tg0"], category="jempir", title="x")
    msg, _ = _message("abc", bot)
    await tb.step_price(msg, state)
    assert await state.get_state() == tb.TaobaoImport.price.state
    await tb.step_price(_message("149.000", bot)[0], state)
    assert (await state.get_data())["price"] == 149000
    assert await state.get_state() == tb.TaobaoImport.confirm.state


def test_cancel_texts_are_not_taken_as_answers():
    assert not tb.TEXT_ANSWER.resolve(SimpleNamespace(text="/cancel"))
    assert not tb.TEXT_ANSWER.resolve(SimpleNamespace(text="❌ Bekor qilish"))
    assert tb.TEXT_ANSWER.resolve(SimpleNamespace(text="Ayollar etigi"))
