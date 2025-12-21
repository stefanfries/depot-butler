"""Pytest configuration and fixtures."""

import os


def pytest_configure(config):
    """
    Configure pytest before test collection begins.

    This runs BEFORE any imports happen, so we can set environment variables
    that are needed by settings.py at import time.
    """
    # Only set if not already defined (allows real .env to override)
    test_env = {
        "BOERSENMEDIEN_BASE_URL": "https://www.boersenmedien.de",
        "BOERSENMEDIEN_LOGIN_URL": "https://www.boersenmedien.de/login",
        "BOERSENMEDIEN_USERNAME": "test_user",
        "BOERSENMEDIEN_PASSWORD": "test_password",
        "ONEDRIVE_CLIENT_ID": "test-client-id",
        "ONEDRIVE_CLIENT_SECRET": "test-client-secret",
        "ONEDRIVE_REFRESH_TOKEN": "test-refresh-token",
        "SMTP_USERNAME": "test@example.com",
        "SMTP_PASSWORD": "test-password",
        "SMTP_ADMIN_ADDRESS": "admin@example.com",
        "DB_NAME": "test_db",
        "DB_ROOT_USERNAME": "test_user",
        "DB_ROOT_PASSWORD": "test_password",
        "DB_CONNECTION_STRING": "mongodb://localhost:27017",
    }

    for key, value in test_env.items():
        if key not in os.environ:
            os.environ[key] = value
