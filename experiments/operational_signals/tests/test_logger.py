from __future__ import annotations

import json
import threading
import time
from pathlib import Path
import tomllib
import unittest
from unittest.mock import patch

from experiments.operational_signals import logger as logger_module
from experiments.operational_signals.logger import initialize_registry, load_registry, record_unmet_use_case
from experiments.operational_signals import schema as schema_module
from experiments.operational_signals.schema import SchemaError
from experiments.operational_signals.tests._workspace_temp import workspace_tempdir


def _record(**overrides):
    payload = {
        "id": "uuc-demo-001",
        "timestamp": "2026-04-20T18:00:00Z",
        "project_context": "demo",
        "task_description": "continue the task",
        "query_or_need": "where is the canonical entry point",
        "surface_used": ["analyze"],
        "failure_mode": "CONTEXT_AMBIGUOUS",
        "manual_workaround": "opened CHECKLIST manually",
        "operational_cost": {
            "minutes_spent": 12,
            "extra_files_opened": 5,
            "manual_search_rounds": 3,
        },
        "repeat_count": 2,
        "evidence": ["CHECKLIST.md"],
        "confidence": "medium",
        "notes": "",
    }
    payload.update(overrides)
    return payload


class LoggerTests(unittest.TestCase):
    def test_initialize_and_record_round_trip(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            record_unmet_use_case(_record(), path=registry_path)

            loaded = load_registry(registry_path)
            self.assertEqual(loaded["schema_version"], "1")
            self.assertEqual(len(loaded["unmet_use_case"]), 1)
            self.assertTrue(loaded["unmet_use_case"][0]["candidate_trigger"])
            parsed = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(len(parsed["unmet_use_case"]), 1)

    def test_incomplete_record_is_rejected(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            with self.assertRaises(SchemaError):
                record_unmet_use_case(_record(surface_used=[]), path=registry_path)

    def test_registry_path_inside_cerebro_is_rejected(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / ".cerebro" / "signals.toml"
            with self.assertRaises(SchemaError):
                initialize_registry(registry_path)

    def test_registry_path_inside_cerebro_case_variant_is_rejected(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / ".CEREBRO" / "signals.toml"
            with self.assertRaises(SchemaError):
                initialize_registry(registry_path)

    def test_concurrent_record_calls_serialize_registry_updates(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            original_atomic_write = logger_module.atomic_write_registry
            first_write_entered = threading.Event()
            call_count = 0
            call_count_lock = threading.Lock()
            errors: list[Exception] = []

            def delayed_atomic_write(path: Path, payload: dict[str, object]) -> Path:
                nonlocal call_count
                with call_count_lock:
                    call_count += 1
                    current_call = call_count
                if current_call == 1:
                    first_write_entered.set()
                    time.sleep(0.05)
                else:
                    self.assertTrue(first_write_entered.wait(1.0))
                return original_atomic_write(path, payload)

            def worker(record_id: str) -> None:
                try:
                    record_unmet_use_case(_record(id=record_id), path=registry_path)
                except Exception as exc:  # pragma: no cover - the assertion below is the contract
                    errors.append(exc)

            with patch.object(logger_module, "atomic_write_registry", side_effect=delayed_atomic_write):
                threads = [
                    threading.Thread(target=worker, args=("uuc-a",)),
                    threading.Thread(target=worker, args=("uuc-b",)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

            self.assertEqual(errors, [])
            loaded = load_registry(registry_path)
            self.assertEqual(len(loaded["unmet_use_case"]), 2)
            self.assertCountEqual(
                [entry["id"] for entry in loaded["unmet_use_case"]],
                ["uuc-a", "uuc-b"],
            )

    def test_initialize_registry_serializes_first_write_against_concurrent_record(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            original_atomic_write = logger_module.atomic_write_registry
            empty_write_entered = threading.Event()
            allow_empty_write = threading.Event()
            record_write_entered = threading.Event()
            errors: list[Exception] = []

            def delayed_atomic_write(path: Path, payload: dict[str, object]) -> Path:
                if path == registry_path and payload.get("unmet_use_case") == []:
                    empty_write_entered.set()
                    self.assertTrue(allow_empty_write.wait(1.0))
                elif path == registry_path:
                    record_write_entered.set()
                return original_atomic_write(path, payload)

            def initialize_worker() -> None:
                try:
                    initialize_registry(registry_path)
                except Exception as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            def record_worker() -> None:
                try:
                    record_unmet_use_case(_record(id="uuc-race"), path=registry_path)
                except Exception as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            with patch.object(logger_module, "atomic_write_registry", side_effect=delayed_atomic_write):
                init_thread = threading.Thread(target=initialize_worker)
                init_thread.start()
                self.assertTrue(empty_write_entered.wait(1.0))

                record_thread = threading.Thread(target=record_worker)
                record_thread.start()

                self.assertFalse(
                    record_write_entered.wait(0.1),
                    "record write should stay blocked until registry initialization finishes",
                )

                allow_empty_write.set()
                init_thread.join()
                record_thread.join()

            self.assertEqual(errors, [])
            loaded = load_registry(registry_path)
            self.assertEqual(len(loaded["unmet_use_case"]), 1)
            self.assertEqual(loaded["unmet_use_case"][0]["id"], "uuc-race")

    def test_record_recovers_stale_registry_lock_from_dead_process(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            lock_path = registry_path.with_suffix(".toml.lock")
            lock_path.write_text(
                json.dumps({"pid": 424242, "created_at": 0.0}),
                encoding="utf-8",
            )

            with patch.object(logger_module, "_pid_is_running", return_value=False):
                stored = record_unmet_use_case(_record(), path=registry_path)

            self.assertEqual(stored["id"], "uuc-demo-001")
            self.assertFalse(lock_path.exists())
            loaded = load_registry(registry_path)
            self.assertEqual(len(loaded["unmet_use_case"]), 1)

    def test_record_recovers_stale_registry_lock_when_pid_was_reused(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            lock_path = registry_path.with_suffix(".toml.lock")
            lock_path.write_text(
                json.dumps(
                    {
                        "pid": 424242,
                        "created_at": 0.0,
                        "process_identity": {"platform": "test", "token": "old-owner"},
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(logger_module, "_pid_is_running", return_value=True),
                patch.object(
                    logger_module,
                    "_read_process_identity",
                    return_value={"platform": "test", "token": "new-owner"},
                ),
            ):
                stored = record_unmet_use_case(_record(), path=registry_path)

            self.assertEqual(stored["id"], "uuc-demo-001")
            self.assertFalse(lock_path.exists())
            loaded = load_registry(registry_path)
            self.assertEqual(len(loaded["unmet_use_case"]), 1)

    def test_registry_lock_keeps_live_owner_when_identity_matches(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            lock_path = registry_path.with_suffix(".toml.lock")
            lock_path.write_text(
                json.dumps(
                    {
                        "pid": 424242,
                        "created_at": 0.0,
                        "process_identity": {"platform": "test", "token": "same-owner"},
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(logger_module, "_pid_is_running", return_value=True),
                patch.object(
                    logger_module,
                    "_read_process_identity",
                    return_value={"platform": "test", "token": "same-owner"},
                ),
            ):
                with self.assertRaises(logger_module.OperationalSignalsLogError):
                    with logger_module._registry_lock(
                        registry_path,
                        timeout_seconds=0.0,
                        poll_seconds=0.0,
                    ):
                        self.fail("lock acquisition should stay blocked for the live owner")

            self.assertTrue(lock_path.exists())

    def test_atomic_write_registry_cleans_up_temp_file_when_replace_fails(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            original_text = registry_path.read_text(encoding="utf-8")
            original_replace = Path.replace

            def failing_replace(self: Path, target: str | Path) -> Path:
                if Path(target) == registry_path:
                    raise OSError("boom")
                return original_replace(self, target)

            with patch.object(Path, "replace", autospec=True, side_effect=failing_replace):
                with self.assertRaises(OSError):
                    schema_module.atomic_write_registry(
                        registry_path,
                        {
                            "schema_version": "1",
                            "unmet_use_case": [_record(id="uuc-fail")],
                        },
                    )

            self.assertEqual(registry_path.read_text(encoding="utf-8"), original_text)
            self.assertEqual(list(registry_path.parent.glob("*.tmp")), [])

    def test_atomic_write_registry_cleans_up_temp_file_when_temp_write_fails(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            original_text = registry_path.read_text(encoding="utf-8")
            original_named_temporary_file = schema_module.tempfile.NamedTemporaryFile

            class _FailingHandle:
                def __init__(self, wrapped) -> None:
                    self._wrapped = wrapped
                    self.name = wrapped.name

                def write(self, _text: str) -> int:
                    raise OSError("boom")

                def __getattr__(self, name: str):
                    return getattr(self._wrapped, name)

            class _FailingNamedTemporaryFile:
                def __init__(self, *args, **kwargs) -> None:
                    self._wrapped = original_named_temporary_file(*args, **kwargs)

                def __enter__(self):
                    wrapped = self._wrapped.__enter__()
                    return _FailingHandle(wrapped)

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return self._wrapped.__exit__(exc_type, exc, tb)

            with patch.object(
                schema_module.tempfile,
                "NamedTemporaryFile",
                side_effect=lambda *args, **kwargs: _FailingNamedTemporaryFile(*args, **kwargs),
            ):
                with self.assertRaises(OSError):
                    schema_module.atomic_write_registry(
                        registry_path,
                        {
                            "schema_version": "1",
                            "unmet_use_case": [_record(id="uuc-write-fail")],
                        },
                    )

            self.assertEqual(registry_path.read_text(encoding="utf-8"), original_text)
            self.assertEqual(list(registry_path.parent.glob("*.tmp")), [])
