import os
import sqlite3
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

logger = logging.getLogger("railway_scheduler.pdm")

def compute_track_health(
    track_age: int,
    gmt_tonnage: float,
    speed_limit_kmh: int,
    route_class: str,
    days_since_inspection: int,
    days_since_tamping: int,
    rail_wear_pct: float = 15.0,
    ballast_condition: str = "Good"
) -> Dict[str, Any]:
    """
    Computes Track Quality Index (TQI, 0-100) and multi-horizon defect probability.
    
    TQI Model:
      - Perfect base: 100.0
      - Age degradation penalty: -0.8 pts/year
      - GMT traffic tonnage wear: -0.2 pts/GMT
      - Speed stress factor: higher speed lines require tighter geometric tolerances
      - Inspection latency penalty: -0.05 pts/day beyond 30 days
      - Tamping cycle degradation: track settling over time
      - Rail head wear penalty
      - Ballast fouling factor
    """
    base_tqi = 100.0
    
    # Age penalty
    age_penalty = min(25.0, track_age * 0.8)
    
    # Tonnage penalty
    tonnage_penalty = min(20.0, (gmt_tonnage or 35.0) * 0.22)
    
    # Speed & route stress factor
    speed_factor = 1.2 if speed_limit_kmh >= 130 else 1.0
    if "Golden" in str(route_class):
        speed_factor += 0.15
        
    # Maintenance latency
    insp_penalty = max(0.0, (days_since_inspection - 30) * 0.08)
    tamping_penalty = max(0.0, (days_since_tamping - 90) * 0.05)
    
    # Physical wear
    wear_penalty = min(18.0, (rail_wear_pct or 15.0) * 0.45)
    ballast_penalties = {"Good": 0.0, "Fair": 5.0, "Degraded": 12.0, "Critical": 20.0}
    ballast_penalty = ballast_penalties.get(ballast_condition, 4.0)
    
    total_deductions = (age_penalty + tonnage_penalty + insp_penalty + 
                        tamping_penalty + wear_penalty + ballast_penalty) * (speed_factor / 1.1)
    
    tqi_score = round(max(30.0, min(98.0, base_tqi - total_deductions)), 1)
    
    # Health status classification
    if tqi_score >= 82.0:
        health_grade = "Sound / Optimal"
        risk_level = "Low"
    elif tqi_score >= 70.0:
        health_grade = "Satisfactory / Monitoring"
        risk_level = "Moderate"
    elif tqi_score >= 58.0:
        health_grade = "Deteriorating / Scheduled Service Needed"
        risk_level = "Elevated"
    else:
        health_grade = "Critical Degradation / Speed Restriction Imminent"
        risk_level = "High"

    # Defect emergence probability forecasting (Weibull hazard curve simulation)
    # Hazard rate lambda increases as TQI drops and traffic accumulates
    hazard_rate = max(0.002, (100.0 - tqi_score) / 1800.0)
    
    p_30 = round(float((1.0 - np.exp(-hazard_rate * 30)) * 100.0), 1)
    p_60 = round(float((1.0 - np.exp(-hazard_rate * 60)) * 100.0), 1)
    p_90 = round(float((1.0 - np.exp(-hazard_rate * 90)) * 100.0), 1)
    
    # Recommended machine and intervention
    if tqi_score < 65.0 or p_30 >= 45.0:
        rec_task = "Targeted Section Tamping & Track Geometry Alignment"
        rec_machine = "CSM Tamping Machine"
        urgency = "Immediate (7 Days)"
    elif rail_wear_pct >= 28.0 or p_60 >= 50.0:
        rec_task = "Rail Head Re-profiling & Surface Grinding"
        rec_machine = "RGM Rail Grinder"
        urgency = "Proactive (15 Days)"
    elif ballast_condition in ("Degraded", "Critical"):
        rec_task = "Ballast Cleaning & Deep Screening"
        rec_machine = "BCM Ballast Cleaner"
        urgency = "Strategic (30 Days)"
    else:
        rec_task = "Routine Ultrasonic Flaw Detection (USFD) Scan"
        rec_machine = "USFD Testing Trolley"
        urgency = "Preventive Cyclic"

    return {
        "tqi_score": tqi_score,
        "health_grade": health_grade,
        "risk_level": risk_level,
        "prob_defect_30d": p_30,
        "prob_defect_60d": p_60,
        "prob_defect_90d": p_90,
        "recommended_task": rec_task,
        "recommended_machine": rec_machine,
        "intervention_urgency": urgency
    }


def analyze_all_tracks_health(db_path: Optional[str] = None) -> pd.DataFrame:
    """Fetches all corridor tracks and calculates predictive health analytics."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    if not os.path.exists(db_path):
        return pd.DataFrame()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT track_id, section_name, route_class, track_age, speed_limit_kmh,
               gmt_tonnage, last_inspected_date, criticality_level,
               COALESCE(tqi_score, 82.0), COALESCE(rail_wear_pct, 15.0),
               COALESCE(ballast_condition, 'Good'), last_tamping_date
        FROM Tracks
        ORDER BY track_id
    """)
    rows = cur.fetchall()
    conn.close()

    today = datetime.now().date()
    records = []

    for r in rows:
        (t_id, s_name, r_cls, age, max_spd, gmt, last_insp_str,
         crit, stored_tqi, wear, ballast, last_tamp_str) = r

        try:
            d_insp = (today - datetime.strptime(last_insp_str, "%Y-%m-%d").date()).days
        except Exception:
            d_insp = 45

        try:
            d_tamp = (today - datetime.strptime(last_tamp_str, "%Y-%m-%d").date()).days if last_tamp_str else 90
        except Exception:
            d_tamp = 90

        health = compute_track_health(
            track_age=age,
            gmt_tonnage=gmt,
            speed_limit_kmh=max_spd,
            route_class=r_cls,
            days_since_inspection=d_insp,
            days_since_tamping=d_tamp,
            rail_wear_pct=wear,
            ballast_condition=ballast
        )

        records.append({
            "Track ID": t_id,
            "Corridor Section": s_name,
            "Route Class": r_cls,
            "Speed (km/h)": max_spd,
            "GMT Tonnage": gmt,
            "Track Age (y)": age,
            "Days Since Insp": d_insp,
            "Rail Wear (%)": wear,
            "Ballast": ballast,
            "TQI Score": health["tqi_score"],
            "Health Grade": health["health_grade"],
            "Risk Level": health["risk_level"],
            "Defect Risk 30d (%)": health["prob_defect_30d"],
            "Defect Risk 60d (%)": health["prob_defect_60d"],
            "Defect Risk 90d (%)": health["prob_defect_90d"],
            "Proactive Task": health["recommended_task"],
            "Required Machine": health["recommended_machine"],
            "Urgency": health["intervention_urgency"]
        })

    return pd.DataFrame(records)


def get_predictive_alerts(db_path: Optional[str] = None, risk_threshold: float = 35.0) -> pd.DataFrame:
    """Identifies tracks requiring proactive maintenance before defect emergence."""
    df = analyze_all_tracks_health(db_path=db_path)
    if df.empty:
        return pd.DataFrame()
    alerts = df[df["Defect Risk 30d (%)"] >= risk_threshold].sort_values("Defect Risk 30d (%)", ascending=False)
    return alerts


def generate_proactive_work_order(track_id: str, db_path: Optional[str] = None) -> Optional[str]:
    """
    Automatically converts a predictive health alert into a formal BDMS work order
    in the database to prevent track faults before they happen.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    df = analyze_all_tracks_health(db_path=db_path)
    row = df[df["Track ID"] == track_id]
    if row.empty:
        return None

    r = row.iloc[0]
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    import uuid
    job_id = f"JOB-PRED-{uuid.uuid4().hex[:5].upper()}"
    today_str = datetime.now().strftime("%Y-%m-%d")
    deadline_str = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

    cur.execute("""
        INSERT INTO Jobs (
            job_id, track_id, department, source_system, maintenance_type,
            task, defect_severity, overdue_days, speed_restriction_imposed,
            min_duration_needed, power_block_required, traffic_block_required,
            planning_horizon, request_date, deadline, status,
            required_machinery, safety_clearance_status
        ) VALUES (?, ?, 'Engineering (P-Way)', 'TMS', 'Predictive Overhaul',
                  ?, 'High', 0, 0, 120, 0, 1, 'Weekly', ?, ?, 'Pending', ?, 'Pre-Approved (PdM)')
    """, (
        job_id, track_id, f"PdM: {r['Proactive Task']}", today_str, deadline_str, r["Required Machine"]
    ))

    conn.commit()
    conn.close()

    # Re-run scoring engine to give the new proactive job its AI score
    try:
        from ai_scorer import run_scoring_engine
        run_scoring_engine(db_path=db_path)
    except Exception:
        pass

    return job_id


if __name__ == "__main__":
    df = analyze_all_tracks_health()
    print("Track Health & Predictive Maintenance Summary:")
    print(df[["Track ID", "TQI Score", "Health Grade", "Defect Risk 30d (%)", "Proactive Task"]].head(10))
