"""Unit tests for openvpn_as_check.py CLI script."""

import json
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


class TestMainOutput:
    def _run_main(self, args, mock_metrics=None):
        """Run main() with given args and return (stdout, exit_code)."""
        if mock_metrics is None:
            mock_metrics = {
                "active_sessions": 5,
                "bytes_in": 1000,
                "bytes_out": 2000,
                "server_version": "2.13.1",
                "xmlrpc_ping": 1,
                "web_portal_status": 1,
                "web_portal_response_ms": 50.3,
            }

        captured = StringIO()
        exit_code = 0

        with patch.object(sys, "argv", ["openvpn_as_check.py"] + args):
            with patch("openvpn_as_check.OpenVPNASClient") as mock_cls:
                mock_client = MagicMock()
                mock_cls.return_value = mock_client
                mock_client.collect_all.return_value = mock_metrics
                with patch("sys.stdout", captured):
                    try:
                        from openvpn_as_check import main
                        main()
                    except SystemExit as e:
                        exit_code = e.code or 0

        return captured.getvalue(), exit_code

    def test_outputs_valid_json(self):
        stdout, code = self._run_main(["10.0.0.1", "943", "admin", "pass"])
        assert code == 0
        data = json.loads(stdout.strip())
        assert isinstance(data, dict)

    def test_json_contains_all_expected_keys(self):
        stdout, _ = self._run_main(["10.0.0.1", "943", "admin", "pass"])
        data = json.loads(stdout.strip())
        assert "active_sessions" in data
        assert "bytes_in" in data
        assert "bytes_out" in data
        assert "server_version" in data
        assert "xmlrpc_ping" in data
        assert "web_portal_status" in data
        assert "web_portal_response_ms" in data

    def test_fatal_error_prints_zbx_notsupported(self):
        captured = StringIO()
        with patch.object(sys, "argv", ["openvpn_as_check.py", "10.0.0.1", "943", "admin", "pass"]):
            with patch("openvpn_as_check.OpenVPNASClient", side_effect=Exception("boom")):
                with patch("sys.stdout", captured):
                    try:
                        from openvpn_as_check import main
                        main()
                    except SystemExit:
                        pass
        assert "ZBX_NOTSUPPORTED" in captured.getvalue()

    def test_missing_args_prints_zbx_notsupported(self):
        captured = StringIO()
        with patch.object(sys, "argv", ["openvpn_as_check.py", "10.0.0.1"]):
            with patch("sys.stdout", captured):
                try:
                    from openvpn_as_check import main
                    main()
                except SystemExit:
                    pass
        assert "ZBX_NOTSUPPORTED" in captured.getvalue()

    def test_password_never_in_logs(self):
        """Verify the actual password string does not appear in log output."""
        import logging

        log_records = []
        handler = logging.Handler()
        handler.emit = lambda record: log_records.append(record)

        password = "SuperSecret123!"
        with patch.object(sys, "argv",
                          ["openvpn_as_check.py", "10.0.0.1", "943", "admin", password]):
            with patch("openvpn_as_check.OpenVPNASClient") as mock_cls:
                mock_client = MagicMock()
                mock_cls.return_value = mock_client
                mock_client.collect_all.return_value = {"xmlrpc_ping": 1}

                logger = logging.getLogger("openvpn_as_check")
                logger.addHandler(handler)
                logger.setLevel(logging.DEBUG)
                try:
                    with patch("sys.stdout", StringIO()):
                        from openvpn_as_check import main
                        main()
                except SystemExit:
                    pass
                finally:
                    logger.removeHandler(handler)

        for record in log_records:
            msg = record.getMessage()
            assert password not in msg, f"Password found in log: {msg}"
