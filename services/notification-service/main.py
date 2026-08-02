# services/notification-service/main.py
"""
WHY THIS FILE EXISTS:
Entry point for Notification Service FastAPI application (Port 8005).

Business Requirements Satisfied:
1. Scheduled Job: Runs every 15 minutes (or configurable interval) scanning for SHIPPED orders.
2. Exactly-Once Notification: Employs two layers of protection:
   - Redis Distributed Lock (`lock:notification_job`) to prevent race conditions between service replicas.
   - DB Unique Index on `order_id` in `notification_db` to guarantee no order receives double notifications.

Interview Explanation:
"Distributed cron jobs in microservices risk duplicate execution if scaled horizontally. We use a Redis distributed 
lock to select a leader for each execution window, and a UNIQUE constraint on order_id in MySQL to enforce exactly-once delivery."
"""

import os
import sys
import asyncio
import httpx
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.database import create_async_db_sessionmaker, Base, init_db_with_retry
from shared.logging import setup_logger
from shared.middleware import get_redis_client
from models import NotificationModel

logger = setup_logger("notification-service")
engine, SessionLocal = create_async_db_sessionmaker("notification_db")

COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8000")
JOB_INTERVAL_SECONDS = int(os.getenv("NOTIFICATION_JOB_INTERVAL", "30"))

app = FastAPI(title="Notification Service", version="1.0.0")


@app.on_event("startup")
async def startup():
    await init_db_with_retry(engine, Base.metadata, logger)
    # Start background polling loop
    asyncio.create_task(background_notification_scheduler())


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def process_shipped_notifications():
    """
    Core notification execution loop protected by Redis Lock.
    """
    redis = get_redis_client()
    lock_key = "lock:notification_job"
    
    # 1. Acquire Redis Distributed Lock (TTL 20 seconds)
    acquired = await redis.set(lock_key, "locked", nx=True, ex=20)
    if not acquired:
        logger.info("Notification job lock held by another instance. Skipping run.")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        logger.info("Acquired notification job lock. Fetching shipped orders...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(f"{COORDINATOR_URL}/api/v1/coordinator/shipped-orders")
            if res.status_code != 200:
                logger.error(f"Failed to fetch shipped orders from coordinator: {res.text}")
                return {"status": "error", "message": res.text}
            
            shipped_orders = res.json().get("orders", [])

        sent_count = 0
        async with SessionLocal() as db:
            for order in shipped_orders:
                order_id = order["order_id"]
                # Check if notification already sent
                existing = await db.execute(select(NotificationModel).where(NotificationModel.order_id == order_id))
                if existing.scalar_one_or_none():
                    continue

                try:
                    notification = NotificationModel(order_id=order_id, channel="EMAIL")
                    db.add(notification)
                    await db.commit()
                    sent_count += 1
                    logger.info(f"Notification successfully sent for order: {order_id}", extra={"order_id": order_id})
                except IntegrityError:
                    await db.rollback()
                    logger.info(f"Notification already recorded concurrently for order: {order_id}")

        return {"status": "success", "notifications_sent": sent_count}
    finally:
        # Release lock
        await redis.delete(lock_key)


async def background_notification_scheduler():
    """Periodic background scheduler loop."""
    logger.info(f"Notification background scheduler started (Interval: {JOB_INTERVAL_SECONDS}s).")
    while True:
        await asyncio.sleep(JOB_INTERVAL_SECONDS)
        try:
            await process_shipped_notifications()
        except Exception as e:
            logger.error(f"Error in background notification scheduler: {str(e)}")


@app.post("/api/v1/notifications/trigger")
async def trigger_notifications_manual():
    """Manual REST trigger for testing/demo purposes."""
    return await process_shipped_notifications()


@app.get("/api/v1/notifications")
async def get_notifications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationModel).order_by(NotificationModel.sent_at.desc()))
    items = result.scalars().all()
    return [{"id": n.id, "order_id": n.order_id, "sent_at": n.sent_at, "channel": n.channel} for n in items]


@app.post("/api/v1/notifications/reset")
async def reset_notifications(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    await db.execute(delete(NotificationModel))
    await db.commit()
    return {"message": "Notifications reset successfully"}
