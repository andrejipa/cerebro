from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from core.digests import sha256_bytes, sha256_file, sha256_text


class DigestHelpersTests(unittest.TestCase):
    def test_sha256_text_matches_hashlib_utf8_digest(self) -> None:
        content = "hello-\u00e7-runtime"
        self.assertEqual(sha256_text(content), hashlib.sha256(content.encode("utf-8")).hexdigest())

    def test_sha256_bytes_matches_hashlib_digest(self) -> None:
        payload = b"\x00hello-\xffpayload"
        self.assertEqual(sha256_bytes(payload), hashlib.sha256(payload).hexdigest())

    def test_sha256_file_matches_hashlib_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "payload.bin"
            payload = (b"abc123\n" * 1024) + b"\x00\xff"
            path.write_bytes(payload)
            self.assertEqual(sha256_file(path), hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
