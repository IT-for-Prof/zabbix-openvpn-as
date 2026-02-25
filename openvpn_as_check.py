#!/usr/bin/env python3
"""Zabbix External Check script for OpenVPN Access Server.

Collects all metrics from OpenVPN AS via XMLRPC API and outputs
a single JSON blob to stdout for Zabbix master item consumption.
Dependent items extract individual values via JSONPath preprocessing.

Usage (positional args for Zabbix External Check compatibility):
    openvpn_as_check.py HOST PORT USERNAME PASSWORD [AUTH_TEST_USER] [AUTH_TEST_PASSWORD] [VERIFY_SSL] [WEB_PORT]

Zabbix item key example:
    openvpn_as_check.py["{$OVPN_HOST}","{$OVPN_PORT}","{$OVPN_USER}","{$OVPN_PASSWORD}","{$OVPN_AUTH_TEST_USER}","{$OVPN_AUTH_TEST_PASSWORD}","{$OVPN_VERIFY_SSL}","{$OVPN_WEB_PORT}"]
"""

import json
import logging
import logging.handlers
import os
import sys

from ovpnas_client import OpenVPNASClient

LOG_FILE = "/tmp/openvpn_as_check.log"
LOG_MAX_BYTES = 1_048_576  # 1 MB
LOG_BACKUP_COUNT = 3


def setup_logging():
    """Configure logging to file only. NEVER stdout/stderr."""
    level_name = os.environ.get("LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers (prevent duplicate output)
    root_logger.handlers.clear()

    try:
        handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
        )
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    except (OSError, PermissionError):
        # Cannot write log file — silently disable logging
        root_logger.addHandler(logging.NullHandler())


logger = logging.getLogger("openvpn_as_check")


def mask_password(password):
    """Mask password for logging: show first 2 chars + ***."""
    if not password:
        return "***"
    return password[:2] + "***" if len(password) >= 2 else "***"


def main():
    setup_logging()

    # Parse positional arguments
    args = sys.argv[1:]

    if len(args) < 4:
        print("ZBX_NOTSUPPORTED: Usage: openvpn_as_check.py HOST PORT USERNAME PASSWORD "
              "[AUTH_TEST_USER] [AUTH_TEST_PASSWORD] [VERIFY_SSL] [WEB_PORT]")
        sys.exit(1)

    host = args[0]
    try:
        port = int(args[1])
    except ValueError:
        print("ZBX_NOTSUPPORTED: PORT must be an integer, got: {}".format(args[1]))
        sys.exit(1)
    username = args[2]
    password = args[3]
    auth_test_user = args[4] if len(args) > 4 else ""
    auth_test_password = args[5] if len(args) > 5 else ""
    verify_ssl_str = args[6] if len(args) > 6 else "0"
    verify_ssl = verify_ssl_str in ("1", "true", "True", "yes")
    web_port_str = args[7] if len(args) > 7 else "443"
    try:
        web_port = int(web_port_str)
    except ValueError:
        print("ZBX_NOTSUPPORTED: WEB_PORT must be an integer, got: {}".format(web_port_str))
        sys.exit(1)

    logger.debug(
        "[openvpn_as_check] Starting {host: %s, port: %d, web_port: %d, user: %s, "
        "pass: %s, auth_test_user: %s, verify_ssl: %s}",
        host, port, web_port, username, mask_password(password),
        auth_test_user or "(none)", verify_ssl,
    )

    try:
        client = OpenVPNASClient(
            host=host,
            username=username,
            password=password,
            port=port,
            web_port=web_port,
            verify_ssl=verify_ssl,
        )
    except Exception as exc:
        logger.error("[openvpn_as_check] Failed to create client: %s", exc, exc_info=True)
        print("ZBX_NOTSUPPORTED: Failed to initialize client: {}".format(exc))
        sys.exit(1)

    try:
        metrics = client.collect_all(
            auth_test_user=auth_test_user if auth_test_user else None,
            auth_test_password=auth_test_password if auth_test_password else None,
        )
    except Exception as exc:
        logger.error("[openvpn_as_check] Collection failed: %s", exc, exc_info=True)
        print("ZBX_NOTSUPPORTED: Collection failed: {}".format(exc))
        sys.exit(1)

    logger.info(
        "[openvpn_as_check] Collection complete {metrics: %d}", len(metrics),
    )

    # Output JSON to stdout for Zabbix master item
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
