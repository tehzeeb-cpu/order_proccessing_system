# coordinator/models.py
"""
WHY THIS FILE EXISTS:
Defines ORM models for Coordinator database (`coordinator_db`).

Why these tables?
1. `saga_orders`: State store for order lifecycle (`PENDING`, `IN_PROGRESS`, `PLACED`, `SHIPPED`, `CANCELLED`, `NEEDS_ATTENTION`).
2. `saga_step_executions`: State store for individual Saga steps (`ORDER`, `INVENTORY`, `PAYMENT`, `SHIPPING`), tracking step-level status, retry counts, latencies, and error tracebacks.
3. `saga_logs`: Audit trail recording every state change and event.

Interview Explanation:
"The Saga Coordinator maintains write-ahead state in coordinator_db. Before calling microservices, 
it records step execution records. This guarantees complete auditability and enables restart recovery."
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum as SQLEnum, JSON, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from shared.database import Base
from shared.schemas import OrderStatus, SagaStepName, SagaStepStatus


class SagaOrderModel(Base):
    __tablename__ = "saga_orders"

    order_id = Column(String(64), primary_key=True)
    sku = Column(String(64), nullable=False)
    qty = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)
    fail_at = Column(String(32), nullable=True)
    comp_fail_at = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    steps = relationship("SagaStepExecutionModel", back_populates="order", cascade="all, delete-orphan")
    logs = relationship("SagaLogModel", back_populates="order", cascade="all, delete-orphan")


class SagaStepExecutionModel(Base):
    __tablename__ = "saga_step_executions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(64), ForeignKey("saga_orders.order_id", ondelete="CASCADE"), nullable=False)
    step_name = Column(SQLEnum(SagaStepName), nullable=False)
    status = Column(SQLEnum(SagaStepStatus), nullable=False, default=SagaStepStatus.PENDING)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("SagaOrderModel", back_populates="steps")


class SagaLogModel(Base):
    __tablename__ = "saga_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(64), ForeignKey("saga_orders.order_id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(String(16), nullable=False)
    event_type = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("SagaOrderModel", back_populates="logs")
