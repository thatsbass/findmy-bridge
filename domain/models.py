"""Domain models — pure dataclasses, zero external dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Tag:
    id: str
    private_key: bytes    # P-224 private key (28 bytes)
    advertising_key: bytes  # SHA-256(public_key)[:28]


@dataclass
class Position:
    tag_id: str
    lat: float
    lng: float
    accuracy: float
    confidence: int
    timestamp: datetime
