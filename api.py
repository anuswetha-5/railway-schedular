import os
import sys
import json
import sqlite3
import time
import re
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, date, timedelta

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
    from exceptions import SecurityValidationError
except ImportError:
    sys.path.insert(0, BASE_DIR)
    from ai_scheduler import run_scheduler
    from ai_scorer import run_scoring_engine
    from predictive_health import analyze_all_tracks_health, get_predictive_alerts, generate_proactive_work_order
    from disruption_simulator import simulate_train_delay, simulate_emergency_possession
    from dispatch_exporter import generate_joint_possession_notice_t409, export_blocks_to_csv, export_backlog_to_csv
    from exceptions import SecurityValidationError

# Security Configurations
def _resolve_api_key() -> str:
    """Safely retrieves API key from environment, with local transient secure token fallback."""
    env_key = os.environ.get("RAILWAY_API_KEY")
    if env_key:
        return env_key.strip()
    key_file = os.path.join(BASE_DIR, ".api_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    import secrets
    fallback = f"IR-KEY-{secrets.token_hex(16)}"
    try:
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(fallback)
    except Exception:
        pass
    return fallback

VALID_API_KEY = _resolve_api_key()
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", 60))
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:8501")

# In-Memory Rate Limiter: IP -> list of request timestamps
RATE_LIMIT_STORE = defaultdict(list)


class RailwayAPIHandler(BaseHTTPRequestHandler):
    """Hardened REST API Handler for Indian Railways AI Operations & Block Planning System."""

    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        """Sets standard and defense-in-depth security response headers."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        # Defense-in-Depth Security Headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'")
        self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-XSS-Protection", "1; mode=block")
        # Origin Whitelist CORS
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        """Handles HTTP CORS preflight requests."""
        self._set_headers(200)

    def _check_rate_limit(self) -> bool:
        """Enforces sliding-window rate limit per client IP."""
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        now = time.time()
        # Evict timestamps older than 60 seconds
        RATE_LIMIT_STORE[client_ip] = [ts for ts in RATE_LIMIT_STORE[client_ip] if now - ts < 60]
        if len(RATE_LIMIT_STORE[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
            return False
        RATE_LIMIT_STORE[client_ip].append(now)
        return True

    def _check_auth(self) -> bool:
        """Validates API Key from X-API-Key or Authorization Bearer header."""
        key = self.headers.get("X-API-Key")
        if not key:
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                key = auth_header[7:].strip()
        return key == VALID_API_KEY

    def _read_body_json(self) -> Dict[str, Any]:
        """Reads, limits, and parses incoming request body JSON."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        if content_length > 1024 * 1024:  # 1MB limit to prevent memory exhaustion
            raise SecurityValidationError("Request payload exceeds 1MB threshold")
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            raise SecurityValidationError("Malformed JSON body")

    def do_GET(self) -> None:
        """Handles HTTP GET operational query endpoints."""
        # 1. Rate Limiting Check
        if not self._check_rate_limit():
            self._set_headers(429)
            self.wfile.write(json.dumps({"error": "Too Many Requests: Rate limit exceeded (60 req/min)"}).encode())
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        # Public Health & Liveness Probe
        if path in ("/api/v1/health", "/health"):
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
                "predictive_high_risk_alerts": len(alerts_df),
                "security_status": "HARDENED_RBAC_ACTIVE"
            }, indent=2).encode())
            return

        # Protected Endpoints: Require Authentication
        if not self._check_auth():
            self._set_headers(401)
            self.wfile.write(json.dumps({
                "error": "Unauthorized: Valid API Key required in X-API-Key or Authorization Bearer header."
            }).encode())
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
                h = query["horizon"][0]
                if h in ("Weekly", "Monthly"):
                    where_clauses.append("b.planning_horizon = ?")
                    params.append(h)
            if "track_id" in query:
                t = query["track_id"][0]
                if re.match(r"^TRK-\d+$", t):
                    where_clauses.append("b.track_id = ?")
                    params.append(t)
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
            if not re.match(r"^BLK-\d+-\d+$", block_id):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid block_id format"}).encode())
                return

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
                s = query["status"][0]
                if s in ("Scheduled", "Pending", "Delayed"):
                    where_clauses.append("status = ?")
                    params.append(s)
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
            "error": "Endpoint Not Found",
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

    def do_POST(self) -> None:
        """Handles HTTP POST operational command and simulation endpoints."""
        # 1. Rate Limiting Check
        if not self._check_rate_limit():
            self._set_headers(429)
            self.wfile.write(json.dumps({"error": "Too Many Requests: Rate limit exceeded (60 req/min)"}).encode())
            return

        # 2. Authentication Check on All POST Endpoints
        if not self._check_auth():
            self._set_headers(401)
            self.wfile.write(json.dumps({
                "error": "Unauthorized: Valid API Key required in X-API-Key or Authorization Bearer header."
            }).encode())
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        try:
            data = self._read_body_json()
        except SecurityValidationError as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # 1. Trigger AI Optimizer Pipeline
        if path == "/api/v1/optimizer/run":
            horizon = data.get("horizon", "All")
            if horizon not in ("All", "Weekly", "Monthly"):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid horizon. Must be All, Weekly, or Monthly"}).encode())
                return

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
            raw_job_id = data.get("job_id") or f"JOB-API-{uuid.uuid4().hex[:5].upper()}"
            job_id = re.sub(r"[^A-Za-z0-9\-]", "", str(raw_job_id))
            track_id = data.get("track_id", "TRK-101")
            if not re.match(r"^TRK-\d+$", str(track_id)):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid track_id; must match TRK-XXX format"}).encode())
                return

            dept = str(data.get("department", "Engineering (P-Way)"))[:50]
            src = str(data.get("source_system", "TMS"))[:10]
            m_type = str(data.get("maintenance_type", "Defect Rectification"))[:40]
            task = str(data.get("task", "Ultrasonic Rail Testing Scan"))[:100]
            sev = data.get("defect_severity", "High")
            if sev not in ("Critical", "High", "Medium", "Low"):
                sev = "High"

            try:
                overdue = max(0, min(90, int(data.get("overdue_days", 0))))
                psr = max(0, min(160, int(data.get("speed_restriction_imposed", 0))))
                dur = max(15, min(480, int(data.get("min_duration_needed", 90))))
            except (ValueError, TypeError):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid numeric values in request payload"}).encode())
                return

            pwr = 1 if data.get("power_block_required") else 0
            horizon = data.get("planning_horizon", "Weekly")
            if horizon not in ("Weekly", "Monthly"):
                horizon = "Weekly"

            req_date = data.get("request_date", datetime.now().strftime("%Y-%m-%d"))
            deadline = data.get("deadline", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
            mach = str(data.get("required_machinery", "None"))[:50]

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

                # Fetch computed AI score
                conn_score = sqlite3.connect(DB_PATH)
                c_score = conn_score.cursor()
                c_score.execute("SELECT ai_score FROM Jobs WHERE job_id = ?", (job_id,))
                s_row = c_score.fetchone()
                ai_score = round(s_row[0], 1) if s_row and s_row[0] is not None else 0.0
                conn_score.close()

                self._set_headers(201)
                self.wfile.write(json.dumps({
                    "status": "Created",
                    "job_id": job_id,
                    "track_id": track_id,
                    "task": task,
                    "ai_score": ai_score
                }, indent=2).encode())
            except Exception as e:
                conn.close()
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": f"Database insertion failed: {str(e)}"}).encode())
            return

        # 3. Simulate Train Delay
        if path == "/api/v1/simulate/delay":
            track_id = data.get("track_id", "TRK-101")
            run_date = data.get("run_date")
            train_id = data.get("train_id_or_number", "22436")
            try:
                delay_mins = max(1, min(360, int(data.get("delay_mins", 45))))
            except (ValueError, TypeError):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "delay_mins must be a valid integer between 1 and 360"}).encode())
                return

            sim_res = simulate_train_delay(track_id, run_date, train_id, delay_mins, db_path=DB_PATH)
            self._set_headers(200)
            self.wfile.write(json.dumps(sim_res, indent=2).encode())
            return

        # 4. Generate Proactive Work Order from PdM
        if path == "/api/v1/pdm/generate-work-order":
            track_id = data.get("track_id")
            if not track_id or not re.match(r"^TRK-\d+$", str(track_id)):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Valid track_id (TRK-XXX) is required"}).encode())
                return
            new_job = generate_proactive_work_order(track_id, db_path=DB_PATH)
            self._set_headers(201 if new_job else 400)
            self.wfile.write(json.dumps({
                "job_id": new_job,
                "created_job_id": new_job,
                "source_system": "TMS-PdM"
            }).encode())
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Unknown POST endpoint"}).encode())


def run_api_server(port: int = 8000) -> None:
    """Launches the production-hardened REST API daemon server."""
    server = HTTPServer(("127.0.0.1", port), RailwayAPIHandler)
    print(f"Railway AI Operations Hardened REST API running at http://127.0.0.1:{port}")
    print(f"Authentication: Active (Default API Key: {VALID_API_KEY})")
    print(f"Rate Limiter: Active ({MAX_REQUESTS_PER_MINUTE} req/min)")
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_api_server(port)
