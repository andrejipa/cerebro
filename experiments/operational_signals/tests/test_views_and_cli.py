from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import threading
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments.operational_signals.analyzer import build_analysis
from experiments.operational_signals.cli import main
from experiments.operational_signals.logger import initialize_registry, record_unmet_use_case
from experiments.operational_signals import report as report_module
from experiments.operational_signals.report import write_report
from experiments.operational_signals.schema import SchemaError
from experiments.operational_signals.tests._workspace_temp import workspace_tempdir
from experiments.operational_signals.views import filter_records, render_json, render_markdown


def _record(record_id: str, *, project: str = "demo", failure_mode: str = "DISCOVERY_COST_TOO_HIGH", repeat_count: int = 2):
    return {
        "id": record_id,
        "timestamp": "2026-04-20T18:00:00Z",
        "project_context": project,
        "task_description": "recover evidence",
        "query_or_need": "where is the state",
        "surface_used": ["analyze"],
        "failure_mode": failure_mode,
        "manual_workaround": "opened more files",
        "operational_cost": {
            "minutes_spent": 12,
            "extra_files_opened": 5,
            "manual_search_rounds": 3,
        },
        "repeat_count": repeat_count,
        "evidence": ["README.md"],
        "confidence": "medium",
        "notes": "",
    }


class ViewsAndCliTests(unittest.TestCase):
    def test_renderers_and_filters_are_stable(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1", project="alpha"), path=registry_path)
            record_unmet_use_case(_record("uuc-2", project="beta", repeat_count=1), path=registry_path)
            analysis = build_analysis(registry_path)

            filtered = filter_records(analysis["records"], project="alpha", candidate_only=True)
            self.assertEqual(len(filtered), 1)
            self.assertIn("derived-observability-only", render_markdown(analysis))
            rendered_json = render_json(analysis)
            self.assertEqual(json.loads(rendered_json)["totals"]["count"], 2)

    def test_cli_report_and_stats_return_json(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1"), path=registry_path)

            report_buffer = io.StringIO()
            with redirect_stdout(report_buffer):
                exit_code = main(["--registry", str(registry_path), "report", "--format", "json"])
            self.assertEqual(exit_code, 0)
            payload = json.loads(report_buffer.getvalue())
            self.assertEqual(payload["authority"], "derived-observability-only")

            stats_buffer = io.StringIO()
            with redirect_stdout(stats_buffer):
                exit_code = main(["--registry", str(registry_path), "stats", "--by", "project", "--format", "json"])
            self.assertEqual(exit_code, 0)
            stats_payload = json.loads(stats_buffer.getvalue())
            self.assertIn("demo", stats_payload)

    def test_cli_view_recomputes_aggregates_for_filtered_records(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1", project="alpha", repeat_count=2), path=registry_path)
            record_unmet_use_case(_record("uuc-2", project="beta", repeat_count=1), path=registry_path)

            view_buffer = io.StringIO()
            with redirect_stdout(view_buffer):
                exit_code = main(["--registry", str(registry_path), "view", "--project", "alpha", "--format", "json"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(view_buffer.getvalue())
            self.assertEqual(len(payload["records"]), 1)
            self.assertEqual(payload["totals"]["count"], 1)
            self.assertEqual(payload["totals"]["candidate_trigger_count"], 1)
            self.assertEqual(list(payload["by_project_context"].keys()), ["alpha"])
            self.assertEqual(payload["by_project_context"]["alpha"]["count"], 1)
            self.assertEqual(len(payload["candidate_triggers"]), 1)
            self.assertEqual(payload["candidate_triggers"][0]["project_context"], "alpha")
            self.assertEqual(len(payload["top_repeaters"]), 1)
            self.assertEqual(payload["top_repeaters"][0]["project_context"], "alpha")

    def test_cli_report_does_not_create_registry_for_read_only_command(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"

            report_buffer = io.StringIO()
            with redirect_stdout(report_buffer):
                exit_code = main(["--registry", str(registry_path), "report", "--format", "json"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(report_buffer.getvalue())
            self.assertEqual(payload["totals"]["count"], 0)
            self.assertFalse(registry_path.exists())

    def test_write_report_materializes_markdown_and_json(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            markdown_path = temp_root / "signals.md"
            json_path = temp_root / "signals.json"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1"), path=registry_path)

            report = write_report(registry_path=registry_path, markdown_path=markdown_path, json_path=json_path)
            self.assertEqual(report["totals"]["count"], 1)
            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())

    def test_write_report_rejects_output_paths_inside_dot_cerebro(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            markdown_path = temp_root / ".cerebro" / "signals.md"
            json_path = temp_root / ".cerebro" / "signals.json"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1"), path=registry_path)

            with self.assertRaises(SchemaError):
                write_report(registry_path=registry_path, markdown_path=markdown_path, json_path=json_path)

            self.assertFalse(markdown_path.exists())
            self.assertFalse(json_path.exists())

    def test_write_report_restores_previous_pair_when_second_write_fails(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            markdown_path = temp_root / "signals.md"
            json_path = temp_root / "signals.json"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1"), path=registry_path)
            markdown_path.write_text("# old markdown", encoding="utf-8")
            json_path.write_text('{"old": true}', encoding="utf-8")
            original_write_text_atomic = report_module._write_text_atomic

            def fail_on_json(path: Path, text: str) -> None:
                if path == json_path and text != '{"old": true}':
                    raise OSError("simulated json write failure")
                original_write_text_atomic(path, text)

            with patch(
                "experiments.operational_signals.report._write_text_atomic",
                side_effect=fail_on_json,
            ):
                with self.assertRaises(OSError):
                    write_report(registry_path=registry_path, markdown_path=markdown_path, json_path=json_path)

            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# old markdown")
            self.assertEqual(json_path.read_text(encoding="utf-8"), '{"old": true}')

    def test_write_report_cleans_up_fresh_outputs_when_second_write_fails_without_previous_files(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            markdown_path = temp_root / "signals.md"
            json_path = temp_root / "signals.json"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1"), path=registry_path)
            original_write_text_atomic = report_module._write_text_atomic
            call_count = 0

            def fail_on_second_write(path: Path, text: str) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated json write failure")
                original_write_text_atomic(path, text)

            with patch(
                "experiments.operational_signals.report._write_text_atomic",
                side_effect=fail_on_second_write,
            ):
                with self.assertRaises(OSError):
                    write_report(registry_path=registry_path, markdown_path=markdown_path, json_path=json_path)

            self.assertFalse(markdown_path.exists())
            self.assertFalse(json_path.exists())

    def test_write_report_attempts_both_restores_when_first_restore_fails(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            markdown_path = temp_root / "signals.md"
            json_path = temp_root / "signals.json"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1"), path=registry_path)
            markdown_path.write_text("# old markdown", encoding="utf-8")
            json_path.write_text('{"old": true}', encoding="utf-8")
            original_write_text_atomic = report_module._write_text_atomic
            call_order: list[str] = []

            def fail_on_json_write_and_markdown_restore(path: Path, text: str) -> None:
                call_order.append(path.name)
                if path == json_path and text != '{"old": true}':
                    raise OSError("simulated json write failure")
                if path == markdown_path and text == "# old markdown":
                    raise OSError("simulated markdown restore failure")
                original_write_text_atomic(path, text)

            with patch(
                "experiments.operational_signals.report._write_text_atomic",
                side_effect=fail_on_json_write_and_markdown_restore,
            ):
                with self.assertRaises(ExceptionGroup):
                    write_report(registry_path=registry_path, markdown_path=markdown_path, json_path=json_path)

            self.assertEqual(json_path.read_text(encoding="utf-8"), '{"old": true}')
            self.assertIn(json_path.name, call_order)
            self.assertGreaterEqual(call_order.count(json_path.name), 2)

    def test_write_report_serializes_concurrent_writers_across_rollback(self) -> None:
        with workspace_tempdir() as temp_root:
            markdown_path = temp_root / "signals.md"
            json_path = temp_root / "signals.json"
            markdown_path.write_text("# old markdown", encoding="utf-8")
            json_path.write_text('{"old": true}', encoding="utf-8")

            first_markdown_written = threading.Event()
            release_first_writer = threading.Event()
            second_started_writing = threading.Event()
            original_write_text_atomic = report_module._write_text_atomic
            first_errors: list[Exception] = []
            second_errors: list[Exception] = []

            def fake_build_report(path: str | Path | None = None) -> dict[str, str]:
                return {"label": Path(path).stem if path else "default"}

            def fake_render_markdown(report: dict[str, str]) -> str:
                return f"md:{report['label']}"

            def fake_render_json(report: dict[str, str]) -> str:
                return f"json:{report['label']}"

            def coordinated_write(path: Path, text: str) -> None:
                thread_name = threading.current_thread().name
                if thread_name == "first-writer" and path == markdown_path:
                    original_write_text_atomic(path, text)
                    first_markdown_written.set()
                    if not release_first_writer.wait(2):
                        raise TimeoutError("timed out waiting to release first writer")
                    return
                if thread_name == "first-writer" and path == json_path:
                    if text == "json:first":
                        raise OSError("simulated first writer json failure")
                if thread_name == "second-writer":
                    second_started_writing.set()
                original_write_text_atomic(path, text)

            def run_first_writer() -> None:
                try:
                    write_report(
                        registry_path=temp_root / "first.toml",
                        markdown_path=markdown_path,
                        json_path=json_path,
                    )
                except Exception as exc:
                    first_errors.append(exc)

            def run_second_writer() -> None:
                try:
                    write_report(
                        registry_path=temp_root / "second.toml",
                        markdown_path=markdown_path,
                        json_path=json_path,
                    )
                except Exception as exc:
                    second_errors.append(exc)

            with patch("experiments.operational_signals.report.build_report", side_effect=fake_build_report):
                with patch("experiments.operational_signals.report.render_markdown", side_effect=fake_render_markdown):
                    with patch("experiments.operational_signals.report.render_json", side_effect=fake_render_json):
                        with patch(
                            "experiments.operational_signals.report._write_text_atomic",
                            side_effect=coordinated_write,
                        ):
                            first_thread = threading.Thread(target=run_first_writer, name="first-writer")
                            second_thread = threading.Thread(target=run_second_writer, name="second-writer")
                            first_thread.start()
                            self.assertTrue(first_markdown_written.wait(2))
                            second_thread.start()
                            self.assertFalse(second_started_writing.wait(0.2))
                            release_first_writer.set()
                            first_thread.join(timeout=2)
                            second_thread.join(timeout=2)

            self.assertFalse(first_thread.is_alive())
            self.assertFalse(second_thread.is_alive())
            self.assertEqual(len(first_errors), 1)
            self.assertIsInstance(first_errors[0], (OSError, ExceptionGroup))
            self.assertEqual(second_errors, [])
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "md:second")
            self.assertEqual(json_path.read_text(encoding="utf-8"), "json:second")

    def test_write_report_serializes_overlapping_partial_writer_across_rollback(self) -> None:
        with workspace_tempdir() as temp_root:
            markdown_path = temp_root / "signals.md"
            json_path = temp_root / "signals.json"
            markdown_path.write_text("# old markdown", encoding="utf-8")
            json_path.write_text('{"old": true}', encoding="utf-8")

            first_markdown_written = threading.Event()
            release_first_writer = threading.Event()
            second_started_writing = threading.Event()
            original_write_text_atomic = report_module._write_text_atomic
            first_errors: list[Exception] = []
            second_errors: list[Exception] = []

            def fake_build_report(path: str | Path | None = None) -> dict[str, str]:
                return {"label": Path(path).stem if path else "default"}

            def fake_render_markdown(report: dict[str, str]) -> str:
                return f"md:{report['label']}"

            def fake_render_json(report: dict[str, str]) -> str:
                return f"json:{report['label']}"

            def coordinated_write(path: Path, text: str) -> None:
                thread_name = threading.current_thread().name
                if thread_name == "first-writer" and path == markdown_path:
                    original_write_text_atomic(path, text)
                    first_markdown_written.set()
                    if not release_first_writer.wait(2):
                        raise TimeoutError("timed out waiting to release first writer")
                    return
                if thread_name == "first-writer" and path == json_path:
                    raise OSError("simulated first writer json failure")
                if thread_name == "second-writer" and path == markdown_path:
                    second_started_writing.set()
                original_write_text_atomic(path, text)

            def run_first_writer() -> None:
                try:
                    write_report(
                        registry_path=temp_root / "first.toml",
                        markdown_path=markdown_path,
                        json_path=json_path,
                    )
                except Exception as exc:
                    first_errors.append(exc)

            def run_second_writer() -> None:
                try:
                    write_report(
                        registry_path=temp_root / "second.toml",
                        markdown_path=markdown_path,
                    )
                except Exception as exc:
                    second_errors.append(exc)

            with patch("experiments.operational_signals.report.build_report", side_effect=fake_build_report):
                with patch("experiments.operational_signals.report.render_markdown", side_effect=fake_render_markdown):
                    with patch("experiments.operational_signals.report.render_json", side_effect=fake_render_json):
                        with patch(
                            "experiments.operational_signals.report._write_text_atomic",
                            side_effect=coordinated_write,
                        ):
                            first_thread = threading.Thread(target=run_first_writer, name="first-writer")
                            second_thread = threading.Thread(target=run_second_writer, name="second-writer")
                            first_thread.start()
                            self.assertTrue(first_markdown_written.wait(2))
                            second_thread.start()
                            self.assertFalse(second_started_writing.wait(0.2))
                            release_first_writer.set()
                            first_thread.join(timeout=2)
                            second_thread.join(timeout=2)

            self.assertFalse(first_thread.is_alive())
            self.assertFalse(second_thread.is_alive())
            self.assertEqual(len(first_errors), 1)
            self.assertIsInstance(first_errors[0], (OSError, ExceptionGroup))
            self.assertEqual(second_errors, [])
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "md:second")
            self.assertEqual(json_path.read_text(encoding="utf-8"), '{"old": true}')
