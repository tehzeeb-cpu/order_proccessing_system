# Key Technical Design Decisions & Trade-Offs

## 1. Saga Orchestration vs. Choreography

* **Decision**: We selected **Saga Orchestration** (Central Coordinator) over Saga Choreography (Event Bus / Kafka).
* **Rationale**: Orchestration keeps transaction state centralized. In event-driven choreography, tracking parallel compensations across 4 services requires complex distributed state tracing. Centralized orchestration makes restart recovery straightforward.
* **Trade-Off**: The Coordinator is a potential point of failure. We mitigate this by persisting every state transition in `coordinator_db` and implementing automatic boot recovery.

---

## 2. Parallel Step Execution via `asyncio.gather`

* **Decision**: Step execution (`Order`, `Inventory`, `Payment`, `Shipping`) runs concurrently per order using Python 3.13 `asyncio.gather()`.
* **Rationale**: Sequential execution takes $T_1 + T_2 + T_3 + T_4 \approx 400\text{ms}$. Parallel execution takes $\max(T_i) \approx 100\text{ms}$, resulting in a **4x throughput gain**.
* **Trade-Off**: Higher concurrent connection load on MySQL. We bound concurrency using an `asyncio.Semaphore(50)` and connection pool settings (`pool_size=20`, `max_overflow=30`).

---

## 3. Database per Service Isolation

* **Decision**: 6 separate MySQL databases (`coordinator_db`, `order_db`, `inventory_db`, `payment_db`, `shipping_db`, `notification_db`).
* **Rationale**: Strict microservice boundary enforcement. Prevents unauthorized cross-domain SQL joins and allows microservices to scale independently.
* **Trade-Off**: Cross-service transactional consistency cannot rely on ACID database locks; instead, distributed consistency is achieved via Saga compensation logic.

---

## 4. Redis Caching & Distributed Lock Strategy

* **Decision**: Redis is used exclusively for two high-value concerns:
  1. **Idempotency Key Deduplication**: Fast sub-millisecond lookup before querying MySQL.
  2. **Notification Service Leader Election**: Redis Distributed Lock (`redlock`) ensures only 1 notification service instance runs the 15-minute background notification job.
* **Trade-Off**: Introduces Redis dependency. Handled with graceful fallback to MySQL idempotency tables if Redis becomes temporarily unreachable.
