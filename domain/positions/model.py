"""Position domain model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    tag_id: str
    lat: float
    lng: float
    accuracy: float
    confidence: int
    timestamp: datetime
