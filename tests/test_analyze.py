from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from cli.commands.analyze import run_analyze
from cli.commands.init import run_init
from core.state_store import StateStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_session_claim(store: StateStore, claim_id: str) -> dict:
    claim_data, claim_errors = store._read_session_claim_file(claim_id)
    if claim_errors or claim_data is None:
        raise AssertionError(f"expected valid session claim for {claim_id}, got {claim_errors}")
    return claim_data


def read_session_claim_bytes(store: StateStore, claim_id: str, *, backend: str | None = None) -> bytes | None:
    return store._read_optional_session_claim_bytes(claim_id, backend=backend)


class AnalyzeCommandTests(unittest.TestCase):
    def test_analyze_with_valid_state_prints_stable_context_and_opens_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Resume work.",
                    "constraints": ["Do not change API"],
                }
            )
            before = store.read_snapshot()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            after = store.read_snapshot()
            self.assertEqual(exit_code, 0)
            for expected_line in [
                "OK",
                "analysis_ready: continuity context loaded",
                "goal: Ship",
                "summary: Checkpoint is ready.",
                "next_step: Resume work.",
                "constraints: 1",
                "- Do not change API",
                "sources: 1",
                "- tracked.txt",
                f"revision: {before.revision}",
                f"updated_at: {before.checkpoint.updated_at}",
                "validation: ok",
                "session_owner_proof: external_claim",
            ]:
                self.assertIn(expected_line, output)
            self.assertEqual(output.count("session_claim_id: claim-"), 1)
            self.assertNotIn("session_token: ", output)
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.checkpoint, before.checkpoint)
            self.assertEqual(after.sources, before.sources)
            self.assertEqual(after.last_validation.result, "ok")
            self.assertTrue(store.session_path.exists())

    def test_analyze_does_not_emit_session_token_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Resume work.",
                    "constraints": [],
                }
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertNotIn("session_token: ", output)
            session = json.loads(store.session_path.read_text(encoding="utf-8"))
            claim = read_session_claim(store, session["owner_claim_id"])
            claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
            self.assertIsNotNone(claim_bytes)
            self.assertIn("session_token_sha256", claim)

    def test_analyze_emits_session_token_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Resume work.",
                    "constraints": [],
                }
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice", "emit_session_token": True}))

            output = stream.getvalue()
            session = json.loads(store.session_path.read_text(encoding="utf-8"))
            claim = read_session_claim(store, session["owner_claim_id"])
            claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
            self.assertIsNotNone(claim_bytes)
            emitted_token = next(line.split(": ", 1)[1] for line in output.splitlines() if line.startswith("session_token: "))
            self.assertEqual(exit_code, 0)
            self.assertIn("session_token: ", output)
            self.assertEqual(claim["session_token_sha256"], store._hash_session_token(emitted_token))
            self.assertNotIn(emitted_token.encode("utf-8"), claim_bytes)

    def test_analyze_blocks_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            tracked.write_text("changed", encoding="utf-8")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("analysis_blocked", output)
            self.assertIn("source_hash_mismatch", output)
            self.assertFalse(store.session_path.exists())

    def test_analyze_blocks_when_local_session_is_already_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Resume work.",
                    "constraints": ["Do not change API"],
                }
            )
            store.open_session("alice")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "bob"}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("analysis_blocked", output)
            self.assertIn("session_open_conflict", output)
            self.assertIn("session-discard", output)
            session = store.session_path.read_text(encoding="utf-8")
            self.assertIn('"actor": "alice"', session)

    def test_analyze_does_not_treat_restored_discarded_session_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Resume work.",
                    "constraints": ["Do not change API"],
                }
            )
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                session_bytes = store.session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                proof_bytes = None
                claim_data = read_session_claim(store, session["owner_claim_id"])
                if store._session_live_proof_backend() == "wincred":
                    proof_bytes = store._read_optional_session_live_proof_bytes(claim_data["live_proof_id"])
                store.discard_session(expected_session_token=session["session_token"])
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                if proof_bytes is not None:
                    store._write_bytes_atomic(
                        store._session_live_proof_path(claim_data["live_proof_id"]),
                        proof_bytes,
                    )
                store._write_bytes_atomic(store.session_path, session_bytes)
            stream = io.StringIO()

            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_analyze(root, type("Args", (), {"actor": "bob"}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("analysis_blocked", output)
            self.assertIn("session_not_registered", output)
            self.assertNotIn("session_open_conflict", output)

    def test_analyze_without_registered_sources_points_to_import_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("analysis_blocked", output)
            self.assertIn("sources_unregistered", output)
            self.assertIn("Next step: run `cerebro import-context --files ...`", output)
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())

    def test_analyze_does_not_change_revision_or_registered_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            before = store.read_snapshot()

            exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            after = store.read_snapshot()
            self.assertEqual(exit_code, 0)
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.checkpoint, before.checkpoint)
            self.assertEqual(after.sources, before.sources)

    def test_analyze_recovers_from_late_runtime_lock_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            original_unlink = Path.unlink
            cleanup_failures = {"remaining": 3}
            stream = io.StringIO()

            def flaky_unlink(path: Path, *args, **kwargs):
                if Path(path) == store.lock_path and cleanup_failures["remaining"] > 0:
                    cleanup_failures["remaining"] -= 1
                    raise OSError("lock cleanup failed")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.unlink", autospec=True, side_effect=flaky_unlink):
                with redirect_stdout(stream):
                    exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("analysis_ready", output)
            self.assertTrue(store.session_path.exists())
            self.assertFalse(store.lock_path.exists())

    def test_analyze_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "analyze", "--actor", "alice"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("analysis_ready", result.stdout)
            self.assertIn("goal: Goal", result.stdout)
