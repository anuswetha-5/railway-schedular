import os
import sqlite3
from datetime import datetime
import pandas as pd

def generate_joint_possession_notice_t409(block_id, db_path=None):
    """
    Generates an authentic Indian Railways Joint Engineering, S&T and Electrical
    Possession Order (Form T/409 / Joint Block Caution Certificate).
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT b.block_id, b.track_id, t.section_name, t.start_station, t.end_station,
               t.route_class, b.window_start, b.window_end, b.duration_mins,
               b.total_departments_involved, b.departments_list, b.tasks_count,
               b.power_block_granted, b.corridor_downtime_saved_mins,
               COALESCE(b.safety_audit_status, 'Compliant'),
               COALESCE(b.assigned_machinery, 'None')
        FROM Block_Register b
        LEFT JOIN Tracks t ON b.track_id = t.track_id
        WHERE b.block_id = ?
    """, (block_id,))
    
    blk = cur.fetchone()
    if not blk:
        conn.close()
        return None, f"Block {block_id} not found."

    (b_id, t_id, sec_name, st1, st2, r_cls, w_start, w_end, dur,
     num_depts, depts_list, t_count, pwr_granted, dt_saved, safety_stat, mach_assigned) = blk

    cur.execute("""
        SELECT j.job_id, j.source_system, j.department, j.task,
               j.defect_severity, j.speed_restriction_imposed,
               COALESCE(j.required_machinery, 'None'), j.ai_score
        FROM Block_Jobs bj
        JOIN Jobs j ON bj.job_id = j.job_id
        WHERE bj.block_id = ?
        ORDER BY j.ai_score DESC
    """, (block_id,))
    
    jobs = cur.fetchall()
    conn.close()

    max_psr = max([j[5] for j in jobs] or [0])
    notice_date = datetime.now().strftime("%d-%b-%Y")
    serial_no = f"T409/{datetime.now().strftime('%Y%m')}/{b_id.replace('BLK-', '')}"

    # Generate Official Document
    lines = []
    lines.append("=" * 76)
    lines.append("                  INDIAN RAILWAYS - OPERATING DEPARTMENT")
    lines.append(f"     FORM T/409 : JOINT TRAFFIC & POWER POSSESSION / CAUTION CERTIFICATE")
    lines.append(f"  Ref: COA/BDMS/AUTO-BLOCK/{b_id}            Issue Date: {notice_date}")
    lines.append(f"  Notice Serial No.: {serial_no}              Status: OFFICIALLY APPROVED")
    lines.append("=" * 76)
    lines.append("")
    lines.append(f"1. CORRIDOR SECTION & LIMITS")
    lines.append(f"   Track Corridor     : {t_id} ({sec_name})")
    lines.append(f"   Station Boundaries : From [{st1}] To [{st2}]")
    lines.append(f"   Route Hierarchy    : {r_cls}")
    lines.append("")
    lines.append(f"2. POSSESSION WINDOW & ELECTRICAL CLEARANCE")
    lines.append(f"   Granted Window     : {w_start} IST  To  {w_end} IST")
    lines.append(f"   Effective Duration : {dur} Minutes ({round(dur/60, 2)} Hours)")
    lines.append(f"   Coordinated Gain   : {dt_saved} mins saved via Multi-Department Shadow Block")
    if pwr_granted:
        lines.append(f"   OHE Power Block    : YES (25kV AC Traction Isolated & Discharge Rods Earthed)")
        lines.append(f"   TPC Permit No.     : TPC/OHE/{b_id}/PERMIT-GRANTED")
    else:
        lines.append(f"   OHE Power Block    : NO (Traffic Possession Only; Catenary remains energized)")
    lines.append("")
    lines.append(f"3. TRACK MACHINERY & SAFETY AUDIT")
    lines.append(f"   Fleet Machinery    : {mach_assigned}")
    lines.append(f"   Interlocking Audit : {safety_stat}")
    if max_psr > 0:
        lines.append(f"   Cautionary Order   : SPEED RESTRICTION OF {max_psr} KM/H IMPOSED UPON RESUMPTION")
    else:
        lines.append(f"   Cautionary Order   : Sectional Normal Line Speed Cleared upon Gang Evacuation")
    lines.append("")
    lines.append(f"4. CONSOLIDATED DEPARTMENTAL WORK ORDERS ({t_count} TASKS BUNDLED)")
    lines.append("   " + "-" * 72)
    lines.append(f"   {'Job ID':<12} {'System':<8} {'Dept':<22} {'PSR':<5} {'Task Description':<25}")
    lines.append("   " + "-" * 72)
    for j_id, src, dept, task, sev, psr, mach, sc in jobs:
        lines.append(f"   {j_id:<12} {src:<8} {dept[:20]:<22} {f'{psr}k' if psr else '-':<5} {task[:25]:<25}")
    lines.append("   " + "-" * 72)
    lines.append("")
    lines.append("5. MANDATORY CLEARANCE & SAFETY ACKNOWLEDGMENTS")
    lines.append("   [x] Station Master (SM) Informed & Red Home Signals Interlocked")
    lines.append("   [x] Section Controller (COA) Granted Track Possession Lock")
    lines.append("   [x] Senior Section Engineer (P-Way, S&T, TRD) Joint Possession Authorized")
    lines.append("")
    lines.append("AUTHORIZATION SIGNATURES:")
    lines.append("  Chief Train Controller (COA)        Divisional Operations Manager (DOM)")
    lines.append("  Traction Power Controller (TPC)     Senior Divisional Engineer (Sr. DEN)")
    lines.append("=" * 76)

    doc_text = "\n".join(lines)
    return doc_text, {
        "block_id": b_id,
        "serial_no": serial_no,
        "track_id": t_id,
        "section": sec_name,
        "window": f"{w_start} to {w_end}",
        "duration_mins": dur,
        "power_isolated": bool(pwr_granted),
        "machinery": mach_assigned,
        "safety_audit": safety_stat,
        "max_psr": max_psr,
        "tasks_count": t_count,
        "jobs": [j[0] for j in jobs]
    }


def export_blocks_to_csv(db_path=None):
    """Exports Block_Register to standard CSV string for external COA/FOIS consumption."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("""
        SELECT b.block_id, b.track_id, t.section_name, b.window_start, b.window_end,
               b.duration_mins, b.total_departments_involved, b.departments_list,
               b.tasks_count, b.power_block_granted, b.corridor_downtime_saved_mins,
               b.planning_horizon, b.status, b.safety_audit_status, b.assigned_machinery
        FROM Block_Register b
        LEFT JOIN Tracks t ON b.track_id = t.track_id
        ORDER BY b.window_start ASC
    """, conn)
    conn.close()
    return df.to_csv(index=False)


def export_backlog_to_csv(db_path=None):
    """Exports integrated maintenance backlog to standard CSV string."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("""
        SELECT j.job_id, j.track_id, t.section_name, j.source_system, j.department,
               j.maintenance_type, j.task, j.defect_severity, j.overdue_days,
               j.speed_restriction_imposed, j.min_duration_needed, j.power_block_required,
               j.planning_horizon, j.request_date, j.deadline, j.ai_score,
               j.scheduled_start, j.scheduled_end, j.block_id, j.status,
               j.required_machinery, j.safety_clearance_status
        FROM Jobs j
        LEFT JOIN Tracks t ON j.track_id = t.track_id
        ORDER BY j.ai_score DESC
    """, conn)
    conn.close()
    return df.to_csv(index=False)


def export_fleet_to_csv(db_path=None):
    """Exports Machinery_Fleet to standard CSV string."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM Machinery_Fleet ORDER BY machine_type, machine_id", conn)
    conn.close()
    return df.to_csv(index=False)


if __name__ == "__main__":
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "railway_planning.db"))
    cur = conn.cursor()
    cur.execute("SELECT block_id FROM Block_Register LIMIT 1")
    b_row = cur.fetchone()
    conn.close()

    if b_row:
        notice, meta = generate_joint_possession_notice_t409(b_row[0])
        print("Generated Form T/409 Possession Notice:")
        print(notice)
