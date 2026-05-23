"""Stable test gate profiles for local Cerebro development.

The default Windows temp ACLs in some shells can make raw unittest discovery
fail before the runtime code is exercised. This runner pins temp and session
proof directories inside the workspace before loading tests.
"""

from __future__ import annotations

import argparse
import errno
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_MODULES = (
    "tests.test_architecture",
    "tests.test_cli",
    "tests.test_doctor",
    "tests.test_validate",
    "tests.test_runtime_manager_store",
    "tests.test_runtime_manager_policy",
)

MCP_MODULES = (
    "tests.test_runtime_manager_mcp_stdio",
    "tests.test_runtime_manager_phase8_mcp",
)


def configure_workspace_environment(workspace: Path = REPO_ROOT) -> None:
    workspace = workspace.resolve()
    for name in (".tmp_test", ".tmp_claims", ".tmp_live_proofs"):
        (workspace / name).mkdir(exist_ok=True)
    os.environ["TEMP"] = str((workspace / ".tmp_test").resolve())
    os.environ["TMP"] = os.environ["TEMP"]
    os.environ["CEREBRO_SESSION_CLAIMS_DIR"] = str((workspace / ".tmp_claims").resolve())
    os.environ["CEREBRO_SESSION_LIVE_PROOFS_DIR"] = str((workspace / ".tmp_live_proofs").resolve())
    existing_pythonpath = os.environ.get("PYTHONPATH")
    root_entry = str(workspace)
    if existing_pythonpath:
        paths = existing_pythonpath.split(os.pathsep)
        if root_entry not in paths:
            os.environ["PYTHONPATH"] = os.pathsep.join([root_entry, *paths])
    else:
        os.environ["PYTHONPATH"] = root_entry
    tempfile.mkdtemp = _workspace_mkdtemp


def _workspace_mkdtemp(suffix=None, prefix=None, dir=None):
    prefix, suffix, dir, output_type = tempfile._sanitize_params(prefix, suffix, dir)
    names = tempfile._get_candidate_names()
    if output_type is bytes:
        names = map(os.fsencode, names)
    for _ in range(tempfile.TMP_MAX):
        name = next(names)
        path = os.path.join(dir, prefix + name + suffix)
        sys.audit("tempfile.mkdtemp", path)
        try:
            os.mkdir(path, 0o777)
        except FileExistsError:
            continue
        except PermissionError:
            if os.name == "nt" and os.path.isdir(dir) and os.access(dir, os.W_OK):
                continue
            raise
        return os.path.abspath(path)
    raise FileExistsError(errno.EEXIST, "No usable temporary directory name found")


def build_suite(profile: str) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    if profile == "base":
        return loader.loadTestsFromNames(BASE_MODULES)
    if profile == "mcp":
        if importlib.util.find_spec("mcp") is None:
            raise RuntimeError('MCP extra is not installed; run `python -m pip install -e ".[mcp]"`.')
        return loader.loadTestsFromNames(MCP_MODULES)
    if profile == "full":
        return loader.discover("tests")
    raise ValueError(f"unknown profile: {profile}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run stable Cerebro test gate profiles.")
    parser.add_argument("--profile", choices=("base", "mcp", "full"), default="base")
    parser.add_argument("-v", "--verbose", action="store_true", help="run unittest with verbosity=2")
    args = parser.parse_args(argv)

    configure_workspace_environment()
    try:
        suite = build_suite(args.profile)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    print(
        f"SUMMARY profile={args.profile} ran={result.testsRun} "
        f"failures={len(result.failures)} errors={len(result.errors)} skipped={len(result.skipped)}"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
