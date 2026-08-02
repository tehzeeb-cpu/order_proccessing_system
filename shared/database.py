# shared/database.py
"""
WHY THIS FILE EXISTS:
Provides a unified, async-native SQLAlchemy 2.0 engine factory and dependency generator for MySQL, 
complete with startup retry logic for containerized environments.

Why Startup Retry Logic?
When Docker Compose boots up, MySQL needs ~5 seconds to initialize database files and execute SQL init scripts.
Without retry logic, microservices boot faster than MySQL and crash with connection refusal. Retry logic 
ensures seamless container orchestration without race conditions.

Interview Explanation:
"Microservices use a retry loop during startup to await database readiness. This guarantees zero startup crash loops 
when containers boot concurrently in Kubernetes or Docker Compose."
"""

import os
import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Default database host configurations
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "rootpassword")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")


def get_database_url(db_name: str) -> str:
    """Constructs async MySQL connection string using aiomysql driver."""
    return f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{db_name}?charset=utf8mb4"


def create_async_db_sessionmaker(db_name: str):
    """
    Creates an async engine and session factory for a specific microservice database.
    Enforces pool size and pre-ping health checks.
    """
    db_url = get_database_url(db_name)
    engine = create_async_engine(
        db_url,
        echo=False,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    return engine, session_factory


async def init_db_with_retry(engine, metadata, logger=None, max_retries: int = 15, delay_seconds: int = 2):
    """
    Awaits MySQL database readiness and creates tables with exponential retry logic.
    """
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            if logger:
                logger.info("Successfully connected to MySQL and initialized database tables.")
            return True
        except Exception as exc:
            if logger:
                logger.warning(f"MySQL connection attempt {attempt}/{max_retries} failed ({str(exc)}). Retrying in {delay_seconds}s...")
            await asyncio.sleep(delay_seconds)

    raise RuntimeError(f"Could not connect to MySQL after {max_retries} attempts.")
