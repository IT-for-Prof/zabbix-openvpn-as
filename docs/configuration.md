[← Installation](installation.md) · [Back to README](../README.md) · [Metrics →](metrics.md)

# Configuration

## External Check Template Macros

Set these macros on the **host** after linking the template. Macros set on the host override template defaults.

| Macro | Default | Required | Description |
|-------|---------|----------|-------------|
| `{$OVPN_HOST}` | `localhost` | Yes | OpenVPN AS hostname or IP address |
| `{$OVPN_PORT}` | `943` | No | XMLRPC admin port |
| `{$OVPN_USER}` | `openvpn` | Yes | API admin username |
| `{$OVPN_PASSWORD}` | *(secret)* | Yes | API admin password |
| `{$OVPN_WEB_PORT}` | `443` | No | Web portal port (client-facing) |
| `{$OVPN_VERIFY_SSL}` | `0` | No | SSL certificate verification (1=verify, 0=skip) |
| `{$OVPN_TIMEOUT}` | `10` | No | Script timeout in seconds |
| `{$OVPN_AUTH_TEST_USER}` | *(empty)* | No | LDAP auth test username — leave empty to skip |
| `{$OVPN_AUTH_TEST_PASSWORD}` | *(secret)* | No | LDAP auth test password |
| `{$OVPN_SESSION_WARN}` | `100` | No | Session count warning threshold |
| `{$OVPN_SESSION_HIGH}` | `200` | No | Session count high/critical threshold |
| `{$OVPN_WEB_RESPONSE_WARN}` | `2000` | No | Web portal response time warning (ms) |

> `{$OVPN_PASSWORD}` and `{$OVPN_AUTH_TEST_PASSWORD}` are `SECRET_TEXT` type — their values are masked in the Zabbix UI.

## Port Separation

Two ports are used independently:

| Port | Macro | Purpose |
|------|-------|---------|
| `943` | `{$OVPN_PORT}` | XMLRPC admin API — used for all metrics collection |
| `443` | `{$OVPN_WEB_PORT}` | Client-facing web portal — reachability and response time check |

This matters when the Zabbix Server/Proxy is outside the network: port 943 is typically firewalled, port 443 is public. If only 443 is reachable, XMLRPC metrics won't work — use a [Zabbix Proxy](installation.md) in the same network instead.

## Web Login Test Setup

The web login test (`{$OVPN_AUTH_TEST_USER}` / `{$OVPN_AUTH_TEST_PASSWORD}`) drives the Zabbix web scenario. It runs every 5 minutes, loads the portal, and authenticates via `POST /__auth__`.

**Setup steps:**

1. Create a dedicated monitoring user in OpenVPN AS
2. Ensure the account has a **non-expiring password**
3. Check that the account is **exempt from lockout policy** or has a high lockout threshold — the scenario authenticates every 5 minutes
4. Set `{$OVPN_AUTH_TEST_USER}` and `{$OVPN_AUTH_TEST_PASSWORD}` on the Zabbix host (use `SECRET_TEXT` type for the password)

**What it detects:**
- Portal unreachable (step 1 fails)
- Disabled or locked-out account (step 2 returns HTTP 403)
- Wrong password (step 2 returns HTTP 403)

## Agent Template Macros

| Macro | Default | Description |
|-------|---------|-------------|
| `{$OVPN_SERVICE_NAME}` | `openvpnas` | systemd service unit name |
| `{$OVPN_LOG_PATH}` | `/var/log/openvpnas/errors.log` | Path to error log file |
| `{$OVPN_LOG_REGEXP}` | `ERROR\|CRITICAL` | Regexp filter — lines matching this trigger the alert |

## See Also

- [Installation](installation.md) — how to deploy scripts and import templates
- [Metrics](metrics.md) — full metrics and triggers reference
- [Troubleshooting](troubleshooting.md) — debug logging and common errors
