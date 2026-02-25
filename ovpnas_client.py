"""OpenVPN Access Server XMLRPC client module.

Provides OpenVPNASClient class for querying OpenVPN AS metrics
via its XMLRPC API at https://<host>:<port>/RPC2.
"""

import logging
import socket
import ssl
import time
import xmlrpc.client
from urllib.request import urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


class _SSLTransport(xmlrpc.client.SafeTransport):
    """Custom XMLRPC transport with configurable SSL context and timeout."""

    def __init__(self, ssl_context, timeout, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ssl_context = ssl_context
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn

    def send_request(self, connection, handler, request_body, debug):
        return super().send_request(connection, handler, request_body, debug)

    def get_host_info(self, host):
        host, extra_headers, x509 = super().get_host_info(host)
        return host, extra_headers, {"context": self._ssl_context}


class OpenVPNASClient:
    """Client for OpenVPN Access Server XMLRPC API.

    Args:
        host: OpenVPN AS hostname or IP address.
        username: API username.
        password: API password.
        port: XMLRPC admin port (default: 943).
        web_port: Web portal port for client-facing connections (default: 443).
        verify_ssl: Whether to verify SSL certificates (default: True).
        timeout: Timeout in seconds for network operations (default: 10).
    """

    def __init__(self, host, username, password, port=943, web_port=443, verify_ssl=True, timeout=10):
        self._host = host
        self._port = port
        self._web_port = web_port
        self._username = username
        self._password = password
        self._timeout = timeout
        self._verify_ssl = verify_ssl

        ssl_context = ssl.create_default_context()
        if not verify_ssl:
            logger.warning(
                "[OpenVPNASClient.__init__] SSL verification disabled for %s:%s",
                host, port,
            )
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        self._ssl_context = ssl_context

        url = "https://{}:{}@{}:{}/RPC2".format(username, password, host, port)
        transport = _SSLTransport(ssl_context, timeout)
        self._proxy = xmlrpc.client.ServerProxy(url, transport=transport)

        logger.debug(
            "[OpenVPNASClient.__init__] Client created {host: %s, port: %s, web_port: %s}",
            host, port, web_port,
        )

    def _call(self, method_name, *args):
        """Execute an XMLRPC method with error translation."""
        logger.debug(
            "[OpenVPNASClient.%s] Calling %s:%s",
            method_name, self._host, self._port,
        )
        try:
            method = getattr(self._proxy, method_name)
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self._timeout)
            try:
                result = method(*args)
            finally:
                socket.setdefaulttimeout(old_timeout)
            logger.debug(
                "[OpenVPNASClient.%s] Success {type: %s}",
                method_name, type(result).__name__,
            )
            return result
        except xmlrpc.client.Fault as exc:
            if exc.faultCode in (401, 403):
                logger.error(
                    "[OpenVPNASClient.%s] Auth failure {code: %s, reason: %s}",
                    method_name, exc.faultCode, exc.faultString,
                )
                raise PermissionError(
                    "Authentication failed: {} {}".format(exc.faultCode, exc.faultString)
                ) from exc
            logger.error(
                "[OpenVPNASClient.%s] XMLRPC fault {code: %s, reason: %s}",
                method_name, exc.faultCode, exc.faultString,
            )
            raise RuntimeError(
                "XMLRPC fault: {} {}".format(exc.faultCode, exc.faultString)
            ) from exc
        except (socket.error, socket.timeout, ConnectionRefusedError, OSError) as exc:
            logger.error(
                "[OpenVPNASClient.%s] Connection error: %s", method_name, exc,
            )
            raise ConnectionError(
                "Connection failed to {}:{}: {}".format(self._host, self._port, exc)
            ) from exc
        except TimeoutError as exc:
            logger.error(
                "[OpenVPNASClient.%s] Timeout after %ss", method_name, self._timeout,
            )
            raise ConnectionError(
                "Timeout connecting to {}:{}".format(self._host, self._port)
            ) from exc

    def get_active_sessions(self):
        """Return count of currently active VPN sessions.

        Returns:
            int: Number of active sessions.
        """
        result = self._call("GetVPNStatus")
        if isinstance(result, dict):
            users = result.get("user_table", result.get("users", []))
            count = len(users) if isinstance(users, list) else 0
        elif isinstance(result, list):
            count = len(result)
        else:
            count = 0
        logger.debug(
            "[OpenVPNASClient.get_active_sessions] Result {active_sessions: %d}", count,
        )
        return count

    def get_active_users(self):
        """Return list of active user session dicts.

        Returns:
            list[dict]: Each dict contains keys: username, real_address,
                        bytes_in, bytes_out, connected_since.
        """
        result = self._call("GetVPNStatus")
        users = []
        raw_users = []
        if isinstance(result, dict):
            raw_users = result.get("user_table", result.get("users", []))
        elif isinstance(result, list):
            raw_users = result

        for u in raw_users:
            if isinstance(u, dict):
                users.append({
                    "username": u.get("username", u.get("common_name", "")),
                    "real_address": u.get("real_address", u.get("real_addr", "")),
                    "bytes_in": int(u.get("bytes_received", u.get("bytes_in", 0))),
                    "bytes_out": int(u.get("bytes_sent", u.get("bytes_out", 0))),
                    "connected_since": u.get("connected_since", u.get("start_time", "")),
                })
        logger.debug(
            "[OpenVPNASClient.get_active_users] Result {user_count: %d}", len(users),
        )
        return users

    def get_server_info(self):
        """Return server version, uptime, and status.

        Returns:
            dict: Keys: version, uptime, status.
        """
        result = self._call("GetVPNStatus")
        info = {}
        if isinstance(result, dict):
            info = {
                "version": str(result.get("version", result.get("openvpn_version", "unknown"))),
                "uptime": result.get("uptime", result.get("up_since", "")),
                "status": result.get("status", result.get("state", "unknown")),
            }
        else:
            info = {"version": "unknown", "uptime": "", "status": "unknown"}
        logger.debug(
            "[OpenVPNASClient.get_server_info] Result {version: %s}",
            info.get("version", "unknown"),
        )
        return info

    def get_bandwidth_stats(self):
        """Return total bytes in/out.

        Returns:
            dict: Keys: bytes_in, bytes_out.
        """
        result = self._call("GetVPNStatus")
        stats = {"bytes_in": 0, "bytes_out": 0}
        if isinstance(result, dict):
            # Sum from user table if per-user stats available
            users = result.get("user_table", result.get("users", []))
            if isinstance(users, list):
                for u in users:
                    if isinstance(u, dict):
                        stats["bytes_in"] += int(u.get("bytes_received", u.get("bytes_in", 0)))
                        stats["bytes_out"] += int(u.get("bytes_sent", u.get("bytes_out", 0)))
            # Override with global stats if available
            if "global_bytes_in" in result:
                stats["bytes_in"] = int(result["global_bytes_in"])
            if "global_bytes_out" in result:
                stats["bytes_out"] = int(result["global_bytes_out"])
        logger.debug(
            "[OpenVPNASClient.get_bandwidth_stats] Result {bytes_in: %d, bytes_out: %d}",
            stats["bytes_in"], stats["bytes_out"],
        )
        return stats

    def ping(self):
        """Check XMLRPC API connectivity.

        Returns:
            bool: True if API responds, False otherwise.
        """
        try:
            self._call("EnumClients")
            logger.debug("[OpenVPNASClient.ping] Success")
            return True
        except Exception as exc:
            logger.debug("[OpenVPNASClient.ping] Failed: %s", exc)
            return False

    def check_web_portal(self, timeout=None):
        """Check web portal reachability via HTTPS GET.

        Args:
            timeout: Request timeout in seconds (default: instance timeout).

        Returns:
            dict: Keys: status (1/0), response_ms, status_code. On failure
                  also includes error key.
        """
        if timeout is None:
            timeout = self._timeout

        url = "https://{}:{}/".format(self._host, self._web_port)
        logger.debug(
            "[OpenVPNASClient.check_web_portal] Checking %s {timeout: %s}", url, timeout,
        )

        start = time.monotonic()
        try:
            response = urlopen(url, timeout=timeout, context=self._ssl_context)
            elapsed_ms = (time.monotonic() - start) * 1000
            status_code = response.getcode()
            is_ok = 200 <= status_code < 400
            result = {
                "status": 1 if is_ok else 0,
                "response_ms": round(elapsed_ms, 1),
                "status_code": status_code,
            }
            if not is_ok:
                logger.warning(
                    "[OpenVPNASClient.check_web_portal] Non-success status {code: %d}",
                    status_code,
                )
            else:
                logger.debug(
                    "[OpenVPNASClient.check_web_portal] OK {code: %d, ms: %.1f}",
                    status_code, elapsed_ms,
                )
            return result
        except (URLError, OSError, socket.timeout, TimeoutError) as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(
                "[OpenVPNASClient.check_web_portal] Failed: %s", exc,
            )
            return {
                "status": 0,
                "response_ms": round(elapsed_ms, 1) if elapsed_ms > 0 else -1,
                "status_code": -1,
                "error": str(exc),
            }

    def test_user_auth(self, test_username, test_password):
        """Test LDAP/auth pipeline by authenticating with test credentials.

        Creates a secondary XMLRPC connection with test_username/test_password
        and attempts a simple API call. If the call succeeds, authentication
        (including LDAP if configured) is working.

        Args:
            test_username: Username to test authentication with.
            test_password: Password for the test user.

        Returns:
            bool: True if authentication succeeds, False if rejected.
        """
        logger.debug(
            "[OpenVPNASClient.test_user_auth] Testing auth for user %s", test_username,
        )
        try:
            url = "https://{}:{}@{}:{}/RPC2".format(
                test_username, test_password, self._host, self._port,
            )
            transport = _SSLTransport(self._ssl_context, self._timeout)
            test_proxy = xmlrpc.client.ServerProxy(url, transport=transport)

            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self._timeout)
            try:
                test_proxy.GetVPNStatus()
            finally:
                socket.setdefaulttimeout(old_timeout)

            logger.info(
                "[OpenVPNASClient.test_user_auth] LDAP auth test passed for user %s",
                test_username,
            )
            return True
        except xmlrpc.client.Fault as exc:
            if exc.faultCode in (401, 403):
                logger.warning(
                    "[OpenVPNASClient.test_user_auth] Auth test failed for user %s: "
                    "credentials rejected", test_username,
                )
                return False
            logger.error(
                "[OpenVPNASClient.test_user_auth] XMLRPC fault {code: %s, reason: %s}",
                exc.faultCode, exc.faultString,
            )
            return False
        except (socket.error, socket.timeout, ConnectionRefusedError,
                OSError, TimeoutError) as exc:
            logger.error(
                "[OpenVPNASClient.test_user_auth] Connection error: %s", exc,
            )
            raise ConnectionError(
                "Connection failed during auth test: {}".format(exc)
            ) from exc

    def collect_all(self, auth_test_user=None, auth_test_password=None):
        """Collect all metrics in one pass for Zabbix master item.

        Calls all monitoring methods and returns a flat dict. Each metric
        is collected independently — a failure in one metric does not
        block others.

        Args:
            auth_test_user: Optional username for LDAP auth test.
            auth_test_password: Optional password for LDAP auth test.

        Returns:
            dict: All metrics as a flat dict suitable for JSON serialization.
        """
        logger.debug("[OpenVPNASClient.collect_all] Starting full collection")
        metrics = {}

        # XMLRPC ping
        try:
            metrics["xmlrpc_ping"] = 1 if self.ping() else 0
        except Exception:
            metrics["xmlrpc_ping"] = 0

        # Active sessions
        try:
            metrics["active_sessions"] = self.get_active_sessions()
        except Exception as exc:
            logger.error("[OpenVPNASClient.collect_all] active_sessions failed: %s", exc)
            metrics["active_sessions"] = None

        # Bandwidth
        try:
            bw = self.get_bandwidth_stats()
            metrics["bytes_in"] = bw["bytes_in"]
            metrics["bytes_out"] = bw["bytes_out"]
        except Exception as exc:
            logger.error("[OpenVPNASClient.collect_all] bandwidth failed: %s", exc)
            metrics["bytes_in"] = None
            metrics["bytes_out"] = None

        # Server version
        try:
            info = self.get_server_info()
            metrics["server_version"] = info.get("version", "unknown")
        except Exception as exc:
            logger.error("[OpenVPNASClient.collect_all] server_info failed: %s", exc)
            metrics["server_version"] = None

        # Web portal
        try:
            portal = self.check_web_portal()
            metrics["web_portal_status"] = portal["status"]
            metrics["web_portal_response_ms"] = portal["response_ms"]
        except Exception as exc:
            logger.error("[OpenVPNASClient.collect_all] web_portal failed: %s", exc)
            metrics["web_portal_status"] = 0
            metrics["web_portal_response_ms"] = -1

        # LDAP auth test (optional)
        if auth_test_user and auth_test_password:
            try:
                metrics["ldap_auth_test"] = 1 if self.test_user_auth(
                    auth_test_user, auth_test_password,
                ) else 0
            except Exception as exc:
                logger.error("[OpenVPNASClient.collect_all] ldap_auth failed: %s", exc)
                metrics["ldap_auth_test"] = 0

        logger.debug(
            "[OpenVPNASClient.collect_all] Collection complete {metrics: %d}",
            len(metrics),
        )
        return metrics
