# services/order-service/main.py
"""
WHY THIS FILE EXISTS:
Entry point for the standalone Order Service FastAPI application.

Why independent application?
Each microservice runs as an isolated process on its own port (Port 8001), listening for REST API requests 
from the Saga Coordinator.

Interview Explanation:
"The Order Service is decoupled from inventory, payments, and shipping. It only manages order record creation 
and cancellation within order_db."
"""

import os
import json
import sys
from fastapi import FastAPI, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Ensure shared package is in import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.database import create_async_db_sessionmaker, Base, init_db_with_retry
from shared.schemas import OrderCreateRequest, GenericServiceResponse
from shared.logging import setup_logger
from shared.middleware import get_redis_client, check_idempotency_key, save_idempotency_key
from models import OrderModel, OrderIdempotencyModel

logger = setup_logger("order-service")
engine, SessionLocal = create_async_db_sessionmaker("order_db")

app = FastAPI(title="Order Service", version="1.0.0")


@app.on_event("startup")
async def startup():
    await init_db_with_retry(engine, Base.metadata, logger)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


@app.post("/api/v1/orders", status_code=201)
async def create_order(
    req: OrderCreateRequest,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates an order record.
    Simulates failure if req.fail_at == 'CREATE_ORDER' or 'ORDER'.
    """
    redis = get_redis_client()
    
    # 1. Idempotency Check (Redis)
    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            logger.info(f"Order Service idempotency hit (Redis) for key: {idempotency_key}")
            return json.loads(cached)

        # 2. Idempotency Check (DB)
        result = await db.execute(select(OrderIdempotencyModel).where(OrderIdempotencyModel.idempotency_key == idempotency_key))
        db_key = result.scalar_one_or_none()
        if db_key:
            logger.info(f"Order Service idempotency hit (DB) for key: {idempotency_key}")
            return json.loads(db_key.response_body)

    # 3. Failure Simulation Check
    if req.fail_at in ["CREATE_ORDER", "ORDER"]:
        logger.warning(f"Simulating CREATE_ORDER failure for order_id: {req.order_id}")
        raise HTTPException(status_code=400, detail=f"Simulated failure at {req.fail_at}")

    # 4. Business Logic
    existing = await db.get(OrderModel, req.order_id)
    if not existing:
        new_order = OrderModel(
            order_id=req.order_id,
            sku=req.sku,
            qty=req.qty,
            amount=req.amount,
            status="CREATED"
        )
        db.add(new_order)

    res_data = {"order_id": req.order_id, "status": "CREATED"}
    
    # 5. Persist Idempotency
    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(OrderIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=201))
        await save_idempotency_key(redis, idempotency_key, res_json)

    await db.commit()
    return res_data


@app.post("/api/v1/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    comp_fail_at: str = None,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancels an order record (Compensation step).
    Simulates compensation failure if comp_fail_at == 'CANCEL_ORDER' or 'ORDER'.
    """
    redis = get_redis_client()

    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            return json.loads(cached)

    if comp_fail_at in ["CANCEL_ORDER", "ORDER", "CANCEL"]:
        logger.warning(f"Simulating CANCEL_ORDER compensation failure for order_id: {order_id}")
        raise HTTPException(status_code=500, detail=f"Simulated compensation failure at {comp_fail_at}")

    order = await db.get(OrderModel, order_id)
    if order:
        order.status = "CANCELLED"
        await db.commit()

    res_data = {"order_id": order_id, "status": "CANCELLED"}

    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(OrderIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=200))
        await save_idempotency_key(redis, idempotency_key, res_json)
        await db.commit()

    return res_data


@app.post("/api/v1/orders/reset")
async def reset_orders(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    await db.execute(delete(OrderIdempotencyModel))
    await db.execute(delete(OrderModel))
    await db.commit()
    return {"message": "Order database reset successfully"}
