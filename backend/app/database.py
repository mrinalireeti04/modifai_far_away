from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

from app.config import get_settings

settings = get_settings()

# We need an async driver for FastAPI. We'll use asyncpg.
# Replace postgresql:// with postgresql+asyncpg:// if needed.
db_url = settings.DATABASE_URL
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "?sslmode=" in db_url:
        db_url = db_url.split("?sslmode=")[0]

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    future=True
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to provide a database session."""
    async with async_session_maker() as session:
        yield session
