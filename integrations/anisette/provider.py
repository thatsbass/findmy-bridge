"""Create the configured Anisette provider in one place."""

from __future__ import annotations

from pathlib import Path


def create_provider(
    mode: str,
    *,
    libs_path: Path,
    url: str | None = None,
) -> object:
    """Create a local or remote provider from validated application settings."""
    if mode == "local":
        from findmy.reports.anisette import LocalAnisetteProvider

        return LocalAnisetteProvider(libs_path=libs_path)

    if mode == "http":
        if not url:
            raise ValueError("ANISETTE_URL is required when ANISETTE_PROVIDER=http")
        from findmy.reports.anisette import RemoteAnisetteProvider

        return RemoteAnisetteProvider(url)

    raise ValueError(f"Unsupported ANISETTE_PROVIDER: {mode}")
