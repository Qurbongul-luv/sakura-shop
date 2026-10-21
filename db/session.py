from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from api.config import settings
from db.models import Base

# Normalize database URL if needed
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://")
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

# Handle SSL parameter and Neon pooling for asyncpg
if "postgresql" in db_url:
    if "sslmode=require" in db_url:
        db_url = db_url.replace("sslmode=require", "ssl=require")
    # Neon direct connection optimization
    if "neon.tech" in db_url:
        db_url = db_url.replace("-pooler.", ".")
        db_url = db_url.replace("&channel_binding=require", "").replace("channel_binding=require&", "").replace("channel_binding=require", "")

# Neon suspends idle compute (~5 min) and drops pooled connections; ping before use and
# recycle old ones so the first request after a quiet period doesn't fail.
pool_options = {"pool_pre_ping": True, "pool_recycle": 240} if "postgresql" in db_url else {}

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    **pool_options,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
