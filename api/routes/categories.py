from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import CategoryOut
from db.models import Category, Product
from db.session import get_db

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=List[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    # Query categories and count active products
    res = await db.execute(select(Category).order_by(Category.sort_order))
    categories = res.scalars().all()

    counts_res = await db.execute(
        select(Product.category, func.count(Product.id)).group_by(Product.category)
    )
    counts_map = dict(counts_res.all())

    return [
        CategoryOut(
            slug=c.slug,
            name=c.name,
            emoji=c.emoji,
            sort_order=c.sort_order,
            product_count=counts_map.get(c.slug, 0),
        )
        for c in categories
    ]
