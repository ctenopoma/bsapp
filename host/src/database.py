"""PostgreSQL async database setup (SQLAlchemy 2.0)."""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

_PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql+asyncpg://bsapp:bsapp@localhost:{_PG_PORT}/bsapp?ssl=disable"
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
        # Migrate: add last_known_ip to users (for IP-based session recovery)
        import sqlalchemy as _sa
        await conn.execute(_sa.text(
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS common_theme TEXT DEFAULT ''"
        ))
        await conn.execute(_sa.text(
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS pre_info TEXT DEFAULT ''"
        ))
        await conn.execute(_sa.text(
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS rag_context TEXT"
        ))
        await conn.execute(_sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_known_ip VARCHAR(45)"
        ))
        await conn.execute(_sa.text(
            "CREATE INDEX IF NOT EXISTS ix_users_last_known_ip ON users (last_known_ip)"
        ))
        await conn.execute(_sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS windows_username VARCHAR(255)"
        ))
        await conn.execute(_sa.text(
            "CREATE INDEX IF NOT EXISTS ix_users_windows_username ON users (windows_username)"
        ))
        # Migrate: add patent_presets table (new columns added via create_all above)
        # Migrate: add patent_context to messages (for patent analysis results in discussions)
        await conn.execute(_sa.text(
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS patent_context TEXT"
        ))
        # Migrate: patent_csvs table and new patent_preset columns
        await conn.execute(_sa.text(
            "ALTER TABLE patent_presets ADD COLUMN IF NOT EXISTS csv_id VARCHAR(36) REFERENCES patent_csvs(id) ON DELETE SET NULL"
        ))
        await conn.execute(_sa.text(
            "ALTER TABLE patent_presets ADD COLUMN IF NOT EXISTS selected_companies TEXT DEFAULT '[]'"
        ))
        await conn.execute(_sa.text(
            "ALTER TABLE patent_presets ADD COLUMN IF NOT EXISTS stats_config_json TEXT DEFAULT '[]'"
        ))
        await conn.execute(_sa.text(
            "ALTER TABLE patent_presets ADD COLUMN IF NOT EXISTS final_llm_prompt TEXT DEFAULT ''"
        ))
