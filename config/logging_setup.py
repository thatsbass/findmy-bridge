"""
LOGGING CONFIGURATION

Dev : human-readable, colored, aligned columns.
Prod : JSON structured (one object per line — compatible with ELK/Datadog/CloudWatch).

A CycleIdFilter injects the current polling cycle ID into every log record so
all logs emitted during a single cycle share the same cycle_id field.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from config import Config


class CycleIdFilter(logging.Filter):
    """Injects cycle_id from contextvars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        from application.poll_cycle import get_cycle_id
        record.cycle_id = get_cycle_id()
        return True

class _DevFormatter(logging.Formatter):
    _COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        ts    = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = f"{color}{record.levelname:<8}{self._RESET}"
        name  = f"{record.name:<30}"
        cid   = f"\033[2m[{record.cycle_id}]\033[0m " if record.cycle_id != "-" else ""
        msg   = record.getMessage()
        line  = f"{ts}  {level}  {name}  {cid}{msg}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts":     datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.cycle_id != "-":
            payload["cycle_id"] = record.cycle_id
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(cfg: Config) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))

    handler = logging.StreamHandler()
    handler.setFormatter(
        _DevFormatter() if cfg.env == "development" else _JsonFormatter()
    )
    handler.addFilter(CycleIdFilter())

    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("anisette").setLevel(logging.WARNING)
    logging.getLogger("tzlocal").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
