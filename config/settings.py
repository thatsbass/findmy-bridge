"""Typed application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULTS = {
    "BACKEND_URL": "http://localhost:5000",
    "POLL_INTERVAL_MINUTES": "20",
    "HEALTH_PORT": "8080",
    "ENV": "development",
    "LOG_LEVEL": "info",
    "ANISETTE_PROVIDER": "local",
    "ANISETTE_LIBS_PATH": ".anisette_libs",
    "APPLE_SESSION_PATH": "account_session.json",
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
    anisette_provider: str
    anisette_url: str | None
    anisette_libs_path: str
    apple_session_path: str

    @classmethod
    def load(cls) -> Config:
        _load_dotenv()

        def env(key: str) -> str:
            return os.getenv(key, _DEFAULTS.get(key, ""))

        def required_env(key: str) -> str:
            value = os.getenv(key)
            if not value:
                raise ValueError(f"Missing required environment variable: {key}")
            return value

        def positive_integer_env(key: str, default: int) -> int:
            raw_value = os.getenv(key)
            if raw_value is None:
                return default
            try:
                value = int(raw_value)
            except ValueError as exc:
                raise ValueError(f"{key} must be an integer") from exc
            if value <= 0:
                raise ValueError(f"{key} must be greater than zero")
            return value

        config = cls(
            apple_id=required_env("APPLE_ID"),
            apple_password=required_env("APPLE_PASSWORD"),
            backend_url=env("BACKEND_URL"),
            backend_api_key=required_env("BACKEND_API_KEY"),
            database_url=required_env("DATABASE_URL"),
            poll_interval_seconds=positive_integer_env("POLL_INTERVAL_MINUTES", 20) * 60,
            health_port=positive_integer_env("HEALTH_PORT", 8080),
            env=env("ENV"),
            log_level=env("LOG_LEVEL"),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
            anisette_provider=env("ANISETTE_PROVIDER"),
            anisette_url=os.getenv("ANISETTE_URL") or None,
            anisette_libs_path=env("ANISETTE_LIBS_PATH"),
            apple_session_path=env("APPLE_SESSION_PATH"),
        )
        config.validate()
        return config

    def validate(self) -> None:
        missing = [field for field in _REQUIRED_FIELDS if not getattr(self, field)]
        if missing:
            raise ValueError(
                f"Invalid configuration, missing fields: {', '.join(missing)}. "
                "Check your environment variables or .env file."
            )
        if self.anisette_provider not in {"local", "http"}:
            raise ValueError("ANISETTE_PROVIDER must be either 'local' or 'http'")
        if self.anisette_provider == "http" and not self.anisette_url:
            raise ValueError("ANISETTE_URL is required when ANISETTE_PROVIDER=http")
        if self.env not in {"development", "production"}:
            raise ValueError("ENV must be either 'development' or 'production'")
        if self.log_level not in {"debug", "info", "warning", "error"}:
            raise ValueError("LOG_LEVEL must be debug, info, warning, or error")


def _load_dotenv(path: str = ".env") -> None:
    """Load key/value pairs without overriding existing environment variables."""
    try:
        with open(path, encoding="utf-8") as file:
            for line in file:
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
