from __future__ import annotations

import unittest

from core.runtime_event_window import events_since_latest_plan_update


class RuntimeEventWindowTests(unittest.TestCase):
    def test_events_since_latest_plan_update_returns_latest_plan_suffix(self) -> None:
        events = [
            "noise",
            {"event": "plan_updated", "event_id": "evt-old-plan"},
            {"event": "task_selected", "event_id": "evt-old-select"},
            None,
            {"event": "plan_updated", "event_id": "evt-new-plan"},
            {"event": "task_selected", "event_id": "evt-new-select"},
            {"event": "verification_completed", "event_id": "evt-new-verify"},
        ]

        window = events_since_latest_plan_update(events)

        self.assertEqual(
            window,
            (
                {"event": "plan_updated", "event_id": "evt-new-plan"},
                {"event": "task_selected", "event_id": "evt-new-select"},
                {"event": "verification_completed", "event_id": "evt-new-verify"},
            ),
        )

    def test_events_since_latest_plan_update_returns_all_normalized_events_without_plan_boundary(self) -> None:
        events = [
            {"event": "task_selected", "event_id": "evt-001"},
            "noise",
            {"event": "retry_blocked", "event_id": "evt-002"},
        ]

        window = events_since_latest_plan_update(events)

        self.assertEqual(
            window,
            (
                {"event": "task_selected", "event_id": "evt-001"},
                {"event": "retry_blocked", "event_id": "evt-002"},
            ),
        )

    def test_events_since_latest_plan_update_fail_closes_for_non_sequence_inputs(self) -> None:
        self.assertEqual(events_since_latest_plan_update(None), ())
        self.assertEqual(events_since_latest_plan_update({"event": "plan_updated"}), ())


if __name__ == "__main__":
    unittest.main()
