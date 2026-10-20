import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, BackgroundTasks
from sqlalchemy import select, func, desc, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_admin, TelegramUser
from api.config import settings
from api.routes.products import enrich_product_out, get_cargo_rate
from api.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductOut,
    CategoryCreate,
    CategoryOut,
    OrderStatusUpdate,
    OrderOut,
    ReviewOut,
    AdminStatsOut,
    BroadcastCreate,
)
from api.services.formatters import build_channel_caption, format_price
from bot.loader import bot
from bot.services.broadcaster import run_broadcast
from bot.services.channel_post import post_product_to_channel
from db.models import Product, Category, Order, Review, User, Admin, Wishlist, Setting
from db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


# ==================== PRODUCTS ====================
@router.post("/products", response_model=ProductOut)
async def admin_create_product(
    payload: ProductCreate,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cargo_rate = await get_cargo_rate(db)
    prod = Product(
        title=payload.title,
        description=payload.description or "",
        price=payload.price,
        old_price=payload.old_price,
        category=payload.category,
        photos=payload.photos,
        sizes=payload.sizes,
        colors=payload.colors,
        weight_grams=payload.weight_grams,
        in_stock=payload.in_stock,
        is_new=payload.is_new,
        is_hit=payload.is_hit,
    )
    db.add(prod)
    await db.commit()
    await db.refresh(prod)
    return enrich_product_out(prod, cargo_rate)


@router.put("/products/{product_id}", response_model=ProductOut)
async def admin_update_product(
    product_id: int,
    payload: ProductUpdate,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cargo_rate = await get_cargo_rate(db)
    res = await db.execute(select(Product).where(Product.id == product_id))
    prod = res.scalars().first()
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot topilmadi")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prod, key, value)

    await db.commit()
    await db.refresh(prod)
    return enrich_product_out(prod, cargo_rate)


@router.delete("/products/{product_id}", response_model=Dict[str, Any])
async def admin_delete_product(
    product_id: int,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Product).where(Product.id == product_id))
    prod = res.scalars().first()
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot topilmadi")

    await db.delete(prod)
    await db.commit()
    return {"success": True, "deleted_id": product_id}


@router.post("/products/{product_id}/post-to-channel", response_model=Dict[str, Any])
async def admin_post_product_to_channel(
    product_id: int,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Product).where(Product.id == product_id))
    prod = res.scalars().first()
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot topilmadi")

    result = await post_product_to_channel(prod)
    return result


# ==================== PHOTO UPLOAD (PHONE GALLERY TO TELEGRAM FILE_ID) ====================
@router.post("/upload-photo", response_model=Dict[str, str])
async def admin_upload_photo(
    file: UploadFile = File(...),
    admin: TelegramUser = Depends(require_admin),
):
    """
    Ingenious Telegram photo upload:
    Sends uploaded file to admin's private chat via bot, extracts file_id,
    immediately deletes message from chat, and caches file locally.
    Zero external storage costs!
    """
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rasm hajmi 10MB dan oshmasligi kerak")

    # Generate filename
    ext = Path(file.filename or "upload.jpg").suffix or ".jpg"
    unique_name = f"upload_{uuid.uuid4().hex}{ext}"
    media_dir = Path(settings.MEDIA_CACHE_DIR)
    media_dir.mkdir(parents=True, exist_ok=True)
    local_path = media_dir / unique_name

    with open(local_path, "wb") as f:
        f.write(content)

    file_id = unique_name

    if bot and admin.id:
        try:
            from aiogram.types import FSInputFile
            input_file = FSInputFile(str(local_path))
            msg = await bot.send_photo(
                chat_id=admin.id,
                photo=input_file,
                caption="🌸 Rasm yuklandi (avtomatik tozalanadi)",
            )
            if msg.photo:
                file_id = msg.photo[-1].file_id
            # Delete message so it doesn't clutter chat
            await bot.delete_message(chat_id=admin.id, message_id=msg.message_id)
        except Exception as e:
            logger.warning(f"Failed to proxy upload to Telegram chat: {e}. Using local cache.")

    return {
        "file_id": file_id,
        "url": f"/api/media/{file_id}",
    }


# ==================== CATEGORIES ====================
@router.post("/categories", response_model=CategoryOut)
async def admin_create_category(
    payload: CategoryCreate,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    clean_slug = payload.slug.replace("#", "").strip().lower()
    existing = await db.execute(select(Category).where(Category.slug == clean_slug))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu kategoriya allaqachon mavjud")

    cat = Category(
        slug=clean_slug,
        name=payload.name,
        emoji=payload.emoji or "🌸",
        sort_order=payload.sort_order,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return CategoryOut(slug=cat.slug, name=cat.name, emoji=cat.emoji, sort_order=cat.sort_order, product_count=0)


@router.delete("/categories/{slug}", response_model=Dict[str, Any])
async def admin_delete_category(
    slug: str,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    clean_slug = slug.replace("#", "").strip().lower()
    res = await db.execute(select(Category).where(Category.slug == clean_slug))
    cat = res.scalars().first()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategoriya topilmadi")

    # Check if products exist in category
    prod_check = await db.execute(select(func.count(Product.id)).where(Product.category == clean_slug))
    count = prod_check.scalar() or 0
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kategoriyada {count} ta mahsulot bor. Avval ularni o'chiring yoki boshqa bo'limga ko'chiring."
        )

    await db.delete(cat)
    await db.commit()
    return {"success": True, "deleted_slug": clean_slug}


# ==================== ORDERS ====================
@router.get("/orders", response_model=List[OrderOut])
async def admin_list_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order)
    if status_filter:
        query = query.where(Order.status == status_filter)
    query = query.order_by(desc(Order.created_at))

    res = await db.execute(query)
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


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
async def admin_update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Order).where(Order.id == order_id))
    order = res.scalars().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyurtma topilmadi")

    order.status = payload.status
    await db.commit()
    await db.refresh(order)

    # Notify customer via Telegram if status changed
    if bot and order.user_id:
        status_text = "qabul qilindi ✅" if payload.status == "accepted" else "bekor qilindi ❌"
        try:
            await bot.send_message(
                chat_id=order.user_id,
                text=f"🌸 <b>Buyurtmangiz (#{order.id}) holati o'zgardi:</b>\nHolat: <b>{status_text}</b>\n\nSavollaringiz bo'lsa @fkhrdnvvvva ga yozishingiz mumkin 💌",
            )
        except Exception as e:
            logger.warning(f"Could not notify user {order.user_id} of order status: {e}")

    return OrderOut(
        id=order.id,
        user_id=order.user_id,
        customer_name=order.customer_name,
        customer_username=order.customer_username,
        items_snapshot=order.items_snapshot,
        total=order.total,
        formatted_total=format_price(order.total),
        estimated_cargo=order.estimated_cargo,
        formatted_cargo=format_price(order.estimated_cargo),
        status=order.status,
        created_at=order.created_at,
    )


# ==================== REVIEWS ====================
@router.get("/reviews", response_model=List[ReviewOut])
async def admin_list_reviews(
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Review).order_by(desc(Review.created_at)))
    return res.scalars().all()


@router.patch("/reviews/{review_id}/approve", response_model=ReviewOut)
async def admin_approve_review(
    review_id: int,
    approved: bool = Query(...),
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Review).where(Review.id == review_id))
    rev = res.scalars().first()
    if not rev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fikr topilmadi")

    rev.approved = approved
    await db.commit()
    await db.refresh(rev)
    return rev


@router.delete("/reviews/{review_id}", response_model=Dict[str, Any])
async def admin_delete_review(
    review_id: int,
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Review).where(Review.id == review_id))
    rev = res.scalars().first()
    if not rev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fikr topilmadi")

    await db.delete(rev)
    await db.commit()
    return {"success": True, "deleted_id": review_id}


# ==================== STATS DASHBOARD ====================
@router.get("/stats", response_model=AdminStatsOut)
async def admin_get_stats(
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cargo_rate = await get_cargo_rate(db)
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # User counts
    total_users = (await db.execute(select(func.count(User.telegram_id)))).scalar() or 0
    new_users_this_week = (
        await db.execute(select(func.count(User.telegram_id)).where(User.first_seen >= week_ago))
    ).scalar() or 0

    # Orders counts
    total_orders = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    new_orders = (await db.execute(select(func.count(Order.id)).where(Order.status == "new"))).scalar() or 0
    accepted_orders = (await db.execute(select(func.count(Order.id)).where(Order.status == "accepted"))).scalar() or 0

    # Products counts
    total_products = (await db.execute(select(func.count(Product.id)))).scalar() or 0
    in_stock_products = (await db.execute(select(func.count(Product.id)).where(Product.in_stock == True))).scalar() or 0

    # Top viewed products
    res_top = await db.execute(
        select(Product).order_by(desc(Product.views)).limit(5)
    )
    top_viewed = [enrich_product_out(p, cargo_rate) for p in res_top.scalars().all()]

    # Most wishlisted
    res_wish = await db.execute(
        select(Wishlist.product_id, func.count(Wishlist.id).label("count"))
        .group_by(Wishlist.product_id)
        .order_by(desc("count"))
        .limit(5)
    )
    wish_rows = res_wish.all()
    wishlisted_list = []
    for pid, wcount in wish_rows:
        p_res = await db.execute(select(Product).where(Product.id == pid))
        p_obj = p_res.scalars().first()
        if p_obj:
            wishlisted_list.append({
                "product_id": pid,
                "title": p_obj.title,
                "wishlist_count": wcount,
                "price": p_obj.price,
                "formatted_price": format_price(p_obj.price),
                "photo": p_obj.photos[0] if p_obj.photos else "",
            })

    # Orders per day (last 7 days)
    orders_per_day = []
    for day_offset in range(6, -1, -1):
        target_day = (now - timedelta(days=day_offset)).date()
        start_day = datetime(target_day.year, target_day.month, target_day.day, tzinfo=timezone.utc)
        end_day = start_day + timedelta(days=1)

        day_count = (
            await db.execute(
                select(func.count(Order.id)).where(Order.created_at >= start_day, Order.created_at < end_day)
            )
        ).scalar() or 0

        orders_per_day.append({
            "date": target_day.strftime("%d.%m"),
            "count": day_count,
        })

    return AdminStatsOut(
        total_users=total_users,
        new_users_this_week=new_users_this_week,
        total_orders=total_orders,
        new_orders=new_orders,
        accepted_orders=accepted_orders,
        total_products=total_products,
        in_stock_products=in_stock_products,
        top_viewed_products=top_viewed,
        most_wishlisted_products=wishlisted_list,
        orders_per_day=orders_per_day,
    )


# ==================== BROADCAST ====================
@router.post("/broadcast", response_model=Dict[str, Any])
async def admin_broadcast(
    payload: BroadcastCreate,
    background_tasks: BackgroundTasks,
    admin: TelegramUser = Depends(require_admin),
):
    background_tasks.add_task(
        run_broadcast,
        text=payload.text,
        photo_url=payload.photo_url,
        admin_id=admin.id,
    )
    return {
        "status": "started",
        "message": "Xabar tarqatish boshlandi 📣 Live progress botda ko'rsatiladi.",
    }


# ==================== SETTINGS ====================
@router.get("/settings", response_model=Dict[str, Any])
async def admin_get_all_settings(
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Setting))
    return {s.key: s.value for s in res.scalars().all()}


@router.post("/settings", response_model=Dict[str, Any])
async def admin_update_settings(
    payload: Dict[str, Any],
    admin: TelegramUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    for k, v in payload.items():
        res = await db.execute(select(Setting).where(Setting.key == k))
        setting = res.scalars().first()
        if setting:
            setting.value = str(v)
        else:
            db.add(Setting(key=k, value=str(v)))

    await db.commit()
    return {"success": True, "updated": list(payload.keys())}
