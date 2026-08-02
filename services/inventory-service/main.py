# services/inventory-service/main.py
"""
WHY THIS FILE EXISTS:
Entry point for Inventory Service FastAPI application (Port 8002).

Business Logic:
- Reserve Stock: Decrements `available_qty`, increments `reserved_qty`, creates reservation record.
- Release Stock (Compensation): Increments `available_qty`, decrements `reserved_qty`, updates reservation status to RELEASED.
- Failure Flags: Honors `fail_at` (`RESERVE_INVENTORY`, `INVENTORY`) and `comp_fail_at` (`RELEASE_INVENTORY`, `INVENTORY`).
"""

import os
import json
import sys
from typing import List, Dict, Any
from fastapi import FastAPI, Header, HTTPException, Depends, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.database import create_async_db_sessionmaker, Base, init_db_with_retry
from shared.schemas import InventoryReserveRequest, InventoryReleaseRequest
from shared.logging import setup_logger
from shared.middleware import get_redis_client, check_idempotency_key, save_idempotency_key
from models import InventoryModel, InventoryReservationModel, InventoryIdempotencyModel

logger = setup_logger("inventory-service")
engine, SessionLocal = create_async_db_sessionmaker("inventory_db")

app = FastAPI(title="Inventory Service", version="1.0.0")


class InventorySeedItem(BaseModel):
    sku: str
    qty: int


@app.on_event("startup")
async def startup():
    await init_db_with_retry(engine, Base.metadata, logger)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


@app.post("/api/v1/inventory/seed")
async def seed_inventory(items: List[InventorySeedItem] = Body(...), db: AsyncSession = Depends(get_db)):
    """Seeds inventory SKUs with initial stock from CSV."""
    for item in items:
        inv = await db.get(InventoryModel, item.sku)
        if inv:
            inv.available_qty = item.qty
        else:
            db.add(InventoryModel(sku=item.sku, available_qty=item.qty, reserved_qty=0))
    await db.commit()
    return {"message": f"Successfully seeded {len(items)} SKUs into inventory database."}


@app.post("/api/v1/inventory/reserve")
async def reserve_stock(
    req: InventoryReserveRequest,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    redis = get_redis_client()

    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            return json.loads(cached)
        
        result = await db.execute(select(InventoryIdempotencyModel).where(InventoryIdempotencyModel.idempotency_key == idempotency_key))
        if result.scalar_one_or_none():
            return json.loads(result.scalar_one_or_none().response_body)

    # Simulated failure
    if req.fail_at in ["RESERVE_INVENTORY", "INVENTORY"]:
        logger.warning(f"Simulating RESERVE_INVENTORY failure for order_id: {req.order_id}")
        raise HTTPException(status_code=400, detail=f"Simulated failure at {req.fail_at}")

    # Check stock
    inv = await db.get(InventoryModel, req.sku)
    if not inv or inv.available_qty < req.qty:
        raise HTTPException(status_code=400, detail=f"Insufficient stock for SKU {req.sku}")

    # Deduct stock & record reservation
    inv.available_qty -= req.qty
    inv.reserved_qty += req.qty
    
    res_rec = InventoryReservationModel(order_id=req.order_id, sku=req.sku, qty=req.qty, status="RESERVED")
    db.add(res_rec)

    res_data = {"order_id": req.order_id, "sku": req.sku, "qty": req.qty, "status": "RESERVED"}

    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(InventoryIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=200))
        await save_idempotency_key(redis, idempotency_key, res_json)

    await db.commit()
    return res_data


@app.post("/api/v1/inventory/release")
async def release_stock(
    req: InventoryReleaseRequest,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    redis = get_redis_client()

    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            return json.loads(cached)

    if req.comp_fail_at in ["RELEASE_INVENTORY", "INVENTORY"]:
        logger.warning(f"Simulating RELEASE_INVENTORY compensation failure for order_id: {req.order_id}")
        raise HTTPException(status_code=500, detail=f"Simulated compensation failure at {req.comp_fail_at}")

    # Find reservation
    result = await db.execute(
        select(InventoryReservationModel).where(
            InventoryReservationModel.order_id == req.order_id,
            InventoryReservationModel.sku == req.sku,
            InventoryReservationModel.status == "RESERVED"
        )
    )
    reservation = result.scalar_one_or_none()
    if reservation:
        reservation.status = "RELEASED"
        inv = await db.get(InventoryModel, req.sku)
        if inv:
            inv.available_qty += req.qty
            inv.reserved_qty = max(0, inv.reserved_qty - req.qty)
        await db.commit()

    res_data = {"order_id": req.order_id, "sku": req.sku, "qty": req.qty, "status": "RELEASED"}

    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(InventoryIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=200))
        await save_idempotency_key(redis, idempotency_key, res_json)
        await db.commit()

    return res_data
