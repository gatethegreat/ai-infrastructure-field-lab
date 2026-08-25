"""Injectable logical clock used to make local runs reproducible."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class LogicalClock:
    def __init__(self, start: datetime | None = None) -> None:
        value = start or datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc)
        if value.tzinfo is None:
            raise ValueError("logical clock start must be timezone aware")
        self._now = value.astimezone(timezone.utc)

    @property
    def now(self) -> datetime:
        return self._now

    def iso_now(self) -> str:
        return self._now.isoformat().replace("+00:00", "Z")

    def advance(self, milliseconds: float = 1.0) -> datetime:
        if milliseconds < 0:
            raise ValueError("logical clock cannot move backward")
        self._now += timedelta(milliseconds=milliseconds)
        return self._now

    def relative_iso(self, *, minutes: int = 0, seconds: int = 0) -> str:
        value = self._now + timedelta(minutes=minutes, seconds=seconds)
        return value.isoformat().replace("+00:00", "Z")
