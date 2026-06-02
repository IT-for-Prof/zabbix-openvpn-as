[← Agent Template](agent-template.md) · [Back to README](../README.md)

# Troubleshooting

## Manual Testing

Test the script directly before configuring Zabbix:

```bash
# Basic test — no LDAP auth check
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password

# With LDAP auth test
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password testuser testpass 0

# With SSL verification enabled and custom web port
python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py \
  vpn.example.com 943 admin password "" "" 1 443

# Verbose logging to /tmp/openvpn_as_check.log
LOG_LEVEL=DEBUG python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password
```

Expected output:
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

## Common Issues

### Script returns `ZBX_NOTSUPPORTED`

- Check host, port, and credentials are correct
- Verify XMLRPC API is reachable: `curl -k https://HOST:943/RPC2`
- Check the log file for details: `cat /tmp/openvpn_as_check.log`

### No data in Zabbix (items show "never")

- Verify scripts are in the ExternalScripts directory:
  ```bash
  grep ExternalScripts /etc/zabbix/zabbix_server.conf
  ls -la /usr/lib/zabbix/externalscripts/openvpn_as_check.py
  ```
- Check Zabbix Server timeout — must be greater than script runtime:
  ```bash
  grep ^Timeout /etc/zabbix/zabbix_server.conf
  ```
- If using a proxy, ensure the scripts are on the **proxy**, not the server

### `xmlrpc_ping: 0` but web portal responds

Port 943 is blocked between the Zabbix Server/Proxy and OpenVPN AS. Options:
- Place a Zabbix Proxy in the same network as OpenVPN AS — see [Architecture](architecture.md)
- Open port 943 from the Zabbix Server/Proxy IP

### `web_portal_status: 0` with non-zero response time

The portal is responding but returning a non-2xx/3xx HTTP status. Check what the portal returns:
```bash
curl -vk -o /dev/null -w "%{http_code}" https://vpn.example.com/
```

### `ldap_auth_test: 0`

- Verify the test user account exists in AD/LDAP and the password is correct
- Verify the test user has **no local account** in OpenVPN AS (must authenticate via LDAP only)
- Check LDAP connectivity from the OpenVPN AS server
- Check `{$OVPN_AUTH_TEST_USER}` and `{$OVPN_AUTH_TEST_PASSWORD}` are set on the host

### SSL errors

- Set `{$OVPN_VERIFY_SSL}` to `0` to skip certificate verification (common for self-signed certs)
- If verification is required, ensure the CA certificate is in the system trust store

### Preprocessing errors on Bytes in/out

`cannot calculate delta (speed per second) for value of type "none"` — this happens when `xmlrpc_ping` is 0 and bandwidth metrics return `null`. These errors resolve automatically once XMLRPC connectivity is restored.

## Debug Logging

- **Log file:** `/tmp/openvpn_as_check.log`
- **Enable verbose:** `LOG_LEVEL=DEBUG` environment variable
- **Rotation:** 1 MB max, 3 backup files

```bash
# Watch log in real time while testing
tail -f /tmp/openvpn_as_check.log &
LOG_LEVEL=DEBUG python3 /usr/lib/zabbix/externalscripts/openvpn_as_check.py \
  192.168.1.1 943 admin password
```

## Web Scenario Issues

### Web scenario never runs / items show "never"

- Verify `{$OVPN_WEB_PORT}` macro is set on the host (default: `443`). A missing or non-numeric value causes: `URL rejected: Port number was not a decimal number between 0 and 65535`
- Check the scenario is enabled: **Data collection → Hosts → Web** — status must be green
- Check Zabbix Server can reach `https://{HOST.CONN}:{$OVPN_WEB_PORT}/` from its network

### Step 2 returns HTTP 403 (or 401)

Authentication failed. The auth step does `GET /rest/GetUserlogin` with HTTP Basic auth.
- **403** (`AUTH_FAILED` / `Access denied`) — credentials reached the server but were rejected:
  - Test user account is disabled or locked out in OpenVPN AS
  - Wrong password in `{$OVPN_AUTH_TEST_PASSWORD}`
  - LDAP/AD is unreachable (if the test user authenticates via LDAP)
  - **OTP/MFA (TOTP) is enabled for the test user** — `/rest/GetUserlogin` then returns an auth challenge a Basic-auth step can't answer. Exempt the test account: `sacli --user <USER> --key prop_google_auth --value false UserPropPut && sacli start` (use the exact LDAP username).
- **401** (`Need Credentials`) — no usable credentials reached the server, almost always an **empty `{$OVPN_AUTH_TEST_PASSWORD}` secret macro**. Editing a host's macros and clicking *Set new value* (or changing the macro type) erases a secret value — re-enter it.

Verify manually (replace USERNAME and PASSWORD):
```bash
curl -sk -u "USERNAME:PASSWORD" "https://vpn.example.com/rest/GetUserlogin" \
  -o /dev/null -w "HTTP: %{http_code}\n"
```

Expected: **200** = login OK (returns the user-locked profile). **403** = bad/locked/MFA account. **401** = no credentials sent.

### `web.test.error` shows old error after recovery

This is expected Zabbix behaviour — `web.test.error` is only updated when a failure occurs; it is not cleared on success. The error trigger checks `AND web.test.fail > 0` so it will not fire when the scenario is passing.

### Trigger `Web login test error` fires but `Web login test failed` does not

Should not happen in normal operation — `error` trigger depends on `failed`. If seen, check that the trigger dependency is correctly configured on the host.

## See Also

- [Installation](installation.md) — script deployment and permissions
- [Configuration](configuration.md) — macro reference
- [Architecture](architecture.md) — proxy setup for network-separated environments
