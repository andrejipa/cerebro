from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from core.state_session_artifacts_service import StateSessionArtifactsService
from core.state_store import StateStoreError


def _read_optional_file_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_bytes(payload)
    os.replace(tmp_path, path)


class StateSessionArtifactsServiceTests(unittest.TestCase):
    def _build_service(self, root: Path, session_path: Path) -> StateSessionArtifactsService:
        return StateSessionArtifactsService(
            root=root,
            session_path=session_path,
            read_optional_file_bytes=_read_optional_file_bytes,
            write_bytes_atomic=_write_bytes_atomic,
            error_cls=StateStoreError,
        )

    def test_write_and_read_session_claim_round_trip_on_file_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, root / ".cerebro" / "session.local.json")
            claim_data = {
                "claim_id": "claim-1",
                "session_id": "session-1",
                "root_sha256": hashlib.sha256(str(root).encode("utf-8")).hexdigest(),
                "session_token_sha256": "a" * 64,
                "live_proof_id": "proof-1",
                "session_live_proof_sha256": "b" * 64,
                "owner_binding_sha256": "c" * 64,
            }

            service.write_session_claim(claim_data)
            loaded_claim, claim_errors = service.read_session_claim_file("claim-1")

            self.assertEqual(claim_errors, [])
            self.assertEqual(loaded_claim, claim_data)
            self.assertTrue(service.session_claim_path("claim-1").exists())

    def test_write_and_validate_session_live_proof_round_trip_on_file_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, root / ".cerebro" / "session.local.json")
            live_proof = "proof-token"
            proof_data = {
                "proof_id": "proof-1",
                "session_id": "session-1",
                "root_sha256": hashlib.sha256(str(root).encode("utf-8")).hexdigest(),
                "session_live_proof": live_proof,
            }
            claim_data = {
                "claim_id": "claim-1",
                "session_id": "session-1",
                "root_sha256": proof_data["root_sha256"],
                "session_token_sha256": "a" * 64,
                "live_proof_id": "proof-1",
                "session_live_proof_sha256": hashlib.sha256(live_proof.encode("utf-8")).hexdigest(),
                "owner_binding_sha256": "c" * 64,
            }
            session_data = {
                "session_id": "session-1",
                "owner_claim_id": "claim-1",
            }

            service.write_session_live_proof(proof_data)
            loaded_proof, proof_errors = service.read_validated_session_live_proof(session_data, claim_data)

            self.assertEqual(proof_errors, [])
            self.assertEqual(loaded_proof, proof_data)
            self.assertTrue(service.session_live_proof_path("proof-1").exists())

    def test_capture_and_restore_session_claim_snapshot_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            service = self._build_service(root, root / ".cerebro" / "session.local.json")
            original = (json.dumps({"claim_id": "claim-1"}) + "\n").encode("utf-8")
            updated = (json.dumps({"claim_id": "claim-2"}) + "\n").encode("utf-8")

            service.write_session_claim_bytes("claim-1", original, backend="file")
            snapshot = service.capture_session_claim_snapshot("claim-1", label="external session claim")
            service.write_session_claim_bytes("claim-1", updated, backend="file")
            self.assertEqual(service.read_optional_session_claim_bytes("claim-1", backend="file"), updated)

            self.assertIsNotNone(snapshot)
            service.restore_session_claim_snapshot(snapshot)

            self.assertEqual(service.read_optional_session_claim_bytes("claim-1", backend="file"), original)

    def test_read_session_file_reports_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            session_path = root / ".cerebro" / "session.local.json"
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text("{invalid json", encoding="utf-8")
            service = self._build_service(root, session_path)

            session_data, session_errors = service.read_session_file()

            self.assertIsNone(session_data)
            self.assertEqual(session_errors[0]["code"], "session_invalid_json")


if __name__ == "__main__":
    unittest.main()
