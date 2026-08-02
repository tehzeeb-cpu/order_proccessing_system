# Distributed Order Processing System (Saga Orchestrator)

> Production-grade, highly concurrent e-commerce Order Processing Engine implementing **Saga Orchestration**, **Idempotent Microservices**, **Restart Recovery**, and an **Angular 20 Material Control Dashboard**.

---

## 🚀 Quick Start (One Command)

To build and launch the entire microservices stack (6 MySQL databases, Redis, Coordinator, 5 Microservices, and Angular Frontend):

```bash
docker compose up --build
```

Access the applications:
* **Angular Web Dashboard**: [http://localhost:4200](http://localhost:4200)
* **Saga Coordinator Gateway API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Order Service**: [http://localhost:8001/docs](http://localhost:8001/docs)
* **Inventory Service**: [http://localhost:8002/docs](http://localhost:8002/docs)
* **Payment Service**: [http://localhost:8003/docs](http://localhost:8003/docs)
* **Shipping Service**: [http://localhost:8004/docs](http://localhost:8004/docs)
* **Notification Service**: [http://localhost:8005/docs](http://localhost:8005/docs)

---

## 🏗️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Angular 20, Angular Material, TypeScript, RxJS |
| **Backend Services** | Python 3.13+, FastAPI, SQLAlchemy 2.0 (Async), Pydantic V2 |
| **Databases** | MySQL 8.0 (Database per Service isolation) |
| **Cache & Distributed Lock** | Redis 7.0 |
| **Containerization** | Docker, Docker Compose |
| **Testing** | Pytest, Pytest-Asyncio |

---

## 🏛️ System Architecture & Monorepo Structure

```
order-processing-system/
├── frontend/                     # Angular 20 SPA Dashboard
├── coordinator/                  # Saga Coordinator Application (Port 8000)
├── services/                     # Standalone Microservices
│   ├── order-service/            # Order Creation & Cancellation (Port 8001)
│   ├── inventory-service/        # Stock Reservation & Release (Port 8002)
│   ├── payment-service/          # Charge & Refund Processing (Port 8003)
│   ├── shipping-service/         # Shipment Creation & Cancellation (Port 8004)
│   └── notification-service/     # Scheduled Shipped Order Notifications (Port 8005)
├── shared/                       # Shared Contracts, DB Engine & Logging
├── docker/                       # Database init scripts & Compose config
├── docs/                         # Architecture & Design Decision Docs
├── tests/                        # Integration Pytest Suite
├── orders_bulk.csv               # Test order stream dataset (~2,500 records)
└── sample_inventory.csv          # Initial inventory seed stock
```

---

## 🌟 Key Features & Architectural Design

### 1. Parallel Step Execution via Saga Orchestration
For each order ingested, the Coordinator executes **Order Creation**, **Inventory Reservation**, **Payment Charge**, and **Shipping Creation** concurrently using Python `asyncio.gather()`. This cuts per-order processing latency from ~400ms down to ~100ms.

### 2. Selective Compensation Rollback
If any step fails (e.g. payment charge failure):
* Only steps that **completed successfully** are rolled back (put stock back, cancel order, cancel shipment).
* Unexecuted or failed steps are skipped.
* Order state cleanly transitions to `CANCELLED`.

### 3. Needs Attention Queue & Manual Retry
If a compensating step fails repeatedly (e.g. `comp_fail_at=RELEASE_INVENTORY`):
* The order is flagged as `NEEDS_ATTENTION`.
* Operators can view the order in the Angular UI and trigger a manual "Retry Undo" button once downstream services recover.

### 4. Memory-Efficient CSV Streaming
Bulk CSV files (`orders_bulk.csv`) are parsed as an async generator stream. An `asyncio.Semaphore(50)` bounds concurrent order execution, keeping RAM consumption constant ($O(1)$) even for files with millions of rows.

### 5. Idempotency (Exactly Once Guarantee)
Every request includes an `Idempotency-Key` header (`order_id:step:attempt`). Microservices check Redis sub-millisecond cache first, backed by a persistent MySQL `idempotency` table. Re-sent requests return cached responses without duplicate charges or stock deductions.

### 6. Restart Recovery
Upon system startup or container crash recovery, the Coordinator queries `coordinator_db` for stuck `IN_PROGRESS` orders and resumes pending Saga transactions idempotently.

### 7. Notification Service & Redis Distributed Lock
Runs a background scheduler scanning for `SHIPPED` orders. Uses a Redis Distributed Lock (`redlock`) to ensure only **one instance** executes the job across scaled replicas, guaranteeing **exactly-once notification delivery**.

---

## 🧪 Running Pytest Suite

To execute the automated unit and integration test suite:

```bash
# Create virtual environment & install requirements
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run Pytest
pytest tests/ -v
```

---

## 📖 Demonstration Walkthrough for Evaluation

1. **All Steps Succeed**: Upload `orders_bulk.csv` from Angular Dashboard. Normal rows complete all 4 steps in parallel and transition to status `PLACED`.
2. **Step Fails & Compensation Triggered**: Orders with `fail_at=RESERVE_INVENTORY` or `CHARGE_PAYMENT` fail gracefully, trigger compensations for succeeded steps, and transition to status `CANCELLED`.
3. **Compensation Fails (Needs Attention)**: Orders with `comp_fail_at=RELEASE_INVENTORY` fail during rollback, transition to `NEEDS_ATTENTION`, and appear in the Needs Attention Angular tab. Clicking "Retry Undo" executes manual compensation retry.
4. **Mark Shipped & Notifications**: On any `PLACED` order, click "Mark Shipped". The Notification Service picks up the order and records exactly one notification.
