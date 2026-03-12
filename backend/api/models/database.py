import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("sahayai.db")

# We need the async version of the postgres URL — asyncpg instead of psycopg2
# .env has: postgresql://postgres:sahayai@localhost:5432/sahayai
# We swap it to: postgresql+asyncpg://... so SQLAlchemy uses the async driver
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:sahayai@localhost:5432/sahayai"
).replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency — gives each request its own DB session and cleans up after"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Called once on startup — creates all tables if they don't exist yet"""
    from api.models.tables import (
        User, CaregiverLink, Routine, Event, Alert,
        DailySummary, Conversation, ConversationMessage,
        Reminder, CCTScore, AACScore
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All tables created (or already exist)")


async def close_db():
    """Called on shutdown — close the connection pool cleanly"""
    await engine.dispose()
    logger.info("DB connection pool closed")