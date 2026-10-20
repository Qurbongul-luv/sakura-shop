from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, TelegramUser, get_current_user_optional
from api.schemas import CartItemAdd, CartItemUpdate, CartItemOut, CartSummaryOut
from api.services.formatters import format_price, calculate_cargo
from db.models import CartItem, Product, Setting
from db.session import get_db

router = APIRouter(prefix="/cart", tags=["cart"])


async def get_user_cart_summary(user_id: int, db: AsyncSession) -> CartSummaryOut:
    # Get cargo rate
    res_rate = await db.execute(select(Setting).where(Setting.key == "cargo_rate"))
    rate_setting = res_rate.scalars().first()
    cargo_rate = int(rate_setting.value) if rate_setting and rate_setting.value.isdigit() else 12000

    # Query cart items
    res = await db.execute(select(CartItem).where(CartItem.user_id == user_id))
    cart_items = res.scalars().all()

    items_out: List[CartItemOut] = []
    subtotal = 0
    total_weight = 0
    total_qty = 0

    for item in cart_items:
        prod = item.product
        if not prod:
            continue
        item_total = prod.price * item.qty
        subtotal += item_total
        total_qty += item.qty
        if prod.weight_grams:
            total_weight += prod.weight_grams * item.qty

        photo = prod.photos[0] if prod.photos and len(prod.photos) > 0 else None

        items_out.append(
            CartItemOut(
                id=item.id,
                product_id=prod.id,
                product_title=prod.title,
                product_price=prod.price,
                product_photo=photo,
                size=item.size,
                color=item.color,
                qty=item.qty,
                weight_grams=prod.weight_grams,
                item_total=item_total,
                formatted_item_total=format_price(item_total),
            )
        )

    estimated_cargo = calculate_cargo(total_weight, cargo_rate) if total_weight > 0 else 0
    grand_total = subtotal + estimated_cargo

    return CartSummaryOut(
        items=items_out,
        total_items=total_qty,
        subtotal=subtotal,
        formatted_subtotal=format_price(subtotal),
        estimated_cargo=estimated_cargo,
        formatted_estimated_cargo=format_price(estimated_cargo),
        grand_total=grand_total,
        formatted_grand_total=format_price(grand_total),
    )


@router.get("", response_model=CartSummaryOut)
async def get_cart(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_cart_summary(user.id, db)


@router.post("", response_model=CartSummaryOut)
async def add_to_cart(
    payload: CartItemAdd,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify product exists
    res = await db.execute(select(Product).where(Product.id == payload.product_id))
    product = res.scalars().first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot topilmadi")

    if not product.in_stock:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu mahsulot sotilgan (mavjud emas)")

    # Check if item with same size & color already in cart
    res_item = await db.execute(
        select(CartItem).where(
            CartItem.user_id == user.id,
            CartItem.product_id == payload.product_id,
            CartItem.size == payload.size,
            CartItem.color == payload.color,
        )
    )
    existing = res_item.scalars().first()
    if existing:
        existing.qty += payload.qty
    else:
        new_item = CartItem(
            user_id=user.id,
            product_id=payload.product_id,
            size=payload.size,
            color=payload.color,
            qty=payload.qty,
        )
        db.add(new_item)

    await db.commit()
    return await get_user_cart_summary(user.id, db)


@router.patch("/{item_id}", response_model=CartSummaryOut)
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id))
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savatdagi element topilmadi")

    item.qty = payload.qty
    await db.commit()
    return await get_user_cart_summary(user.id, db)


@router.delete("/{item_id}", response_model=CartSummaryOut)
async def remove_cart_item(
    item_id: int,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id))
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savatdagi element topilmadi")

    await db.delete(item)
    await db.commit()
    return await get_user_cart_summary(user.id, db)


@router.delete("", response_model=CartSummaryOut)
async def clear_cart(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    return await get_user_cart_summary(user.id, db)
