# Implementation Plan: Zabbix Template + Python Script for OpenVPN AS Monitoring

Branch: none (fast mode)
Created: 2026-02-25
Refined: 2026-02-25

## Settings
- Testing: yes
- Logging: verbose (to log file, NEVER stdout/stderr)
- Docs: yes (README.md)
- Zabbix: 7.0 compatible
- Python: 3.6+ stdlib only

## Architecture Decision

**Master item + Dependent items pattern.** Instead of spawning 8 separate processes per polling cycle, the template uses a single External Check master item that returns all metrics as JSON. Zabbix dependent items extract individual values via JSONPath preprocessing. This reduces load from 8 fork+exec+connect cycles to 1.

## Commit Plan
- **Commit 1** (after tasks #9, #10, #11): `feat: add OpenVPN AS XMLRPC client and Zabbix check script`
- **Commit 2** (after tasks #12, #13, #14): `feat: add Zabbix 7.0 template, tests, and documentation`

## Tasks

### Phase 1: Core Python Implementation

- [x] Task #9: Create OpenVPN AS XMLRPC client module (`ovpnas_client.py`)
- [x] Task #10: Create Zabbix external check script (`openvpn_as_check.py`) (depends on #9)
- [x] Task #11: Create `.gitignore`, `requirements.txt`, `requirements-test.txt`
<!-- Commit checkpoint: tasks #9, #10, #11 -->

### Phase 2: Zabbix Template, Tests & Docs

- [x] Task #12: Create Zabbix 7.0 template YAML with master + dependent items (depends on #10)
- [x] Task #13: Write unit tests (depends on #9, #10)
- [x] Task #14: Write README.md (depends on #9, #10, #12)
<!-- Commit checkpoint: tasks #12, #13, #14 -->

### Phase 3: Zabbix Agent Companion Template

- [x] Task #15: Create Zabbix agent template for process, service, and log monitoring
- [x] Task #16: Update README.md with agent template section (depends on #15)
<!-- Commit checkpoint: tasks #15, #16 -->

---

## Task Details

### Task #9: Create OpenVPN AS XMLRPC client module

**File:** `ovpnas_client.py`

Create Python 3 module with class `OpenVPNASClient` connecting to OpenVPN AS XMLRPC API at `https://<host>:<port>/RPC2`.

**Constructor:**
`__init__(host, username, password, port=943, verify_ssl=True, timeout=10)`
- Build XMLRPC URL with credentials
- Create `xmlrpc.client.ServerProxy` with custom SSL context
- Disable SSL verification when `verify_ssl=False` (custom `SafeTransport` subclass)

**Methods (all with explicit timeout):**
- `get_active_sessions()` → `int`
- `get_active_users()` → `list[dict]` — username, real_address, bytes_in, bytes_out, connected_since
- `get_server_info()` → `dict` — version, uptime, status
- `get_bandwidth_stats()` → `dict` — bytes_in, bytes_out
- `ping()` → `bool` — XMLRPC connectivity check
- `check_web_portal(timeout=10)` → `dict` — HTTPS GET to `https://{host}:{port}/`, returns `{"status": 1, "response_ms": 142.5, "status_code": 200}` or error dict
- `test_user_auth(test_username, test_password)` → `bool` — create secondary `ServerProxy` with test creds, attempt simple API call. True=auth works, False=rejected
- `collect_all(auth_test_user=None, auth_test_password=None)` → `dict` — calls ALL methods, returns flat dict with all metrics. Catches per-metric errors individually.

**Error handling:**
- `ConnectionError` on network failures
- `PermissionError` on auth failures (Fault 401/403)
- `RuntimeError` for other XMLRPC faults
- Explicit `timeout` on all socket/HTTP operations

LOGGING: `logging.getLogger(__name__)`, DEBUG on calls, ERROR on failures, WARNING on SSL disabled.

---

### Task #10: Create Zabbix external check script

**File:** `openvpn_as_check.py`

Master data collector for Zabbix External Check. Returns ALL metrics as single JSON blob.

**CLI (positional args for Zabbix compatibility):**
```
openvpn_as_check.py HOST PORT USERNAME PASSWORD [AUTH_TEST_USER] [AUTH_TEST_PASSWORD] [VERIFY_SSL]
```

Maps to Zabbix item key:
`openvpn_as_check.py["{$OVPN_HOST}","{$OVPN_PORT}","{$OVPN_USER}","{$OVPN_PASSWORD}","{$OVPN_AUTH_TEST_USER}","{$OVPN_AUTH_TEST_PASSWORD}","{$OVPN_VERIFY_SSL}"]`

**Output (JSON to stdout):**
```json
{
  "active_sessions": 42,
  "bytes_in": 1234567890,
  "bytes_out": 9876543210,
  "server_version": "2.13.1",
  "xmlrpc_ping": 1,
  "web_portal_status": 1,
  "web_portal_response_ms": 142.5,
  "ldap_auth_test": 1
}
```

On fatal error: `ZBX_NOTSUPPORTED: <message>`, exit 1.
On partial metric failure: set that metric to `null`, don't fail entire collection.

**CRITICAL:** Log to file only (`/tmp/openvpn_as_check.log`) with `RotatingFileHandler` (1MB, 3 backups). NEVER write to stdout (corrupts Zabbix item value) or stderr (also captured by Zabbix 7.0). Log level via `LOG_LEVEL` env var (default: WARNING).

Shebang: `#!/usr/bin/env python3`

---

### Task #11: Create .gitignore, requirements.txt, requirements-test.txt

**Files:** `.gitignore`, `requirements.txt`, `requirements-test.txt`

`.gitignore`: `__pycache__/`, `*.pyc`, `*.pyo`, `.env`, `*.log`, `.pytest_cache/`, `*.egg-info/`, `.venv/`

`requirements.txt`: Comment noting stdlib-only, no external deps.

`requirements-test.txt`: `pytest>=7.0`, `pytest-mock>=3.0`

---

### Task #12: Create Zabbix 7.0 template YAML

**File:** `template/zbx_template_openvpn_as.yaml`

Zabbix 7.0 YAML template with `zabbix_export.version: '7.0'`.

**Template name:** `OpenVPN Access Server by External Check`
**Group:** `Templates/VPN`

**Macros (11 total):**
`{$OVPN_HOST}` (localhost), `{$OVPN_USER}` (openvpn), `{$OVPN_PASSWORD}` (SECRET_TEXT), `{$OVPN_PORT}` (943), `{$OVPN_VERIFY_SSL}` (0), `{$OVPN_TIMEOUT}` (10), `{$OVPN_AUTH_TEST_USER}` (empty), `{$OVPN_AUTH_TEST_PASSWORD}` (SECRET_TEXT), `{$OVPN_SESSION_WARN}` (100), `{$OVPN_SESSION_HIGH}` (200), `{$OVPN_WEB_RESPONSE_WARN}` (2000)

**1 Master Item (EXTERNAL):** Collects all metrics as JSON, delay: 1m, value_type: TEXT

**8 Dependent Items (DEPENDENT):** Each uses JSONPATH preprocessing to extract one metric from master JSON. No additional process spawns.

**7 Triggers:** XMLRPC unreachable, web portal unreachable, web portal slow, LDAP auth failing, high sessions, critical sessions, no data collection.

**3 Graphs:** VPN Sessions, Network Traffic, Web Portal Response Time.

---

### Task #13: Write unit tests

**Files:** `tests/__init__.py`, `tests/test_ovpnas_client.py`, `tests/test_openvpn_as_check.py`

pytest with `unittest.mock`. 14 test cases for client, 5 for check script. Key tests:
- All client methods: success + error paths
- `collect_all` partial failure resilience
- CLI JSON output validity
- Password never appears in logs
- Nothing written to stderr

---

### Task #14: Write README.md

**File:** `README.md`

Sections: Overview, Features, Requirements, Installation, Configuration (macro table), LDAP Auth Test Setup, Metrics Reference, Triggers Reference, Manual Testing, Troubleshooting, Architecture (master+dependent pattern), License (MIT).

---

### Task #15: Create Zabbix agent template

**File:** `template/zbx_template_openvpn_as_agent.yaml`

Companion template `OpenVPN Access Server by Zabbix agent` in group `Templates/VPN`. Link to same host as the External Check template for full coverage.

**Macros:** `{$OVPN_SERVICE_NAME}` (openvpnas), `{$OVPN_LOG_PATH}` (/var/log/openvpnas/errors.log), `{$OVPN_LOG_REGEXP}` (ERROR|CRITICAL)

**Items:**
- `proc.num[openvpnas]` — ZABBIX_PASSIVE, UNSIGNED, 1m
- `systemd.unit.info[{$OVPN_SERVICE_NAME},ActiveState]` — ZABBIX_PASSIVE, CHAR, 1m
- `log[{$OVPN_LOG_PATH},{$OVPN_LOG_REGEXP},,100,skip]` — ZABBIX_ACTIVE, LOG, delay 0

**Triggers (inside each item):**
- Process not running (proc.num=0 for #3) → DISASTER
- Service not active (ActiveState≠"active") → HIGH
- Error in log → WARNING, recovery_mode: NONE

---

### Task #16: Update README.md with agent template section

**File:** `README.md`

Add "Agent Template" section after "Architecture". Include: overview of hybrid approach, installation (ServerActive in agent conf), macros table, triggers table. Update Features list to mention process/service/log monitoring.
