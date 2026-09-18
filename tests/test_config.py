import os
import unittest
from unittest.mock import patch

from config.settings import Config


class ConfigTests(unittest.TestCase):
    def test_loads_required_values_and_converts_poll_interval_to_seconds(self) -> None:
        environment = {
            "APPLE_ID": "apple@example.com",
            "APPLE_PASSWORD": "password",
            "BACKEND_API_KEY": "api-key",
            "DATABASE_URL": "postgresql://localhost/findmy",
            "POLL_INTERVAL_MINUTES": "5",
        }

        with patch.dict(os.environ, environment, clear=True):
            config = Config.load()

        self.assertEqual(config.apple_id, "apple@example.com")
        self.assertEqual(config.poll_interval_seconds, 300)
        self.assertEqual(config.backend_url, "http://localhost:5000")
        self.assertIsNone(config.slack_webhook_url)
        self.assertEqual(config.anisette_provider, "local")
        self.assertEqual(config.anisette_libs_path, ".anisette_libs")
        self.assertEqual(config.apple_session_path, "account_session.json")

    def test_load_rejects_missing_required_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "APPLE_ID"):
                Config.load()

    def test_invalid_poll_interval_uses_existing_default(self) -> None:
        environment = {
            "APPLE_ID": "apple@example.com",
            "APPLE_PASSWORD": "password",
            "BACKEND_API_KEY": "api-key",
            "DATABASE_URL": "postgresql://localhost/findmy",
            "POLL_INTERVAL_MINUTES": "not-a-number",
        }

        with patch.dict(os.environ, environment, clear=True):
            config = Config.load()

        self.assertEqual(config.poll_interval_seconds, 20 * 60)

    def test_http_anisette_requires_a_url(self) -> None:
        environment = {
            "APPLE_ID": "apple@example.com",
            "APPLE_PASSWORD": "password",
            "BACKEND_API_KEY": "api-key",
            "DATABASE_URL": "postgresql://localhost/findmy",
            "ANISETTE_PROVIDER": "http",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "ANISETTE_URL"):
                Config.load()
