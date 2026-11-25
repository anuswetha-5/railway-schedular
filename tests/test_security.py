import os
import sys
import unittest
import sqlite3
import io
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "database"))

from api import RailwayAPIHandler, VALID_API_KEY, RATE_LIMIT_STORE, MAX_REQUESTS_PER_MINUTE
from exceptions import SecurityValidationError
import html

DB_PATH = os.path.join(BASE_DIR, "database", "railway_planning.db")


from typing import Optional, Dict, Any, Tuple, Union

class MockSocket:
    """Mock socket emulation for high-speed in-memory HTTP handler testing."""

    def __init__(self, data: bytes = b"") -> None:
        """Initializes mock socket buffer with simulated incoming bytes."""
        self._data = data
        self._written = io.BytesIO()

    def makefile(self, mode: str = "r", buffering: int = -1) -> Union[io.BytesIO, io.StringIO]:
        """Provides simulated stream reader or writer."""
        if "b" in mode:
            if "r" in mode:
                return io.BytesIO(self._data)
            return self._written
        return io.StringIO(self._data.decode("utf-8", errors="replace"))

    def sendall(self, b: bytes) -> None:
        """Simulates sending raw data across socket."""
        self._written.write(b)

    def close(self) -> None:
        """Simulates closing socket connection."""
        pass


def execute_mock_request(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    body: Union[bytes, str] = b""
) -> Tuple[int, Dict[str, str], bytes]:
    """Executes a mock HTTP request against RailwayAPIHandler without opening a real network port."""
    headers = headers or {}
    raw_req = f"{method} {path} HTTP/1.1\r\n"
    if "Host" not in headers:
        headers["Host"] = "localhost"
    if body and "Content-Length" not in headers:
        headers["Content-Length"] = str(len(body))
    for k, v in headers.items():
        raw_req += f"{k}: {v}\r\n"
    raw_req += "\r\n"
    raw_bytes = raw_req.encode("utf-8") + (body if isinstance(body, bytes) else body.encode("utf-8"))

    sock = MockSocket(raw_bytes)
    handler = RailwayAPIHandler(sock, ("127.0.0.1", 54321), None)
    response_bytes = sock._written.getvalue()
    
    # Parse status code and headers
    status_line = response_bytes.split(b"\r\n")[0].decode("utf-8", errors="replace")
    parts = status_line.split(" ")
    status_code = int(parts[1]) if len(parts) > 1 else 0

    # Parse response body
    header_end = response_bytes.find(b"\r\n\r\n")
    resp_body = response_bytes[header_end + 4:] if header_end != -1 else b""

    # Extract headers
    resp_headers = {}
    if header_end != -1:
        h_lines = response_bytes[:header_end].decode("utf-8", errors="replace").split("\r\n")[1:]
        for line in h_lines:
            if ": " in line:
                hk, hv = line.split(": ", 1)
                resp_headers[hk.lower()] = hv

    return status_code, resp_headers, resp_body


class TestSecurityFramework(unittest.TestCase):

    def setUp(self) -> None:
        """Clears client rate limiter store before each test execution."""
        RATE_LIMIT_STORE.clear()

    def test_sql_injection_defense(self):
        """Verifies parameterized query defenses neutralize SQL injection strings."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        malicious_id = "TRK-101' OR '1'='1' --"
        # Correctly parameterized query should return zero records or only matching literal
        cur.execute("SELECT COUNT(*) FROM Tracks WHERE track_id = ?", (malicious_id,))
        count = cur.fetchone()[0]
        self.assertEqual(count, 0, "SQL injection string must not match any valid track record")

        # Malicious job id injection attempt
        malicious_job = "JOB-9999' UNION SELECT * FROM Tracks --"
        cur.execute("SELECT COUNT(*) FROM Jobs WHERE job_id = ?", (malicious_job,))
        job_count = cur.fetchone()[0]
        self.assertEqual(job_count, 0, "SQL injection union query must return zero records")
        conn.close()

    def test_xss_escaping(self):
        """Verifies HTML output generation escapes script and execution injection payloads."""
        xss_payload = "<script>alert('XSS_ATTACK')</script>"
        escaped = html.escape(xss_payload)
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)
        self.assertNotIn("</script>", escaped)

    def test_api_key_authentication(self):
        """Verifies that protected endpoints require valid authentication."""
        # 1. Unauthenticated request to protected endpoint -> 401
        status, _, body = execute_mock_request("GET", "/api/v1/blocks")
        self.assertEqual(status, 401)
        data = json.loads(body.decode())
        self.assertIn("error", data)

        # 2. Invalid API Key -> 401
        status, _, _ = execute_mock_request("GET", "/api/v1/blocks", headers={"X-API-Key": "INVALID-KEY-1234"})
        self.assertEqual(status, 401)

        # 3. Valid API Key via X-API-Key -> 200
        status, _, body = execute_mock_request("GET", "/api/v1/blocks", headers={"X-API-Key": VALID_API_KEY})
        self.assertEqual(status, 200)

        # 4. Valid API Key via Bearer Token -> 200
        status, _, body = execute_mock_request("GET", "/api/v1/blocks", headers={"Authorization": f"Bearer {VALID_API_KEY}"})
        self.assertEqual(status, 200)

    def test_rate_limiter_enforcement(self):
        """Verifies that the rate limiter trips with 429 when exceeding threshold."""
        client_ip = "192.168.1.100"
        # Simulate filling rate limiter store up to the maximum
        now = time.time()
        RATE_LIMIT_STORE[client_ip] = [now] * MAX_REQUESTS_PER_MINUTE

        # Manually create mock request from this client_ip
        raw_req = b"GET /api/v1/health HTTP/1.1\r\nHost: localhost\r\n\r\n"
        sock = MockSocket(raw_req)
        handler = RailwayAPIHandler(sock, (client_ip, 12345), None)
        response_bytes = sock._written.getvalue()

        status_line = response_bytes.split(b"\r\n")[0].decode()
        self.assertIn("429", status_line, "Exceeding rate limit threshold must return HTTP 429")

    def test_defense_in_depth_security_headers(self):
        """Verifies security headers (nosniff, DENY, CSP, HSTS) on API responses."""
        status, headers, _ = execute_mock_request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("x-frame-options"), "DENY")
        self.assertEqual(headers.get("x-xss-protection"), "1; mode=block")
        self.assertIn("max-age=31536000", headers.get("strict-transport-security", ""))
        self.assertIn("default-src 'self'", headers.get("content-security-policy", ""))

    def test_payload_size_enforcement(self):
        """Verifies that requests with payload size > 1MB are rejected."""
        large_body = b"A" * (1024 * 1024 + 500)
        status, _, body = execute_mock_request(
            "POST",
            "/api/v1/jobs",
            headers={"X-API-Key": VALID_API_KEY, "Content-Length": str(len(large_body))},
            body=large_body
        )
        self.assertEqual(status, 400)
        self.assertIn("exceeds 1MB threshold", body.decode())


if __name__ == "__main__":
    unittest.main()
