# coordinator/main.py
"""
WHY THIS FILE EXISTS:
Entry point for the Saga Coordinator FastAPI Application (Port 8000).

Role in Architecture:
The Coordinator is the central gateway ("The Brain"). The Angular frontend communicates ONLY 
with the Coordinator. The Coordinator handles bulk uploads, monitors Saga executions, manages order 
status transitions, and exposes REST endpoints for manual operational retries.

Interview Explanation:
"By exposing a single gateway API for Angular, we encapsulate microservices internal topology. 
The Coordinator orchestrates distributed transactions while serving paginated dashboard queries."
"""

import os
import sys
import httpx
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.database import create_async_db_sessionmaker, Base, init_db_with_retry
from shared.schemas import (
    OrderStatus, SagaStepName, SagaStepStatus,
    DashboardStatsResponse, GenericServiceResponse
)
from shared.logging import setup_logger
from models import SagaOrderModel, SagaStepExecutionModel, SagaLogModel
from saga_engine import boot_recovery, retry_failed_compensation
from csv_ingestor import process_bulk_orders_stream, seed_inventory_from_file

logger = setup_logger("coordinator-gateway")
engine, SessionLocal = create_async_db_sessionmaker("coordinator_db")

app = FastAPI(title="Saga Coordinator Gateway", version="1.0.0")

# Enable CORS for Angular Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db_with_retry(engine, Base.metadata, logger)
    
    # Auto-seed inventory from workspace sample_inventory.csv if present
    seed_file_path = os.getenv("SAMPLE_INVENTORY_PATH", "../sample_inventory.csv")
    await seed_inventory_from_file(seed_file_path)
    
    # Execute Boot Recovery for any stuck IN_PROGRESS orders
    await boot_recovery(SessionLocal)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# --- APIs ---

@app.post("/api/v1/coordinator/upload-bulk")
async def upload_bulk_orders(file: UploadFile = File(...)):
    """
    Streams CSV file uploaded from Angular UI and dispatches Saga processing tasks.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    try:
        raw_bytes = await file.read()
        content = raw_bytes.decode("utf-8-sig", errors="ignore")
        count = await process_bulk_orders_stream(content, SessionLocal)
        return {"message": f"Successfully ingested CSV stream. Processing {count} orders concurrently.", "count": count}
    except Exception as e:
        logger.error(f"Error in upload_bulk_orders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading CSV file: {str(e)}")


@app.get("/api/v1/coordinator/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Returns aggregate order counts grouped by status."""
    total = (await db.execute(select(func.count(SagaOrderModel.order_id)))).scalar() or 0
    placed = (await db.execute(select(func.count(SagaOrderModel.order_id)).where(SagaOrderModel.status == OrderStatus.PLACED))).scalar() or 0
    shipped = (await db.execute(select(func.count(SagaOrderModel.order_id)).where(SagaOrderModel.status == OrderStatus.SHIPPED))).scalar() or 0
    cancelled = (await db.execute(select(func.count(SagaOrderModel.order_id)).where(SagaOrderModel.status == OrderStatus.CANCELLED))).scalar() or 0
    needs_attn = (await db.execute(select(func.count(SagaOrderModel.order_id)).where(SagaOrderModel.status == OrderStatus.NEEDS_ATTENTION))).scalar() or 0
    in_progress = (await db.execute(select(func.count(SagaOrderModel.order_id)).where(SagaOrderModel.status == OrderStatus.IN_PROGRESS))).scalar() or 0

    return DashboardStatsResponse(
        total_orders=total,
        placed_count=placed,
        shipped_count=shipped,
        cancelled_count=cancelled,
        needs_attention_count=needs_attn,
        in_progress_count=in_progress
    )


@app.get("/api/v1/coordinator/orders")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Paginated order query endpoint with status filtering and ID search."""
    stmt = select(SagaOrderModel)
    
    if status and status != "ALL":
        stmt = stmt.where(SagaOrderModel.status == status)
    if search:
        stmt = stmt.where(SagaOrderModel.order_id.like(f"%{search}%"))

    # Total count query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(SagaOrderModel.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    orders = result.scalars().all()

    items = []
    for o in orders:
        items.append({
            "order_id": o.order_id,
            "sku": o.sku,
            "qty": o.qty,
            "amount": o.amount,
            "status": o.status,
            "fail_at": o.fail_at,
            "comp_fail_at": o.comp_fail_at,
            "created_at": o.created_at,
            "updated_at": o.updated_at
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@app.get("/api/v1/coordinator/orders/{order_id}")
async def get_order_details(order_id: str, db: AsyncSession = Depends(get_db)):
    """Fetches full order state, step executions timeline, and audit logs."""
    order = await db.get(SagaOrderModel, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    steps_res = await db.execute(
        select(SagaStepExecutionModel).where(SagaStepExecutionModel.order_id == order_id)
    )
    steps = steps_res.scalars().all()

    logs_res = await db.execute(
        select(SagaLogModel).where(SagaLogModel.order_id == order_id).order_by(SagaLogModel.created_at.desc())
    )
    logs = logs_res.scalars().all()

    return {
        "order_id": order.order_id,
        "sku": order.sku,
        "qty": order.qty,
        "amount": order.amount,
        "status": order.status,
        "fail_at": order.fail_at,
        "comp_fail_at": order.comp_fail_at,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "steps": [
            {
                "step_name": s.step_name,
                "status": s.status,
                "retry_count": s.retry_count,
                "error_message": s.error_message,
                "execution_time_ms": s.execution_time_ms,
                "updated_at": s.updated_at
            } for s in steps
        ],
        "logs": [
            {
                "id": l.id,
                "level": l.level,
                "event_type": l.event_type,
                "message": l.message,
                "created_at": l.created_at
            } for l in logs
        ]
    }


@app.post("/api/v1/coordinator/orders/{order_id}/retry-undo")
async def retry_order_undo(order_id: str):
    """Manual trigger to re-run failed compensation for orders in NEEDS_ATTENTION."""
    success = await retry_failed_compensation(order_id, SessionLocal)
    if success:
        return {"success": True, "message": f"Successfully retried compensation. Order {order_id} is now CANCELLED."}
    else:
        return {"success": False, "message": f"Compensation retry failed. Order {order_id} remains in NEEDS_ATTENTION."}


@app.post("/api/v1/coordinator/orders/{order_id}/mark-shipped")
async def mark_order_shipped(order_id: str, db: AsyncSession = Depends(get_db)):
    """Marks a PLACED order as SHIPPED and notifies Shipping Service."""
    order = await db.get(SagaOrderModel, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.PLACED:
        raise HTTPException(status_code=400, detail="Only PLACED orders can be marked as SHIPPED.")

    order.status = OrderStatus.SHIPPED
    await db.commit()

    # Call Shipping Service mark shipped endpoint
    SHIPPING_SERVICE_URL = os.getenv("SHIPPING_SERVICE_URL", "http://localhost:8004")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(f"{SHIPPING_SERVICE_URL}/api/v1/shipments/{order_id}/ship")
        except Exception as e:
            logger.error(f"Error notifying shipping service for mark shipped: {str(e)}")

    return {"success": True, "order_id": order_id, "status": "SHIPPED"}


@app.get("/api/v1/coordinator/shipped-orders")
async def get_shipped_orders(db: AsyncSession = Depends(get_db)):
    """Endpoint consumed by Notification Service to discover shipped orders."""
    result = await db.execute(select(SagaOrderModel).where(SagaOrderModel.status == OrderStatus.SHIPPED))
    orders = result.scalars().all()
    return {"orders": [{"order_id": o.order_id} for o in orders]}


@app.get("/api/v1/coordinator/logs")
async def get_system_logs(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Global system audit logs."""
    stmt = select(SagaLogModel).order_by(SagaLogModel.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "order_id": l.order_id,
            "level": l.level,
            "event_type": l.event_type,
            "message": l.message,
            "created_at": l.created_at
        } for l in logs
    ]


@app.post("/api/v1/coordinator/reset-demo")
async def reset_demo_database(db: AsyncSession = Depends(get_db)):
    """Clears all orders and logs from coordinator_db, flushes Redis, resets all microservices, and re-seeds stock."""
    from sqlalchemy import delete
    from shared.middleware import get_redis_client

    # 1. Clear Coordinator DB
    await db.execute(delete(SagaLogModel))
    await db.execute(delete(SagaStepExecutionModel))
    await db.execute(delete(SagaOrderModel))
    await db.commit()

    # 2. Flush Redis cache (Idempotency keys & Locks)
    try:
        redis = get_redis_client()
        await redis.flushdb()
    except Exception as e:
        logger.warning(f"Failed to flush Redis: {str(e)}")

    # 3. Reset all microservices
    microservice_urls = [
        ("order", os.getenv("ORDER_SERVICE_URL", "http://order-service:8001") + "/api/v1/orders/reset"),
        ("inventory", os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8002") + "/api/v1/inventory/reset"),
        ("payment", os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8003") + "/api/v1/payments/reset"),
        ("shipping", os.getenv("SHIPPING_SERVICE_URL", "http://shipping-service:8004") + "/api/v1/shipments/reset"),
        ("notification", os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8005") + "/api/v1/notifications/reset"),
    ]

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in microservice_urls:
            try:
                await client.post(url)
            except Exception as e:
                logger.warning(f"Failed to reset {name} service: {str(e)}")

    # 4. Re-seed Inventory
    seed_file_path = os.getenv("SAMPLE_INVENTORY_PATH", "../sample_inventory.csv")
    await seed_inventory_from_file(seed_file_path)

    return {"message": "Global system state reset successfully across all 6 databases, Redis, and microservices."}
