"""
Owner-only profit: purchase cost is stored per product (cost_som) and copied onto each order as
cost_total when the order is placed, so later price or cost edits never rewrite past profit.
Nothing here is ever shown to plain admins or customers.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from db.models import Admin, Order, Product, utcnow

# Orders that represent a real sale: accepted onward, never new or cancelled.
SOLD_STATUSES = ("accepted", "purchased", "shipping", "arrived", "delivered")
TOP_PRODUCTS = 5


@dataclass(frozen=True)
class ProfitReport:
    orders: int
    revenue: int
    costed_orders: int
    costed_revenue: int
    cost: int
    uncosted_orders: int
    top_products: Tuple[Tuple[str, int, int], ...]  # (title, qty, revenue)

    @property
    def profit(self) -> int:
        return self.costed_revenue - self.cost

    @property
    def margin_percent(self) -> Optional[float]:
        return round(self.profit / self.costed_revenue * 100, 1) if self.costed_revenue else None


async def is_owner(session: AsyncSession, user_id: int) -> bool:
    if settings.DEV_ADMIN_ID and user_id == settings.DEV_ADMIN_ID:
        return True
    admin = (await session.execute(select(Admin).where(Admin.telegram_id == user_id))).scalars().first()
    return admin is not None and admin.role == "owner"


def _qty(item: Mapping[str, Any]) -> int:
    try:
        return max(1, int(item.get("qty", 1)))
    except (TypeError, ValueError):
        return 1


async def order_cost(session: AsyncSession, items: Sequence[Mapping[str, Any]]) -> Optional[int]:
    """Sum of cost × qty, or None when any item has no known cost (profit would be a guess)."""
    if not items:
        return None
    ids = []
    for item in items:
        try:
            ids.append(int(item.get("product_id")))
        except (TypeError, ValueError):
            return None
    rows = (await session.execute(select(Product.id, Product.cost_som).where(Product.id.in_(ids)))).all()
    costs = {row.id: row.cost_som for row in rows}
    total = 0
    for pid, item in zip(ids, items, strict=True):
        cost = costs.get(pid)
        if cost is None:
            return None
        total += int(cost) * _qty(item)
    return total


def summarize(orders: Iterable[Order]) -> ProfitReport:
    count = revenue = costed = costed_revenue = cost = 0
    per_product: Dict[str, List[int]] = {}
    for o in orders:
        count += 1
        revenue += o.total or 0
        if o.cost_total is not None:
            costed += 1
            costed_revenue += o.total or 0
            cost += o.cost_total
        for item in o.items_snapshot or []:
            title = str(item.get("title") or "Mahsulot")
            qty = _qty(item)
            try:
                line = int(item.get("price", 0)) * qty
            except (TypeError, ValueError):
                line = 0
            stats = per_product.setdefault(title, [0, 0])
            stats[0] += qty
            stats[1] += line
    top = sorted(per_product.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))[:TOP_PRODUCTS]
    return ProfitReport(
        orders=count,
        revenue=revenue,
        costed_orders=costed,
        costed_revenue=costed_revenue,
        cost=cost,
        uncosted_orders=count - costed,
        top_products=tuple((t, s[0], s[1]) for t, s in top),
    )


async def build_report(session: AsyncSession, days: Optional[int]) -> ProfitReport:
    stmt = select(Order).where(Order.status.in_(SOLD_STATUSES))
    if days:
        since: datetime = utcnow() - timedelta(days=days)
        stmt = stmt.where(Order.created_at >= since)
    orders = (await session.execute(stmt)).scalars().all()
    return summarize(orders)
