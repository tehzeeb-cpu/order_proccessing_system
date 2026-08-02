# coordinator/services_client.py
"""
WHY THIS FILE EXISTS:
Async HTTP REST client layer wrapping communications with Order, Inventory, Payment, and Shipping services.

Key Architecture Features:
1. Idempotency Key Injection: Sends `Idempotency-Key` header with format `order_id:step_name:attempt`.
2. Exponential Backoff Retries: Retries failed HTTP calls up to MAX_RETRIES (3) with increasing delays.
3. Strict Timeout Controls: Enforces HTTP timeouts (5 seconds) per request to prevent hanging Saga threads.

Interview Explanation:
"The ServicesClient abstracts microservice communication. It implements exponential backoff and idempotency header 
injection, protecting against transient network glitches while ensuring downstream operations are never duplicated."
"""

import os
import asyncio
import time
import httpx
from typing import Dict, Any, Tuple

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8001")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8002")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003")
SHIPPING_SERVICE_URL = os.getenv("SHIPPING_SERVICE_URL", "http://localhost:8004")

MAX_RETRIES = 3
TIMEOUT_SECONDS = 5.0


class ServicesClient:
    def __init__(self):
        self.timeout = httpx.Timeout(TIMEOUT_SECONDS)

    async def _post_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        idempotency_key: str
    ) -> Tuple[bool, int, Dict[str, Any], int]:
        """
        Executes an HTTP POST with exponential backoff retries.
        Returns: (success: bool, status_code: int, response_data: dict, total_latency_ms: int)
        """
        start_time = time.time()
        headers = {"Idempotency-Key": idempotency_key, "Content-Type": "application/json"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    res = await client.post(url, json=payload, headers=headers)
                    latency = int((time.time() - start_time) * 1000)
                    
                    if res.status_code in [200, 201]:
                        return True, res.status_code, res.json(), latency
                    
                    # 4xx errors (e.g. simulated business failure) should NOT be retried endlessly
                    if 400 <= res.status_code < 500:
                        return False, res.status_code, {"detail": res.text}, latency

                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt == MAX_RETRIES:
                        latency = int((time.time() - start_time) * 1000)
                        return False, 504, {"detail": str(exc)}, latency
                
                # Backoff delay (0.2s, 0.4s, 0.8s)
                await asyncio.sleep(0.2 * (2 ** (attempt - 1)))

        latency = int((time.time() - start_time) * 1000)
        return False, 500, {"detail": "Max retries exhausted"}, latency

    # --- Step Actions ---

    async def execute_order_step(self, order_id: str, sku: str, qty: int, amount: float, fail_at: str = None):
        url = f"{ORDER_SERVICE_URL}/api/v1/orders"
        payload = {"order_id": order_id, "sku": sku, "qty": qty, "amount": amount, "fail_at": fail_at}
        key = f"{order_id}:ORDER:CREATE"
        return await self._post_with_retry(url, payload, key)

    async def execute_inventory_step(self, order_id: str, sku: str, qty: int, fail_at: str = None):
        url = f"{INVENTORY_SERVICE_URL}/api/v1/inventory/reserve"
        payload = {"order_id": order_id, "sku": sku, "qty": qty, "fail_at": fail_at}
        key = f"{order_id}:INVENTORY:RESERVE"
        return await self._post_with_retry(url, payload, key)

    async def execute_payment_step(self, order_id: str, amount: float, fail_at: str = None):
        url = f"{PAYMENT_SERVICE_URL}/api/v1/payments/charge"
        payload = {"order_id": order_id, "amount": amount, "fail_at": fail_at}
        key = f"{order_id}:PAYMENT:CHARGE"
        return await self._post_with_retry(url, payload, key)

    async def execute_shipping_step(self, order_id: str, sku: str, qty: int, fail_at: str = None):
        url = f"{SHIPPING_SERVICE_URL}/api/v1/shipments"
        payload = {"order_id": order_id, "sku": sku, "qty": qty, "fail_at": fail_at}
        key = f"{order_id}:SHIPPING:CREATE"
        return await self._post_with_retry(url, payload, key)

    # --- Compensation Actions ---

    async def compensate_order_step(self, order_id: str, comp_fail_at: str = None):
        url = f"{ORDER_SERVICE_URL}/api/v1/orders/{order_id}/cancel?comp_fail_at={comp_fail_at or ''}"
        key = f"{order_id}:ORDER:CANCEL"
        return await self._post_with_retry(url, {}, key)

    async def compensate_inventory_step(self, order_id: str, sku: str, qty: int, comp_fail_at: str = None):
        url = f"{INVENTORY_SERVICE_URL}/api/v1/inventory/release"
        payload = {"order_id": order_id, "sku": sku, "qty": qty, "comp_fail_at": comp_fail_at}
        key = f"{order_id}:INVENTORY:RELEASE"
        return await self._post_with_retry(url, payload, key)

    async def compensate_payment_step(self, order_id: str, amount: float, comp_fail_at: str = None):
        url = f"{PAYMENT_SERVICE_URL}/api/v1/payments/refund"
        payload = {"order_id": order_id, "amount": amount, "comp_fail_at": comp_fail_at}
        key = f"{order_id}:PAYMENT:REFUND"
        return await self._post_with_retry(url, payload, key)

    async def compensate_shipping_step(self, order_id: str, comp_fail_at: str = None):
        url = f"{SHIPPING_SERVICE_URL}/api/v1/shipments/{order_id}/cancel"
        payload = {"order_id": order_id, "comp_fail_at": comp_fail_at}
        key = f"{order_id}:SHIPPING:CANCEL"
        return await self._post_with_retry(url, payload, key)
