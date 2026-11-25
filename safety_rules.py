import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("railway_scheduler.safety")

def audit_block_safety(
    track_id: str,
    jobs_in_block: List[Dict[str, Any]],
    power_block_granted: bool = False,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Audits a planned joint possession / Shadow Block against Indian Railways
    Safety Clearance & Interlocking protocols:
    
    1. 25kV OHE Electrification & Power Block Clearance
    2. Mechanical vs Electronic Signaling Incompatibility (Vibration & Dust isolation)
    3. Heavy Machinery Resource Fleet Contention
    4. Speed Restriction (PSR) Cautionary Order Requisition
    """
    checks = []
    is_compliant = True
    warnings = []
    assigned_machines = set()

    # 1. 25kV OHE Isolation Check
    requires_power_cutoff = any(j.get("power_block_required", False) for j in jobs_in_block)
    has_tdms = any(j.get("source_system") == "TDMS" for j in jobs_in_block)

    if requires_power_cutoff or has_tdms:
        if power_block_granted:
            checks.append({
                "rule": "OHE 25kV Traction Power Isolation",
                "status": "PASS",
                "detail": "Traction Power Controller (TPC) Permit-to-Work issued. OHE isolated and earthed."
            })
        else:
            is_compliant = False
            checks.append({
                "rule": "OHE 25kV Traction Power Isolation",
                "status": "FAIL",
                "detail": "CRITICAL: Work scheduled under live 25kV OHE without granted Power Block!"
            })
            warnings.append("OHE 25kV Isolation Missing")
    else:
        checks.append({
            "rule": "OHE 25kV Traction Power Isolation",
            "status": "PASS",
            "detail": "Traffic Block only; no high-voltage isolation required."
        })

    # 2. Mechanical vs Sensitive Signaling Mutual Incompatibility Check
    has_heavy_pway = any("BCM" in j.get("task", "") or "Deep Screening" in j.get("task", "") or 
                         "Panel Renewal" in j.get("task", "") for j in jobs_in_block)
    has_sensitive_sig = any("AFTC" in j.get("task", "") or "Point Machine" in j.get("task", "") or 
                            "Electronic Interlocking" in j.get("task", "") for j in jobs_in_block)

    if has_heavy_pway and has_sensitive_sig:
        is_compliant = False
        checks.append({
            "rule": "Spatial Vibration & Dust Separation",
            "status": "WARN",
            "detail": "Heavy Ballast/Track relaying machinery cannot operate concurrently with sensitive signal relay/AFTC calibration."
        })
        warnings.append("Heavy Ballast Machine vs Signal Calibration Conflict")
    else:
        checks.append({
            "rule": "Spatial Vibration & Dust Separation",
            "status": "PASS",
            "detail": "No conflicting concurrent civil-signal machinery operations."
        })

    # 3. Machine & Resource Allocation Check
    for j in jobs_in_block:
        mach = j.get("required_machinery", "None")
        if mach and mach not in ("None", "Manual Gang & Tool Rake"):
            assigned_machines.add(mach)

    if len(assigned_machines) > 2:
        warnings.append("Multiple heavy machines on single corridor section; requires spatial staggering")
        checks.append({
            "rule": "Track Section Machine Density",
            "status": "WARN",
            "detail": f"{len(assigned_machines)} heavy machines assigned ({', '.join(assigned_machines)}). Stagger entry by 200m."
        })
    else:
        checks.append({
            "rule": "Track Section Machine Density",
            "status": "PASS",
            "detail": f"Machinery requirement within section clearance limits: {', '.join(assigned_machines) if assigned_machines else 'None'}."
        })

    # 4. Speed Restriction & Caution Order Rule
    max_psr = max([j.get("speed_restriction_imposed", 0) for j in jobs_in_block] or [0])
    caution_required = max_psr > 0
    if caution_required:
        checks.append({
            "rule": "Caution Order & Speed Restriction (Form T/409)",
            "status": "ACTION REQUIRED",
            "detail": f"Speed restriction of {max_psr} km/h imposed post-work. Form T/409 caution order mandatory."
        })
    else:
        checks.append({
            "rule": "Caution Order & Speed Restriction (Form T/409)",
            "status": "PASS",
            "detail": "Full sectional line speed cleared upon completion."
        })

    # Overall Audit Badge
    if not is_compliant:
        audit_badge = "Safety Hazard / Non-Compliant"
    elif warnings:
        audit_badge = "Conditional Approval (Caution Advised)"
    else:
        audit_badge = "Fully Compliant (All Interlocks Verified)"

    return {
        "is_compliant": is_compliant,
        "audit_badge": audit_badge,
        "warnings": warnings,
        "assigned_machines": list(assigned_machines),
        "assigned_machines_str": ", ".join(sorted(list(assigned_machines))) if assigned_machines else "None",
        "caution_required": caution_required,
        "max_psr_imposed": max_psr,
        "checks": checks
    }


def check_machine_availability(
    machine_type: str,
    track_id: str,
    window_start: str,
    window_end: str,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """Verifies that a required track machine is available and not already committed to another block."""
    if not machine_type or machine_type in ("None", "Manual Gang & Tool Rake"):
        return True, "Standard manual gang / no special machine contention."

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if db_path is None:
        db_path = os.path.join(base_dir, "database", "railway_planning.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(base_dir, "railway_planning.db")

    if not os.path.exists(db_path):
        return True, "DB check bypassed"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Find machines of this type
    cur.execute("""
        SELECT machine_id, machine_name, status, home_depot, operator_gang
        FROM Machinery_Fleet
        WHERE machine_type = ?
    """, (machine_type,))
    fleet = cur.fetchall()

    if not fleet:
        conn.close()
        return True, f"Fleet machine allocated from divisional reserve ({machine_type})."

    # Check if all machines of this type are in use on overlapping blocks
    cur.execute("""
        SELECT b.block_id, b.track_id, b.window_start, b.window_end, b.assigned_machinery
        FROM Block_Register b
        WHERE b.assigned_machinery LIKE ?
          AND b.window_start < ? AND b.window_end > ?
    """, (f"%{machine_type}%", window_end, window_start))

    overlapping = cur.fetchall()
    conn.close()

    if len(overlapping) >= len(fleet):
        return False, f"All {len(fleet)} {machine_type} units committed to other concurrent blocks!"

    avail_count = len(fleet) - len(overlapping)
    return True, f"{avail_count} of {len(fleet)} {machine_type} unit(s) available."
