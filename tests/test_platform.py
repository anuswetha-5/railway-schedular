import os
import sys
import unittest
import sqlite3

# Insert base directory and database directory into sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "database"))

from ai_scorer import compute_priority_score
from predictive_health import compute_track_health, analyze_all_tracks_health, get_predictive_alerts
from disruption_simulator import simulate_train_delay, simulate_emergency_possession
from safety_rules import audit_block_safety, check_machine_availability
from dispatch_exporter import generate_joint_possession_notice_t409, export_blocks_to_csv, export_backlog_to_csv

DB_PATH = os.path.join(BASE_DIR, "database", "railway_planning.db")


class TestRailwayPlatform(unittest.TestCase):

    def test_database_tables_exist(self):
        """Verifies that all 7 relational tables exist in railway_planning.db."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = set(r[0] for r in cur.fetchall())
        conn.close()

        required = {"Tracks", "Trains", "Jobs", "Corridor_Availability",
                    "Block_Register", "Block_Jobs", "Machinery_Fleet"}
        for tbl in required:
            self.assertIn(tbl, tables, f"Missing table: {tbl}")

    def test_ai_scoring_engine(self):
        """Verifies that AI scoring produces valid bounded scores and honors defect severity."""
        crit_score, b_crit = compute_priority_score("Critical", 25, "Golden Quadrilateral", 18, 60.0, "Critical", 30, "TMS")
        low_score, b_low = compute_priority_score("Low", 0, "Trunk Route A", 4, 25.0, "Low", 0, "TMS")

        self.assertGreater(crit_score, low_score, "Critical defect should score higher than low defect")
        self.assertGreaterEqual(crit_score, 5.0)
        self.assertLessEqual(crit_score, 100.0)
        self.assertIn("severity_risk", b_crit)
        self.assertIn("capacity_impact", b_crit)

    def test_predictive_health_model(self):
        """Verifies Track Quality Index (TQI) calculation and Weibull hazard probabilities."""
        health = compute_track_health(
            track_age=12,
            gmt_tonnage=45.0,
            speed_limit_kmh=130,
            route_class="High Density Network (HDN)",
            days_since_inspection=20,
            days_since_tamping=45,
            rail_wear_pct=14.0,
            ballast_condition="Good"
        )
        self.assertGreaterEqual(health["tqi_score"], 30.0)
        self.assertLessEqual(health["tqi_score"], 100.0)
        self.assertIn(health["risk_level"], ["Low", "Moderate", "Elevated", "High"])
        self.assertLessEqual(health["prob_defect_30d"], health["prob_defect_60d"])
        self.assertLessEqual(health["prob_defect_60d"], health["prob_defect_90d"])

    def test_safety_interlocking_matrix(self):
        """Verifies safety audit flags live wire work without power cutoff and mechanical conflicts."""
        # Unsafe: TDMS electrical task without power block granted
        unsafe_jobs = [{"job_id": "JOB-TEST", "source_system": "TDMS", "task": "OHE Contact Wire", "power_block_required": 1}]
        res_unsafe = audit_block_safety("TRK-101", unsafe_jobs, power_block_granted=False, db_path=DB_PATH)
        self.assertFalse(res_unsafe["is_compliant"])
        self.assertIn("OHE 25kV Isolation Missing", res_unsafe["warnings"])

        # Safe: Same job with power block granted
        res_safe = audit_block_safety("TRK-101", unsafe_jobs, power_block_granted=True, db_path=DB_PATH)
        self.assertTrue(res_safe["is_compliant"])

        # Mechanical conflict: BCM deep screening + sensitive signal testing
        clashing_jobs = [
            {"job_id": "J1", "task": "Ballast Cleaning Machine (BCM) Deep Screening"},
            {"job_id": "J2", "task": "Audio Frequency Track Circuit (AFTC) Tuning"}
        ]
        res_clash = audit_block_safety("TRK-101", clashing_jobs, power_block_granted=True, db_path=DB_PATH)
        self.assertFalse(res_clash["is_compliant"])

    def test_disruption_simulator(self):
        """Verifies train delay simulation and conflict detection return structured response."""
        res = simulate_train_delay("TRK-101", None, "22436", 45, db_path=DB_PATH)
        self.assertEqual(res["status"], "Success")
        self.assertIn("target_train", res)
        self.assertIn("clashing_blocks_count", res)
        self.assertIn("total_cascading_delay_mins", res)

    def test_dispatch_exporter_form_t409(self):
        """Verifies Form T/409 official Joint Possession Certificate generation."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT block_id FROM Block_Register LIMIT 1")
        b_row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(b_row, "Block_Register must contain at least one scheduled block")
        blk_id = b_row[0]
        notice_txt, meta = generate_joint_possession_notice_t409(blk_id, db_path=DB_PATH)

        self.assertIsNotNone(notice_txt)
        self.assertIn("FORM T/409", notice_txt)
        self.assertIn("INDIAN RAILWAYS", notice_txt)
        self.assertEqual(meta["block_id"], blk_id)

    def test_csv_exports(self):
        """Verifies CSV string generation for blocks and backlog."""
        blocks_csv = export_blocks_to_csv(DB_PATH)
        self.assertIn("block_id,track_id,section_name", blocks_csv)

        backlog_csv = export_backlog_to_csv(DB_PATH)
        self.assertIn("job_id,track_id,section_name", backlog_csv)


if __name__ == "__main__":
    unittest.main()
