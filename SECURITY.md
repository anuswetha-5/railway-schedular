# Security Policy & Threat Model

## Automatic Block Planning System (ABPS)

---

## 1. Security Overview
The **Automatic Block Planning System (ABPS)** orchestrates railway corridor possessions and maintenance planning across high-density passenger and freight routes. Given the safety-critical nature of national rail infrastructure, security is engineered with a **defense-in-depth** methodology.

---

## 2. Threat Modeling (STRIDE Analysis)

| Threat Category | Potential Attack Vector | Platform Countermeasure & Defense |
|---|---|---|
| **Spoofing** | Attacker impersonates Section Engineer or Station Master to requisition false track blocks | API Key Authentication (`X-API-Key` / Bearer token), role-based audit logs in Form T/409 |
| **Tampering** | Man-in-the-middle or malicious payload alters defect severity or speed restrictions | Parameterized SQLite queries, regex input whitelisting, immutable block hash references |
| **Repudiation** | Operator denies granting a high-voltage 25kV power cutoff permit | Form T/409 includes official serial numbering (`T409/YYYYMM/...`), timestamped signatures, and persistent audit logging |
| **Information Disclosure** | Unauthorized snooping on train timetables, sensitive freight movements (coal/POL rakes) | Rate-limiting, origin-whitelisted CORS headers, sanitized exception traces, restricted API visibility |
| **Denial of Service (DoS)** | Rapid burst requests flood scheduler API, blocking urgent corridor requisitions | Token-Bucket sliding window rate limiter (60 req/min per IP), 1MB payload caps, indexed queries |
| **Elevation of Privilege** | Normal client bypasses safety interlocks to approve unverified power blocks | Backend enforcement in `safety_rules.py` executes server-side; client UI cannot override safety matrix |

---

## 3. Defense-in-Depth Mechanisms

### 3.1 API Key Authentication & Rate Limiting
- All mutating endpoints (`/api/v1/jobs`, `/api/v1/optimizer/run`, `/api/v1/simulate/delay`, `/api/v1/pdm/generate-work-order`) and sensitive query endpoints strictly require an authorized API Key.
- Token-bucket sliding window rate limiting restricts traffic to 60 requests per minute per IP, rejecting floods with HTTP 429.

### 3.2 HTTP Security Headers
Every HTTP response emitted by the platform injects industry-standard defensive headers:
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
X-XSS-Protection: 1; mode=block
```

### 3.3 SQL Injection Resistance
Zero dynamic SQL string concatenation is permitted. All queries in `app.py`, `ai_scheduler.py`, and `api.py` use parameterized placeholders (`?`), neutralizing SQL injection attempts.

### 3.4 Cross-Site Scripting (XSS) Prevention
Any dynamic values rendered within Streamlit HTML components pass through Python's `html.escape()`.

---

## 4. Reporting a Vulnerability
To report a security vulnerability or exploit:
1. Please **do NOT** open a public issue.
2. Send detailed disclosure and proof of concept to `security-team@indianrailways.gov.in`.
3. The security team will acknowledge receipt within 24 hours and issue a CVE remediation within 72 hours.
