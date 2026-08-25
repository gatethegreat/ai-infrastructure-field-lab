"""Checks externally visible evidence without importing an experiment runtime."""

from __future__ import annotations

from collections.abc import Sequence

from shared.contracts import TimelineEvent


COMPLETED_EVENT_TYPES = (
    "incident_validated",
    "runbook_retrieved",
    "inspection_completed",
    "proposal_created",
    "approval_requested",
    "approval_decided",
    "action_completed",
    "execution_finished",
)


def verify_completed_timeline(events: Sequence[TimelineEvent]) -> None:
    """Raise AssertionError unless evidence proves the completed happy path."""
    assert tuple(event.event_type for event in events) == COMPLETED_EVENT_TYPES
    assert tuple(event.sequence for event in events) == tuple(
        range(1, len(events) + 1)
    )
    assert len({event.correlation_id for event in events}) == 1
    approval = events[5]
    assert approval.data["decision"] == "approve"
    action = events[6]
    assert action.data["simulated"] is True
    finished = events[7]
    assert finished.data == {"status": "completed", "action_executed": True}
