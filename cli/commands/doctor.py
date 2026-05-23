"""Read-only diagnostics for the external Cerebro model."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from core.state_store import StateStore, StateStoreError, StateValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]

STATUS_HEALTHY = "SAUDAVEL"
STATUS_WARNING = "ATENCAO"
STATUS_CRITICAL = "CRITICO"
SUITE_TIMEOUT_SECONDS = 240


def build_doctor_report(root: Path, *, repo_root: Path | None = None) -> dict[str, object]:
    resolved_root = Path(root).resolve()
    resolved_repo_root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    store = StateStore(resolved_root)

    state_check, runtime = _state_check(store)
    checks = [
        _python_check(),
        _installation_check(resolved_repo_root),
        _suite_check(resolved_repo_root),
        state_check,
        _session_check(store, runtime),
        _weakness_check(resolved_repo_root),
        _freeze_check(resolved_repo_root),
    ]
    return {
        "project_root": str(resolved_root),
        "checks": checks,
    }


def run_doctor(root: Path, args=None) -> int:
    report = build_doctor_report(root)
    checks = report["checks"]
    has_critical = any(item["status"] == STATUS_CRITICAL for item in checks)

    print("FAIL" if has_critical else "OK")
    print("DOCTOR")
    print("mode: read-only")
    print(f"project_root: {report['project_root']}")
    for item in checks:
        print(f"- {item['name']}: {item['status']} - {item['message']}")
    return 1 if has_critical else 0


def _python_check() -> dict[str, str]:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    executable = sys.executable or "<unknown>"
    return {
        "name": "python",
        "status": STATUS_HEALTHY,
        "message": f"runtime available via {executable} ({version})",
    }


def _installation_check(repo_root: Path) -> dict[str, str]:
    missing = [
        str(path.relative_to(repo_root))
        for path in (
            repo_root / "cli" / "main.py",
            repo_root / "core" / "__init__.py",
            repo_root / "extensions" / "__init__.py",
        )
        if not path.exists()
    ]
    if missing:
        return {
            "name": "installation",
            "status": STATUS_CRITICAL,
            "message": f"repo root is missing import packages: {', '.join(missing)}",
        }

    import_result = _run_isolated_import_check(repo_root)
    if import_result["status"] == STATUS_CRITICAL:
        return import_result

    executable_result = _run_cerebro_executable_check()
    if executable_result["status"] != STATUS_HEALTHY:
        return executable_result

    return {
        "name": "installation",
        "status": STATUS_HEALTHY,
        "message": "isolated Python import and cerebro executable are available",
    }


def _run_isolated_import_check(repo_root: Path) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import json, cli.main, core, extensions; "
                        "print(json.dumps({'cli.main': cli.main.__file__, "
                        "'core': core.__file__, 'extensions': extensions.__file__}))"
                    ),
                ],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                check=False,
                env=_environment_without_pythonpath(),
            )
        except OSError as exc:
            return {
                "name": "installation",
                "status": STATUS_CRITICAL,
                "message": f"isolated installed import could not be executed: {exc}",
            }
    if result.returncode != 0:
        return {
            "name": "installation",
            "status": STATUS_CRITICAL,
            "message": f"isolated installed import failed: {_first_output_line(result)}",
        }
    module_paths = _parse_isolated_import_output(result)
    if module_paths is None:
        return {
            "name": "installation",
            "status": STATUS_CRITICAL,
            "message": f"isolated installed import returned invalid output: {_first_output_line(result)}",
        }

    foreign = {
        name: path
        for name, path in module_paths.items()
        if not path or not _path_is_within(Path(path).resolve(), repo_root)
    }
    if foreign:
        details = ", ".join(f"{name} -> {path}" for name, path in sorted(foreign.items()))
        return {
            "name": "installation",
            "status": STATUS_CRITICAL,
            "message": f"isolated installed import points outside this repo: {details}",
        }
    return {
        "name": "installation",
        "status": STATUS_HEALTHY,
        "message": "isolated installed import points at this repo",
    }


def _run_cerebro_executable_check() -> dict[str, str]:
    executable = shutil.which("cerebro")
    if executable is None:
        return {
            "name": "installation",
            "status": STATUS_WARNING,
            "message": "cerebro executable was not found on PATH",
        }

    expected_scripts_dir = _scripts_dir_for_current_interpreter()
    executable_dir = Path(executable).resolve().parent
    if not _same_path(executable_dir, expected_scripts_dir):
        return {
            "name": "installation",
            "status": STATUS_WARNING,
            "message": (
                "cerebro executable on PATH is from a different Python environment "
                f"({executable}); expected it under {expected_scripts_dir}"
            ),
        }

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            result = subprocess.run(
                [executable, "--help"],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                check=False,
                env=_environment_without_pythonpath(),
            )
        except OSError as exc:
            return {
                "name": "installation",
                "status": STATUS_CRITICAL,
                "message": f"cerebro executable could not be started from PATH ({executable}): {exc}",
            }
    if result.returncode != 0:
        return {
            "name": "installation",
            "status": STATUS_CRITICAL,
            "message": f"cerebro executable failed from PATH ({executable}): {_first_output_line(result)}",
        }
    return {
        "name": "installation",
        "status": STATUS_HEALTHY,
        "message": f"cerebro executable works from PATH ({executable})",
    }


def _environment_without_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _first_output_line(result: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part for part in (result.stderr, result.stdout) if part)
    return next((line.strip() for line in combined.splitlines() if line.strip()), "no output")


def _parse_isolated_import_output(result: subprocess.CompletedProcess[str]) -> dict[str, str] | None:
    required_keys = {"cli.main", "core", "extensions"}
    for line in reversed(result.stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and all(isinstance(value, str) for value in payload.values()):
            if required_keys.issubset(payload):
                return payload
    return None


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _scripts_dir_for_current_interpreter() -> Path:
    executable = Path(sys.executable).resolve()
    if os.name == "nt" and executable.parent.name.lower() != "scripts":
        return executable.parent / "Scripts"
    return executable.parent


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _suite_check(repo_root: Path) -> dict[str, str]:
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return {
            "name": "suite",
            "status": STATUS_CRITICAL,
            "message": f"test suite not available under {tests_dir}",
        }

    try:
        result = subprocess.run(
            [sys.executable, "-m", "tests.gate_runner", "--profile", "base"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=SUITE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "name": "suite",
            "status": STATUS_CRITICAL,
            "message": f"base gate timed out after {SUITE_TIMEOUT_SECONDS}s",
        }
    except OSError as exc:
        return {
            "name": "suite",
            "status": STATUS_CRITICAL,
            "message": f"failed to execute test suite: {exc}",
        }

    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    summary_line = next((line.strip() for line in reversed(combined.splitlines()) if line.strip().startswith("SUMMARY ")), "")
    ran_line = next((line.strip() for line in combined.splitlines() if line.strip().startswith("Ran ")), "suite result unavailable")
    final_line = next(
        (
            line.strip()
            for line in reversed(combined.splitlines())
            if line.strip() == "OK" or line.strip().startswith("OK ") or line.strip().startswith("FAILED")
        ),
        "suite status unavailable",
    )
    return {
        "name": "suite",
        "status": STATUS_HEALTHY if result.returncode == 0 else STATUS_CRITICAL,
        "message": f"{summary_line or ran_line}; {final_line}",
    }


def _state_check(store: StateStore) -> tuple[dict[str, str], dict | None]:
    if not store.state_path.exists():
        return {
            "name": "state",
            "status": STATUS_WARNING,
            "message": f"runtime state not initialized at {store.state_path}",
        }, None

    try:
        snapshot, runtime = store.read_snapshot_and_runtime()
    except StateValidationError as exc:
        detail = exc.errors[0]["code"] if exc.errors else "state_invalid"
        return {
            "name": "state",
            "status": STATUS_CRITICAL,
            "message": f"canonical state is invalid ({detail})",
        }, None
    except StateStoreError as exc:
        return {
            "name": "state",
            "status": STATUS_CRITICAL,
            "message": f"failed to read canonical state: {exc}",
        }, None

    validation_result = snapshot.last_validation.result
    return {
        "name": "state",
        "status": STATUS_HEALTHY if validation_result == "ok" else STATUS_CRITICAL,
        "message": (
            f"revision {snapshot.revision}; validation {validation_result}; "
            f"sources {len(snapshot.sources)}"
        ),
    }, runtime


def _session_check(store: StateStore, runtime: dict | None) -> dict[str, str]:
    session_file_present = store.has_active_session()
    if runtime is None:
        return {
            "name": "session",
            "status": STATUS_CRITICAL if session_file_present else STATUS_WARNING,
            "message": (
                "local session sidecar exists but state could not be inspected"
                if session_file_present
                else "no active local session"
            ),
        }

    audit = runtime.get("audit", {}) if isinstance(runtime, dict) else {}
    active_session_id = audit.get("active_session_id", "") if isinstance(audit, dict) else ""
    active_claim_id = audit.get("active_session_claim_id", "") if isinstance(audit, dict) else ""
    registry_active = bool(active_session_id) or bool(active_claim_id)

    if registry_active and session_file_present:
        return {
            "name": "session",
            "status": STATUS_HEALTHY,
            "message": f"active session registered ({active_session_id})",
        }
    if not registry_active and not session_file_present:
        return {
            "name": "session",
            "status": STATUS_WARNING,
            "message": "no active local session",
        }
    return {
        "name": "session",
        "status": STATUS_CRITICAL,
        "message": "session registry and local sidecar are inconsistent",
    }


def _weakness_check(repo_root: Path) -> dict[str, str]:
    path = repo_root / "docs" / "operations" / "WEAKNESS_REPORT.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {
            "name": "weakness_report",
            "status": STATUS_WARNING,
            "message": f"unable to read weakness report: {exc}",
        }

    critical_open = _count_open_items(text, "CRÍTICO")
    high_open = _count_open_items(text, "ALTO")
    if critical_open is None or high_open is None:
        return {
            "name": "weakness_report",
            "status": STATUS_WARNING,
            "message": "unable to classify open CRITICO/ALTO items",
        }
    if critical_open > 0:
        status = STATUS_CRITICAL
    elif high_open > 0:
        status = STATUS_WARNING
    else:
        status = STATUS_HEALTHY
    return {
        "name": "weakness_report",
        "status": status,
        "message": f"CRITICO abertos: {critical_open}; ALTO abertos: {high_open}",
    }


def _count_open_items(text: str, heading: str) -> int | None:
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    in_section = False

    for line in lines:
        stripped = line.rstrip()
        if stripped == f"### {heading}":
            in_section = True
            current = []
            continue
        if in_section and (stripped.startswith("### ") or stripped.startswith("## ")):
            break
        if not in_section:
            continue
        if stripped.startswith("- "):
            if current:
                blocks.append(current)
            current = [stripped]
            continue
        if current:
            current.append(stripped)

    if current:
        blocks.append(current)

    if not blocks:
        return None
    if any("Nenhum item" in " ".join(block) for block in blocks):
        return 0
    return sum(1 for block in blocks if "Status atual:" in " ".join(block))


def _freeze_check(repo_root: Path) -> dict[str, str]:
    path = repo_root / "docs" / "operations" / "FREEZE_POLICY.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {
            "name": "freeze",
            "status": STATUS_WARNING,
            "message": f"unable to read freeze policy: {exc}",
        }

    if "This freeze applies to growth, not to corrective maintenance." not in text:
        return {
            "name": "freeze",
            "status": STATUS_WARNING,
            "message": "freeze policy found but corrective-maintenance carve-out was not confirmed",
        }
    return {
        "name": "freeze",
        "status": STATUS_HEALTHY,
        "message": "growth remains frozen; corrective maintenance is explicitly allowed",
    }
