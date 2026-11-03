from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import create_engine, inspect, select, text

from api.services.taobao import PriceRule, calculate_cost
from bot.handlers import orders as order_handlers
from bot.handlers import profit as profit_handlers
from bot.handlers import review_request as review_handlers
from bot.services import order_status as st
from bot.services.profit import ProfitReport, build_report, order_cost, summarize
from bot.services.review_requests import save_review, send_review_requests
from db.models import Admin, Order, Product, Review, utcnow
from db.session import _add_missing_columns
from tests.conftest import generate_test_init_data

CUSTOMER = 4242
OWNER = 999999999  # DEV_ADMIN_ID in the test env counts as owner
PLAIN_ADMIN = 5555


def _items(*rows):
    return [{"product_id": pid, "title": f"P{pid}", "price": price, "qty": qty} for pid, price, qty in rows]


async def _order(session, status="new", total=100000, cost_total=None, items=None, **extra):
    order = Order(
        user_id=CUSTOMER, customer_name="Malika", customer_username="malika",
        items_snapshot=items or _items((1, total, 1)), total=total, status=status, cost_total=cost_total, **extra,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


# ==================== STATUS RULES ====================
def test_status_moves_forward_or_cancels_only():
    assert st.is_allowed("new", "accepted")
    assert st.is_allowed("new", "shipping")  # skipping steps is fine
    assert st.is_allowed("arrived", "delivered")
    assert st.is_allowed("shipping", "cancelled")
    assert not st.is_allowed("shipping", "accepted")  # never backwards
    assert not st.is_allowed("delivered", "cancelled")
    assert not st.is_allowed("cancelled", "accepted")
    assert not st.is_allowed("new", "new")
    assert not st.is_allowed("new", "lost")
    assert st.next_status("new") == "accepted"
    assert st.next_status("arrived") == "delivered"
    assert st.next_status("delivered") is None and st.next_status("cancelled") is None


@pytest.mark.asyncio
async def test_change_notifies_customer_once_and_records_delivery(test_db_session):
    bot = AsyncMock()
    async with test_db_session() as session:
        order = await _order(session)
        change = await st.change_status_and_notify(session, bot, order.id, "shipping")
        assert change.result == st.RESULT_CHANGED and change.previous == "new"
        assert change.order.status == "shipping" and change.order.status_updated_at is not None
        sent = bot.send_message.await_args.kwargs
        assert sent["chat_id"] == CUSTOMER and "yo'lda" in sent["text"].lower()

        again = await st.change_status_and_notify(session, bot, order.id, "shipping")
        assert again.result == st.RESULT_UNCHANGED
        back = await st.change_status_and_notify(session, bot, order.id, "accepted")
        assert back.result == st.RESULT_NOT_ALLOWED
        assert bot.send_message.await_count == 1

        done = await st.change_status_and_notify(session, bot, order.id, "delivered")
        assert done.order.delivered_at is not None
        missing = await st.change_status_and_notify(session, bot, 98765, "accepted")
        assert missing.result == st.RESULT_NOT_FOUND


@pytest.mark.asyncio
async def test_concurrent_tap_changes_and_notifies_once(test_db_session, monkeypatch):
    from sqlalchemy.sql.dml import Update

    bot = AsyncMock()
    async with test_db_session() as session:
        order = await _order(session)
        real_execute = session.execute
        raced = {"done": False}

        async def racing_execute(stmt, *args, **kwargs):
            # Another admin's tap lands after our read but before our update.
            if isinstance(stmt, Update) and not raced["done"]:
                raced["done"] = True
                async with test_db_session() as other:
                    assert (await st.change_status(other, order.id, "accepted")).result == st.RESULT_CHANGED
            return await real_execute(stmt, *args, **kwargs)

        monkeypatch.setattr(session, "execute", racing_execute)
        change = await st.change_status_and_notify(session, bot, order.id, "accepted")
    assert raced["done"]
    assert change.result == st.RESULT_RACE and change.order.status == "accepted"
    bot.send_message.assert_not_awaited()  # the other tap already told the customer


def test_card_and_buttons():
    order = SimpleNamespace(
        id=7, status="accepted", customer_name="Malika", customer_username=None, user_id=CUSTOMER,
        items_snapshot=[{"title": "Etik", "price": 145000, "qty": 2, "size": "37", "color": "qora"}],
        total=290000, estimated_cargo=24000,
    )
    card = st.order_card(order)
    assert "#7" in card and "Etik (37, qora) × 2 — 290.000 so'm" in card and "tannarx" not in card.lower()
    calls = [b.callback_data for row in st.order_markup(order, True).inline_keyboard for b in row if b.callback_data]
    assert calls[0] == "ord_st:7:purchased"
    assert "ord_st:7:cancelled" in calls and calls[-1] == "admin_orders"
    delivered = SimpleNamespace(**{**order.__dict__, "status": "delivered"})
    assert all(not (b.callback_data or "").startswith("ord_st") for row in st.order_markup(delivered).inline_keyboard for b in row)


# ==================== BOT BUTTONS ====================
def _callback(data, user_id=OWNER, with_list_button=False):
    markup = InlineKeyboardMarkup(inline_keyboard=[])
    if with_list_button:
        markup = st.order_markup(SimpleNamespace(id=1, status="new", customer_username="x", user_id=1), True)
    message = SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock(), reply_markup=markup)
    return SimpleNamespace(data=data, from_user=SimpleNamespace(id=user_id), message=message, answer=AsyncMock(), bot=AsyncMock())


@pytest.mark.asyncio
async def test_status_button_and_legacy_accept_button(test_db_session, monkeypatch):
    monkeypatch.setattr(order_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        order = await _order(session)

    cb = _callback(f"order_accept_{order.id}")  # button on an old order notice
    await order_handlers.handle_order_accept(cb)
    assert "qabul" in cb.message.edit_text.await_args.args[0].lower()
    cb.bot.send_message.assert_awaited_once()

    cb2 = _callback(f"ord_st:{order.id}:accepted")
    await order_handlers.handle_order_status(cb2)
    assert cb2.answer.await_args.kwargs.get("show_alert") is True  # already accepted
    cb2.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_orders_list_hides_finished_orders(test_db_session, monkeypatch):
    monkeypatch.setattr(order_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        active = await _order(session, status="shipping")
        await _order(session, status="delivered")
        await _order(session, status="cancelled")
    cb = _callback("admin_orders")
    await order_handlers.handle_orders_list(cb)
    markup = cb.message.edit_text.await_args.kwargs["reply_markup"]
    targets = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert targets == [f"ord_view:{active.id}", "admin_menu"]


@pytest.mark.asyncio
async def test_non_admin_cannot_press_order_buttons(test_db_session, monkeypatch):
    monkeypatch.setattr(order_handlers, "async_session_factory", test_db_session)
    assert not await order_handlers.admin_callback(_callback("ord_st:1:accepted", user_id=CUSTOMER))


@pytest.mark.asyncio
async def test_admin_api_uses_the_same_rules(client, test_db_session, monkeypatch):
    from api.routes import admin as admin_routes

    monkeypatch.setattr(admin_routes, "bot", AsyncMock())
    async with test_db_session() as session:
        session.add(Admin(telegram_id=PLAIN_ADMIN, name="A", role="admin"))
        await session.commit()
        order = await _order(session, status="shipping")
    headers = {"X-Telegram-Init-Data": generate_test_init_data(user_id=PLAIN_ADMIN)}

    ok = await client.patch(f"/api/admin/orders/{order.id}/status", json={"status": "arrived"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["status"] == "arrived"
    back = await client.patch(f"/api/admin/orders/{order.id}/status", json={"status": "accepted"}, headers=headers)
    assert back.status_code == 409
    bad = await client.patch(f"/api/admin/orders/{order.id}/status", json={"status": "lost"}, headers=headers)
    assert bad.status_code == 422
    assert "cost_total" not in ok.json()


# ==================== PROFIT ====================
def test_cost_from_taobao_price():
    assert calculate_cost(89.5, PriceRule(yuan_rate=1800, markup_percent=30)) == 161100  # no markup
    assert calculate_cost(10, PriceRule(yuan_rate=0)) is None


@pytest.mark.asyncio
async def test_order_cost_needs_every_item_costed(test_db_session):
    async with test_db_session() as session:
        session.add(Product(id=2, title="B", price=50000, category="jempir", photos=[], cost_som=20000))
        prod1 = (await session.execute(select(Product).where(Product.id == 1))).scalars().one()
        prod1.cost_som = 60000
        await session.commit()
        assert await order_cost(session, _items((1, 99000, 2), (2, 50000, 1))) == 140000
        prod1.cost_som = None
        await session.commit()
        assert await order_cost(session, _items((1, 99000, 1), (2, 50000, 1))) is None
        assert await order_cost(session, [{"title": "no id", "price": 1}]) is None
        assert await order_cost(session, []) is None


def test_summary_counts_only_costed_orders_as_profit():
    orders = [
        SimpleNamespace(total=200000, cost_total=120000, items_snapshot=_items((1, 100000, 2))),
        SimpleNamespace(total=50000, cost_total=None, items_snapshot=_items((2, 50000, 1))),
    ]
    r = summarize(orders)
    assert (r.orders, r.revenue, r.costed_revenue, r.cost, r.profit, r.uncosted_orders) == (2, 250000, 200000, 120000, 80000, 1)
    assert r.margin_percent == 40.0
    assert r.top_products[0] == ("P1", 2, 200000)
    assert summarize([]) == ProfitReport(0, 0, 0, 0, 0, 0, ())


@pytest.mark.asyncio
async def test_report_skips_new_and_cancelled_and_old_orders(test_db_session):
    async with test_db_session() as session:
        await _order(session, status="delivered", total=300000, cost_total=200000)
        await _order(session, status="new", total=999999, cost_total=1)
        await _order(session, status="cancelled", total=888888, cost_total=1)
        await _order(session, status="accepted", total=100000, cost_total=50000, created_at=utcnow() - timedelta(days=40))
        month = await build_report(session, 30)
        assert (month.orders, month.revenue, month.profit) == (1, 300000, 100000)
        ever = await build_report(session, None)
        assert (ever.orders, ever.profit) == (2, 150000)


@pytest.mark.asyncio
async def test_profit_is_owner_only(test_db_session, monkeypatch):
    monkeypatch.setattr(profit_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        session.add_all([Admin(telegram_id=PLAIN_ADMIN, name="A", role="admin"), Admin(telegram_id=777, name="O", role="owner")])
        await session.commit()
    who = lambda uid: SimpleNamespace(from_user=SimpleNamespace(id=uid))  # noqa: E731
    assert await profit_handlers.owner_event(who(777))
    assert await profit_handlers.owner_event(who(OWNER))
    assert not await profit_handlers.owner_event(who(PLAIN_ADMIN))
    assert not await profit_handlers.owner_event(who(CUSTOMER))


@pytest.mark.asyncio
async def test_stats_and_product_buttons_show_profit_only_to_owner(test_db_session, monkeypatch):
    from bot.handlers import admin as admin_handlers

    monkeypatch.setattr(admin_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        session.add(Admin(telegram_id=PLAIN_ADMIN, name="A", role="admin"))
        await session.commit()

    def buttons(cb):
        markup = cb.message.edit_text.await_args.kwargs["reply_markup"]
        return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]

    for uid, sees in ((OWNER, True), (PLAIN_ADMIN, False)):
        cb = _callback("admin_stats", user_id=uid)
        await admin_handlers.handle_admin_stats(cb)
        assert ("own_profit:30" in buttons(cb)) is sees
        cb = _callback("admin_prod_manage_1", user_id=uid)
        await admin_handlers.handle_manage_single_product(cb)
        assert ("own_cost:1" in buttons(cb)) is sees


@pytest.mark.asyncio
async def test_owner_sets_product_cost(test_db_session, monkeypatch):
    monkeypatch.setattr(profit_handlers, "async_session_factory", test_db_session)
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=OWNER, user_id=OWNER))
    await state.set_state(profit_handlers.OwnerCost.waiting)
    await state.update_data(cost_product_id=1)
    msg = SimpleNamespace(text="65.000", from_user=SimpleNamespace(id=OWNER), answer=AsyncMock())
    await profit_handlers.handle_cost_input(msg, state)
    async with test_db_session() as session:
        assert (await session.execute(select(Product.cost_som).where(Product.id == 1))).scalar() == 65000
    assert "34.000 so'm" in msg.answer.await_args.args[0]  # 99.000 - 65.000
    assert profit_handlers.parse_cost("abc") is None and profit_handlers.parse_cost("0") == 0


def test_profit_text_mentions_unknown_costs():
    text = profit_handlers.report_text(ProfitReport(3, 500000, 2, 400000, 250000, 1, (("Etik", 3, 435000),)), "30 kun")
    assert "150.000 so'm" in text and "1 ta buyurtmada tannarx noma'lum" in text and "Etik" in text
    assert "yo'q" in profit_handlers.report_text(summarize([]), "7 kun")


# ==================== REVIEW REQUESTS ====================
@pytest.mark.asyncio
async def test_review_is_requested_once_three_days_after_delivery(test_db_session):
    bot = AsyncMock()
    async with test_db_session() as session:
        due = await _order(session, status="delivered", delivered_at=utcnow() - timedelta(days=3, minutes=1))
        await _order(session, status="delivered", delivered_at=utcnow() - timedelta(days=2))
        await _order(session, status="shipping")
        assert await send_review_requests(session, bot) == 1
        assert await send_review_requests(session, bot) == 0  # never asked twice
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == CUSTOMER and f"#{due.id}" in kwargs["text"]
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == f"rv_start:{due.id}"


@pytest.mark.asyncio
async def test_blocked_customer_is_not_retried(test_db_session):
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("Forbidden: bot was blocked by the user")
    async with test_db_session() as session:
        await _order(session, status="delivered", delivered_at=utcnow() - timedelta(days=4))
        assert await send_review_requests(session, bot) == 0
        assert await send_review_requests(session, bot) == 0
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_save_review_checks_owner_status_and_repeats(test_db_session):
    async with test_db_session() as session:
        order = await _order(session, status="delivered", delivered_at=utcnow())
        assert await save_review(session, order.id, 1111, "Boshqa", "x", []) is None  # not their order
        review = await save_review(session, order.id, CUSTOMER, "Malika", "  Zo'r!  ", ["p1"] * 8)
        assert review is not None and review.approved is False
        assert (review.text, len(review.photos)) == ("Zo'r!", 5)
        assert await save_review(session, order.id, CUSTOMER, "Malika", "yana", []) is None
        shipping = await _order(session, status="shipping")
        assert await save_review(session, shipping.id, CUSTOMER, "M", "erta", []) is None


@pytest.mark.asyncio
async def test_customer_review_flow_reaches_admins(test_db_session, monkeypatch):
    monkeypatch.setattr(review_handlers, "async_session_factory", test_db_session)
    async with test_db_session() as session:
        order = await _order(session, status="delivered", delivered_at=utcnow())
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=CUSTOMER, user_id=CUSTOMER))

    stranger = _callback(f"rv_start:{order.id}", user_id=1111)
    await review_handlers.handle_review_start(stranger, state)
    assert await state.get_state() is None

    await review_handlers.handle_review_start(_callback(f"rv_start:{order.id}", user_id=CUSTOMER), state)
    assert await state.get_state() == review_handlers.ReviewSubmit.waiting.state

    bot = AsyncMock()
    msg = SimpleNamespace(
        chat=SimpleNamespace(id=CUSTOMER), message_id=50, media_group_id=None,
        photo=[SimpleNamespace(file_id="big")], caption="Juda yoqdi!", text=None,
        from_user=SimpleNamespace(id=CUSTOMER, first_name="Malika"), bot=bot,
    )
    await review_handlers.handle_review_message(msg, state)
    assert await state.get_state() is None

    async with test_db_session() as session:
        review = (await session.execute(select(Review).where(Review.text == "Juda yoqdi!"))).scalars().one()
        assert review.photos == ["big"] and review.approved is False
        assert (await session.execute(select(Order.reviewed_at).where(Order.id == order.id))).scalar() is not None
    texts = [c.kwargs.get("text") or c.args[1] for c in bot.send_message.await_args_list]
    assert any("Rahmat" in t for t in texts)
    admin_msg = next(c for c in bot.send_message.await_args_list if c.kwargs.get("chat_id") == OWNER)
    assert admin_msg.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == f"admin_toggle_rev_{review.id}"
    bot.send_photo.assert_awaited()  # the photo goes separately so approve can edit the text message


def test_review_answer_filter_skips_commands():
    assert not review_handlers.ANSWER.resolve(SimpleNamespace(photo=None, text="/cancel"))
    assert review_handlers.ANSWER.resolve(SimpleNamespace(photo=None, text="Zo'r"))


# ==================== SCHEMA ====================
def test_new_order_and_product_columns_are_added(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE contests (id INTEGER PRIMARY KEY, extra_prizes JSON)"))
        conn.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, status VARCHAR(50))"))
        _add_missing_columns(conn)
        _add_missing_columns(conn)
        orders = {c["name"] for c in inspect(conn).get_columns("orders")}
        products = {c["name"] for c in inspect(conn).get_columns("products")}
    assert {"status_updated_at", "delivered_at", "review_requested_at", "reviewed_at", "cost_total"} <= orders
    assert {"channel_chat_id", "taobao_item_id", "cost_som"} <= products
