"""Explicit iteration-commit automation for the Cerebro engineering repo."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from cli.output import print_fail, print_ok, user_error

REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_STATUS_PATH = REPO_ROOT / "docs" / "operations" / "IMPLEMENTATION_STATUS.md"


def run_iteration_commit(root: Path, args=None) -> int:
    requested_paths = list(getattr(args, "path", []) or [])
    try:
        result = build_iteration_commit(requested_paths, repo_root=REPO_ROOT, status_path=IMPLEMENTATION_STATUS_PATH)
    except IterationCommitError as exc:
        print_fail([user_error("iteration_commit_failed", str(exc))])
        return 1

    print_ok(
        [
            "mode: explicit automation",
            f"repo_root: {result['repo_root']}",
            f"message: {result['message']}",
            f"tests: {result['tests']}",
            f"paths: {', '.join(result['paths'])}",
        ]
    )
    return 0


def build_iteration_commit(
    requested_paths: list[str],
    *,
    repo_root: Path,
    status_path: Path,
) -> dict[str, object]:
    resolved_repo_root = Path(repo_root).resolve()
    relative_paths = _normalize_requested_paths(resolved_repo_root, requested_paths)
    _confirm_git_repo_root(resolved_repo_root)
    tests = _run_required_gates(resolved_repo_root)
    message = _build_commit_message(status_path, tests)
    _ensure_clean_index(resolved_repo_root)
    staged_selection = False
    try:
        _stage_paths(resolved_repo_root, relative_paths)
        staged_selection = True
        _ensure_staged_changes(resolved_repo_root, relative_paths)
        _commit(resolved_repo_root, message)
    except Exception:
        if staged_selection:
            _unstage_paths(resolved_repo_root, relative_paths)
        raise
    return {
        "repo_root": str(resolved_repo_root),
        "message": message,
        "tests": str(tests),
        "paths": relative_paths,
    }


class IterationCommitError(RuntimeError):
    """Stable user-facing failure for iteration-commit automation."""


def _normalize_requested_paths(repo_root: Path, requested_paths: list[str]) -> list[str]:
    if not requested_paths:
        raise IterationCommitError("at least one --path is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in requested_paths:
        candidate = Path(raw_path)
        resolved = (repo_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            relative = resolved.relative_to(repo_root)
        except ValueError as exc:
            raise IterationCommitError(f"path is outside the Cerebro repository: {resolved}") from exc
        relative_text = relative.as_posix()
        if relative_text in seen:
            continue
        seen.add(relative_text)
        normalized.append(relative_text)
    return normalized


def _confirm_git_repo_root(repo_root: Path) -> None:
    result = _run_command(["git", "rev-parse", "--show-toplevel"], cwd=repo_root)
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or "git repository root could not be resolved"
        raise IterationCommitError(detail)
    reported_root = Path(result.stdout.strip()).resolve()
    if reported_root != repo_root:
        raise IterationCommitError(
            f"iteration-commit must run from the Cerebro repository root: expected {repo_root}, got {reported_root}"
        )


def _run_required_gates(repo_root: Path) -> int:
    suite_result = _run_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=repo_root)
    if suite_result.returncode != 0:
        detail = _extract_suite_verdict(suite_result) or "full test suite failed"
        raise IterationCommitError(f"full test suite is not green: {detail}")
    tests = _extract_suite_count(suite_result)
    if tests is None:
        raise IterationCommitError("full test suite passed but the test count could not be determined")

    architecture_result = _run_command([sys.executable, "-m", "unittest", "tests.test_architecture", "-v"], cwd=repo_root)
    if architecture_result.returncode != 0:
        detail = _extract_suite_verdict(architecture_result) or "tests.test_architecture failed"
        raise IterationCommitError(f"architecture test suite is not green: {detail}")
    return tests


def _build_commit_message(status_path: Path, tests: int) -> str:
    try:
        text = Path(status_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise IterationCommitError(f"unable to read implementation status: {exc}") from exc

    current_match = re.search(
        r"## Fatia atual\s+.*?- Qual é: `FATIA\s+(\d+)\s+[—-]\s+([^`]+)`\s+.*?- Estado: `([^`]+)`",
        text,
        flags=re.DOTALL,
    )
    if current_match is not None and current_match.group(3).strip() == "concluída":
        iteration_number = current_match.group(1).strip()
        item = current_match.group(2).strip()
        return f"iter-{iteration_number}: {item} — {tests} testes"

    completed_matches = re.findall(r"- Fatia\s+(\d+): `([^`]+)`", text)
    if completed_matches:
        iteration_number, item = completed_matches[-1]
        return f"iter-{iteration_number}: {item.strip()} — {tests} testes"
    raise IterationCommitError("implementation status does not expose a concluded fatia to name the commit")


def _ensure_clean_index(repo_root: Path) -> None:
    result = _run_command(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or "unable to inspect staged changes"
        raise IterationCommitError(detail)
    staged = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if staged:
        raise IterationCommitError(
            "iteration-commit requires a clean index before staging the selected paths"
        )


def _stage_paths(repo_root: Path, relative_paths: list[str]) -> None:
    result = _run_command(["git", "add", "--", *relative_paths], cwd=repo_root)
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or "git add failed"
        raise IterationCommitError(detail)


def _ensure_staged_changes(repo_root: Path, relative_paths: list[str]) -> None:
    result = _run_command(["git", "diff", "--cached", "--name-only", "--", *relative_paths], cwd=repo_root)
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or "unable to inspect staged selection"
        raise IterationCommitError(detail)
    staged = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not staged:
        raise IterationCommitError("selected paths produced no staged changes")


def _commit(repo_root: Path, message: str) -> None:
    result = _run_command(["git", "commit", "-m", message], cwd=repo_root)
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or "git commit failed"
        raise IterationCommitError(detail)


def _unstage_paths(repo_root: Path, relative_paths: list[str]) -> None:
    result = _run_command(["git", "reset", "HEAD", "--", *relative_paths], cwd=repo_root)
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or "git reset failed during iteration-commit cleanup"
        raise IterationCommitError(detail)


def _extract_suite_count(result: subprocess.CompletedProcess[str]) -> int | None:
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    match = re.search(r"Ran\s+(\d+)\s+tests?\b", combined)
    if match is None:
        return None
    return int(match.group(1))


def _extract_suite_verdict(result: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    verdict = next(
        (
            line.strip()
            for line in reversed(combined.splitlines())
            if line.strip() == "OK" or line.strip().startswith("OK ") or line.strip().startswith("FAILED")
        ),
        "",
    )
    ran_line = next((line.strip() for line in combined.splitlines() if line.strip().startswith("Ran ")), "")
    return "; ".join(part for part in (ran_line, verdict) if part)


def _stderr_or_stdout(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip()


def _run_command(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise IterationCommitError(f"failed to execute {' '.join(command)}: {exc}") from exc
