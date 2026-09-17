"""Configuration loader from environment and .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULTS = {
    "BACKEND_URL": "http://localhost:5000",
    "POLL_INTERVAL_MINUTES": "20",
    "HEALTH_PORT": "8080",
    "ENV": "development",
    "LOG_LEVEL": "info",
}

_REQUIRED_FIELDS = [
    "apple_id",
    "apple_password",
    "backend_api_key",
    "database_url",
]


@dataclass
class Config:
    apple_id: str
    apple_password: str
    backend_url: str
    backend_api_key: str
    database_url: str
    poll_interval_seconds: int
    health_port: int
    env: str
    log_level: str
    slack_webhook_url: str | None

    @classmethod
    def load(cls) -> Config:
        """Load configuration from environment, with .env fallback."""
        _load_dotenv()

        def _env(key: str) -> str:
            return os.getenv(key, _DEFAULTS.get(key, ""))

        def _env_required(key: str) -> str:
            value = os.getenv(key)
            if not value:
                raise ValueError(f"Missing required environment variable: {key}")
            return value

        def _int_env(key: str, default: int) -> int:
            try:
                return int(_env(key))
            except (ValueError, TypeError):
                return default

        cfg = cls(
            apple_id=_env_required("APPLE_ID"),
            apple_password=_env_required("APPLE_PASSWORD"),
            backend_url=_env("BACKEND_URL"),
            backend_api_key=_env_required("BACKEND_API_KEY"),
            database_url=_env_required("DATABASE_URL"),
            poll_interval_seconds=_int_env("POLL_INTERVAL_MINUTES", 20) * 60,
            health_port=_int_env("HEALTH_PORT", 8080),
            env=_env("ENV"),
            log_level=_env("LOG_LEVEL"),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
        )
        cfg._validate()
        return cfg

    def _validate(self) -> None:
        missing = [f for f in _REQUIRED_FIELDS if not getattr(self, f)]
        if missing:
            raise ValueError(
                f"Invalid configuration, missing fields: {', '.join(missing)}. "
                "Check your environment variables or .env file."
            )


def _load_dotenv(path: str = ".env") -> None:
    """Load key=value pairs from .env — does not override existing env vars."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass
