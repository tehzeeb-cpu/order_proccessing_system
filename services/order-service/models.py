# services/order-service/models.py
"""
WHY THIS FILE EXISTS:
Defines SQLAlchemy ORM models specifically for the Order Service database (`order_db`).

Why isolated models per service?
Microservices must never share ORM model definitions or database tables.
The Order Service owns the canonical record of the initial order creation.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from datetime import datetime
from shared.database import Base


class OrderModel(Base):
    __tablename__ = "orders"

    order_id = Column(String(64), primary_key=True)
    sku = Column(String(64), nullable=False)
    qty = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default="CREATED")  # CREATED, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)


class OrderIdempotencyModel(Base):
    __tablename__ = "order_idempotency"

    idempotency_key = Column(String(128), primary_key=True)
    response_body = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
