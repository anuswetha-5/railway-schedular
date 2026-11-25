import os
import sys
import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "railway_planning.db")
if not os.path.exists(DB_PATH):
    alt = os.path.join(BASE_DIR, "railway_planning.db")
    if os.path.exists(alt):
        DB_PATH = alt

try:
    from ai_scheduler import run_scheduler
    from ai_scorer import run_scoring_engine
    from predictive_health import analyze_all_tracks_health, get_predictive_alerts, generate_proactive_work_order
    from disruption_simulator import simulate_train_delay, simulate_emergency_possession
    from dispatch_exporter import generate_joint_possession_notice_t409, export_blocks_to_csv, export_backlog_to_csv
except ImportError:
    sys.path.insert(0, BASE_DIR)
    from ai_scheduler import run_scheduler
    from ai_scorer import run_scoring_engine
    from predictive_health import analyze_all_tracks_health, get_predictive_alerts, generate_proactive_work_order
    from disruption_simulator import simulate_train_delay, simulate_emergency_possession
    from dispatch_exporter import generate_joint_possession_notice_t409, export_blocks_to_csv, export_backlog_to_csv


class RailwayAPIHandler(BaseHTTPRequestHandler):
    """REST API Handler for Indian Railways AI Operations & Block Planning System."""

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def _read_body_json(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        # 1. System Health & Platform Meta
        if path == "/api/v1/health" or path == "/health":
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM Tracks")
            n_tracks = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM Jobs")
            n_jobs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM Block_Register")
            n_blocks = cur.fetchone()[0]
            conn.close()

            alerts_df = get_predictive_alerts(db_path=DB_PATH)

            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ONLINE",
                "system": "Automatic Block Planning System (ABPS) / Railway AI Operations",
                "version": "2.0-Enterprise",
                "timestamp": datetime.now().isoformat(),
                "tracks_count": n_tracks,
                "jobs_count": n_jobs,
                "scheduled_blocks_count": n_blocks,
                "predictive_high_risk_alerts": len(alerts_df)
            }, indent=2).encode())
            return

        # 2. Tracks & Asset Quality Indices
        if path == "/api/v1/tracks":
            health_df = analyze_all_tracks_health(db_path=DB_PATH)
            self._set_headers(200)
            self.wfile.write(health_df.to_json(orient="records").encode())
            return

        # 3. Scheduled Shadow Blocks
        if path == "/api/v1/blocks":
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            sql = """
                SELECT b.block_id, b.track_id, t.section_name, b.window_start, b.window_end,
                       b.duration_mins, b.total_departments_involved, b.departments_list,
                       b.tasks_count, b.power_block_granted, b.corridor_downtime_saved_mins,
                       b.planning_horizon, b.status,
                       COALESCE(b.safety_audit_status, 'Compliant') AS safety_audit_status,
                       COALESCE(b.assigned_machinery, 'None') AS assigned_machinery
                FROM Block_Register b
                LEFT JOIN Tracks t ON b.track_id = t.track_id
            """
            params = []
            where_clauses = []
            if "horizon" in query:
                where_clauses.append("b.planning_horizon = ?")
                params.append(query["horizon"][0])
            if "track_id" in query:
                where_clauses.append("b.track_id = ?")
                params.append(query["track_id"][0])
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            sql += " ORDER BY b.window_start ASC"

            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            blocks = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()

            self._set_headers(200)
            self.wfile.write(json.dumps(blocks, indent=2).encode())
            return

        # 4. Form T/409 Possession Order Notice
        if path.startswith("/api/v1/possession-notice/"):
            block_id = path.split("/")[-1]
            notice_text, meta = generate_joint_possession_notice_t409(block_id, db_path=DB_PATH)
            if not notice_text:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": f"Block {block_id} not found"}).encode())
                return
            self._set_headers(200)
            self.wfile.write(json.dumps({"metadata": meta, "notice_text": notice_text}, indent=2).encode())
            return

        # 5. Maintenance Backlog
        if path == "/api/v1/jobs":
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            sql = "SELECT * FROM Jobs"
            params = []
            where_clauses = []
            if "status" in query:
                where_clauses.append("status = ?")
                params.append(query["status"][0])
            if "department" in query:
                where_clauses.append("department = ?")
                params.append(query["department"][0])
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            sql += " ORDER BY ai_score DESC"

            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            jobs = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()

            self._set_headers(200)
            self.wfile.write(json.dumps(jobs, indent=2).encode())
            return

        # 6. Predictive Health Alerts
        if path == "/api/v1/alerts":
            alerts_df = get_predictive_alerts(db_path=DB_PATH)
            self._set_headers(200)
            self.wfile.write(alerts_df.to_json(orient="records").encode())
            return

        # 7. Machinery Fleet
        if path == "/api/v1/machinery":
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT * FROM Machinery_Fleet ORDER BY machine_type, machine_id")
            cols = [d[0] for d in cur.description]
            fleet = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()
            self._set_headers(200)
            self.wfile.write(json.dumps(fleet, indent=2).encode())
            return

        # 404 Fallback
        self._set_headers(404)
        self.wfile.write(json.dumps({
            "error": "Not Found",
            "available_endpoints": [
                "GET /api/v1/health",
                "GET /api/v1/tracks",
                "GET /api/v1/blocks",
                "GET /api/v1/jobs",
                "GET /api/v1/alerts",
                "GET /api/v1/machinery",
                "GET /api/v1/possession-notice/<block_id>",
                "POST /api/v1/jobs",
                "POST /api/v1/optimizer/run",
                "POST /api/v1/simulate/delay",
                "POST /api/v1/pdm/generate-work-order"
            ]
        }, indent=2).encode())

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        data = self._read_body_json()

        # 1. Trigger AI Optimizer Pipeline
        if path == "/api/v1/optimizer/run":
            horizon = data.get("horizon", "All")
            blocks_created = run_scheduler(db_path=DB_PATH, horizon=horizon)
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "Success",
                "blocks_created": blocks_created,
                "horizon_applied": horizon
            }, indent=2).encode())
            return

        # 2. Submit New Maintenance Work Order
        if path == "/api/v1/jobs":
            import uuid
            job_id = data.get("job_id") or f"JOB-API-{uuid.uuid4().hex[:5].upper()}"
            track_id = data.get("track_id", "TRK-101")
            dept = data.get("department", "Engineering (P-Way)")
            src = data.get("source_system", "TMS")
            m_type = data.get("maintenance_type", "Defect Rectification")
            task = data.get("task", "Ultrasonic Rail Testing Scan")
            sev = data.get("defect_severity", "High")
            overdue = int(data.get("overdue_days", 0))
            psr = int(data.get("speed_restriction_imposed", 0))
            dur = int(data.get("min_duration_needed", 90))
            pwr = 1 if data.get("power_block_required") else 0
            horizon = data.get("planning_horizon", "Weekly")
            req_date = data.get("request_date", datetime.now().strftime("%Y-%m-%d"))
            deadline = data.get("deadline", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
            mach = data.get("required_machinery", "None")

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO Jobs (
                        job_id, track_id, department, source_system, maintenance_type,
                        task, defect_severity, overdue_days, speed_restriction_imposed,
                        min_duration_needed, power_block_required, traffic_block_required,
                        planning_horizon, request_date, deadline, status,
                        required_machinery, safety_clearance_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'Pending', ?, 'Pending Audit')
                """, (
                    job_id, track_id, dept, src, m_type, task, sev, overdue,
                    psr, dur, pwr, horizon, req_date, deadline, mach
                ))
                conn.commit()
                conn.close()

                # Trigger AI Scorer
                run_scoring_engine(db_path=DB_PATH)

                self._set_headers(201)
                self.wfile.write(json.dumps({
                    "status": "Created",
                    "job_id": job_id,
                    "track_id": track_id,
                    "task": task
                }, indent=2).encode())
            except Exception as e:
                conn.close()
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # 3. Simulate Train Delay
        if path == "/api/v1/simulate/delay":
            track_id = data.get("track_id", "TRK-101")
            run_date = data.get("run_date")
            train_id = data.get("train_id_or_number", "22436")
            delay_mins = int(data.get("delay_mins", 45))

            sim_res = simulate_train_delay(track_id, run_date, train_id, delay_mins, db_path=DB_PATH)
            self._set_headers(200)
            self.wfile.write(json.dumps(sim_res, indent=2).encode())
            return

        # 4. Generate Proactive Work Order from PdM
        if path == "/api/v1/pdm/generate-work-order":
            track_id = data.get("track_id")
            if not track_id:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "track_id is required"}).encode())
                return
            new_job = generate_proactive_work_order(track_id, db_path=DB_PATH)
            self._set_headers(201 if new_job else 400)
            self.wfile.write(json.dumps({"created_job_id": new_job}).encode())
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Unknown POST endpoint"}).encode())


def run_api_server(port=8501):
    server = HTTPServer(("127.0.0.1", port), RailwayAPIHandler)
    print(f"Railway AI Operations REST API running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_api_server(port)
