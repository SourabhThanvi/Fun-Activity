"""
Database connection setup.

What this does:
    1. Reads DATABASE_URL from .env
    2. Creates an async connection to PostgreSQL
    3. Provides get_db() for FastAPI to use in routes
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Load .env from project root (one level up)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env")

# Create engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Base class — all models inherit from this
class Base(DeclarativeBase):
    pass


# FastAPI dependency — use this in routes to get a DB session
async def get_db():
    async with async_session() as session:
        yield session