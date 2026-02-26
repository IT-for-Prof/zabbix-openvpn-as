[← Architecture](architecture.md) · [Back to README](../README.md) · [Troubleshooting →](troubleshooting.md)

# Agent Template

## Overview

`template/zbx_template_openvpn_as_agent.yaml` monitors OpenVPN AS from inside the server using a Zabbix agent. Link it to the same host as the External Check template for full coverage.

| Template | Perspective | What it detects |
|----------|-------------|-----------------|
| External Check | Outside | XMLRPC unreachable, web portal down, LDAP auth broken, high sessions |
| Zabbix agent | Inside | Process crashed, service failed, error log entries |

The two templates cover different failure modes. Example: the OpenVPN AS process can crash while the XMLRPC port stays open briefly — only the agent catches this.

## Installation

1. Install Zabbix agent on the OpenVPN AS server
2. Import `template/zbx_template_openvpn_as_agent.yaml` into Zabbix
3. Link `OpenVPN Access Server by Zabbix agent` to the same host as the External Check template

No `UserParameter` configuration is needed — all items use built-in agent keys.

## Active Agent Mode (required for log monitoring)

The `log` item requires **active agent mode** — the agent connects outbound to the Zabbix Server/Proxy on port 10051.

Add to `/etc/zabbix/zabbix_agentd.conf`:

```ini
ServerActive=<zabbix-server-or-proxy-ip>
Hostname=<host-name-matching-zabbix>
```

Passive checks (`proc.num`, `systemd.unit.info`) work with standard passive configuration and do not require `ServerActive`.

## Macros

| Macro | Default | Description |
|-------|---------|-------------|
| `{$OVPN_SERVICE_NAME}` | `openvpnas` | systemd service unit name |
| `{$OVPN_LOG_PATH}` | `/var/log/openvpnas/errors.log` | Path to error log file |
| `{$OVPN_LOG_REGEXP}` | `ERROR\|CRITICAL` | Regexp filter for log trigger |

## Triggers

| Trigger | Severity | Condition |
|---------|----------|-----------|
| Process is not running | Disaster | `proc.num = 0` for last 3 checks |
| Service is not active | High | `ActiveState ≠ "active"` |
| Error found in log | Warning | Matching line found in error log |

The log trigger has **manual close** enabled — acknowledge it in Zabbix after reviewing the log entry.

## See Also

- [Metrics](metrics.md) — full agent metrics and trigger expressions
- [Configuration](configuration.md) — agent template macro reference
- [Architecture](architecture.md) — network ports required for active agent
