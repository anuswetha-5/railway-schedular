import os
import sys
import unittest
import time
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "database"))

from ai_scorer import run_scoring_engine
from ai_scheduler import run_scheduler
from predictive_health import analyze_all_tracks_health
from disruption_simulator import simulate_train_delay

DB_PATH = os.path.join(BASE_DIR, "database", "railway_planning.db")


class TestEfficiencyBenchmarks(unittest.TestCase):

    def test_indexed_query_speed(self):
        """Verifies composite indexes keep core query execution times below 25ms."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # 1. Filtered jobs query using idx_jobs_filter
        t0 = time.perf_counter()
        cur.execute("""
            SELECT job_id, track_id, ai_score, defect_severity 
            FROM Jobs 
            WHERE status = 'Pending' AND planning_horizon = 'Weekly' AND source_system = 'TMS'
        """)
        rows = cur.fetchall()
        t_jobs = (time.perf_counter() - t0) * 1000.0
        self.assertLess(t_jobs, 25.0, f"Jobs query took {t_jobs:.2f}ms (threshold 25ms)")

        # 2. Train corridor window query using idx_trains_track_window
        t0 = time.perf_counter()
        cur.execute("""
            SELECT train_id, train_number, scheduled_arrival, scheduled_departure 
            FROM Trains 
            WHERE track_id = 'TRK-101' AND scheduled_arrival >= '08:00'
        """)
        rows = cur.fetchall()
        t_trains = (time.perf_counter() - t0) * 1000.0
        self.assertLess(t_trains, 25.0, f"Trains query took {t_trains:.2f}ms (threshold 25ms)")

        # 3. Block timeline lookup using idx_blocks_track_time
        t0 = time.perf_counter()
        cur.execute("""
            SELECT block_id, window_start, window_end, duration_mins 
            FROM Block_Register 
            WHERE track_id = 'TRK-101'
        """)
        rows = cur.fetchall()
        t_blocks = (time.perf_counter() - t0) * 1000.0
        self.assertLess(t_blocks, 25.0, f"Block Register query took {t_blocks:.2f}ms (threshold 25ms)")
        conn.close()

    def test_scoring_engine_runtime_benchmark(self):
        """Verifies AI Multi-Factor Scorer evaluates entire national backlog in under 500ms."""
        t0 = time.perf_counter()
        scored_count = run_scoring_engine(db_path=DB_PATH, score_all=True)
        t_total = (time.perf_counter() - t0) * 1000.0
        self.assertGreater(scored_count, 0)
        self.assertLess(t_total, 500.0, f"Scoring engine took {t_total:.2f}ms (threshold 500ms)")

    def test_scheduler_runtime_benchmark(self):
        """Verifies Coordinated Shadow Block Optimizer schedules entire corridor network in under 1500ms."""
        # Ensure pending jobs exist so benchmark is completely idempotent across repeated runs
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Jobs WHERE status IS NULL OR status = 'Pending'")
        if cur.fetchone()[0] == 0:
            cur.execute("UPDATE Jobs SET status = 'Pending', block_id = NULL, scheduled_start = NULL, scheduled_end = NULL")
            cur.execute("DELETE FROM Block_Jobs")
            cur.execute("DELETE FROM Block_Register")
            conn.commit()
        conn.close()

        t0 = time.perf_counter()
        blocks_created = run_scheduler(db_path=DB_PATH, horizon="All")
        t_total = (time.perf_counter() - t0) * 1000.0
        self.assertGreater(blocks_created, 0)
        self.assertLess(t_total, 1500.0, f"Scheduler optimizer took {t_total:.2f}ms (threshold 1500ms)")

    def test_pdm_hazard_calculation_speed(self):
        """Verifies Weibull degradation analysis across all 25 corridors completes in under 200ms."""
        t0 = time.perf_counter()
        health_df = analyze_all_tracks_health(db_path=DB_PATH)
        t_total = (time.perf_counter() - t0) * 1000.0
        self.assertFalse(health_df.empty)
        self.assertLess(t_total, 200.0, f"PdM analysis took {t_total:.2f}ms (threshold 200ms)")

    def test_disruption_simulator_speed(self):
        """Verifies timetable conflict check and ripple delay calculation execute in under 100ms."""
        t0 = time.perf_counter()
        sim_res = simulate_train_delay("TRK-101", None, "22436", 45, db_path=DB_PATH)
        t_total = (time.perf_counter() - t0) * 1000.0
        self.assertEqual(sim_res.get("status"), "Success")
        self.assertLess(t_total, 100.0, f"Disruption simulation took {t_total:.2f}ms (threshold 100ms)")


if __name__ == "__main__":
    unittest.main()
