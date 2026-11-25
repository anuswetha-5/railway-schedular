# Problem Statement: Intelligent Railway Corridor Maintenance & Automatic Block Planning System (ABPS)
## AI-Driven Multi-Departmental Possession Scheduler & Safety Interlocking Engine

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![WCAG 2.1 AA](https://img.shields.io/badge/Accessibility-WCAG%202.1%20AA-brightgreen.svg)](#accessibility)
[![Security: Audited](https://img.shields.io/badge/Security-Hardened%20API%20%26%20RBAC-green.svg)](#security-architecture)
[![Coverage: 100%](https://img.shields.io/badge/Tests-Passing%20(All%20Suites)-success.svg)](#testing--verification)

---

## 1. Executive Summary & Problem Statement

### 1.1 Ministry / Operational Background
**Organization:** Ministry of Railways, Government of India (Indian Railways)  
**Domain:** National Rail Traffic Control, Multi-Departmental Maintenance & Corridor Asset Optimization  

Indian Railways operates one of the world's most intricate and heavily congested railway networks, carrying over **24 million passengers** and **3.5 million tonnes of freight daily** across 68,000+ route kilometers. Maintaining the safety and geometric integrity of track infrastructure requires routine physical possessions of track lines, known as **"Maintenance Blocks"** or **"Traffic & Power Blocks"**.

### 1.2 The Core Operational Problem
Traditionally, maintenance requisitions originate independently across departmental silos:
1. **Civil Engineering / P-Way (Track Management System - TMS):** Rail fracture renewals, deep screening, track tamping, turnout overhauls.
2. **Electrical / Traction Distribution (TDMS):** 25kV AC overhead catenary (OHE) contact wire renewal, isolator checks, tower wagon inspections.
3. **Signal & Telecom (SMMS):** Electronic Interlocking (EI), point machine motors, Digital Axle Counters (MSDAC), track circuit (AFTC) tuning.
4. **Traffic & Operations (Control Office Application - COA / FOIS):** Passenger and freight train path dispatching and timetabling.

### 1.3 Critical Failure Modes of Existing Manual Systems
- **Severe Section Capacity Loss:** When departments request separate block possessions on the same section at different times, line capacity is squandered, causing train delays and freight detentions.
- **Safety Interlock Breaches:** Without automated cross-departmental interlocking, workers risk working under live 25kV OHE catenary or operating vibration-heavy track machines near sensitive electronic signaling relays.
- **Reactive "Fix-on-Failure" Paradigms:** Maintenance is frequently scheduled only after defects are detected or severe Permanent Speed Restrictions (PSRs) are imposed, degrading average network speed.
- **Timetable Fragility:** Unanticipated upstream train delays collide with planned maintenance blocks, generating cascading ripple delays across entire trunk corridors.

### 1.4 The ABPS AI Solution
The **Automatic Block Planning System (ABPS)** provides an end-to-end, enterprise-grade AI operations platform that integrates TMS, SMMS, TDMS, and COA. It automates:
1. **Multi-Factorial AI Prioritization:** Evaluates risk, degradation, route criticality, and bottleneck lifting to rank work orders.
2. **Coordinated Shadow Block Optimization:** Identifies natural timetable gaps and bundles multi-departmental companion jobs into joint possessions ("Shadow Blocks"), eliminating redundant downtime.
3. **Predictive Asset Health (PdM):** Calculates Track Quality Index (TQI) and forecasts 30/60/90-day defect emergence hazards using Weibull degradation models.
4. **Disruption & What-If Simulation:** Injects train delays, detects block infringements, and advises dynamic timetable adjustments.
5. **Safety Compliance Interlocking:** Strictly interlocks 25kV power isolation permits and enforces mechanical separation rules.
6. **Fleet & Heavy Machine Resource Manager:** Manages division track machines (tampers, cleaners, tower wagons) to eliminate resource double-booking.
7. **Official Field Dispatch & Form T/409:** Automatically generates Indian Railways Form T/409 Joint Possession Orders and CSV/REST data feeds.

---

## 2. System Architecture & End-to-End Pipeline

```
                       +-------------------------------------------------------------+
                       |              DEPARTMENTAL DATA SOURCES & INGESTION          |
                       +-------------------------------------------------------------+
                       |  TMS (Civil/P-Way)  |  TDMS (Electrical)  |  SMMS (Signal)  |
                       +---------------------+---------------------+-----------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |   INTEGRATED WORK ORDER BACKLOG     |
                               |    (Unified Relational SQLite)      |
                               +-------------------------------------+
                                                  |
                                                  v
+------------------------+     +-------------------------------------+     +--------------------------+
|  PREDICTIVE HEALTH     |     |       AI PRIORITIZATION ENGINE      |     |  TRAIN TIMETABLES &      |
|  ENGINE (PdM)          | --> |       (Multi-Factorial Scorer)      | <-- |  COA CORRIDOR WINDOWS    |
|  - TQI Calculation     |     |  - Severity & Overdue Penalties     |     |  - Passenger Timetables  |
|  - Weibull Hazard 30d  |     |  - Route Class & Asset Age          |     |  - Goods Train Forecasts |
+------------------------+     |  - Bottleneck (PSR) Lifting Benefit |     |  - Natural Gap Detection |
                               +-------------------------------------+     +--------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |   COORDINATED SHADOW BLOCK ENGINE   |
                               |  - Parallel Department Bundling     |
                               |  - Window Space Fitting             |
                               |  - Downtime Savings Calculation     |
                               +-------------------------------------+
                                                  |
                                                  v
+-----------------------------------------------------------------------------------------------------+
|                                 SAFETY & RESOURCE INTERLOCKING GUARD                                |
|  - 25kV OHE Power Isolation Interlock    - Heavy Machinery Contention & Fleet Allocation            |
|  - Spatial Vibration & Dust Separation   - Form T/409 Caution Order Speed Restriction Check         |
+-----------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |     APPROVED JOINT BLOCK REGISTER   |
                               +-------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
+--------------------------------------------------+     +------------------------------------+
|          OPERATIONAL DISPATCH & EXPORTS          |     |       DISRUPTION & WHAT-IF         |
|  - Official Form T/409 Joint Possession Order    |     |       TIMETABLE SIMULATOR          |
|  - FOIS / COA Interoperability CSV Data Feeds    |     |  - Train Delay Injection           |
|  - RESTful JSON Microservice API (api.py)        |     |  - Clashing Possession Detection   |
|  - Interactive 8-Pillar Streamlit UI (app.py)    |     |  - Dynamic Cascade Mitigation      |
+--------------------------------------------------+     +------------------------------------+
```

---

## 3. Mathematical Formulations & Algorithms

### 3.1 Multi-Factorial Priority Scoring Model
Each maintenance work order $j$ is evaluated across five weighted operational criteria to yield a normalized AI score $S_j \in [5.0, 100.0]$:

$$S_j = w_1 S_{\text{severity}} + w_2 S_{\text{urgency}} + w_3 S_{\text{route}} + w_4 S_{\text{capacity}} + w_5 S_{\text{compliance}}$$

Where:
- **$S_{\text{severity}}$ ($w_1 = 0.30$):** Safety defect severity (Critical $= 30$, High $= 20$, Medium $= 12$, Low $= 5$).
- **$S_{\text{urgency}}$ ($w_2 = 0.25$):** Statutory overdue penalty based on days elapsed past the maintenance cycle:
  $$S_{\text{urgency}} = \min\left(25, 10 + 0.7 \cdot \text{overdue\_days}\right)$$
- **$S_{\text{route}}$ ($w_3 = 0.20$):** Route classification (Golden Quadrilateral $= 10$, High Density Network $= 8$, Trunk Route A $= 5$) plus asset GMT tonnage and track age wear multipliers.
- **$S_{\text{capacity}}$ ($w_4 = 0.15$):** Bottleneck removal benefit; higher priority given to lifting severe speed restrictions ($\le 30$ km/h $= 15$ pts).
- **$S_{\text{compliance}}$ ($w_5 = 0.10$):** Departmental statutory safety compliance factor.

### 3.2 Coordinated Shadow Block Downtime Savings
When multiple tasks $j_1, j_2, \dots, j_k$ from different departments (TMS, SMMS, TDMS) are bundled into a single joint possession window of duration $T_{\text{block}}$, the net corridor downtime saved is:

$$\Delta T_{\text{saved}} = \sum_{i=1}^{k} D_{j_i} - \max_{1 \le i \le k}(D_{j_i})$$

Where $D_{j_i}$ represents the independent duration needed by task $j_i$.

### 3.3 Predictive Track Health & Weibull Hazard Degradation Model
The **Track Quality Index (TQI)** is modeled as:

$$\text{TQI} = \max\left(30, 100 - \left[ c_{\text{age}} A + c_{\text{tonnage}} G + c_{\text{wear}} W + P_{\text{insp}} + P_{\text{tamp}} + P_{\text{ballast}} \right] \cdot \Phi_{\text{speed}} \right)$$

The defect emergence hazard rate $\lambda$ and corresponding cumulative probability of defect failure over $t$ days is given by:

$$\lambda = \frac{100 - \text{TQI}}{1800}$$

$$P(\text{Defect within } t \text{ days}) = 1 - e^{-\lambda t}$$

Calculated across rolling operational horizons ($t = 30, 60, 90$ days).

---

## 4. Operational Manuals & Railway Regulatory Compliance

ABPS algorithms strictly adhere to the operational guidelines prescribed by Indian Railways:
- **Indian Railways General Rules (G&SR):** Chapters IV & V governing train working, caution orders, and block working.
- **Indian Railways Permanent Way Manual (IRPWM):** Section 613 on speed restrictions, Section 805 on integrated machine maintenance, and ultrasonic testing cycles.
- **Traction Distribution Manual (TRDM):** Chapter III on 25kV OHE isolation permits, earthing discharge rod protocols, and power block granting procedures.
- **Signal Engineering Manual (SEM):** Part II on point machine inspection, axle counter maintenance, and electronic interlocking changeovers.
- **Form T/409:** Caution order and joint engineering/traffic possession notice format standardized under Indian Railways operating regulations.

---

## 5. System Modules & Directory Structure

```
c:/railway_schedular-main/
|-- README.md                    # Primary project documentation and architecture dossier
|-- PROBLEM_STATEMENT_ALIGNMENT.md # Line-by-line requirement traceability matrix
|-- SECURITY.md                  # Security policies, threat model, and auth architecture
|-- ACCESSIBILITY.md             # WCAG 2.1 AA compliance audit and assistive technology map
|-- requirements.txt             # Python environment dependencies
|-- exceptions.py                # Domain exception hierarchy
|-- run_tests.py                 # Unified test runner with coverage and benchmarking
|
|-- app.py                       # 8-Pillar Streamlit UI platform
|-- ai_scheduler.py              # Coordinated Shadow Block scheduling engine
|-- ai_scorer.py                 # Multi-factorial AI priority scoring engine
|-- predictive_health.py         # Track Quality Index (TQI) & Weibull hazard PdM engine
|-- disruption_simulator.py      # Timetable delay injection & conflict mitigation simulator
|-- safety_rules.py              # 25kV OHE & spatial interlocking safety compliance matrix
|-- dispatch_exporter.py         # Form T/409 certificate generator & CSV data exporter
|-- api.py                       # Hardened RESTful JSON microservice API
|-- update_availability.py       # Natural timetable corridor gap calculator
|
|-- database/
|   |-- createdata.py            # 7-table relational schema & automatic migrations
|   |-- generatedata.py          # 30-day authentic Indian Railways corridor dataset generator
|   |-- railway_planning.db      # SQLite relational database
|
|-- tests/
|   |-- __init__.py              # Tests package marker
|   |-- test_platform.py         # Core platform unit & integration tests
|   |-- test_security.py         # Security injection, auth, and rate-limiting tests
|   |-- test_api_endpoints.py    # REST API endpoint integration tests
|   |-- test_efficiency.py       # Performance benchmarks & query latency tests
```

---

## 6. Security Architecture & Threat Defense

The platform implements defense-in-depth principles:
1. **API Key Authentication:** All mutating and querying endpoints require valid `X-API-Key` or `Authorization: Bearer <key>` headers.
2. **Token-Bucket Rate Limiter:** Enforces a 60 requests/minute limit per client IP, shielding the platform from Denial of Service (DoS) attacks.
3. **Security Headers Injected on All HTTP Responses:**
   - `Content-Security-Policy: default-src 'self'`
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
   - `Referrer-Policy: strict-origin-when-cross-origin`
4. **Input Sanitization & Parameterized SQL:** Strict regex whitelisting for all user inputs; 100% of database interactions execute through parameterized SQL statements, eliminating SQL injection.
5. **Cross-Site Scripting (XSS) Prevention:** All dynamic HTML rendered in Streamlit passes through `html.escape()`.

---

## 7. Accessibility & WCAG 2.1 AA Compliance

The user interface adheres to **WCAG 2.1 Level AA** standards:
- **Semantic Tables:** Generated tables use `<table role="table">`, `<th scope="col">`, and `<td role="cell">` for assistive screen-reader navigability.
- **Color Independence:** Status badges include screen-reader text (`.sr-only`) and explicit text labels so status is never conveyed by color alone.
- **Contrast Ratios:** All text-to-background combinations maintain a contrast ratio $\ge 4.5:1$ in both Light and Dark vintage themes.
- **Keyboard Focusability:** All interactive components include `:focus-visible` outline rings for keyboard-only navigation.

---

## 8. Installation, Execution & API Guide

### 8.1 Setup & Installation
```bash
# Clone the repository
git clone https://github.com/railwaySchedule/railway_schedular.git
cd railway_schedular-main

# Install dependencies
pip install -r requirements.txt
```

### 8.2 Launching the Web Application
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` to access the 8-Pillar Operations Office.

### 8.3 Starting the Hardened REST API
```bash
python api.py 8000
```
Test health endpoint:
```bash
curl -H "X-API-Key: IR-AI-OPS-SECRET-KEY-2026" http://127.0.0.1:8000/api/v1/health
```

### 8.4 Running the Automated Test Suite
```bash
python run_tests.py
```

---

## 9. License & Citations
Developed for Indian Railways Operations Modernization. Distributed under the MIT License.
