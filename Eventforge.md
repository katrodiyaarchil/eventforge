# EventForge
## Real-Time Distributed Financial Transaction Monitoring & Fraud Detection Platform

---

# 1. Project Vision

EventForge is a distributed, event-driven financial transaction processing and fraud detection platform.

The system simulates a fintech-grade payment processor with:

- Real-time transaction processing
- Stateful stream processing
- Fraud detection engine
- AML rule enforcement
- Double-entry ledger
- Event sourcing architecture
- Analytics pipeline

This is NOT a CRUD system.
This is a distributed systems engineering project.

---

# 2. Core Architecture Style

- Event-Driven Architecture (EDA)
- Event Sourcing
- CQRS Pattern
- Stateful Stream Processing
- Idempotent Transaction Handling
- Exactly-Once Processing (Design Goal)

---

# 3. Core Services

## 3.1 API Gateway Service
- FastAPI
- JWT Authentication
- Idempotency Key Support
- Request validation

Endpoints:
- POST /auth/login
- POST /transactions
- GET /transactions/{id}
- GET /accounts/{id}

---

## 3.2 Transaction Ingestion Service
Responsibilities:
- Validate business rules
- Generate transaction_id
- Attach metadata (geo, device, IP)
- Publish to Kafka topic: transactions.raw

---

## 3.3 Stream Processing Engine
Technology:
- Faust (or Kafka Streams equivalent)

Consumes:
- transactions.raw

Processors:

1. Balance Validator
2. Fraud Scoring Engine
3. AML Rule Engine
4. Decision Engine

Publishes:
- transactions.enriched
- transactions.decisions

---

## 3.4 Ledger Service
- Consumes approved transactions
- Performs atomic double-entry update
- Persists to PostgreSQL
- Ensures accounting invariant

Invariant:
Sum(Debits) = Sum(Credits)

---

## 3.5 Analytics Engine
- ClickHouse
- Aggregated metrics
- Fraud rate analysis
- Transaction volume per region
- Real-time dashboards

---

# 4. Kafka Topics

- transactions.raw
- transactions.enriched
- transactions.decisions
- ledger.entries
- alerts.fraud

Partitioning Strategy:
- Partition by from_account_id

---

# 5. Transaction Lifecycle

1. User initiates transaction
2. API validates request
3. Idempotency key checked
4. Event published to transactions.raw
5. Balance processor validates funds
6. Fraud engine calculates risk score
7. AML rules applied
8. Decision engine sets status (APPROVED / REJECTED / REVIEW)
9. Approved transactions sent to ledger
10. Ledger performs double-entry update
11. Analytics updated

---

# 6. Fraud Detection Model (Rule-Based Initial Version)

Features:
- Transaction velocity (last 5 min window)
- Amount anomaly ratio
- Geo anomaly
- Device anomaly

Risk Score Formula:

risk_score = w1*(amount / avg_amount) 
           + w2*velocity 
           + w3*geo_change 
           + w4*device_change

Thresholds:
- > 0.85 → REVIEW
- > 0.95 → BLOCK

---

# 7. Storage Systems

PostgreSQL:
- Users
- Accounts
- Ledger
- Transactions (final state)

Redis:
- Session store
- Rate limiting
- Cached balances

ClickHouse:
- Raw + enriched transaction analytics

Kafka:
- Event backbone
- Replay support
- Failure recovery

---

# 8. Failure Handling Strategy

- Dead-letter topics
- Idempotent producers
- Retry with exponential backoff
- Consumer offset management
- Out-of-order event handling
- Replay capability

---

# 9. Engineering Objectives

This project demonstrates:

- Distributed systems design
- Financial-grade data integrity
- Event-driven architecture
- Stateful stream processing
- Real-time fraud detection
- Ledger accounting systems
- Scalability and fault tolerance

---

# 10. Future Extensions

- ML-based fraud scoring
- Graph-based money laundering detection
- Multi-currency support
- Cross-border transaction routing
- Horizontal scaling benchmarks
- Chaos testing