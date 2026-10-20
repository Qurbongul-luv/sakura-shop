from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import ProductOut
from api.services.formatters import format_price, calculate_cargo
from db.models import Product, Setting
from db.session import get_db

router = APIRouter(prefix="/products", tags=["products"])


def enrich_product_out(product: Product, cargo_rate: int = 12000) -> ProductOut:
    cargo = calculate_cargo(product.weight_grams, cargo_rate)
    return ProductOut(
        id=product.id,
        title=product.title,
        description=product.description or "",
        price=product.price,
        old_price=product.old_price,
        category=product.category,
        photos=product.photos or [],
        sizes=product.sizes or [],
        colors=product.colors or [],
        weight_grams=product.weight_grams,
        in_stock=product.in_stock,
        is_new=product.is_new,
        is_hit=product.is_hit,
        views=product.views,
        created_at=product.created_at,
        formatted_price=format_price(product.price),
        formatted_old_price=format_price(product.old_price) if product.old_price else None,
        cargo_estimate=cargo,
        formatted_cargo_estimate=format_price(cargo),
    )


async def get_cargo_rate(db: AsyncSession) -> int:
    res = await db.execute(select(Setting).where(Setting.key == "cargo_rate"))
    setting = res.scalars().first()
    if setting and setting.value.isdigit():
        return int(setting.value)
    return 12000


@router.get("", response_model=List[ProductOut])
async def list_products(
    category: Optional[str] = Query(None, description="Category slug"),
    search: Optional[str] = Query(None, description="Search term in title/description"),
    is_new: Optional[bool] = Query(None),
    is_hit: Optional[bool] = Query(None),
    in_stock_only: Optional[bool] = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    cargo_rate = await get_cargo_rate(db)
    query = select(Product)

    if category:
        clean_cat = category.replace("#", "").strip()
        query = query.where(Product.category == clean_cat)

    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(Product.title.ilike(term), Product.description.ilike(term)))

    if is_new is not None:
        query = query.where(Product.is_new == is_new)

    if is_hit is not None:
        query = query.where(Product.is_hit == is_hit)

    if in_stock_only:
        query = query.where(Product.in_stock == True)

    query = query.order_by(desc(Product.in_stock), desc(Product.created_at)).offset(offset).limit(limit)
    res = await db.execute(query)
    products = res.scalars().all()

    return [enrich_product_out(p, cargo_rate) for p in products]


@router.get("/hero", response_model=Optional[ProductOut])
async def get_hero_product(db: AsyncSession = Depends(get_db)):
    """
    Get 'Kun mahsuloti 🌸' (Product of the day)
    """
    cargo_rate = await get_cargo_rate(db)
    # Prefer is_hit and in_stock, otherwise latest in_stock
    query = (
        select(Product)
        .where(Product.in_stock == True)
        .order_by(desc(Product.is_hit), desc(Product.views), desc(Product.created_at))
        .limit(1)
    )
    res = await db.execute(query)
    product = res.scalars().first()
    if not product:
        return None
    return enrich_product_out(product, cargo_rate)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product_detail(product_id: int, db: AsyncSession = Depends(get_db)):
    cargo_rate = await get_cargo_rate(db)
    res = await db.execute(select(Product).where(Product.id == product_id))
    product = res.scalars().first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mahsulot topilmadi")

    # Increment view count
    product.views += 1
    await db.commit()
    await db.refresh(product)

    return enrich_product_out(product, cargo_rate)
