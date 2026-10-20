from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, TelegramUser
from api.schemas import OrderCreate, OrderOut
from api.services.formatters import format_price, calculate_cargo
from bot.services.order_notifier import notify_new_order
from db.models import Order, CartItem, Product, Setting
from db.session import get_db

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut)
async def create_order(
    payload: OrderCreate,
    background_tasks: BackgroundTasks,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Retrieve current cart items
    res_cart = await db.execute(select(CartItem).where(CartItem.user_id == user.id))
    cart_items = res_cart.scalars().all()

    if not cart_items and not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Savat bo'sh, buyurtma berish uchun mahsulot tanlang"
        )

    # Get cargo rate
    res_rate = await db.execute(select(Setting).where(Setting.key == "cargo_rate"))
    rate_setting = res_rate.scalars().first()
    cargo_rate = int(rate_setting.value) if rate_setting and rate_setting.value.isdigit() else 12000

    items_snapshot = []
    total = 0
    total_weight = 0

    if cart_items:
        for item in cart_items:
            prod = item.product
            if not prod:
                continue
            item_subtotal = prod.price * item.qty
            total += item_subtotal
            if prod.weight_grams:
                total_weight += prod.weight_grams * item.qty

            photo = prod.photos[0] if prod.photos and len(prod.photos) > 0 else ""
            items_snapshot.append({
                "product_id": prod.id,
                "title": prod.title,
                "price": prod.price,
                "size": item.size,
                "color": item.color,
                "qty": item.qty,
                "weight_grams": prod.weight_grams,
                "photo": photo,
            })
    elif payload.items:
        items_snapshot = payload.items
        for it in items_snapshot:
            total += int(it.get("price", 0)) * int(it.get("qty", 1))
            w = it.get("weight_grams")
            if w:
                total_weight += int(w) * int(it.get("qty", 1))

    estimated_cargo = calculate_cargo(total_weight, cargo_rate)

    customer_name = payload.customer_name or f"{user.first_name} {user.last_name or ''}".strip() or "Mijoz"
    customer_username = payload.customer_username or user.username

    new_order = Order(
        user_id=user.id,
        customer_name=customer_name,
        customer_username=customer_username,
        items_snapshot=items_snapshot,
        total=total,
        estimated_cargo=estimated_cargo,
        status="new",
    )
    db.add(new_order)
    await db.flush()

    # Clear user's cart
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    await db.refresh(new_order)

    # Trigger background Telegram notification
    background_tasks.add_task(
        notify_new_order,
        order_id=new_order.id,
        user_id=user.id,
        customer_name=customer_name,
        customer_username=customer_username,
        items=items_snapshot,
        total=total,
        estimated_cargo=estimated_cargo,
    )

    return OrderOut(
        id=new_order.id,
        user_id=new_order.user_id,
        customer_name=new_order.customer_name,
        customer_username=new_order.customer_username,
        items_snapshot=new_order.items_snapshot,
        total=new_order.total,
        formatted_total=format_price(new_order.total),
        estimated_cargo=new_order.estimated_cargo,
        formatted_cargo=format_price(new_order.estimated_cargo),
        status=new_order.status,
        created_at=new_order.created_at,
    )


@router.get("", response_model=List[OrderOut])
async def list_user_orders(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Order).where(Order.user_id == user.id).order_by(desc(Order.created_at))
    )
    orders = res.scalars().all()
    return [
        OrderOut(
            id=o.id,
            user_id=o.user_id,
            customer_name=o.customer_name,
            customer_username=o.customer_username,
            items_snapshot=o.items_snapshot,
            total=o.total,
            formatted_total=format_price(o.total),
            estimated_cargo=o.estimated_cargo,
            formatted_cargo=format_price(o.estimated_cargo),
            status=o.status,
            created_at=o.created_at,
        )
        for o in orders
    ]
