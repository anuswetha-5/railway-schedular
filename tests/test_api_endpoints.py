import os
import sys
import unittest
import json
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "database"))

from tests.test_security import execute_mock_request
from api import VALID_API_KEY, RATE_LIMIT_STORE

DB_PATH = os.path.join(BASE_DIR, "database", "railway_planning.db")


class TestAPIEndpoints(unittest.TestCase):

    def setUp(self):
        RATE_LIMIT_STORE.clear()
        self.auth_headers = {"X-API-Key": VALID_API_KEY, "Content-Type": "application/json"}

    def test_health_endpoint(self):
        """Verifies public health endpoint returns system status and asset counts."""
        status, headers, body = execute_mock_request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertEqual(data.get("status"), "ONLINE")
        self.assertGreater(data.get("tracks_count", 0), 0)
        self.assertGreater(data.get("jobs_count", 0), 0)
        self.assertIn("security_status", data)

    def test_tracks_endpoint(self):
        """Verifies GET /api/v1/tracks returns Track Quality Index health records."""
        status, headers, body = execute_mock_request("GET", "/api/v1/tracks", headers=self.auth_headers)
        self.assertEqual(status, 200)
        tracks = json.loads(body.decode())
        self.assertIsInstance(tracks, list)
        self.assertGreater(len(tracks), 0)
        first = tracks[0]
        self.assertIn("Track ID", first)
        self.assertIn("TQI Score", first)
        self.assertIn("Risk Level", first)

    def test_blocks_endpoint(self):
        """Verifies GET /api/v1/blocks returns scheduled possession windows."""
        status, headers, body = execute_mock_request("GET", "/api/v1/blocks", headers=self.auth_headers)
        self.assertEqual(status, 200)
        blocks = json.loads(body.decode())
        self.assertIsInstance(blocks, list)
        if len(blocks) > 0:
            first = blocks[0]
            self.assertIn("block_id", first)
            self.assertIn("window_start", first)
            self.assertIn("safety_audit_status", first)

    def test_blocks_filter_endpoint(self):
        """Verifies GET /api/v1/blocks?horizon=Weekly filters correctly."""
        status, headers, body = execute_mock_request("GET", "/api/v1/blocks?horizon=Weekly", headers=self.auth_headers)
        self.assertEqual(status, 200)
        blocks = json.loads(body.decode())
        for b in blocks:
            self.assertEqual(b.get("planning_horizon"), "Weekly")

    def test_jobs_endpoint(self):
        """Verifies GET /api/v1/jobs returns backlog records."""
        status, headers, body = execute_mock_request("GET", "/api/v1/jobs", headers=self.auth_headers)
        self.assertEqual(status, 200)
        jobs = json.loads(body.decode())
        self.assertIsInstance(jobs, list)
        self.assertGreater(len(jobs), 0)
        first = jobs[0]
        self.assertIn("job_id", first)
        self.assertIn("defect_severity", first)
        self.assertIn("ai_score", first)

    def test_alerts_endpoint(self):
        """Verifies GET /api/v1/alerts returns high-risk predictive maintenance warnings."""
        status, headers, body = execute_mock_request("GET", "/api/v1/alerts", headers=self.auth_headers)
        self.assertEqual(status, 200)
        alerts = json.loads(body.decode())
        self.assertIsInstance(alerts, list)

    def test_machinery_fleet_endpoint(self):
        """Verifies GET /api/v1/machinery returns fleet equipment inventory."""
        status, headers, body = execute_mock_request("GET", "/api/v1/machinery", headers=self.auth_headers)
        self.assertEqual(status, 200)
        fleet = json.loads(body.decode())
        self.assertIsInstance(fleet, list)
        self.assertGreater(len(fleet), 0)
        first = fleet[0]
        self.assertIn("machine_id", first)
        self.assertIn("machine_type", first)

    def test_possession_notice_endpoint(self):
        """Verifies Form T/409 notice generation via API."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT block_id FROM Block_Register LIMIT 1")
        row = cur.fetchone()
        conn.close()

        if row:
            b_id = row[0]
            status, _, body = execute_mock_request("GET", f"/api/v1/possession-notice/{b_id}", headers=self.auth_headers)
            self.assertEqual(status, 200)
            data = json.loads(body.decode())
            self.assertIn("notice_text", data)
            self.assertIn("FORM T/409", data["notice_text"])

    def test_post_jobs_creation(self):
        """Verifies POST /api/v1/jobs creates a new work order and computes AI score."""
        payload = {
            "track_id": "TRK-101",
            "department": "Engineering (P-Way)",
            "source_system": "TMS",
            "task": "Automated Ultrasonic Track Weld Testing",
            "defect_severity": "High",
            "overdue_days": 12,
            "min_duration_needed": 90,
            "planning_horizon": "Weekly",
            "required_machinery": "USFD Testing Trolley"
        }
        status, _, body = execute_mock_request(
            "POST",
            "/api/v1/jobs",
            headers=self.auth_headers,
            body=json.dumps(payload).encode()
        )
        self.assertEqual(status, 201)
        res = json.loads(body.decode())
        self.assertEqual(res.get("status"), "Created")
        self.assertIn("job_id", res)
        self.assertGreater(res.get("ai_score", 0), 0)

    def test_post_disruption_simulation(self):
        """Verifies POST /api/v1/simulate/delay returns timetable cascade analysis."""
        payload = {
            "track_id": "TRK-101",
            "train_number": "22436",
            "delay_mins": 45
        }
        status, _, body = execute_mock_request(
            "POST",
            "/api/v1/simulate/delay",
            headers=self.auth_headers,
            body=json.dumps(payload).encode()
        )
        self.assertEqual(status, 200)
        res = json.loads(body.decode())
        self.assertIn("clashing_blocks_count", res)
        self.assertIn("total_cascading_delay_mins", res)

    def test_post_pdm_generate_work_order(self):
        """Verifies POST /api/v1/pdm/generate-work-order creates a proactive job."""
        payload = {"track_id": "TRK-101"}
        status, _, body = execute_mock_request(
            "POST",
            "/api/v1/pdm/generate-work-order",
            headers=self.auth_headers,
            body=json.dumps(payload).encode()
        )
        self.assertEqual(status, 201)
        res = json.loads(body.decode())
        self.assertIn("job_id", res)
        self.assertEqual(res.get("source_system"), "TMS-PdM")

    def test_404_not_found(self):
        """Verifies 404 response for unknown routes with list of available endpoints."""
        status, _, body = execute_mock_request("GET", "/api/v1/nonexistent", headers=self.auth_headers)
        self.assertEqual(status, 404)
        data = json.loads(body.decode())
        self.assertIn("available_endpoints", data)


if __name__ == "__main__":
    unittest.main()
