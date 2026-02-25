# Zabbix OpenVPN Access Server Monitoring

Zabbix monitoring template for OpenVPN Access Server. Collects VPN sessions, bandwidth, web portal health, and LDAP authentication status via the XMLRPC API.

Uses an efficient **master item + dependent items** architecture — a single script invocation per polling cycle collects all metrics as JSON, and Zabbix extracts individual values via JSONPath preprocessing.

## Features

**External Check template** (`zbx_template_openvpn_as.yaml`):
- Active VPN session count
- Network traffic (bytes in/out with rate calculation)
- Server version tracking
- XMLRPC API availability check
- Web portal reachability and response time (client-facing port 443)
- LDAP authentication health test (optional)
- 7 pre-configured triggers with customizable thresholds
- 3 built-in graphs

**Agent template** (`zbx_template_openvpn_as_agent.yaml`):
- OpenVPN AS process alive check
- systemd service state monitoring
- Error log monitoring with configurable regexp

## Requirements

- **Python** 3.6+ (stdlib only — no external dependencies)
- **Zabbix Server/Proxy** 7.0+
- **OpenVPN Access Server** with XMLRPC API enabled (port 943)
- **Zabbix Agent** 6.0+ on the OpenVPN AS server *(agent template only)*

## Installation

### 1. Copy scripts to Zabbix ExternalScripts directory

```bash
# Find your ExternalScripts path (check zabbix_server.conf or zabbix_proxy.conf)
grep ExternalScripts /etc/zabbix/zabbix_server.conf

# Copy scripts (default path shown)
cp ovpnas_client.py /usr/lib/zabbix/externalscripts/
cp openvpn_as_check.py /usr/lib/zabbix/externalscripts/

# Set permissions
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/ovpnas_client.py
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/openvpn_as_check.py
chmod 755 /usr/lib/zabbix/externalscripts/openvpn_as_check.py
chmod 644 /usr/lib/zabbix/externalscripts/ovpnas_client.py
```

### 2. Import template into Zabbix

1. Go to **Data collection** > **Templates**
2. Click **Import**
3. Select `template/zbx_template_openvpn_as.yaml`
4. Click **Import**

### 3. Link template to a host

1. Go to **Data collection** > **Hosts**
2. Select or create a host for your OpenVPN AS server
3. Go to **Templates** tab and link `OpenVPN Access Server by External Check`
4. Configure the required macros (see below)

## Configuration

Set these macros on the host after linking the template:

| Macro | Default | Required | Description |
|-------|---------|----------|-------------|
| `{$OVPN_HOST}` | `localhost` | Yes | OpenVPN AS hostname or IP |
| `{$OVPN_PORT}` | `943` | No | XMLRPC and web portal port |
| `{$OVPN_USER}` | `openvpn` | Yes | API username |
| `{$OVPN_PASSWORD}` | *(secret)* | Yes | API password |
| `{$OVPN_VERIFY_SSL}` | `0` | No | SSL certificate verification (1=verify, 0=skip) |
| `{$OVPN_TIMEOUT}` | `10` | No | Script timeout (seconds) |
| `{$OVPN_AUTH_TEST_USER}` | *(empty)* | No | LDAP auth test username |
| `{$OVPN_AUTH_TEST_PASSWORD}` | *(secret)* | No | LDAP auth test password |
| `{$OVPN_WEB_PORT}` | `443` | No | Web portal port (client-facing, separate from XMLRPC port 943) |
| `{$OVPN_SESSION_WARN}` | `100` | No | Session count warning threshold |
| `{$OVPN_SESSION_HIGH}` | `200` | No | Session count high threshold |
| `{$OVPN_WEB_RESPONSE_WARN}` | `2000` | No | Web response time warning (ms) |

## LDAP Auth Test Setup

To monitor LDAP authentication health, create a dedicated test account on your OpenVPN AS:

1. Create a read-only user in OpenVPN AS (e.g., `zabbix-monitor`)
2. Ensure this user authenticates via LDAP (same auth pipeline as regular users)
3. Set `{$OVPN_AUTH_TEST_USER}` and `{$OVPN_AUTH_TEST_PASSWORD}` on the Zabbix host

The script will periodically authenticate with these credentials. If LDAP is down or misconfigured, the `ldap_auth_test` metric returns `0` and triggers a High severity alert.

When `{$OVPN_AUTH_TEST_USER}` is empty, the LDAP test is skipped.

## Metrics Reference

| Metric | JSONPath | Type | Description |
|--------|----------|------|-------------|
| Active sessions | `$.active_sessions` | Integer | Connected VPN clients |
| Bytes in | `$.bytes_in` | Integer (B/s) | Inbound traffic rate |
| Bytes out | `$.bytes_out` | Integer (B/s) | Outbound traffic rate |
| Server version | `$.server_version` | String | OpenVPN AS version |
| XMLRPC ping | `$.xmlrpc_ping` | Integer (0/1) | API reachability |
| Web portal status | `$.web_portal_status` | Integer (0/1) | Portal reachability |
| Web portal response | `$.web_portal_response_ms` | Float (ms) | Portal response time |
| LDAP auth test | `$.ldap_auth_test` | Integer (0/1) | Auth pipeline health |

## Triggers Reference

| Trigger | Severity | Condition |
|---------|----------|-----------|
| XMLRPC API is unreachable | High | `xmlrpc_ping = 0` for last 3 checks |
| Web portal is unreachable | High | `web_portal_status = 0` for last 3 checks |
| Web portal slow response | Warning | Response time > `{$OVPN_WEB_RESPONSE_WARN}` ms for 5 min |
| LDAP authentication is failing | High | `ldap_auth_test = 0` for last 3 checks |
| High session count | Warning | `active_sessions` > `{$OVPN_SESSION_WARN}` |
| Critical session count | High | `active_sessions` > `{$OVPN_SESSION_HIGH}` |
| No data collection | Average | No data received for 5 minutes |

## Manual Testing

Test the script directly from command line:

```bash
# Basic test (no LDAP auth check, web portal on port 443)
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py 192.168.1.1 943 admin password

# With LDAP auth test
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py 192.168.1.1 943 admin password testuser testpass 0

# With SSL verification and custom web port
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py vpn.example.com 943 admin password "" "" 1 443

# With verbose logging
LOG_LEVEL=DEBUG python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py 192.168.1.1 943 admin password
```

Expected output (JSON):
```json
{
  "xmlrpc_ping": 1,
  "active_sessions": 42,
  "bytes_in": 1234567890,
  "bytes_out": 9876543210,
  "server_version": "2.13.1",
  "web_portal_status": 1,
  "web_portal_response_ms": 142.5,
  "ldap_auth_test": 1
}
```

## Troubleshooting

**Script returns `ZBX_NOTSUPPORTED`**
- Check that the host, port, and credentials are correct
- Verify XMLRPC API is accessible: `curl -k https://HOST:943/RPC2`

**No data in Zabbix**
- Verify script is in the ExternalScripts directory: `grep ExternalScripts /etc/zabbix/zabbix_server.conf`
- Check file permissions: `ls -la /usr/lib/zabbix/externalscripts/openvpn_as_check.py`
- Check Zabbix server timeout: `grep ^Timeout /etc/zabbix/zabbix_server.conf` (must be > script runtime)

**Debug logging**
- Log file: `/tmp/openvpn_as_check.log`
- Set `LOG_LEVEL=DEBUG` environment variable for verbose output
- Check log rotation: max 1 MB, 3 backup files

**SSL errors**
- Set `{$OVPN_VERIFY_SSL}` to `0` to skip certificate verification (common for self-signed certs)
- If verification is needed, ensure the CA certificate is in the system trust store

## Architecture

```
Zabbix Server/Proxy
  │
  ├── Master Item (EXTERNAL, 1m interval)
  │     openvpn_as_check.py → stdout: { JSON with all metrics }
  │
  └── Dependent Items (no process spawn)
        ├── ovpn.active_sessions    ← $.active_sessions
        ├── ovpn.bytes_in           ← $.bytes_in (+ CHANGE_PER_SECOND)
        ├── ovpn.bytes_out          ← $.bytes_out (+ CHANGE_PER_SECOND)
        ├── ovpn.server_version     ← $.server_version
        ├── ovpn.xmlrpc_ping        ← $.xmlrpc_ping
        ├── ovpn.web_portal_status  ← $.web_portal_status
        ├── ovpn.web_portal_response_ms ← $.web_portal_response_ms
        └── ovpn.ldap_auth_test     ← $.ldap_auth_test
```

One script invocation per polling cycle. All dependent items are processed in-memory by Zabbix preprocessing — no additional external processes.

## Agent Template

`template/zbx_template_openvpn_as_agent.yaml` is a companion template that monitors OpenVPN AS from inside the server using a Zabbix agent. Link both templates to the same host for full coverage.

| Template | Perspective | What it checks |
|----------|-------------|----------------|
| External Check | Outside | XMLRPC reachability, web portal, LDAP auth, sessions, bandwidth |
| Zabbix agent | Inside | Process alive, systemd service state, error log |

The two templates cover different failure modes. The XMLRPC API can appear healthy while the underlying process has crashed, or the process can be running while a firewall blocks external access.

### Agent Template Installation

1. Install Zabbix agent on the OpenVPN AS server
2. Import `template/zbx_template_openvpn_as_agent.yaml` into Zabbix
3. Link `OpenVPN Access Server by Zabbix agent` to the same host as the External Check template

The `log` item requires **active agent mode** (agent connects to Zabbix server). Add to `zabbix_agentd.conf`:

```ini
ServerActive=<zabbix-server-ip>
Hostname=<host-name-matching-zabbix>
```

No `UserParameter` configuration is needed — all items use built-in agent keys.

### Agent Template Macros

| Macro | Default | Description |
|-------|---------|-------------|
| `{$OVPN_SERVICE_NAME}` | `openvpnas` | systemd service name |
| `{$OVPN_LOG_PATH}` | `/var/log/openvpnas/errors.log` | Path to error log file |
| `{$OVPN_LOG_REGEXP}` | `ERROR\|CRITICAL` | Regexp filter for log trigger |

### Agent Template Triggers

| Trigger | Severity | Condition |
|---------|----------|-----------|
| Process is not running | Disaster | `proc.num = 0` for last 3 checks |
| Service is not active | High | `ActiveState ≠ "active"` |
| Error found in log | Warning | Matching line found in error log |

The log trigger has **manual close** enabled — acknowledge it in Zabbix after reviewing the log entry.

## License

MIT
