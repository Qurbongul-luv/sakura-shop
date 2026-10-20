from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user, TelegramUser
from api.schemas import ReviewCreate, ReviewOut
from db.models import Review
from db.session import get_db

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=List[ReviewOut])
async def list_approved_reviews(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Review).where(Review.approved == True).order_by(desc(Review.created_at))
    )
    reviews = res.scalars().all()
    return reviews


@router.post("", response_model=ReviewOut)
async def submit_review(
    payload: ReviewCreate,
    user: TelegramUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    customer_name = payload.customer_name or f"{user.first_name} {user.last_name or ''}".strip() or "Mijoz"
    new_rev = Review(
        customer_name=customer_name,
        text=payload.text or "",
        photos=payload.photos or [],
        approved=False,  # Moderation required
    )
    db.add(new_rev)
    await db.commit()
    await db.refresh(new_rev)
    return new_rev
