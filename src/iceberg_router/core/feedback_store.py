"""Visibility-safe feedback snapshots backed by the immutable audit journal."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from iceberg_router.contracts._validation import parse_utc_timestamp, require_utc_timestamp
from iceberg_router.contracts.feedback import FeedbackChannel, FeedbackEvent
from iceberg_router.contracts.identifiers import OutputId, RequestId, SnapshotVersion

from .journal import (
    JournalAppendResult,
    JournalEventType,
    SQLiteAuditJournal,
)


class FeedbackStoreError(RuntimeError):
    """Stored feedback cannot be projected into a trustworthy snapshot."""


@dataclass(frozen=True, slots=True)
class FeedbackSnapshot:
    snapshot_version: SnapshotVersion
    visible_through: str
    journal_through_sequence: int
    events: tuple[FeedbackEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_version, SnapshotVersion):
            raise TypeError("snapshot_version must be SnapshotVersion")
        cutoff = parse_utc_timestamp(self.visible_through, "visible_through")
        if isinstance(self.journal_through_sequence, bool) or not isinstance(
            self.journal_through_sequence, int
        ):
            raise TypeError("journal_through_sequence must be an integer")
        if self.journal_through_sequence < 0:
            raise ValueError("journal_through_sequence must be non-negative")
        if not isinstance(self.events, tuple):
            raise TypeError("events must be a tuple")
        if any(not isinstance(event, FeedbackEvent) for event in self.events):
            raise TypeError("events must contain FeedbackEvent values")
        if len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("feedback event IDs must be unique")
        if any(
            parse_utc_timestamp(event.visible_at, "visible_at") > cutoff
            for event in self.events
        ):
            raise ValueError("snapshot contains feedback that was not yet visible")


class BlindEvaluationCapability:
    """Opaque capability required to construct a blind-evaluation view."""


@dataclass(frozen=True, slots=True)
class FeedbackChannelView:
    store: "JournalFeedbackStore"
    channels: frozenset[FeedbackChannel]

    def snapshot(self, visible_through: str, **filters) -> FeedbackSnapshot:
        return self.store._snapshot_channels(visible_through, self.channels, **filters)


class JournalFeedbackStore:
    """Append feedback and create deterministic as-of visibility snapshots."""

    def __init__(
        self,
        journal: SQLiteAuditJournal,
        *,
        blind_capability: BlindEvaluationCapability | None = None,
    ):
        if not isinstance(journal, SQLiteAuditJournal):
            raise TypeError("journal must be SQLiteAuditJournal")
        self.journal = journal
        self._blind_capability = blind_capability

    def learning_view(self) -> FeedbackChannelView:
        return FeedbackChannelView(
            self,
            frozenset(
                {
                    FeedbackChannel.OPERATIONAL_CHECKER,
                    FeedbackChannel.USER,
                    FeedbackChannel.TRAINING_LABEL,
                }
            ),
        )

    def operational_checker_view(self) -> FeedbackChannelView:
        return FeedbackChannelView(
            self, frozenset({FeedbackChannel.OPERATIONAL_CHECKER})
        )

    def user_feedback_view(self) -> FeedbackChannelView:
        return FeedbackChannelView(self, frozenset({FeedbackChannel.USER}))

    def training_label_view(self) -> FeedbackChannelView:
        return FeedbackChannelView(
            self, frozenset({FeedbackChannel.TRAINING_LABEL})
        )

    def blind_evaluation_view(
        self, capability: BlindEvaluationCapability
    ) -> FeedbackChannelView:
        if capability is not self._blind_capability:
            raise PermissionError("blind-evaluation capability is required")
        return FeedbackChannelView(
            self, frozenset({FeedbackChannel.BLIND_EVALUATION})
        )

    def append_channel(self, event: FeedbackEvent, channel: FeedbackChannel):
        if event.channel is not channel:
            raise ValueError("feedback event channel does not match append API")
        return self.append(event)

    def append_operational_checker(self, event: FeedbackEvent):
        return self.append_channel(event, FeedbackChannel.OPERATIONAL_CHECKER)

    def append_user_feedback(self, event: FeedbackEvent):
        return self.append_channel(event, FeedbackChannel.USER)

    def append_training_label(self, event: FeedbackEvent):
        return self.append_channel(event, FeedbackChannel.TRAINING_LABEL)

    def append_blind_evaluation(
        self, event: FeedbackEvent, capability: BlindEvaluationCapability
    ):
        if capability is not self._blind_capability:
            raise PermissionError("blind-evaluation capability is required")
        return self.append_channel(event, FeedbackChannel.BLIND_EVALUATION)

    def append(self, event: FeedbackEvent) -> JournalAppendResult:
        if not isinstance(event, FeedbackEvent):
            raise TypeError("event must be FeedbackEvent")
        return self.journal.append_feedback(event)

    def snapshot(
        self,
        visible_through: str,
        **filters,
    ) -> FeedbackSnapshot:
        """Legacy/non-blind view; blind final labels are never returned."""
        return self._snapshot_channels(
            visible_through,
            frozenset(
                {
                    FeedbackChannel.LEGACY_COMBINED,
                    FeedbackChannel.OPERATIONAL_CHECKER,
                    FeedbackChannel.USER,
                    FeedbackChannel.TRAINING_LABEL,
                }
            ),
            **filters,
        )

    def _snapshot_channels(
        self,
        visible_through: str,
        channels: frozenset[FeedbackChannel],
        *,
        request_id: RequestId | None = None,
        output_id: OutputId | None = None,
        journal_through_sequence: int | None = None,
    ) -> FeedbackSnapshot:
        cutoff_text = require_utc_timestamp(visible_through, "visible_through")
        cutoff = parse_utc_timestamp(cutoff_text, "visible_through")
        if request_id is not None and not isinstance(request_id, RequestId):
            raise TypeError("request_id must be RequestId or None")
        if output_id is not None and not isinstance(output_id, OutputId):
            raise TypeError("output_id must be OutputId or None")
        if journal_through_sequence is not None and (
            isinstance(journal_through_sequence, bool)
            or not isinstance(journal_through_sequence, int)
        ):
            raise TypeError("journal_through_sequence must be an integer or None")
        if journal_through_sequence is not None and journal_through_sequence < 0:
            raise ValueError("journal_through_sequence must be non-negative")

        self.journal.verify_chain()
        entries = self.journal.entries()
        maximum_sequence = 0 if not entries else entries[-1].sequence
        high_water = (
            maximum_sequence
            if journal_through_sequence is None
            else journal_through_sequence
        )
        if high_water > maximum_sequence:
            raise ValueError("journal_through_sequence exceeds the journal tail")
        events: list[FeedbackEvent] = []
        for entry in entries:
            if entry.sequence > high_water:
                break
            if entry.event_type is not JournalEventType.FEEDBACK:
                continue
            try:
                event = FeedbackEvent.from_json(entry.payload)
            except (TypeError, ValueError) as error:
                raise FeedbackStoreError(
                    f"feedback journal entry {entry.event_id.value} is invalid"
                ) from error
            if event.channel not in channels:
                continue
            if parse_utc_timestamp(event.visible_at, "visible_at") > cutoff:
                continue
            if request_id is not None and event.request_id != request_id:
                continue
            if output_id is not None and event.output_id != output_id:
                continue
            events.append(event)
        events.sort(
            key=lambda event: (
                parse_utc_timestamp(event.visible_at, "visible_at"),
                parse_utc_timestamp(event.observed_at, "observed_at"),
                event.event_id.value,
            )
        )
        frozen = tuple(events)
        material = {
            "channels": sorted(channel.value for channel in channels),
            "events": [event.to_json() for event in frozen],
            "journalThroughSequence": high_water,
            "outputId": None if output_id is None else output_id.value,
            "requestId": None if request_id is None else request_id.value,
            "visibleThrough": cutoff_text,
        }
        encoded = json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        version = SnapshotVersion(f"feedback-{hashlib.sha256(encoded).hexdigest()}")
        return FeedbackSnapshot(version, cutoff_text, high_water, frozen)
