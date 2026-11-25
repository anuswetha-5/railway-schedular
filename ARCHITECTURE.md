# System Architecture & Technical Design Document
## Automatic Block Planning System (ABPS) — Indian Railways

---

## 1. Architectural Philosophy & Design Principles

The Automatic Block Planning System is designed according to **Clean Architecture** and **Domain-Driven Design (DDD)** principles:
* **Separation of Concerns:** Business rules and optimization logic are decoupled from presentation (Streamlit) and transport layers (HTTP REST API).
* **High Cohesion & Low Coupling:** Distinct subsystems handle Scoring, Corridor Gap Finding, Safety Auditing, Machine Fleet Allocation, and Possession Dispatching.
* **Deterministic Execution:** Eliminates unconstrained LLM hallucinations by executing proven mathematical and constraint-satisfaction algorithms for safety-critical railway decisions.
* **Resilience & Self-Healing:** Automatic database bootstrap, graceful SQLite rollback handling, and in-memory caching.

---

## 2. High-Level System Architecture (C4 Layered Diagram)

```
+--------------------------------------------------------------------------------------------------+
|                                    PRESENTATION & INGESTION LAYER                                |
|                                                                                                  |
|   +------------------------------------+          +------------------------------------------+   |
|   |   Streamlit Operations UI (app.py) |          |  Hardened RESTful API Service (api.py)   |   |
|   |  - 8 Operational Pillars           |          |  - Token / Bearer Key Authentication     |   |
|   |  - Theme Registry (themes.py)      |          |  - Sliding-Window Rate Limiter (60/min)  |   |
|   |  - WCAG 2.1 Level AA Accessibility |          |  - Security Headers (CSP, HSTS, DENY)    |   |
|   +-----------------+------------------+          +--------------------+---------------------+   |
+---------------------|--------------------------------------------------|-------------------------+
                      |                                                  |
                      +------------------------+-------------------------+
                                               |
                                               v
+--------------------------------------------------------------------------------------------------+
|                                       DOMAIN & DECISION ENGINES                                  |
|                                                                                                  |
|   +------------------------------------+          +------------------------------------------+   |
|   |  AI Prioritization (ai_scorer.py)  |          | Coordinated Optimizer (ai_scheduler.py)  |   |
|   |  - Multi-Factorial Scoring (0-100) |          | - Natural Corridor Gap Matching          |   |
|   |  - Risk, Overdue, PSR, Compliance  |          | - Multi-Department Shadow Block Bundling |   |
|   +------------------------------------+          +--------------------+---------------------+   |
|                                                                        |                         |
|   +------------------------------------+          +--------------------+---------------------+   |
|   |   Predictive Health (PdM Engine)   |          | Safety Interlocking (safety_rules.py)    |   |
|   |   - Track Quality Index (TQI)      |          | - 25kV OHE Electrical Cutoff Audit       |   |
|   |   - Weibull Hazard Curves (30/60d) |          | - Spatial Vibration Separation Guard     |   |
|   +------------------------------------+          | - Machinery Fleet Contention Check       |   |
|                                                   +------------------------------------------+   |
|   +------------------------------------+          +------------------------------------------+   |
|   | Disruption Simulator               |          | Statutory Dispatch (dispatch_exporter.py)|   |
|   | - Timetable Delay Injection        |          | - Form T/409 Caution Notice Generator    |   |
|   | - Cascading Ripple Analysis        |          | - COA / FOIS CSV Export Feeds            |   |
|   +------------------------------------+          +------------------------------------------+   |
+----------------------------------------------|---------------------------------------------------+
                                               |
                                               v
+--------------------------------------------------------------------------------------------------+
|                                        DATA PERSISTENCE LAYER                                    |
|                                                                                                  |
|   SQLite Relational Engine with Composite B-Tree Indexes & In-Memory Dataframe Caching           |
|   - PRAGMA journal_mode=DELETE; PRAGMA cache_size=-64000; PRAGMA synchronous=NORMAL;             |
|   - Tables: Tracks | Trains | Jobs | Corridor_Availability | Block_Register | Block_Jobs | Fleet  |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Design Patterns Applied

| Design Pattern | Implementation Location | Operational Rationale |
| :--- | :--- | :--- |
| **Strategy Pattern** | [`ai_scorer.py`](file:///c:/railway_schedular-main/ai_scorer.py) | Dynamic calculation of multi-factorial priority weights based on asset route class, defect severity, and statutory overdue latency. |
| **Factory Pattern** | [`dispatch_exporter.py`](file:///c:/railway_schedular-main/dispatch_exporter.py) | Instantiates official Indian Railways Form T/409 Joint Block Orders with dynamic cautionary speed stipulations and statutory signatories. |
| **Observer / Interceptor** | [`safety_rules.py`](file:///c:/railway_schedular-main/safety_rules.py) | Audits proposed shadow blocks before persistence, intercepting live-wire hazards and machinery resource collisions. |
| **Repository Pattern** | [`app.py`](file:///c:/railway_schedular-main/app.py), [`api.py`](file:///c:/railway_schedular-main/api.py) | Encapsulates SQL database access behind cached, thread-safe accessors (`fetch_dashboard_tables()`). |
| **Token Bucket / Sliding Window** | [`api.py`](file:///c:/railway_schedular-main/api.py) | Enforces precise IP-level request rate limiting to protect services against DDoS and resource starvation. |

---

## 4. Database Schema & Entity Relationships (ERD)

```
+--------------------+        1:N        +-------------------------+
|       Tracks       |-------------------|         Trains          |
|--------------------|                   |-------------------------|
| track_id (PK)      |                   | train_id (PK)           |
| section_name       |                   | train_number            |
| route_class        |                   | track_id (FK)           |
| speed_limit_kmh    |                   | run_date                |
| gmt_tonnage        |                   | scheduled_arrival       |
| tqi_score          |                   | scheduled_departure     |
| rail_wear_pct      |                   +-------------------------+
+---------+----------+                                |
          |                                           | Generates (Train Gaps)
          | 1:N                                       v
          |                              +-------------------------+
          |                              |  Corridor_Availability  |
          |                              |-------------------------|
          |                              | availability_id (PK)    |
          |                              | track_id (FK)           |
          |                              | available_date          |
          |                              | window_start            |
          |                              | window_end              |
          |                              | duration_mins           |
          |                              +-------------------------+
          |                                           |
          | 1:N                                       | Consumed By
          v                                           v
+--------------------+                   +-------------------------+
|        Jobs        |                   |     Block_Register      |
|--------------------|                   |-------------------------|
| job_id (PK)        |                   | block_id (PK)           |
| track_id (FK)      |                   | track_id (FK)           |
| department         |                   | window_start            |
| source_system      |                   | window_end              |
| task               |                   | duration_mins           |
| defect_severity    |                   | total_depts_involved    |
| ai_score           |                   | power_block_granted     |
| status             |                   | safety_audit_status     |
| required_machinery |                   | assigned_machinery      |
+---------+----------+                   +------------+------------+
          |                                           |
          |           +-------------------+           |
          +---------->|    Block_Jobs     |<----------+
                  N:1 |-------------------| 1:N
                      | block_id (FK)     |
                      | job_id (FK)       |
                      +-------------------+

+-------------------------+
|     Machinery_Fleet     |
|-------------------------|
| machine_id (PK)         |
| machine_name            |
| machine_type            |
| assigned_track (FK)     |
| status (Available/Busy) |
| home_depot              |
| operator_gang           |
+-------------------------+
```

---

## 5. Security & Threat Mitigation Architecture

1. **Least-Privilege RBAC:** REST endpoints enforce strict authentication tokens via `X-API-Key` or `Authorization: Bearer <key>`.
2. **Denial-of-Service Defense:**
   - 1MB max payload threshold to prevent memory exhaustion attacks.
   - 60 requests/minute per IP rate limiter.
3. **Injection Countermeasures:**
   - 100% of SQL queries utilize parameterized `?` prepared statements.
   - Alphanumeric regex validation on all URL and query parameters.
4. **Browser Hardening:** HTTP headers inject `nosniff`, `DENY` framing, Strict-Transport-Security, and Content Security Policies.
