# services/shipping-service/main.py
"""
WHY THIS FILE EXISTS:
Entry point for Shipping Service FastAPI application (Port 8004).

Business Logic:
- Create Shipment: Creates a shipment record (`CREATED`).
- Cancel Shipment (Compensation): Updates shipment record (`CANCELLED`).
- Mark Shipped: Updates shipment record (`SHIPPED`).
- Failure Flags: Honors `fail_at` (`CREATE_SHIPMENT`, `SHIPPING`) and `comp_fail_at` (`CANCEL_SHIPMENT`, `SHIPPING`).
"""

import os
import uuid
import json
import sys
from fastapi import FastAPI, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.database import create_async_db_sessionmaker, Base, init_db_with_retry
from shared.schemas import ShippingCreateRequest, ShippingCancelRequest
from shared.logging import setup_logger
from shared.middleware import get_redis_client, check_idempotency_key, save_idempotency_key
from models import ShipmentModel, ShippingIdempotencyModel

logger = setup_logger("shipping-service")
engine, SessionLocal = create_async_db_sessionmaker("shipping_db")

app = FastAPI(title="Shipping Service", version="1.0.0")


@app.on_event("startup")
async def startup():
    await init_db_with_retry(engine, Base.metadata, logger)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


@app.post("/api/v1/shipments", status_code=201)
async def create_shipment(
    req: ShippingCreateRequest,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    redis = get_redis_client()

    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            return json.loads(cached)

    if req.fail_at in ["CREATE_SHIPMENT", "SHIPPING", "SHIPMENT"]:
        logger.warning(f"Simulating CREATE_SHIPMENT failure for order_id: {req.order_id}")
        raise HTTPException(status_code=400, detail=f"Simulated failure at {req.fail_at}")

    shipment_id = f"SHIP-{uuid.uuid4().hex[:8].upper()}"
    shipment = ShipmentModel(
        shipment_id=shipment_id,
        order_id=req.order_id,
        sku=req.sku,
        qty=req.qty,
        status="CREATED"
    )
    db.add(shipment)

    res_data = {"shipment_id": shipment_id, "order_id": req.order_id, "status": "CREATED"}

    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(ShippingIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=201))
        await save_idempotency_key(redis, idempotency_key, res_json)

    await db.commit()
    return res_data


@app.post("/api/v1/shipments/{order_id}/cancel")
async def cancel_shipment(
    order_id: str,
    req: ShippingCancelRequest = None,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    redis = get_redis_client()

    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            return json.loads(cached)

    comp_fail = req.comp_fail_at if req else None
    if comp_fail in ["CANCEL_SHIPMENT", "SHIPPING", "CANCEL"]:
        logger.warning(f"Simulating CANCEL_SHIPMENT compensation failure for order_id: {order_id}")
        raise HTTPException(status_code=500, detail=f"Simulated compensation failure at {comp_fail}")

    result = await db.execute(select(ShipmentModel).where(ShipmentModel.order_id == order_id))
    shipment = result.scalar_one_or_none()
    if shipment:
        shipment.status = "CANCELLED"
        await db.commit()

    res_data = {"order_id": order_id, "status": "CANCELLED"}

    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(ShippingIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=200))
        await save_idempotency_key(redis, idempotency_key, res_json)
        await db.commit()

    return res_data


@app.post("/api/v1/shipments/{order_id}/ship")
async def mark_shipped(order_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ShipmentModel).where(ShipmentModel.order_id == order_id))
    shipment = result.scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment record not found")

    shipment.status = "SHIPPED"
    await db.commit()
    return {"order_id": order_id, "status": "SHIPPED"}


@app.post("/api/v1/shipments/reset")
async def reset_shipments(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    await db.execute(delete(ShippingIdempotencyModel))
    await db.execute(delete(ShipmentModel))
    await db.commit()
    return {"message": "Shipping database reset successfully"}
