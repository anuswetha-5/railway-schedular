# Problem Statement: AI-Powered Railway Corridor Maintenance & Automatic Block Planning System (ABPS)

## 1. Challenge Title & Identification
* **Challenge Title:** Intelligent Railway Corridor Maintenance Management & Automatic Block Planning System (ABPS)
* **Domain:** Transportation Logistics, Railway Operations, Infrastructure Maintenance & Operations Research
* **Target Stakeholder:** Ministry of Railways, Government of India (Indian Railways), Divisional Railway Managers (DRM), Chief Track Engineers (CTE), Section Controllers, and Permanent Way Inspectors (PWI).

---

## 2. Background & Context
Indian Railways is one of the world's largest and most heavily utilized transportation networks, transporting over **24 million passengers** and **3.5 million tonnes of freight daily** across 68,000+ route kilometers. Maintaining the safety and geometric integrity of track infrastructure requires routine physical possessions of track lines, known as **"Maintenance Blocks"** or **"Traffic & Power Blocks"**.

Historically, Indian Railways maintenance operates under departmental silos:
1. **Civil Engineering / P-Way (Track Management System - TMS):** Rail fracture renewals, deep screening, track tamping, turnout overhauls, weld grinding.
2. **Electrical / Traction Distribution (TDMS):** 25kV AC overhead catenary (OHE) contact wire renewal, isolator maintenance, tower wagon inspections.
3. **Signal & Telecom (SMMS):** Electronic Interlocking (EI), point machine motors, Digital Axle Counters (MSDAC), Audio Frequency Track Circuits (AFTC).
4. **Traffic & Operations (Control Office Application - COA / FOIS):** Passenger and freight train path dispatching and timetabling.

---

## 3. Core Problem Definition & Failure Modes
The existing manual and semi-digital block coordination processes suffer from severe structural failure modes:
1. **Disparate Sinks & Capacity Squandering:** TMS, SMMS, and TDMS submit maintenance block requisitions independently. When two departments require separate 2-hour possessions on the same track on the same day, the corridor is closed for 4 hours instead of being combined into a single 2-hour coordinated possession. This wastes line capacity, delaying express trains and holding back high-value freight rakes.
2. **Safety Violations & Mechanical Incompatibilities:** Manual scheduling increases the risk of safety incidents:
   - S&T workers working under live 25kV OHE catenary wires without power cutoff.
   - Vibration-heavy track machines (e.g. Ballast Cleaning Machines) operating simultaneously alongside sensitive electronic relay tuning, corrupting signaling sensors.
   - Heavy machinery fleet contention (e.g. CSM tamping machines double-booked across adjacent sections).
3. **Reactive "Fix-on-Failure" Bias:** Maintenance is frequently prioritized only after defects emerge or severe Permanent Speed Restrictions (PSRs) are imposed, degrading average network speed and punctuality.
4. **Schedule Fragility & Cascading Ripple Delays:** When a passenger train is delayed upstream, controllers lack automated real-time decision support to assess whether downstream maintenance blocks conflict with the delayed train or whether to compress or reschedule the possession.

---

## 4. Key Functional & Technical Requirements

### 4.1 Multi-Department Work Order Ingestion
* Ingest maintenance requisitions across all three engineering branches: **TMS (Civil)**, **SMMS (Signal)**, and **TDMS (Electrical)**.
* Standardize data attributes: asset ID, track section, min duration needed, defect severity, overdue days, imposed speed restriction (PSR km/h), required heavy machinery, and power block requirement.

### 4.2 Multi-Factorial AI Prioritization Engine
* Formulate an automated, transparent mathematical scoring function ($0 - 100$) integrating:
  1. **Safety & Defect Severity Risk** (Max 30 pts): Critical track fractures vs. cyclic inspections.
  2. **Statutory Overdue Penalty** (Max 25 pts): Exponential penalty as inspections exceed IRPWM statutory intervals.
  3. **Route Class & Asset Criticality** (Max 20 pts): High-density trunk routes (Golden Quadrilateral) prioritized by traffic density (GMT).
  4. **Operational Capacity Impact / PSR Lifting** (Max 15 pts): Eliminating speed bottlenecks (30 km/h PSRs) to restore line velocity.
  5. **Departmental Compliance Weight** (Max 10 pts): Regulatory cross-departmental parity.

### 4.3 Corridor Availability Window Identification
* Continuously ingest train timetables from the Control Office Application (COA).
* Dynamically compute non-overlapping natural train gap intervals ($\ge 30$ mins) between scheduled passenger and freight runs.
* Support goods train headway regulation to widen maintenance windows when critical work orders are pending.

### 4.4 Coordinated Shadow Block Optimizer
* Implement an automated constraint-satisfaction optimizer that identifies primary critical work orders and opportunistically bundles compatible companion tasks from other departments into unified **"Shadow Blocks"**.
* Enforce Indian Railways safety interlocks:
  - 25kV OHE power cutoff verification whenever TDMS electrical work is present.
  - Spatial and vibration incompatibility guards (e.g., separating heavy ballast cleaning from sensitive signaling relay tuning).
  - Heavy machine fleet resource contention guard (preventing double-allocation of CSM tampers, BCM cleaners, and OHE tower wagons).
* Quantify and log net corridor downtime saved ($\sum \text{Duration}_j - \text{Block\_Duration}$).

### 4.5 Multi-Horizon Strategic Planning
* Provide dual operational planning horizons:
  - **Weekly Operational Horizon (7-Day Rolling):** Fast-cycle defect rectification and cyclic inspections.
  - **Monthly Strategic Horizon (30-Day Outlook):** Deep track renewal, tamping cycles, and machine fleet overhaul planning.

### 4.6 Predictive Track Health & Degradation Modeling (PdM)
* Compute a standardized Track Quality Index (TQI, $0 - 100$) based on track age, GMT tonnage, inspection latency, rail wear %, and ballast fouling.
* Implement Weibull hazard degradation curves to forecast defect emergence probability across **30, 60, and 90-day** rolling windows.
* Enable automated, one-click proactive work order dispatch into the integrated backlog before failure occurs.

### 4.7 Real-Time Disruption & What-If Simulation
* Enable traffic controllers to inject hypothetical upstream train delays (15 to 180 minutes) and test corridor resilience.
* Automatically detect timetable clashes between delayed train paths and approved maintenance blocks.
* Quantify cascading ripple delays across trailing passenger and freight trains, providing prescriptive mitigation recommendations.
* Model unscheduled emergency track possessions (e.g. rail fracture or OHE breakdown).

### 4.8 Standardized Statutory Dispatch & Interoperability
* Generate official Indian Railways **Form T/409 (Joint Traffic & Power Block Order)** caution notices ready for immediate transmission to Station Masters, Section Controllers, and Field Gangs.
* Provide automated CSV data export feeds for COA, FOIS, and ICMS enterprise integrations.
* Expose a hardened, authenticated RESTful microservice API (`api.py`) with token authentication, rate limiting, and security headers.

---

## 5. Traceability Matrix: Code Implementation

| Requirement | Code Module | Primary Function / Component | Status |
| :--- | :--- | :--- | :--- |
| **Multi-Dept Work Order Ingestion** | [`app.py`](file:///c:/railway_schedular-main/app.py), [`database/createdata.py`](file:///c:/railway_schedular-main/database/createdata.py) | `Jobs` Table, BDMS requisition form | **100% Implemented** |
| **AI Priority Scoring Model** | [`ai_scorer.py`](file:///c:/railway_schedular-main/ai_scorer.py) | `compute_priority_score()`, `run_scoring_engine()` | **100% Implemented** |
| **Corridor Window Extraction** | [`update_availability.py`](file:///c:/railway_schedular-main/update_availability.py), [`database/generatedata.py`](file:///c:/railway_schedular-main/database/generatedata.py) | `calculate_availability_for_corridors()` | **100% Implemented** |
| **Coordinated Block Optimizer** | [`ai_scheduler.py`](file:///c:/railway_schedular-main/ai_scheduler.py) | `run_scheduler()` | **100% Implemented** |
| **Safety Interlocking Matrix** | [`safety_rules.py`](file:///c:/railway_schedular-main/safety_rules.py) | `audit_block_safety()`, `check_machine_availability()` | **100% Implemented** |
| **Predictive Track Health (PdM)** | [`predictive_health.py`](file:///c:/railway_schedular-main/predictive_health.py) | `compute_track_health()`, `get_predictive_alerts()` | **100% Implemented** |
| **Disruption & Delay Simulator** | [`disruption_simulator.py`](file:///c:/railway_schedular-main/disruption_simulator.py) | `simulate_train_delay()`, `simulate_emergency_possession()` | **100% Implemented** |
| **Form T/409 Circular Notice** | [`dispatch_exporter.py`](file:///c:/railway_schedular-main/dispatch_exporter.py) | `generate_joint_possession_notice_t409()` | **100% Implemented** |
| **Machinery Fleet Manager** | [`database/createdata.py`](file:///c:/railway_schedular-main/database/createdata.py), [`app.py`](file:///c:/railway_schedular-main/app.py) | `Machinery_Fleet` Table, Tab 8 Manager | **100% Implemented** |
| **Restful API Service** | [`api.py`](file:///c:/railway_schedular-main/api.py) | `RailwayAPIHandler` (Auth, Rate Limiter, CSP) | **100% Implemented** |
| **WCAG 2.1 AA Accessibility** | [`app.py`](file:///c:/railway_schedular-main/app.py), [`themes.py`](file:///c:/railway_schedular-main/themes.py) | Semantic ARIA tables, `.sr-only`, `:focus-visible` | **100% Implemented** |
| **Automated Verification Suite** | [`run_tests.py`](file:///c:/railway_schedular-main/run_tests.py), [`tests/`](file:///c:/railway_schedular-main/tests/) | 33 Unit, Security, Efficiency & A11y Tests | **100% Implemented** |
