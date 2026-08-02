# services/payment-service/main.py
"""
WHY THIS FILE EXISTS:
Entry point for Payment Service FastAPI application (Port 8003).

Business Logic:
- Charge Payment: Creates a payment record (`CHARGED`).
- Refund Payment (Compensation): Updates payment record (`REFUNDED`).
- Failure Flags: Honors `fail_at` (`CHARGE_PAYMENT`, `PAYMENT`, `CHARGE`) and `comp_fail_at` (`REFUND_PAYMENT`, `PAYMENT`, `REFUND`).
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
from shared.schemas import PaymentChargeRequest, PaymentRefundRequest
from shared.logging import setup_logger
from shared.middleware import get_redis_client, check_idempotency_key, save_idempotency_key
from models import PaymentModel, PaymentIdempotencyModel

logger = setup_logger("payment-service")
engine, SessionLocal = create_async_db_sessionmaker("payment_db")

app = FastAPI(title="Payment Service", version="1.0.0")


@app.on_event("startup")
async def startup():
    await init_db_with_retry(engine, Base.metadata, logger)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


@app.post("/api/v1/payments/charge")
async def charge_payment(
    req: PaymentChargeRequest,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    redis = get_redis_client()

    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            return json.loads(cached)

        result = await db.execute(select(PaymentIdempotencyModel).where(PaymentIdempotencyModel.idempotency_key == idempotency_key))
        db_key = result.scalar_one_or_none()
        if db_key:
            return json.loads(db_key.response_body)

    if req.fail_at in ["CHARGE_PAYMENT", "PAYMENT", "CHARGE"]:
        logger.warning(f"Simulating CHARGE_PAYMENT failure for order_id: {req.order_id}")
        raise HTTPException(status_code=400, detail=f"Simulated failure at {req.fail_at}")

    # Charge transaction
    payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    payment = PaymentModel(payment_id=payment_id, order_id=req.order_id, amount=req.amount, status="CHARGED")
    db.add(payment)

    res_data = {"payment_id": payment_id, "order_id": req.order_id, "amount": req.amount, "status": "CHARGED"}

    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(PaymentIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=200))
        await save_idempotency_key(redis, idempotency_key, res_json)

    await db.commit()
    return res_data


@app.post("/api/v1/payments/refund")
async def refund_payment(
    req: PaymentRefundRequest,
    idempotency_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    redis = get_redis_client()

    if idempotency_key:
        cached = await check_idempotency_key(redis, idempotency_key)
        if cached:
            return json.loads(cached)

    if req.comp_fail_at in ["REFUND_PAYMENT", "PAYMENT", "REFUND"]:
        logger.warning(f"Simulating REFUND_PAYMENT compensation failure for order_id: {req.order_id}")
        raise HTTPException(status_code=500, detail=f"Simulated compensation failure at {req.comp_fail_at}")

    result = await db.execute(select(PaymentModel).where(PaymentModel.order_id == req.order_id))
    payment = result.scalar_one_or_none()
    if payment:
        payment.status = "REFUNDED"
        await db.commit()

    res_data = {"order_id": req.order_id, "amount": req.amount, "status": "REFUNDED"}

    if idempotency_key:
        res_json = json.dumps(res_data)
        db.add(PaymentIdempotencyModel(idempotency_key=idempotency_key, response_body=res_json, status_code=200))
    return res_data


@app.post("/api/v1/payments/reset")
async def reset_payments(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    await db.execute(delete(PaymentIdempotencyModel))
    await db.execute(delete(PaymentModel))
    await db.commit()
    return {"message": "Payment database reset successfully"}
