"""PostgreSQL async database setup (SQLAlchemy 2.0)."""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://bsapp:bsapp@localhost:5432/bsapp?ssl=disable"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they don't exist yet, and apply migrations."""
    from src import db_models  # noqa: F401 – ensure models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate: drop obsolete columns from session_presets
        for col in ("active_persona_ids", "active_task_ids"):
            await conn.execute(
                __import__("sqlalchemy").text(
                    f"ALTER TABLE session_presets DROP COLUMN IF EXISTS {col}"
                )
            )
