# Zabbix OpenVPN Access Server Monitoring

> Zabbix 7.0 template for monitoring OpenVPN Access Server.

Two monitoring approaches in one template set:
- **Web login test** — Zabbix web scenario that loads the portal and authenticates a test user via `POST /__auth__`. No scripts required. Detects disabled accounts, auth backend failures, and portal outages.
- **XMLRPC metrics** — external check script collecting sessions, bandwidth, and server info via the admin API on port 943. Optional — requires port 943 reachable from Zabbix Server/Proxy.

## Quick Start

### Web login monitoring only (no scripts needed)

1. Import `template/zbx_template_openvpn_as.yaml`
2. Link template to the host
3. Set macros: `{$OVPN_AUTH_TEST_USER}`, `{$OVPN_AUTH_TEST_PASSWORD}`, `{$OVPN_WEB_PORT}`

The web scenario runs every 5 minutes and fires within one interval if login fails.

### Full monitoring (web login + XMLRPC metrics)

```bash
# Copy scripts to Zabbix ExternalScripts directory
cp ovpnas_client.py openvpn_as_check.py /usr/lib/zabbix/externalscripts/
chmod 755 /usr/lib/zabbix/externalscripts/openvpn_as_check.py

# Import template in Zabbix: Data collection → Templates → Import
# File: template/zbx_template_openvpn_as.yaml
```

Set all macros including `{$OVPN_HOST}`, `{$OVPN_PASSWORD}`. See [Configuration](docs/configuration.md).

> The master item `OpenVPN AS: Collect all metrics` is **disabled by default**. The web login scenario starts working immediately after linking. Enable the master item only after deploying the scripts and confirming port 943 is reachable.

## Features

**External Check template** — two independent monitoring layers:

*Web login scenario (no scripts — runs on Zabbix Server):*
- Loads portal, follows redirects, verifies `OpenVPN CWS` page content
- Authenticates test user via `POST /__auth__` — detects disabled/locked accounts within 5 min
- Response time tracking per step
- 4 triggers with dependency chain · detection time ≤ 5 min

*XMLRPC metrics (requires scripts + port 943):*
- Active VPN session count with configurable thresholds
- Network traffic (bytes in/out, rate per second)
- XMLRPC API and web portal availability
- LDAP authentication health test (optional)
- 7 triggers · 3 graphs
- ⚠️ Not tested against a live server — based on public XMLRPC API docs

**Agent template** — monitors from inside the server:
- Process alive check (`proc.num`)
- systemd service state
- Error log monitoring

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](docs/installation.md) | Deploy scripts, import templates, proxy setup |
| [Configuration](docs/configuration.md) | Macros, port separation, LDAP auth test setup |
| [Metrics & Triggers](docs/metrics.md) | All metrics, item keys, trigger conditions |
| [Architecture](docs/architecture.md) | Master item pattern, network requirements |
| [Agent Template](docs/agent-template.md) | Agent installation and active mode setup |
| [Troubleshooting](docs/troubleshooting.md) | Common issues, debug logging, manual testing |

## Requirements

- Zabbix Server or Proxy 7.0+
- OpenVPN Access Server with web portal on port 443
- Python 3.6+ stdlib — *only for XMLRPC metrics collection*
- Port 943 reachable from Zabbix Server/Proxy — *only for XMLRPC metrics collection*

## Author

**Konstantin Tyutyunnik** — [itforprof.com](https://itforprof.com)

## License

MIT
