[← Metrics](metrics.md) · [Back to README](../README.md) · [Agent Template →](agent-template.md)

# Architecture

## Master Item + Dependent Items Pattern

A single external check script runs once per polling cycle and returns all metrics as JSON. Zabbix dependent items extract individual values via JSONPath preprocessing — no additional processes spawned.

```
Zabbix Server/Proxy
  │
  ├── Master Item (EXTERNAL, 1m interval)
  │     openvpn_as_check.py → stdout: { JSON with all metrics }
  │
  └── Dependent Items (no process spawn)
        ├── ovpn.active_sessions        ← $.active_sessions
        ├── ovpn.bytes_in               ← $.bytes_in  (+ CHANGE_PER_SECOND)
        ├── ovpn.bytes_out              ← $.bytes_out (+ CHANGE_PER_SECOND)
        ├── ovpn.server_version         ← $.server_version
        ├── ovpn.xmlrpc_ping            ← $.xmlrpc_ping
        ├── ovpn.web_portal_status      ← $.web_portal_status
        ├── ovpn.web_portal_response_ms ← $.web_portal_response_ms
        └── ovpn.ldap_auth_test         ← $.ldap_auth_test
```

**Why this pattern?** The alternative — 8 separate External Check items — would spawn 8 processes per polling cycle, each opening a new XMLRPC connection. One script invocation is enough.

## Script Architecture

```
openvpn_as_check.py          ← Zabbix entry point (positional args, JSON stdout)
        │
        └── ovpnas_client.py  ← OpenVPN AS XMLRPC client library
                │
                ├── xmlrpc.client.ServerProxy  ← XMLRPC API at https://host:943/RPC2
                └── urllib.request.urlopen     ← Web portal check at https://host:443/
```

`openvpn_as_check.py` is the thin CLI wrapper — it parses args, calls `OpenVPNASClient.collect_all()`, and prints JSON. All logic lives in `ovpnas_client.py`.

## Network Requirements

| Check | Protocol | Port | Direction |
|-------|----------|------|-----------|
| XMLRPC metrics | HTTPS | 943 | Zabbix Server/Proxy → OpenVPN AS |
| Web portal | HTTPS | 443 | Zabbix Server/Proxy → OpenVPN AS |
| Agent passive checks | TCP | 10050 | Zabbix Server/Proxy → OpenVPN AS |
| Agent active checks (log) | TCP | 10051 | OpenVPN AS → Zabbix Server/Proxy |

## Zabbix Proxy Deployment

If the Zabbix Server is in a different network from OpenVPN AS (port 943 is not reachable from the server), use a **Zabbix Proxy** in the same network:

```
Zabbix Server (external network)
        │
        │  (no direct access to port 943)
        │
Zabbix Proxy (same network as OpenVPN AS)
        │
        ├── port 943 → OpenVPN AS XMLRPC
        └── port 443 → OpenVPN AS web portal
```

Deploy the scripts to the proxy's `ExternalScripts` directory and assign the host to the proxy in Zabbix. No template changes needed.

## Logging

The script logs to `/tmp/openvpn_as_check.log` using a `RotatingFileHandler` (1 MB max, 3 backups). It never writes to stdout or stderr — both are captured by Zabbix 7.0 as the item value.

Log level is controlled by the `LOG_LEVEL` environment variable (default: `WARNING`).

## See Also

- [Installation](installation.md) — proxy deployment steps
- [Metrics](metrics.md) — full metrics and triggers reference
- [Troubleshooting](troubleshooting.md) — debug logging
