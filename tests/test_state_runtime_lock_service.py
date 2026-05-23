from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core.state_runtime_lock_service import StateRuntimeLockService
from core.state_store import StateStoreError


class StateRuntimeLockServiceTests(unittest.TestCase):
    def _build_service(
        self,
        root: Path,
        *,
        timeout_seconds: float = 5.0,
        poll_seconds: float = 0.01,
    ) -> StateRuntimeLockService:
        cerebro_dir = root / ".cerebro"
        lock_path = cerebro_dir / "runtime.lock"
        return StateRuntimeLockService(
            cerebro_dir=cerebro_dir,
            lock_path=lock_path,
            error_cls=StateStoreError,
            timeout_seconds=lambda: timeout_seconds,
            poll_seconds=lambda: poll_seconds,
            release_retry_limit=lambda: 3,
            pid_probe=lambda pid: os.kill(pid, 0),
            monotonic=lambda: time.monotonic(),
            sleep_fn=lambda seconds: time.sleep(seconds),
            get_pid=lambda: os.getpid(),
        )

    def test_runtime_lock_recovers_stale_lock_when_pid_probe_is_invalid_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, timeout_seconds=0.0, poll_seconds=0.0)
            service.lock_path.parent.mkdir(parents=True, exist_ok=True)
            service.lock_path.write_text("999999", encoding="utf-8")
            probe_error = OSError(22, "invalid parameter")
            probe_error.winerror = 87

            with mock.patch("os.kill", side_effect=probe_error):
                with service.runtime_lock():
                    self.assertTrue(service.lock_path.exists())

            self.assertFalse(service.lock_path.exists())

    def test_runtime_lock_timeout_reports_stale_lock_guidance_when_owner_still_looks_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, timeout_seconds=0.0, poll_seconds=0.0)
            service.lock_path.parent.mkdir(parents=True, exist_ok=True)
            service.lock_path.write_text("999999", encoding="utf-8")

            with mock.patch("os.kill", return_value=None):
                with self.assertRaises(StateStoreError) as exc_info:
                    with service.runtime_lock():
                        self.fail("service should not acquire a live-looking stale lock")

            message = str(exc_info.exception)
            self.assertIn("runtime.lock", message)
            self.assertIn("stale lock", message)
            self.assertEqual(service.lock_path.read_text(encoding="utf-8"), "999999")

    def test_runtime_lock_is_reentrant_within_the_same_service_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, timeout_seconds=0.0, poll_seconds=0.0)

            with service.runtime_lock():
                self.assertEqual(service._lock_depth, 1)
                self.assertTrue(service.process_runtime_lock_is_held())
                self.assertTrue(service.lock_path.exists())

                with service.runtime_lock():
                    self.assertEqual(service._lock_depth, 2)
                    self.assertTrue(service.process_runtime_lock_is_held())
                    self.assertTrue(service.lock_path.exists())

                self.assertEqual(service._lock_depth, 1)
                self.assertTrue(service.process_runtime_lock_is_held())
                self.assertTrue(service.lock_path.exists())

            self.assertEqual(service._lock_depth, 0)
            self.assertFalse(service.process_runtime_lock_is_held())
            self.assertFalse(service.lock_path.exists())

    def test_register_and_unregister_process_runtime_lock_track_local_hold_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root)

            self.assertFalse(service.process_runtime_lock_is_held())
            service.register_process_runtime_lock()
            self.assertTrue(service.process_runtime_lock_is_held())
            service.register_process_runtime_lock()
            self.assertTrue(service.process_runtime_lock_is_held())
            service.unregister_process_runtime_lock()
            self.assertTrue(service.process_runtime_lock_is_held())
            service.unregister_process_runtime_lock()
            self.assertFalse(service.process_runtime_lock_is_held())

    def test_try_recover_invalid_runtime_lock_removes_aged_malformed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, timeout_seconds=1.0, poll_seconds=0.0)
            service.lock_path.parent.mkdir(parents=True, exist_ok=True)
            service.lock_path.write_text("not-a-pid", encoding="utf-8")
            old_time = time.time() - 10
            os.utime(service.lock_path, (old_time, old_time))

            self.assertTrue(service.try_recover_invalid_runtime_lock())
            self.assertFalse(service.lock_path.exists())

    def test_try_recover_invalid_runtime_lock_preserves_recent_malformed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, timeout_seconds=5.0, poll_seconds=0.0)
            service.lock_path.parent.mkdir(parents=True, exist_ok=True)
            service.lock_path.write_text("not-a-pid", encoding="utf-8")

            self.assertFalse(service.try_recover_invalid_runtime_lock())
            self.assertTrue(service.lock_path.exists())

    def test_release_runtime_lock_clears_local_state_even_if_close_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root)
            service._lock_fd = 123
            service._lock_depth = 1
            service.register_process_runtime_lock()

            with mock.patch("os.close", side_effect=OSError("close failed")):
                with mock.patch.object(service, "try_remove_runtime_lock_file", return_value=True) as remove_mock:
                    service.release_runtime_lock()

            self.assertIsNone(service._lock_fd)
            self.assertEqual(service._lock_depth, 0)
            self.assertFalse(service.process_runtime_lock_is_held())
            remove_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
