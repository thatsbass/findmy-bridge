"""Tag domain model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Tag:
    id: str
    private_key: bytes
    advertising_key: bytes
