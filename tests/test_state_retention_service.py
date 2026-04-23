from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.state_retention_service import StateRetentionService
from core.state_store import StateStore, StateStoreError
from tests.test_validate import RETENTION_NON_CONSOLIDATION_EVENT_LIMIT, seed_retention_fixture


class StateRetentionServiceTests(unittest.TestCase):
    def _build_service(self, store: StateStore) -> StateRetentionService:
        return StateRetentionService(
            cerebro_dir=store.cerebro_dir,
            events_path=store.events_path,
            artifacts_dir=store.artifacts_dir,
            trash_dir=store.trash_dir,
            error_cls=StateStoreError,
            parse_parallel_approach_consolidation_line=store._parse_parallel_approach_consolidation_line,
            parse_event_log_event_type=store._parse_event_log_event_type,
            iter_live_runtime_artifact_refs=store._iter_live_runtime_artifact_refs,
            resolve_runtime_artifact_ref=store._resolve_runtime_artifact_ref,
            write_json_atomic=store._write_json_atomic,
            commit_trace_events=store._commit_trace_events,
        )

    def test_build_retention_report_matches_state_store_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            service = self._build_service(store)
            state = store.load_state()

            expected = store.inspect_retention(expected_revision=state["revision"])

            self.assertEqual(service.build_retention_report(state), expected)

    def test_finalize_pending_retention_archive_replays_pending_manifest_without_recomputing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            service = self._build_service(store)
            expected_revision = store.validate_state()["revision"]
            original_write_json_atomic = StateStore._write_json_atomic
            manifest_failure = {"triggered": False}

            def flaky_write_json_atomic(store_self: StateStore, path: Path, data: object) -> None:
                target = Path(path)
                if (
                    not manifest_failure["triggered"]
                    and target.name == "manifest.json"
                    and "/trash/retention/retention-" in target.as_posix()
                ):
                    manifest_failure["triggered"] = True
                    raise StateStoreError("simulated retention manifest write failure")
                original_write_json_atomic(store_self, target, data)

            with mock.patch.object(
                StateStore,
                "_write_json_atomic",
                autospec=True,
                side_effect=flaky_write_json_atomic,
            ):
                with self.assertRaisesRegex(StateStoreError, "simulated retention manifest write failure"):
                    store.apply_retention(expected_revision=expected_revision)

            archives = sorted((store.trash_dir / "retention").glob("retention-*"))
            self.assertEqual(len(archives), 1)
            archive_root = archives[0]
            pending_manifest = json.loads((archive_root / "manifest.pending.json").read_text(encoding="utf-8"))

            result = service.finalize_pending_retention_archive(store.load_state(), archive_root, pending_manifest)

            self.assertTrue(result["applied"])
            self.assertFalse((archive_root / "manifest.pending.json").exists())
            manifest = json.loads((archive_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["retention_event_id"], pending_manifest["retention_event"]["event_id"])

    def test_build_event_log_retention_plan_preserves_retention_applied_outside_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            service = self._build_service(store)
            retained_event = {
                "event_id": "retention-applied-001",
                "trace_thread_id": "retain",
                "recorded_at": "2026-04-15T00:00:00+00:00",
                "revision": 0,
                "event": "retention_applied",
                "event_type": "retention_applied",
                "phase": "validate",
                "step": "retention",
                "parent_event_id": "",
                "target": ".cerebro/trash/retention/retention-001",
            }

            lines = store.events_path.read_bytes().splitlines()
            insert_at = len(lines) - (RETENTION_NON_CONSOLIDATION_EVENT_LIMIT + 5)
            lines.insert(insert_at, json.dumps(retained_event, separators=(",", ":")).encode("utf-8"))
            store.events_path.write_bytes(b"\n".join(lines) + b"\n")

            plan = service.build_event_log_retention_plan()
            retained_events = []
            for line in plan["_retained_lines"]:
                try:
                    retained_events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

            self.assertGreater(plan["archived_line_count"], 0)
            self.assertTrue(any(event.get("event_type") == "retention_applied" for event in retained_events))

    def test_build_artifact_retention_plan_counts_unknown_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            service = self._build_service(store)
            odd_artifact = store.artifacts_dir / "misc" / "odd.txt"
            odd_artifact.parent.mkdir(parents=True, exist_ok=True)
            odd_artifact.write_text("unexpected", encoding="utf-8")

            plan = service.build_artifact_retention_plan(store.load_state())

            self.assertEqual(plan["blocked_unknown_group_count"], 1)
            self.assertEqual(plan["blocked_unknown_examples"], ("misc/odd.txt",))

    def test_live_artifact_group_paths_ignores_resolution_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            service = self._build_service(store)
            state = store.load_state()

            with mock.patch.object(service, "_resolve_runtime_artifact_ref", side_effect=StateStoreError("bad ref")):
                self.assertEqual(service.live_artifact_group_paths(state), set())

    def test_artifact_retention_group_path_returns_none_for_short_or_invalid_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            service = self._build_service(store)

            self.assertIsNone(service.artifact_retention_group_path("odd.txt"))
            self.assertIsNone(service.artifact_retention_group_path("misc/odd.txt"))


if __name__ == "__main__":
    unittest.main()
