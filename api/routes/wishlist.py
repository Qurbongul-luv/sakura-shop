from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, TelegramUser
from api.routes.products import enrich_product_out, get_cargo_rate
from api.schemas import ProductOut, WishlistToggle
from db.models import Wishlist, Product
from db.session import get_db

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=List[ProductOut])
async def get_wishlist(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cargo_rate = await get_cargo_rate(db)
    res = await db.execute(
        select(Wishlist).where(Wishlist.user_id == user.id).order_by(Wishlist.created_at.desc())
    )
    items = res.scalars().all()
    products = [item.product for item in items if item.product]
    return [enrich_product_out(p, cargo_rate) for p in products]


@router.get("/ids", response_model=List[int])
async def get_wishlist_ids(
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Wishlist.product_id).where(Wishlist.user_id == user.id))
    return [row[0] for row in res.all()]


@router.post("/toggle", response_model=Dict[str, Any])
async def toggle_wishlist(
    payload: WishlistToggle,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify product exists
    res_p = await db.execute(select(Product).where(Product.id == payload.product_id))
    if not res_p.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot topilmadi")

    res = await db.execute(
        select(Wishlist).where(
            Wishlist.user_id == user.id,
            Wishlist.product_id == payload.product_id,
        )
    )
    existing = res.scalars().first()
    if existing:
        await db.delete(existing)
        await db.commit()
        return {"product_id": payload.product_id, "is_wishlisted": False}
    else:
        new_entry = Wishlist(user_id=user.id, product_id=payload.product_id)
        db.add(new_entry)
        await db.commit()
        return {"product_id": payload.product_id, "is_wishlisted": True}
