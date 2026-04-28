from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import unittest
from dataclasses import replace
from pathlib import Path

from core.material_scope import (
    FilePreimage,
    MaterialScopeError,
    MaterialScopeManifest,
    assert_effects_within_scope,
    snapshot_material_scope,
    verify_commit_scope,
    verify_material_scope,
)


class MaterialScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        import platform as _platform
        _tmp_base = Path(os.environ.get("TEMP") or (".tmp_test" if _platform.system() == "Windows" else "/tmp/cerebro_material_scope_tests"))
        base = _tmp_base.resolve()
        base.mkdir(parents=True, exist_ok=True)
        self.root = base / f"material_scope_{secrets.token_hex(8)}"
        self.root.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def write_file(self, relative_path: str, content: bytes) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def test_snapshot_captures_existing_and_missing_files_distinctly(self) -> None:
        self.write_file("a.txt", b"alpha")

        manifest = snapshot_material_scope(self.root, ["a.txt", "missing.txt"])

        by_path = {preimage.path: preimage for preimage in manifest.files}
        self.assertEqual(manifest.root, str(self.root.resolve()))
        self.assertEqual(by_path["a.txt"].exists, True)
        self.assertEqual(by_path["a.txt"].sha256, "sha256:" + hashlib.sha256(b"alpha").hexdigest())
        self.assertEqual(by_path["a.txt"].size, 5)
        self.assertEqual(by_path["a.txt"].file_type, "file")
        self.assertEqual(by_path["missing.txt"], FilePreimage("missing.txt", False, "", None, "missing"))

    def test_verify_accepts_unchanged_preimages(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt", "missing.txt"])

        verify_material_scope(manifest)

    def test_verify_detects_content_mutation(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt"])
        self.write_file("a.txt", b"beta")

        with self.assertRaisesRegex(MaterialScopeError, "material preimage changed: a.txt"):
            verify_material_scope(manifest)

    def test_verify_detects_deleted_file(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt"])
        (self.root / "a.txt").unlink()

        with self.assertRaisesRegex(MaterialScopeError, "material preimage changed: a.txt"):
            verify_material_scope(manifest)

    def test_verify_detects_created_file_for_missing_preimage(self) -> None:
        manifest = snapshot_material_scope(self.root, ["new.txt"])
        self.write_file("new.txt", b"created")

        with self.assertRaisesRegex(MaterialScopeError, "material preimage changed: new.txt"):
            verify_material_scope(manifest)

    def test_empty_existing_file_is_not_equal_to_missing_file(self) -> None:
        self.write_file("empty.txt", b"")

        manifest = snapshot_material_scope(self.root, ["empty.txt", "missing.txt"])
        by_path = {preimage.path: preimage for preimage in manifest.files}

        self.assertTrue(by_path["empty.txt"].exists)
        self.assertEqual(by_path["empty.txt"].sha256, "sha256:" + hashlib.sha256(b"").hexdigest())
        self.assertNotEqual(by_path["empty.txt"], by_path["missing.txt"])

    def test_absolute_paths_fail_closed(self) -> None:
        absolute = str((self.root / "a.txt").resolve())

        with self.assertRaisesRegex(MaterialScopeError, "material path must be relative"):
            snapshot_material_scope(self.root, [absolute])

    def test_traversal_paths_fail_closed(self) -> None:
        for unsafe in ("../outside.txt", "nested/../inside.txt", "./inside.txt"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaisesRegex(MaterialScopeError, "traversal-free"):
                    snapshot_material_scope(self.root, [unsafe])

    def test_duplicate_normalized_paths_fail_closed(self) -> None:
        with self.assertRaisesRegex(MaterialScopeError, "duplicate material scope paths: nested/file.txt"):
            snapshot_material_scope(self.root, ["nested/file.txt", "nested\\file.txt"])

    def test_directory_paths_fail_closed(self) -> None:
        (self.root / "folder").mkdir()

        with self.assertRaisesRegex(MaterialScopeError, "material path is not a file: folder"):
            snapshot_material_scope(self.root, ["folder"])

    def test_effects_inside_scope_are_returned_normalized(self) -> None:
        self.write_file("nested/file.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["nested/file.txt"])

        touched = assert_effects_within_scope(manifest, ["nested\\file.txt"])

        self.assertEqual(touched, ("nested/file.txt",))

    def test_effects_outside_scope_fail_closed(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt"])

        with self.assertRaisesRegex(MaterialScopeError, "material effects outside declared scope: b.txt"):
            assert_effects_within_scope(manifest, ["a.txt", "b.txt"])

    def test_commit_scope_checks_effects_before_preimage(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt"])
        self.write_file("a.txt", b"beta")

        with self.assertRaisesRegex(MaterialScopeError, "material effects outside declared scope: b.txt"):
            verify_commit_scope(manifest, ["b.txt"])

    def test_commit_scope_detects_preimage_drift_for_in_scope_effects(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt"])
        self.write_file("a.txt", b"beta")

        with self.assertRaisesRegex(MaterialScopeError, "material preimage changed: a.txt"):
            verify_commit_scope(manifest, ["a.txt"])

    def test_manifest_duplicate_paths_fail_closed(self) -> None:
        preimage = FilePreimage("a.txt", False, "", None, "missing")
        manifest = MaterialScopeManifest(str(self.root.resolve()), (preimage, preimage))

        with self.assertRaisesRegex(MaterialScopeError, "duplicate material manifest path: a.txt"):
            verify_material_scope(manifest)

    def test_manifest_shape_rejects_noncanonical_preimage_path(self) -> None:
        manifest = MaterialScopeManifest(
            str(self.root.resolve()),
            (FilePreimage("nested/../a.txt", False, "", None, "missing"),),
        )

        with self.assertRaisesRegex(MaterialScopeError, "traversal-free"):
            verify_material_scope(manifest)

    def test_manifest_shape_rejects_invalid_existing_digest(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt"])
        invalid = replace(manifest.files[0], sha256="not-a-digest")

        with self.assertRaisesRegex(MaterialScopeError, "sha256 digest"):
            verify_material_scope(MaterialScopeManifest(manifest.root, (invalid,)))

    def test_manifest_shape_rejects_truncated_existing_digest(self) -> None:
        self.write_file("a.txt", b"alpha")
        manifest = snapshot_material_scope(self.root, ["a.txt"])
        invalid = replace(manifest.files[0], sha256="sha256:abc")

        with self.assertRaisesRegex(MaterialScopeError, "sha256 digest"):
            verify_material_scope(MaterialScopeManifest(manifest.root, (invalid,)))


if __name__ == "__main__":
    unittest.main()
