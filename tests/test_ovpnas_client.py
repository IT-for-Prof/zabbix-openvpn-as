"""Unit tests for ovpnas_client.OpenVPNASClient."""

import logging
import socket
import ssl
import xmlrpc.client
from unittest.mock import MagicMock, patch

import pytest

from ovpnas_client import OpenVPNASClient


@pytest.fixture
def client():
    """Create an OpenVPNASClient with mocked ServerProxy."""
    with patch("ovpnas_client.xmlrpc.client.ServerProxy") as mock_proxy_cls:
        mock_proxy = MagicMock()
        mock_proxy_cls.return_value = mock_proxy
        c = OpenVPNASClient("10.0.0.1", "admin", "secret", verify_ssl=False)
        c._proxy = mock_proxy
        yield c


class TestGetActiveSessions:
    def test_success_with_user_table(self, client):
        client._proxy.GetVPNStatus.return_value = {
            "user_table": [
                {"username": "alice", "real_address": "1.2.3.4"},
                {"username": "bob", "real_address": "5.6.7.8"},
            ]
        }
        assert client.get_active_sessions() == 2

    def test_success_empty(self, client):
        client._proxy.GetVPNStatus.return_value = {"user_table": []}
        assert client.get_active_sessions() == 0

    def test_connection_refused(self, client):
        client._proxy.GetVPNStatus.side_effect = ConnectionRefusedError("refused")
        with pytest.raises(ConnectionError):
            client.get_active_sessions()


class TestGetActiveUsers:
    def test_success(self, client):
        client._proxy.GetVPNStatus.return_value = {
            "user_table": [
                {
                    "username": "alice",
                    "real_address": "1.2.3.4",
                    "bytes_received": "1000",
                    "bytes_sent": "2000",
                    "connected_since": "2026-01-01T00:00:00",
                },
            ]
        }
        users = client.get_active_users()
        assert len(users) == 1
        assert users[0]["username"] == "alice"
        assert users[0]["bytes_in"] == 1000
        assert users[0]["bytes_out"] == 2000


class TestGetServerInfo:
    def test_success(self, client):
        client._proxy.GetVPNStatus.return_value = {
            "version": "2.13.1",
            "uptime": "5 days",
            "status": "running",
        }
        info = client.get_server_info()
        assert info["version"] == "2.13.1"
        assert info["status"] == "running"


class TestPing:
    def test_returns_true_on_success(self, client):
        client._proxy.EnumClients.return_value = []
        assert client.ping() is True

    def test_returns_false_on_error(self, client):
        client._proxy.EnumClients.side_effect = ConnectionRefusedError("refused")
        assert client.ping() is False


class TestAuthFailure:
    def test_raises_permission_error(self, client):
        client._proxy.GetVPNStatus.side_effect = xmlrpc.client.Fault(
            403, "Access denied"
        )
        with pytest.raises(PermissionError, match="Authentication failed"):
            client.get_active_sessions()

    def test_xmlrpc_fault_other_code(self, client):
        client._proxy.GetVPNStatus.side_effect = xmlrpc.client.Fault(
            500, "Internal error"
        )
        with pytest.raises(RuntimeError, match="XMLRPC fault"):
            client.get_active_sessions()


class TestSSLWarning:
    def test_warning_logged_when_disabled(self, caplog):
        with patch("ovpnas_client.xmlrpc.client.ServerProxy"):
            with caplog.at_level(logging.WARNING):
                OpenVPNASClient("10.0.0.1", "admin", "secret", verify_ssl=False)
        assert any("SSL verification disabled" in r.message for r in caplog.records)


class TestCheckWebPortal:
    def test_success(self, client):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        with patch("ovpnas_client.urlopen", return_value=mock_response):
            result = client.check_web_portal()
        assert result["status"] == 1
        assert result["status_code"] == 200
        assert result["response_ms"] >= 0

    def test_connection_refused(self, client):
        from urllib.error import URLError

        with patch("ovpnas_client.urlopen", side_effect=URLError("refused")):
            result = client.check_web_portal()
        assert result["status"] == 0
        assert result["status_code"] == -1
        assert "error" in result


class TestTestUserAuth:
    def test_success(self, client):
        with patch("ovpnas_client.xmlrpc.client.ServerProxy") as mock_cls:
            mock_test_proxy = MagicMock()
            mock_cls.return_value = mock_test_proxy
            mock_test_proxy.GetVPNStatus.return_value = {}
            assert client.test_user_auth("testuser", "testpass") is True

    def test_auth_failure(self, client):
        with patch("ovpnas_client.xmlrpc.client.ServerProxy") as mock_cls:
            mock_test_proxy = MagicMock()
            mock_cls.return_value = mock_test_proxy
            mock_test_proxy.GetVPNStatus.side_effect = xmlrpc.client.Fault(
                401, "Unauthorized"
            )
            assert client.test_user_auth("testuser", "badpass") is False


class TestCollectAll:
    def test_returns_all_metrics(self, client):
        client._proxy.EnumClients.return_value = []
        client._proxy.GetVPNStatus.return_value = {
            "user_table": [{"username": "alice"}],
            "version": "2.13.1",
        }
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        with patch("ovpnas_client.urlopen", return_value=mock_response):
            metrics = client.collect_all()

        assert "xmlrpc_ping" in metrics
        assert "active_sessions" in metrics
        assert "bytes_in" in metrics
        assert "bytes_out" in metrics
        assert "server_version" in metrics
        assert "web_portal_status" in metrics
        assert "web_portal_response_ms" in metrics
        # ldap_auth_test should be absent when no test user provided
        assert "ldap_auth_test" not in metrics

    def test_partial_failure(self, client):
        # ping succeeds
        client._proxy.EnumClients.return_value = []
        # GetVPNStatus fails (affects sessions, bandwidth, server_info)
        client._proxy.GetVPNStatus.side_effect = ConnectionRefusedError("down")
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        with patch("ovpnas_client.urlopen", return_value=mock_response):
            metrics = client.collect_all()

        # ping should still work
        assert metrics["xmlrpc_ping"] == 1
        # Failed metrics should be None
        assert metrics["active_sessions"] is None
        assert metrics["bytes_in"] is None
        # Web portal should still work
        assert metrics["web_portal_status"] == 1

    def test_with_ldap_auth(self, client):
        client._proxy.EnumClients.return_value = []
        client._proxy.GetVPNStatus.return_value = {"user_table": [], "version": "2.13.1"}
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        with patch("ovpnas_client.urlopen", return_value=mock_response):
            with patch("ovpnas_client.xmlrpc.client.ServerProxy") as mock_cls:
                mock_test_proxy = MagicMock()
                mock_cls.return_value = mock_test_proxy
                mock_test_proxy.GetVPNStatus.return_value = {}
                metrics = client.collect_all(
                    auth_test_user="testuser",
                    auth_test_password="testpass",
                )

        assert metrics["ldap_auth_test"] == 1
