# shared/schemas.py
"""
WHY THIS FILE EXISTS:
Centralized schema definitions (Pydantic V2) enforce data contract consistency between 
the Saga Coordinator and Microservices. 

Why this approach?
Instead of duplicating schema models across microservices, sharing a unified Pydantic schema library 
guarantees strong typing, payload validation, and prevents runtime deserialization bugs.

Interview Explanation:
"By standardizing schemas in a shared contract layer, microservices agree on payload shapes and status 
enums. Pydantic V2 provides ultra-fast Rust-backed validation and automatic OpenAPI doc generation."
"""

from enum import Enum
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PLACED = "PLACED"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


class SagaStepName(str, Enum):
    ORDER = "ORDER"
    INVENTORY = "INVENTORY"
    PAYMENT = "PAYMENT"
    SHIPPING = "SHIPPING"


class SagaStepStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"


# --- Service DTOs ---

class OrderCreateRequest(BaseModel):
    order_id: str = Field(..., example="ORD000001")
    sku: str = Field(..., example="WIDGET-A")
    qty: int = Field(..., gt=0, example=5)
    amount: float = Field(..., gt=0.0, example=199.99)
    fail_at: Optional[str] = None
    comp_fail_at: Optional[str] = None


class OrderResponse(BaseModel):
    order_id: str
    sku: str
    qty: int
    amount: float
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InventoryReserveRequest(BaseModel):
    order_id: str
    sku: str
    qty: int
    fail_at: Optional[str] = None


class InventoryReleaseRequest(BaseModel):
    order_id: str
    sku: str
    qty: int
    comp_fail_at: Optional[str] = None


class PaymentChargeRequest(BaseModel):
    order_id: str
    amount: float
    fail_at: Optional[str] = None


class PaymentRefundRequest(BaseModel):
    order_id: str
    amount: float
    comp_fail_at: Optional[str] = None


class ShippingCreateRequest(BaseModel):
    order_id: str
    sku: str
    qty: int
    fail_at: Optional[str] = None


class ShippingCancelRequest(BaseModel):
    order_id: Optional[str] = None
    comp_fail_at: Optional[str] = None


class GenericServiceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# --- Coordinator & Saga DTOs ---

class StepExecutionDetail(BaseModel):
    step_name: SagaStepName
    status: SagaStepStatus
    retry_count: int = 0
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrderDetailResponse(BaseModel):
    order_id: str
    sku: str
    qty: int
    amount: float
    status: OrderStatus
    fail_at: Optional[str] = None
    comp_fail_at: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    steps: List[StepExecutionDetail] = []
    model_config = ConfigDict(from_attributes=True)


class DashboardStatsResponse(BaseModel):
    total_orders: int
    placed_count: int
    shipped_count: int
    cancelled_count: int
    needs_attention_count: int
    in_progress_count: int


class AuditLogEntry(BaseModel):
    id: int
    order_id: str
    level: str
    event_type: str
    message: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
