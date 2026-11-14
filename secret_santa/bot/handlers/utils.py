"""Shared helpers for update handlers."""

from __future__ import annotations


def parse_game_id(data: str | None) -> int:
    """Extract the trailing game id from ``prefix:action:<id>`` callback data."""
    if data is None:
        raise RuntimeError("Callback data is unavailable")
    return int(data.rsplit(":", maxsplit=1)[1])
