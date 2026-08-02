# services/notification-service/models.py
"""
WHY THIS FILE EXISTS:
Defines ORM models for Notification Service database (`notification_db`).

Why a separate table for Notifications?
The notification domain records dispatch metadata (sent_at, channel, status).
Having a UNIQUE constraint on `order_id` in `notifications` guarantees DB-level exactly-once enforcement.
"""

from sqlalchemy import Column, String, DateTime, BigInteger
from datetime import datetime
from shared.database import Base


class NotificationModel(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(64), nullable=False, unique=True, index=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    channel = Column(String(32), default="EMAIL")
