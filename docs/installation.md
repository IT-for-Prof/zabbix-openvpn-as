[Back to README](../README.md) · [Configuration →](configuration.md)

# Installation

## Requirements

| Component | Required for |
|-----------|-------------|
| Zabbix Server or Proxy 7.0+ | Everything |
| OpenVPN AS web portal on port 443 | Web login scenario |
| Python 3.6+ (stdlib only) | XMLRPC metrics only |
| Port 943 reachable from Zabbix Server/Proxy | XMLRPC metrics only |
| Zabbix Agent 6.0+ on the OpenVPN AS server | Agent template only |

> **Web login monitoring requires no scripts.** If XMLRPC (port 943) is not available, skip step 1 and disable the master item `OpenVPN AS: Collect all metrics` on the host after linking the template.

> **Note:** The XMLRPC external check script (`openvpn_as_check.py`) has not been tested against a live OpenVPN AS instance. The web login scenario has been tested and verified. If you use the XMLRPC path, please report any issues.

## 1. Copy scripts to ExternalScripts directory *(XMLRPC metrics only)*

The external check script must be on the machine that runs the check — Zabbix Server or Zabbix Proxy.

> **Network note:** If your Zabbix Server is in a different network from OpenVPN AS (port 943 not reachable), place the scripts on a **Zabbix Proxy** in the same network as OpenVPN AS instead.

### Docker Compose setup

If Zabbix runs in Docker Compose with a bind-mounted ExternalScripts directory, copy the scripts to the host directory that is mounted into the container.

Example compose volume:
```yaml
volumes:
  - /opt/zabbix/externalscripts:/usr/lib/zabbix/externalscripts:ro
```

Copy scripts to the host-side directory:
```bash
cp ovpnas_client.py openvpn_as_check.py /opt/zabbix/externalscripts/
chmod 755 /opt/zabbix/externalscripts/openvpn_as_check.py
chmod 644 /opt/zabbix/externalscripts/ovpnas_client.py
```

The bind mount makes the files available inside the container immediately — no container restart needed.

Set the script timeout via Docker environment variable (must be greater than script runtime, 30 seconds is safe):
```yaml
environment:
  ZBX_TIMEOUT: 30
```

### pfSense (FreeBSD) Zabbix Proxy

pfSense uses FreeBSD. The ExternalScripts directory and Python path differ from Linux.

```sh
# Create the ExternalScripts directory
mkdir -p /usr/local/share/zabbix7/externalscripts

# Copy scripts (from your workstation via scp, or paste inline)
cp ovpnas_client.py openvpn_as_check.py /usr/local/share/zabbix7/externalscripts/

# Set permissions
chmod 755 /usr/local/share/zabbix7/externalscripts/openvpn_as_check.py
chmod 644 /usr/local/share/zabbix7/externalscripts/ovpnas_client.py
```

pfSense ships Python as a versioned binary (`python3.11`, not `python3`). Fix the shebang:

```sh
# Check which Python is available
which python3.11

# Rewrite the shebang in the check script (FreeBSD sed requires '' after -i)
sed -i '' '1s|^#!/usr/bin/env python3$|#!/usr/local/bin/python3.11|' \
  /usr/local/share/zabbix7/externalscripts/openvpn_as_check.py
```

Add to `/usr/local/etc/zabbix7/zabbix_proxy.conf`:
```ini
ExternalScripts=/usr/local/share/zabbix7/externalscripts
Timeout=30
```

Restart the proxy:
```sh
/usr/local/etc/rc.d/zabbix_proxy.sh restart
```

Test manually:
```sh
/usr/local/share/zabbix7/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password
```

### Bare-metal / package install

Find the ExternalScripts path from the config file:
```bash
grep ExternalScripts /etc/zabbix/zabbix_server.conf
# or for proxy:
grep ExternalScripts /etc/zabbix/zabbix_proxy.conf
```

Copy and set permissions (default path shown):
```bash
cp ovpnas_client.py openvpn_as_check.py /usr/lib/zabbix/externalscripts/
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/ovpnas_client.py
chown zabbix:zabbix /usr/lib/zabbix/externalscripts/openvpn_as_check.py
chmod 755 /usr/lib/zabbix/externalscripts/openvpn_as_check.py
chmod 644 /usr/lib/zabbix/externalscripts/ovpnas_client.py
```

Set the timeout in `zabbix_server.conf` (or `zabbix_proxy.conf`):
```ini
Timeout=30
```

## 2. Import templates into Zabbix

### External Check template

1. Go to **Data collection** → **Templates**
2. Click **Import**
3. Select `template/zbx_template_openvpn_as.yaml`
4. Click **Import**

### Agent template *(optional)*

Repeat the import steps for `template/zbx_template_openvpn_as_agent.yaml`.

## 3. Link template to a host

1. Go to **Data collection** → **Hosts**
2. Select or create a host for your OpenVPN AS server
3. Go to the **Templates** tab and link `OpenVPN Access Server by External Check`
4. Set the required macros — see [Configuration](configuration.md)

### Linking both templates

For full coverage, link both templates to the same host:

| Template | Monitors | Requires |
|----------|----------|----------|
| `OpenVPN Access Server by External Check` | Web login test (always), XMLRPC metrics (optional) | Port 443; scripts + port 943 for XMLRPC |
| `OpenVPN Access Server by Zabbix agent` | Process, service state, error log | Zabbix agent on OpenVPN AS server |

> The master item `OpenVPN AS: Collect all metrics` is **disabled by default** in the template. The web login scenario runs immediately after linking. To enable XMLRPC metrics, deploy the scripts (step 1) and enable the master item on the host: **Hosts → Items → OpenVPN AS: Collect all metrics → Enabled**.

## 4. Verify script works

Run the script manually from the machine where the scripts are deployed:

```bash
# Docker Compose (from WSL host or inside container)
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password

# Bare-metal Linux
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password

# pfSense (FreeBSD) — script is executable, runs via shebang
/usr/local/share/zabbix7/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password
```

Expected output: JSON blob with all metrics. See [Troubleshooting](troubleshooting.md) if you get `ZBX_NOTSUPPORTED`.

## See Also

- [Configuration](configuration.md) — macro reference and LDAP auth test setup
- [Architecture](architecture.md) — how the master item + proxy setup works
- [Troubleshooting](troubleshooting.md) — script errors and debug logging
