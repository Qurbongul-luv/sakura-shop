from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False, default="")
    username = Column(String(255), nullable=True)
    language = Column(String(10), nullable=False, default="uz")
    first_seen = Column(DateTime(timezone=True), default=utcnow)
    last_seen = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    blocked_bot = Column(Boolean, default=False, nullable=False)


class Admin(Base):
    __tablename__ = "admins"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False, default="")
    username = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="admin")  # "owner" or "admin"
    added_at = Column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"

    slug = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    emoji = Column(String(20), nullable=False, default="🌸")
    sort_order = Column(Integer, default=0, nullable=False)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    price = Column(Integer, nullable=False)  # in so'm, e.g. 99000
    old_price = Column(Integer, nullable=True)  # in so'm, e.g. 120000
    category = Column(String(100), ForeignKey("categories.slug"), nullable=False, index=True)
    photos = Column(JSON, nullable=False, default=list)  # list of file_ids / local filenames
    sizes = Column(JSON, nullable=False, default=list)  # list of strings e.g. ["S", "M", "L"]
    colors = Column(JSON, nullable=False, default=list)  # list of strings e.g. ["Pushti 🌸", "Oq 🤍"]
    weight_grams = Column(Integer, nullable=True)  # e.g. 350g
    in_stock = Column(Boolean, default=True, nullable=False, index=True)
    is_new = Column(Boolean, default=False, nullable=False, index=True)
    is_hit = Column(Boolean, default=False, nullable=False, index=True)
    views = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    channel_message_id = Column(Integer, nullable=True)

    category_rel = relationship("Category", backref="products", lazy="joined")


class Wishlist(Base):
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    product = relationship("Product", lazy="joined")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    size = Column(String(100), nullable=True)
    color = Column(String(100), nullable=True)
    qty = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    product = relationship("Product", lazy="joined")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_username = Column(String(255), nullable=True)
    items_snapshot = Column(JSON, nullable=False)  # [{product_id, title, price, size, color, qty, photo}]
    total = Column(Integer, nullable=False)
    estimated_cargo = Column(Integer, nullable=False, default=0)
    status = Column(String(50), default="new", nullable=False)  # new, accepted, cancelled
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    photos = Column(JSON, nullable=False, default=list)  # list of file_ids / filenames
    text = Column(Text, nullable=True, default="")
    customer_name = Column(String(255), nullable=False)
    approved = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


class Contest(Base):
    __tablename__ = "contests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prize_1 = Column(String(255), nullable=False)
    prize_2 = Column(String(255), nullable=False)
    prize_3 = Column(String(255), nullable=False)
    photo_file_id = Column(String(255), nullable=True)
    channel_message_id = Column(BigInteger, nullable=True)
    status = Column(String(50), default="active", nullable=False, index=True)  # active, pending_approval, completed, cancelled
    only_new_subscribers = Column(Boolean, default=True, nullable=False)
    disqualified_user_ids = Column(JSON, default=list, nullable=False)
    winners_snapshot = Column(JSON, nullable=True)
    total_subscribers_gained = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False, index=True)

    referrals = relationship("ContestReferral", back_populates="contest", cascade="all, delete-orphan")


class ContestReferral(Base):
    __tablename__ = "contest_referrals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    invitee_id = Column(BigInteger, nullable=False, index=True)
    referrer_id = Column(BigInteger, nullable=False, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, confirmed, revoked
    was_member_before = Column(Boolean, default=False, nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    reminder_sent = Column(Boolean, default=False, nullable=False)

    contest = relationship("Contest", back_populates="referrals")

    __table_args__ = (
        UniqueConstraint("contest_id", "invitee_id", name="uq_contest_invitee"),
        CheckConstraint("invitee_id != referrer_id", name="ck_no_self_referral"),
        Index("ix_contest_referrer_status", "contest_id", "referrer_id", "status"),
        Index("ix_contest_status", "contest_id", "status"),
    )


class ContestReferralAudit(Base):
    __tablename__ = "contest_referral_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, nullable=False, index=True)
    referral_id = Column(Integer, nullable=True, index=True)
    invitee_id = Column(BigInteger, nullable=False, index=True)
    referrer_id = Column(BigInteger, nullable=False, index=True)
    action = Column(String(50), nullable=False)  # created_pending, confirmed, revoked_left_channel, reconfirmed, disqualified, recheck_revoked
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
