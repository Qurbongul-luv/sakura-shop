from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==================== PRODUCT SCHEMAS ====================
class ProductBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(default="", max_length=5000)
    price: int = Field(..., ge=0, le=1_000_000_000)
    old_price: Optional[int] = Field(default=None, ge=0, le=1_000_000_000)
    category: str = Field(..., min_length=1, max_length=100)
    photos: List[str] = Field(default_factory=list, max_length=15)
    sizes: List[str] = Field(default_factory=list, max_length=20)
    colors: List[str] = Field(default_factory=list, max_length=20)
    weight_grams: Optional[int] = Field(default=None, ge=0, le=100_000)
    in_stock: bool = True
    is_new: bool = False
    is_hit: bool = False


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    price: Optional[int] = Field(default=None, ge=0, le=1_000_000_000)
    old_price: Optional[int] = Field(default=None, ge=0, le=1_000_000_000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    photos: Optional[List[str]] = None
    sizes: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    weight_grams: Optional[int] = Field(default=None, ge=0, le=100_000)
    in_stock: Optional[bool] = None
    is_new: Optional[bool] = None
    is_hit: Optional[bool] = None


class ProductOut(ProductBase):
    id: int
    views: int
    created_at: datetime
    formatted_price: str = ""
    formatted_old_price: Optional[str] = None
    cargo_estimate: int = 0
    formatted_cargo_estimate: str = ""

    model_config = ConfigDict(from_attributes=True)


# ==================== CATEGORY SCHEMAS ====================
class CategoryBase(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    emoji: str = Field(default="🌸", max_length=20)
    sort_order: int = Field(default=0)


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    product_count: int = 0
    model_config = ConfigDict(from_attributes=True)


# ==================== CART SCHEMAS ====================
class CartItemAdd(BaseModel):
    product_id: int
    size: Optional[str] = None
    color: Optional[str] = None
    qty: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    qty: int = Field(..., ge=1, le=99)


class CartItemOut(BaseModel):
    id: int
    product_id: int
    product_title: str
    product_price: int
    product_photo: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    qty: int
    weight_grams: Optional[int] = None
    item_total: int
    formatted_item_total: str


class CartSummaryOut(BaseModel):
    items: List[CartItemOut]
    total_items: int
    subtotal: int
    formatted_subtotal: str
    estimated_cargo: int
    formatted_estimated_cargo: str
    grand_total: int
    formatted_grand_total: str


# ==================== ORDER SCHEMAS ====================
class OrderCreate(BaseModel):
    customer_name: Optional[str] = None
    customer_username: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None  # If client provides snapshot, or default to current cart


class OrderOut(BaseModel):
    id: int
    user_id: int
    customer_name: str
    customer_username: Optional[str] = None
    items_snapshot: List[Dict[str, Any]]
    total: int
    formatted_total: str = ""
    estimated_cargo: int
    formatted_cargo: str = ""
    status: str  # new, accepted, cancelled
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(new|accepted|cancelled)$")


# ==================== WISHLIST SCHEMAS ====================
class WishlistToggle(BaseModel):
    product_id: int


class WishlistOut(BaseModel):
    product_id: int
    product: ProductOut


# ==================== REVIEW SCHEMAS ====================
class ReviewCreate(BaseModel):
    text: Optional[str] = Field(default="", max_length=2000)
    customer_name: str = Field(..., min_length=2, max_length=100)
    photos: List[str] = Field(default_factory=list, max_length=5)


class ReviewOut(BaseModel):
    id: int
    photos: List[str]
    text: Optional[str]
    customer_name: str
    approved: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== SETTINGS SCHEMAS ====================
class SettingsDict(BaseModel):
    cargo_rate: int = 12000
    delivery_days: str = "10–15 kun"
    delivery_scope: str = "O'zbekiston bo'ylab"
    payment_terms: str = "100% oldindan to'lov"
    location: str = "Toshkent"
    contact_username: str = "fkhrdnvvvva"
    channel_url: str = "https://t.me/sakuraaa_chinese_shop"
    channel_id: str = ""
    welcome_text: str = "Sakura shop ga xush kelibsiz! 🌸"


# ==================== STATS SCHEMAS ====================
class AdminStatsOut(BaseModel):
    total_users: int
    new_users_this_week: int
    total_orders: int
    new_orders: int
    accepted_orders: int
    total_products: int
    in_stock_products: int
    top_viewed_products: List[ProductOut]
    most_wishlisted_products: List[Dict[str, Any]]
    orders_per_day: List[Dict[str, Any]]


# ==================== BROADCAST SCHEMAS ====================
class BroadcastCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    photo_url: Optional[str] = None


# ==================== CONTEST SCHEMAS ====================
class ContestCreate(BaseModel):
    prize_1: str = Field(..., min_length=1, max_length=255)
    prize_2: str = Field(..., min_length=1, max_length=255)
    prize_3: str = Field(..., min_length=1, max_length=255)
    ends_at: datetime
    photo_file_id: Optional[str] = None
    only_new_subscribers: bool = True


class ContestUpdatePrizes(BaseModel):
    prize_1: str = Field(..., min_length=1, max_length=255)
    prize_2: str = Field(..., min_length=1, max_length=255)
    prize_3: str = Field(..., min_length=1, max_length=255)


class ContestExtend(BaseModel):
    additional_days: Optional[int] = Field(default=None, ge=1, le=60)
    new_ends_at: Optional[datetime] = None


class ContestOut(BaseModel):
    id: int
    prize_1: str
    prize_2: str
    prize_3: str
    photo_file_id: Optional[str] = None
    channel_message_id: Optional[int] = None
    status: str
    only_new_subscribers: bool = True
    created_at: datetime
    ends_at: datetime
    formatted_ends_at: str = ""
    is_active: bool = False
    total_participants: int = 0
    total_confirmed_invites: int = 0
    channel_url: str = ""
    winners_snapshot: Optional[List[Dict[str, Any]]] = None
    total_subscribers_gained: int = 0

    model_config = ConfigDict(from_attributes=True)


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    name: str
    username: Optional[str] = None
    score: int
    last_confirmed_at: Optional[datetime] = None


class ContestInviteItem(BaseModel):
    id: int
    invitee_id: int
    name: str
    username: Optional[str] = None
    status: str  # pending, confirmed, revoked
    started_at: datetime
    confirmed_at: Optional[datetime] = None


class MyContestStatsOut(BaseModel):
    has_active_contest: bool
    contest: Optional[ContestOut] = None
    user_id: int
    invite_link: str
    score: int
    rank: Optional[int] = None
    next_rank_score: Optional[int] = None
    invites: List[ContestInviteItem] = Field(default_factory=list)


class DisqualifyPayload(BaseModel):
    user_id: int
    reason: str = Field(default="Suspicious referral activity", max_length=255)


class SuspiciousUserItem(BaseModel):
    referrer_id: int
    name: str
    username: Optional[str] = None
    total_invites: int
    confirmed_invites: int
    revoked_invites: int
    revoked_ratio: float

