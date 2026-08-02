# services/shipping-service/models.py
"""
WHY THIS FILE EXISTS:
Defines ORM models for Shipping Service database (`shipping_db`).
"""

from sqlalchemy import Column, String, Integer, DateTime, Text
from datetime import datetime
from shared.database import Base


class ShipmentModel(Base):
    __tablename__ = "shipments"

    shipment_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), nullable=False, unique=True, index=True)
    sku = Column(String(64), nullable=False)
    qty = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="CREATED")  # CREATED, CANCELLED, SHIPPED
    created_at = Column(DateTime, default=datetime.utcnow)


class ShippingIdempotencyModel(Base):
    __tablename__ = "shipping_idempotency"

    idempotency_key = Column(String(128), primary_key=True)
    response_body = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
