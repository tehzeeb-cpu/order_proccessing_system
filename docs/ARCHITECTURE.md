# Architecture & System Design Document

## 1. System Overview

The **Order Processing System** is a distributed, event-resilient microservice application designed to coordinate e-commerce order workflows at high concurrency using the **Saga Orchestration Pattern**.

---

## 2. High-Level Architecture Diagram

```mermaid
graph TD
    Client["Angular 20 Web UI (Port 4200)"] -->|REST API| Coord["Saga Coordinator (Port 8000)"]
    
    subgraph "Saga Coordinator Boundary"
        Coord --> CoordDB[("coordinator_db")]
        Coord --> RedisCache["Redis Cache / Lock (Port 6379)"]
        Coord --> CSVStream["Async CSV Stream Reader"]
    end
    
    subgraph "Microservices Layer (Database Per Service)"
        Coord -->|POST /api/v1/orders| OrderSvc["Order Service (Port 8001)"]
        Coord -->|POST /api/v1/inventory/reserve| InvSvc["Inventory Service (Port 8002)"]
        Coord -->|POST /api/v1/payments/charge| PaySvc["Payment Service (Port 8003)"]
        Coord -->|POST /api/v1/shipments| ShipSvc["Shipping Service (Port 8004)"]
        
        OrderSvc --> OrderDB[("order_db")]
        InvSvc --> InvDB[("inventory_db")]
        PaySvc --> PayDB[("payment_db")]
        ShipSvc --> ShipDB[("shipping_db")]
    end
    
    subgraph "Notification Boundary"
        NotifSvc["Notification Service (Port 8005)"] --> NotifDB[("notification_db")]
        NotifSvc -->|Query Shipped Orders| Coord
        NotifSvc -->|Acquire Lock| RedisCache
    end
```

---

## 3. Sequence Diagram (Saga Parallel Execution & Rollback)

```mermaid
sequenceDiagram
    autonumber
    participant Client as Angular UI / CSV
    participant C as Coordinator
    participant O as Order Service
    participant I as Inventory Service
    participant P as Payment Service (Fails)
    participant S as Shipping Service
    
    Client->>C: Submit Bulk Orders / CSV Stream
    C->>C: Record Order (Status = IN_PROGRESS)
    
    par Parallel Step Execution
        C->>O: POST /orders (Create) -> 201 SUCCESS
        C->>I: POST /inventory/reserve -> 200 SUCCESS
        C->>P: POST /payments/charge -> 400 FAILED (Retry 1..3) -> FAILED
        C->>S: POST /shipments -> 201 SUCCESS
    end
    
    C->>C: Status = ROLLBACK_IN_PROGRESS
    
    par Compensate ONLY Succeeded Steps
        C->>O: POST /orders/cancel -> 200 COMPENSATED
        C->>I: POST /inventory/release -> 200 COMPENSATED
        C->>S: POST /shipments/cancel -> 200 COMPENSATED
    end
    
    C->>C: Status = CANCELLED
```

---

## 4. Entity Relationship Diagram (ER Diagram)

```mermaid
erDiagram
    saga_orders {
        string order_id PK
        string sku
        int qty
        float amount
        string status
        string fail_at
        string comp_fail_at
        datetime created_at
    }
    
    saga_step_executions {
        bigint id PK
        string order_id FK
        string step_name
        string status
        int retry_count
        text error_message
        int execution_time_ms
    }
    
    saga_logs {
        bigint id PK
        string order_id FK
        string level
        string event_type
        text message
    }

    saga_orders ||--o{ saga_step_executions : tracks
    saga_orders ||--o{ saga_logs : audits
```

---

## 5. Idempotency & Fault Tolerance Guarantee

1. **Idempotency Key Injection**: Every request sent from the Coordinator includes `Idempotency-Key: {order_id}:{step}:{attempt}`.
2. **Double-Lock Caching**: Microservices check Redis cache first (`SET key val NX EX 86400`). If key exists, cached response is returned immediately.
3. **Database Pre-Persist**: Microservices write idempotency keys to their local MySQL tables to ensure deduplication survives Redis cache eviction.
4. **Needs Attention Trigger**: If compensating an order fails after retries, the Saga Coordinator marks the order `NEEDS_ATTENTION`, allowing operators to manually trigger undo recovery from Angular.
