# services/inventory-service/models.py
"""
WHY THIS FILE EXISTS:
Defines ORM models for Inventory Service database (`inventory_db`).

Why separate tables for Inventory and Reservations?
To prevent race conditions during concurrent stock reservations, stock items use `available_qty` and `reserved_qty` 
counters while individual reservation records record which order reserved how many items.
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, BigInteger
from datetime import datetime
from shared.database import Base


class InventoryModel(Base):
    __tablename__ = "inventory"

    sku = Column(String(64), primary_key=True)
    available_qty = Column(Integer, nullable=False, default=0)
    reserved_qty = Column(Integer, nullable=False, default=0)


class InventoryReservationModel(Base):
    __tablename__ = "inventory_reservations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(64), nullable=False, index=True)
    sku = Column(String(64), nullable=False)
    qty = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="RESERVED")  # RESERVED, RELEASED
    created_at = Column(DateTime, default=datetime.utcnow)


class InventoryIdempotencyModel(Base):
    __tablename__ = "inventory_idempotency"

    idempotency_key = Column(String(128), primary_key=True)
    response_body = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
