import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

def simulate_train_delay(track_id, run_date, train_id_or_number, delay_mins, db_path=None):
    """
    Simulates injecting a train delay and detects resulting clashes with:
    1. Approved Coordinated Shadow Blocks (Possession conflicts)
    2. Following train schedules on the same track (Cascading headway ripples)
    
    Returns structured metrics, clashing blocks, affected trains, and AI mitigation proposals.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    if not os.path.exists(db_path):
        return {"error": "Database not found"}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 0. Validate and resolve run_date to existing timetable dates
    cur.execute("SELECT 1 FROM Trains WHERE track_id = ? AND run_date = ? LIMIT 1", (track_id, run_date))
    if not cur.fetchone():
        cur.execute("SELECT MIN(run_date) FROM Trains WHERE track_id = ?", (track_id,))
        row = cur.fetchone()
        if row and row[0]:
            run_date = row[0]
        else:
            cur.execute("SELECT MIN(run_date) FROM Trains")
            r2 = cur.fetchone()
            if r2 and r2[0]:
                run_date = r2[0]

    # 1. Locate target train
    cur.execute("""
        SELECT train_id, train_number, train_name, train_type,
               scheduled_arrival, scheduled_departure, priority_tier, flexibility_mins
        FROM Trains
        WHERE track_id = ? AND run_date = ? AND (train_id = ? OR train_number = ?)
        LIMIT 1
    """, (track_id, run_date, str(train_id_or_number), str(train_id_or_number)))
    
    target_train = cur.fetchone()
    if not target_train:
        # Fallback: select first train on that track and date
        cur.execute("""
            SELECT train_id, train_number, train_name, train_type,
                   scheduled_arrival, scheduled_departure, priority_tier, flexibility_mins
            FROM Trains
            WHERE track_id = ? AND run_date = ?
            ORDER BY scheduled_arrival ASC LIMIT 1
        """, (track_id, run_date))
        target_train = cur.fetchone()

    if not target_train:
        conn.close()
        return {"error": f"No trains found on Track {track_id} on {run_date}"}

    (tr_id, tr_num, tr_name, tr_type, arr_str, dep_str, tier, flex) = target_train

    # Calculate delayed train occupancy interval
    orig_start = datetime.strptime(f"{run_date} {arr_str}", "%Y-%m-%d %H:%M")
    orig_end = datetime.strptime(f"{run_date} {dep_str}", "%Y-%m-%d %H:%M")
    
    delayed_start = orig_start + timedelta(minutes=delay_mins)
    delayed_end = orig_end + timedelta(minutes=delay_mins)

    # 2. Check for clashes with Approved Shadow Blocks on this track
    cur.execute("""
        SELECT block_id, window_start, window_end, duration_mins,
               departments_list, tasks_count, power_block_granted, status
        FROM Block_Register
        WHERE track_id = ? AND DATE(window_start) = ?
    """, (track_id, run_date))
    
    blocks = cur.fetchall()
    conflicting_blocks = []

    for b in blocks:
        (b_id, b_start_str, b_end_str, b_dur, b_depts, b_tasks, b_pwr, b_stat) = b
        try:
            b_start = datetime.strptime(b_start_str, "%Y-%m-%d %H:%M")
            b_end = datetime.strptime(b_end_str, "%Y-%m-%d %H:%M")
        except Exception:
            continue

        # Overlap test: StartA < EndB and EndA > StartB
        if delayed_start < b_end and delayed_end > b_start:
            overlap_mins = int((min(delayed_end, b_end) - max(delayed_start, b_start)).total_seconds() / 60)
            
            # Fetch bundled jobs for this block
            cur.execute("""
                SELECT j.job_id, j.task, j.department, j.ai_score
                FROM Block_Jobs bj
                JOIN Jobs j ON bj.job_id = j.job_id
                WHERE bj.block_id = ?
            """, (b_id,))
            bundled_jobs = cur.fetchall()

            # Generate smart resolution options
            if "Goods" in tr_type and tier >= 3:
                rec_action = f"Regulate Freight {tr_num} ({tr_name}) at outer loop line; Protect Maintenance Block."
                action_type = "Regulate Freight"
            elif overlap_mins <= (b_dur - 45):
                rec_action = f"Compress Block by {overlap_mins}m; Reschedule non-critical sub-tasks."
                action_type = "Compress Block"
            else:
                rec_action = f"Reschedule Block {b_id} to following corridor gap; Notify P-Way & OHE gangs."
                action_type = "Reschedule Block"

            conflicting_blocks.append({
                "Block ID": b_id,
                "Block Timing": f"{b_start_str} - {b_end_str}",
                "Overlap (mins)": overlap_mins,
                "Departments": b_depts,
                "Tasks Count": b_tasks,
                "Power Isolated": "Yes" if b_pwr else "No",
                "Jobs Impacted": [f"{j[0]}: {j[1]} ({j[2]})" for j in bundled_jobs],
                "Recommended Action": rec_action,
                "Action Type": action_type
            })

    # 3. Check for Headway / Cascading delay on subsequent trains
    cur.execute("""
        SELECT train_id, train_number, train_name, train_type,
               scheduled_arrival, scheduled_departure, priority_tier
        FROM Trains
        WHERE track_id = ? AND run_date = ? AND scheduled_arrival > ?
        ORDER BY scheduled_arrival ASC
    """, (track_id, run_date, arr_str))
    
    subsequent_trains = cur.fetchall()
    cascading_trains = []
    total_cascading_delay_mins = 0
    current_tail = delayed_end

    for st_id, st_num, st_name, st_type, s_arr_str, s_dep_str, s_tier in subsequent_trains:
        s_arr = datetime.strptime(f"{run_date} {s_arr_str}", "%Y-%m-%d %H:%M")
        s_dep = datetime.strptime(f"{run_date} {s_dep_str}", "%Y-%m-%d %H:%M")
        train_run_dur = int((s_dep - s_arr).total_seconds() / 60)

        # Minimum headway spacing: 12 minutes
        min_allowed_arrival = current_tail + timedelta(minutes=12)
        if s_arr < min_allowed_arrival:
            forced_delay = int((min_allowed_arrival - s_arr).total_seconds() / 60)
            total_cascading_delay_mins += forced_delay
            new_arr = min_allowed_arrival
            new_dep = new_arr + timedelta(minutes=train_run_dur)
            current_tail = new_dep

            cascading_trains.append({
                "Train No.": st_num,
                "Train Name": st_name,
                "Category": st_type,
                "Original Arrival": s_arr_str,
                "Forced Delay (mins)": forced_delay,
                "New Projected Arrival": new_arr.strftime("%H:%M"),
                "Priority Tier": s_tier
            })
        else:
            # Trailing gap is sufficient; cascade stops
            break

    conn.close()

    return {
        "status": "Success",
        "target_train": {
            "train_id": tr_id,
            "train_number": tr_num,
            "train_name": tr_name,
            "train_type": tr_type,
            "original_window": f"{arr_str} - {dep_str}",
            "delayed_window": f"{delayed_start.strftime('%H:%M')} - {delayed_end.strftime('%H:%M')}",
            "injected_delay_mins": delay_mins,
            "track_id": track_id,
            "run_date": run_date
        },
        "conflicts_detected": len(conflicting_blocks) > 0,
        "clashing_blocks_count": len(conflicting_blocks),
        "clashing_blocks": conflicting_blocks,
        "cascading_trains_count": len(cascading_trains),
        "total_cascading_delay_mins": total_cascading_delay_mins,
        "cascading_trains": cascading_trains,
        "summary": (
            f"Train {tr_num} (+{delay_mins}m delay) causes {len(conflicting_blocks)} possession block clash(es) "
            f"and ripples into {len(cascading_trains)} trailing train(s) (+{total_cascading_delay_mins}m total cascading delay)."
        )
    }


def simulate_emergency_possession(track_id, run_date, start_time_str, duration_mins, db_path=None):
    """
    Simulates a sudden emergency track possession (e.g. rail fracture or OHE failure)
    and lists all train cancellations or regulations required.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    emg_start = datetime.strptime(f"{run_date} {start_time_str}", "%Y-%m-%d %H:%M")
    emg_end = emg_start + timedelta(minutes=duration_mins)

    cur.execute("""
        SELECT train_id, train_number, train_name, train_type,
               scheduled_arrival, scheduled_departure, priority_tier
        FROM Trains
        WHERE track_id = ? AND run_date = ?
        ORDER BY scheduled_arrival ASC
    """, (track_id, run_date))

    trains = cur.fetchall()
    interrupted_trains = []

    for tr_id, tr_num, tr_name, tr_type, arr_str, dep_str, tier in trains:
        t_arr = datetime.strptime(f"{run_date} {arr_str}", "%Y-%m-%d %H:%M")
        t_dep = datetime.strptime(f"{run_date} {dep_str}", "%Y-%m-%d %H:%M")

        if t_arr < emg_end and t_dep > emg_start:
            overlap = int((min(t_dep, emg_end) - max(t_arr, emg_start)).total_seconds() / 60)
            regulation = "Divert via Loop Line" if "Goods" in tr_type else "Hold at Station Platform"
            interrupted_trains.append({
                "Train No.": tr_num,
                "Train Name": tr_name,
                "Type": tr_type,
                "Schedule": f"{arr_str} - {dep_str}",
                "Overlap (m)": overlap,
                "Action": regulation
            })

    conn.close()

    return {
        "emergency_window": f"{emg_start.strftime('%Y-%m-%d %H:%M')} to {emg_end.strftime('%H:%M')} ({duration_mins}m)",
        "track_id": track_id,
        "interrupted_trains_count": len(interrupted_trains),
        "interrupted_trains": interrupted_trains
    }


if __name__ == "__main__":
    res = simulate_train_delay("TRK-101", None, "22436", 60)
    print("Simulation Output:")
    if "summary" in res:
        print(res["summary"])
        print(f"Clashes: {len(res['clashing_blocks'])}")
    else:
        print(res)
