# coordinator/saga_engine.py
"""
WHY THIS FILE EXISTS:
The Saga Orchestrator engine ("The Brain").

Business Requirements Satisfied:
1. Parallel Execution: Executes Order, Inventory, Payment, and Shipping steps concurrently using asyncio.gather().
2. Compensation Rollback: If any step fails, compensates ONLY steps that actually completed successfully.
3. Needs Attention Handling: If an undo/compensation fails after retries, flags the order as NEEDS_ATTENTION.
4. Restart Recovery: Scans coordinator_db upon application start to resume incomplete Sagas.

Interview Explanation:
"Saga Orchestration centralizes workflow state transitions. We execute forward steps in parallel. 
On failure, we selectively compensate finished steps. If a compensation fails, the order enters NEEDS_ATTENTION 
to allow manual operational recovery without data corruption."
"""

import asyncio
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.schemas import OrderStatus, SagaStepName, SagaStepStatus
from shared.logging import setup_logger
from models import SagaOrderModel, SagaStepExecutionModel, SagaLogModel
from services_client import ServicesClient

logger = setup_logger("saga-engine")
client = ServicesClient()


async def log_event(db: AsyncSession, order_id: str, level: str, event_type: str, message: str, metadata: dict = None):
    log_entry = SagaLogModel(
        order_id=order_id,
        level=level,
        event_type=event_type,
        message=message,
        metadata_json=metadata
    )
    db.add(log_entry)


async def execute_order_saga(order_data: Dict[str, Any], session_factory) -> str:
    """
    Executes a single order Saga.
    """
    order_id = order_data["order_id"]
    sku = order_data["sku"]
    qty = order_data["qty"]
    amount = order_data["amount"]
    fail_at = order_data.get("fail_at")
    comp_fail_at = order_data.get("comp_fail_at")

    async with session_factory() as db:
        # 1. Initialize Order in DB
        order = await db.get(SagaOrderModel, order_id)
        if not order:
            order = SagaOrderModel(
                order_id=order_id,
                sku=sku,
                qty=qty,
                amount=amount,
                status=OrderStatus.IN_PROGRESS,
                fail_at=fail_at,
                comp_fail_at=comp_fail_at
            )
            db.add(order)
        else:
            order.status = OrderStatus.IN_PROGRESS

        # Create step execution records
        steps_map = {}
        for step_name in SagaStepName:
            step_rec = await db.execute(
                select(SagaStepExecutionModel).where(
                    SagaStepExecutionModel.order_id == order_id,
                    SagaStepExecutionModel.step_name == step_name
                )
            )
            existing_step = step_rec.scalar_one_or_none()
            if not existing_step:
                existing_step = SagaStepExecutionModel(
                    order_id=order_id,
                    step_name=step_name,
                    status=SagaStepStatus.PENDING
                )
                db.add(existing_step)
            steps_map[step_name] = existing_step

        await log_event(db, order_id, "INFO", "SAGA_STARTED", f"Saga initiated for order {order_id}")
        await db.commit()

    # 2. Execute 4 Steps in Parallel
    results = await asyncio.gather(
        client.execute_order_step(order_id, sku, qty, amount, fail_at),
        client.execute_inventory_step(order_id, sku, qty, fail_at),
        client.execute_payment_step(order_id, amount, fail_at),
        client.execute_shipping_step(order_id, sku, qty, fail_at),
        return_exceptions=True
    )

    order_res, inv_res, pay_res, ship_res = results

    step_results = {
        SagaStepName.ORDER: order_res if isinstance(order_res, tuple) else (False, 500, {"detail": str(order_res)}, 0),
        SagaStepName.INVENTORY: inv_res if isinstance(inv_res, tuple) else (False, 500, {"detail": str(inv_res)}, 0),
        SagaStepName.PAYMENT: pay_res if isinstance(pay_res, tuple) else (False, 500, {"detail": str(pay_res)}, 0),
        SagaStepName.SHIPPING: ship_res if isinstance(ship_res, tuple) else (False, 500, {"detail": str(ship_res)}, 0),
    }

    all_succeeded = all(success for success, _, _, _ in step_results.values())

    async with session_factory() as db:
        order = await db.get(SagaOrderModel, order_id)
        
        # Update step execution statuses in DB
        for step_name, (success, code, body, latency) in step_results.items():
            step_rec = (await db.execute(
                select(SagaStepExecutionModel).where(
                    SagaStepExecutionModel.order_id == order_id,
                    SagaStepExecutionModel.step_name == step_name
                )
            )).scalar_one()
            
            step_rec.execution_time_ms = latency
            if success:
                step_rec.status = SagaStepStatus.SUCCESS
            else:
                step_rec.status = SagaStepStatus.FAILED
                step_rec.error_message = body.get("detail", "Step execution failed")

        if all_succeeded:
            order.status = OrderStatus.PLACED
            await log_event(db, order_id, "INFO", "SAGA_SUCCESS", f"All 4 steps succeeded. Order PLACED.")
            await db.commit()
            return OrderStatus.PLACED

        # --- Failure Case: Trigger Compensation for Succeeded Steps ---
        await log_event(db, order_id, "WARN", "SAGA_FAILED", "One or more steps failed. Triggering rollback compensation.")
        await db.commit()

    # Identify succeeded steps to roll back
    succeeded_steps = [s_name for s_name, (success, _, _, _) in step_results.items() if success]
    
    compensation_tasks = []
    comp_step_names = []

    for step_name in succeeded_steps:
        comp_step_names.append(step_name)
        if step_name == SagaStepName.ORDER:
            compensation_tasks.append(client.compensate_order_step(order_id, comp_fail_at))
        elif step_name == SagaStepName.INVENTORY:
            compensation_tasks.append(client.compensate_inventory_step(order_id, sku, qty, comp_fail_at))
        elif step_name == SagaStepName.PAYMENT:
            compensation_tasks.append(client.compensate_payment_step(order_id, amount, comp_fail_at))
        elif step_name == SagaStepName.SHIPPING:
            compensation_tasks.append(client.compensate_shipping_step(order_id, comp_fail_at))

    if compensation_tasks:
        comp_results = await asyncio.gather(*compensation_tasks, return_exceptions=True)
    else:
        comp_results = []

    comp_failed = False
    async with session_factory() as db:
        order = await db.get(SagaOrderModel, order_id)
        
        for i, step_name in enumerate(comp_step_names):
            comp_res = comp_results[i]
            success = comp_res[0] if isinstance(comp_res, tuple) else False
            
            step_rec = (await db.execute(
                select(SagaStepExecutionModel).where(
                    SagaStepExecutionModel.order_id == order_id,
                    SagaStepExecutionModel.step_name == step_name
                )
            )).scalar_one()

            if success:
                step_rec.status = SagaStepStatus.COMPENSATED
            else:
                step_rec.status = SagaStepStatus.COMPENSATION_FAILED
                comp_failed = True
                await log_event(db, order_id, "ERROR", "COMPENSATION_FAILED", f"Compensation failed for step {step_name}")

        if comp_failed:
            order.status = OrderStatus.NEEDS_ATTENTION
            await log_event(db, order_id, "ERROR", "NEEDS_ATTENTION", "Compensation incomplete. Marked NEEDS_ATTENTION.")
        else:
            order.status = OrderStatus.CANCELLED
            await log_event(db, order_id, "INFO", "SAGA_CANCELLED", "All completed steps rolled back cleanly. Order CANCELLED.")

        await db.commit()

    return order.status


async def retry_failed_compensation(order_id: str, session_factory) -> bool:
    """
    Manually retries failed compensations for orders in NEEDS_ATTENTION status.
    """
    async with session_factory() as db:
        order = await db.get(SagaOrderModel, order_id)
        if not order or order.status != OrderStatus.NEEDS_ATTENTION:
            return False

        # Find steps with COMPENSATION_FAILED
        failed_steps = (await db.execute(
            select(SagaStepExecutionModel).where(
                SagaStepExecutionModel.order_id == order_id,
                SagaStepExecutionModel.status == SagaStepStatus.COMPENSATION_FAILED
            )
        )).scalars().all()

        sku = order.sku
        qty = order.qty
        amount = order.amount

    all_fixed = True
    for step in failed_steps:
        success = False
        # Retry with no comp_fail_at simulation to allow manual fix override
        if step.step_name == SagaStepName.ORDER:
            res = await client.compensate_order_step(order_id, comp_fail_at=None)
            success = res[0]
        elif step.step_name == SagaStepName.INVENTORY:
            res = await client.compensate_inventory_step(order_id, sku, qty, comp_fail_at=None)
            success = res[0]
        elif step.step_name == SagaStepName.PAYMENT:
            res = await client.compensate_payment_step(order_id, amount, comp_fail_at=None)
            success = res[0]
        elif step.step_name == SagaStepName.SHIPPING:
            res = await client.compensate_shipping_step(order_id, comp_fail_at=None)
            success = res[0]

        async with session_factory() as db:
            step_rec = (await db.execute(
                select(SagaStepExecutionModel).where(
                    SagaStepExecutionModel.order_id == order_id,
                    SagaStepExecutionModel.step_name == step.step_name
                )
            )).scalar_one()

            if success:
                step_rec.status = SagaStepStatus.COMPENSATED
                await log_event(db, order_id, "INFO", "MANUAL_RETRY_SUCCESS", f"Manual retry succeeded for step {step.step_name}")
            else:
                all_fixed = False
                await log_event(db, order_id, "ERROR", "MANUAL_RETRY_FAILED", f"Manual retry failed for step {step.step_name}")
            
            await db.commit()

    if all_fixed:
        async with session_factory() as db:
            order = await db.get(SagaOrderModel, order_id)
            order.status = OrderStatus.CANCELLED
            await log_event(db, order_id, "INFO", "SAGA_RESOLVED", "Order resolved cleanly to CANCELLED via manual retry.")
            await db.commit()

    return all_fixed


async def boot_recovery(session_factory):
    """
    Restart Recovery Loop: Runs on Coordinator startup.
    Finds un-finalized orders (IN_PROGRESS) and resumes execution.
    """
    logger.info("Executing Saga Boot Recovery Check...")
    async with session_factory() as db:
        pending_orders = (await db.execute(
            select(SagaOrderModel).where(SagaOrderModel.status == OrderStatus.IN_PROGRESS)
        )).scalars().all()

        if not pending_orders:
            logger.info("Boot Recovery Complete: No stuck IN_PROGRESS orders found.")
            return

        logger.info(f"Found {len(pending_orders)} incomplete orders. Resuming Saga execution...")
        for order in pending_orders:
            order_data = {
                "order_id": order.order_id,
                "sku": order.sku,
                "qty": order.qty,
                "amount": order.amount,
                "fail_at": order.fail_at,
                "comp_fail_at": order.comp_fail_at
            }
            asyncio.create_task(execute_order_saga(order_data, session_factory))
