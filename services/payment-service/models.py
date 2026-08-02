# services/payment-service/models.py
"""
WHY THIS FILE EXISTS:
Defines ORM models for Payment Service database (`payment_db`).
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from datetime import datetime
from shared.database import Base


class PaymentModel(Base):
    __tablename__ = "payments"

    payment_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), nullable=False, unique=True, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default="CHARGED")  # CHARGED, REFUNDED
    created_at = Column(DateTime, default=datetime.utcnow)


class PaymentIdempotencyModel(Base):
    __tablename__ = "payment_idempotency"

    idempotency_key = Column(String(128), primary_key=True)
    response_body = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
