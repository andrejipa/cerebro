"""Git worktree management commands."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess

from cli.output import print_fail, print_ok, user_error
from cli.worktree_registry import (
    WorktreeRegistryError,
    locked_worktree_registry,
    load_worktrees,
    update_worktrees,
    validate_worktree_name,
)


class WorktreeCommandError(RuntimeError):
    """Raised when one worktree command cannot complete safely."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def run_worktree(root: Path, args) -> int:
    if args.worktree_command == "create":
        return run_worktree_create(root, args)
    if args.worktree_command == "list":
        return run_worktree_list(root)
    if args.worktree_command == "clean":
        return run_worktree_clean(root, args)

    print_fail([user_error("worktree_command_invalid", f"unsupported worktree subcommand: {args.worktree_command}")])
    return 1


def run_worktree_create(root: Path, args) -> int:
    try:
        created = create_worktree(root, args.name)
    except WorktreeCommandError as exc:
        print_fail([user_error(exc.code, exc.message)])
        return 1

    print_ok(
        [
            f"repo_root: {created['repo_root']}",
            f"worktree: {created['name']}",
            f"branch: {created['branch']}",
            f"path: {created['path']}",
        ]
    )
    return 0


def run_worktree_list(root: Path) -> int:
    try:
        listed = list_worktrees(root)
    except WorktreeCommandError as exc:
        print_fail([user_error(exc.code, exc.message)])
        return 1

    lines = [
        f"repo_root: {listed['repo_root']}",
        f"worktrees: {len(listed['entries'])}",
    ]
    for entry in listed["entries"]:
        branch = entry["branch"] or "-"
        lines.append(f"{entry['name']} | {branch} | {entry['status']} | {entry['path']}")

    print_ok(lines)
    return 0


def run_worktree_clean(root: Path, args) -> int:
    try:
        cleaned = clean_worktree(root, args.name)
    except WorktreeCommandError as exc:
        print_fail([user_error(exc.code, exc.message)])
        return 1

    print_ok(
        [
            f"repo_root: {cleaned['repo_root']}",
            f"worktree: {cleaned['name']}",
            f"branch: {cleaned['branch']}",
            f"path: {cleaned['path']}",
        ]
    )
    return 0


def create_worktree(root: Path, raw_name: str) -> dict[str, str]:
    root = Path(root).resolve()
    if not root.exists():
        raise WorktreeCommandError("worktree_root_not_found", f"project root does not exist: {root}")
    if not root.is_dir():
        raise WorktreeCommandError("worktree_root_invalid", f"project root is not a directory: {root}")

    try:
        name = validate_worktree_name(raw_name)
    except WorktreeRegistryError as exc:
        raise WorktreeCommandError("invalid_worktree_name", str(exc)) from exc

    repo_root = _resolve_repo_root(root)
    branch = _expected_worktree_branch(name)
    worktree_path = repo_root / ".worktrees" / name
    worktree_created = False
    entry_persisted = False
    try:
        with locked_worktree_registry(repo_root) as registry:
            existing_entries = registry.load()

            if any(item["name"] == name for item in existing_entries):
                raise WorktreeCommandError("worktree_already_registered", f"worktree is already registered: {name}")
            if any(item["branch"] == branch for item in existing_entries):
                raise WorktreeCommandError("worktree_branch_exists", f"worktree branch is already registered: {branch}")
            if worktree_path.exists():
                raise WorktreeCommandError("worktree_path_exists", f"worktree path already exists: {worktree_path}")
            if _git_branch_exists(repo_root, branch):
                raise WorktreeCommandError("worktree_branch_exists", f"git branch already exists: {branch}")

            create_result = _run_git_command(
                ["git", "worktree", "add", "-b", branch, str(worktree_path)],
                cwd=repo_root,
                failure_code="worktree_create_failed",
            )
            if create_result.returncode != 0:
                detail = _stderr_or_stdout(create_result) or "git worktree add failed"
                raise WorktreeCommandError("worktree_create_failed", detail)
            worktree_created = True

            entry = {
                "name": name,
                "path": str(worktree_path),
                "branch": branch,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": "active",
            }
            registry.save([*existing_entries, entry])
            entry_persisted = True
    except WorktreeRegistryError as exc:
        if entry_persisted:
            raise WorktreeCommandError("worktree_registry_invalid", str(exc)) from exc
        if not worktree_created:
            raise WorktreeCommandError("worktree_registry_invalid", str(exc)) from exc
        cleanup_errors = _cleanup_failed_create(repo_root, worktree_path, branch)
        message = f"failed to persist worktree registry: {exc}"
        if cleanup_errors:
            message = f"{message}; cleanup failed: {'; '.join(cleanup_errors)}"
        raise WorktreeCommandError("worktree_registry_invalid", message) from exc

    return {
        "repo_root": str(repo_root),
        "name": name,
        "branch": branch,
        "path": str(worktree_path),
    }


def clean_worktree(root: Path, raw_name: str) -> dict[str, str]:
    root = Path(root).resolve()
    if not root.exists():
        raise WorktreeCommandError("worktree_root_not_found", f"project root does not exist: {root}")
    if not root.is_dir():
        raise WorktreeCommandError("worktree_root_invalid", f"project root is not a directory: {root}")

    try:
        name = validate_worktree_name(raw_name)
    except WorktreeRegistryError as exc:
        raise WorktreeCommandError("invalid_worktree_name", str(exc)) from exc

    repo_root = _resolve_repo_root(root)
    registered_entries = _load_existing_entries(repo_root)
    registered = True

    try:
        registered_entry = _find_registered_entry(registered_entries, name)
    except WorktreeCommandError as exc:
        if exc.code != "worktree_not_registered":
            raise
        registered = False
        clean_target = _resolve_unregistered_clean_target(repo_root, name)
        worktree_path = Path(clean_target["path"]).resolve()
        branch = clean_target["branch"]
    else:
        worktree_path = Path(registered_entry["path"]).resolve()
        branch = registered_entry["branch"]
        clean_target = _resolve_clean_target(repo_root, registered_entry, worktree_path)

    if clean_target["mode"] == "active":
        if _is_worktree_dirty(worktree_path):
            raise WorktreeCommandError(
                "worktree_clean_dirty",
                f"worktree contains modified or untracked files: {worktree_path}",
            )

        remove_result = _run_git_command(
            ["git", "worktree", "remove", str(worktree_path)],
            cwd=repo_root,
            failure_code="worktree_clean_failed",
        )
        if remove_result.returncode != 0:
            detail = _stderr_or_stdout(remove_result) or f"failed to remove worktree: {worktree_path}"
            if "modified or untracked files" in detail:
                raise WorktreeCommandError("worktree_clean_dirty", detail)
            raise WorktreeCommandError("worktree_clean_failed", detail)
    elif clean_target["mode"] == "unregistered":
        if worktree_path.exists() and _is_worktree_dirty(worktree_path):
            raise WorktreeCommandError(
                "worktree_clean_dirty",
                f"worktree contains modified or untracked files: {worktree_path}",
            )

        remove_command = ["git", "worktree", "remove"]
        if not worktree_path.exists():
            remove_command.append("--force")
        remove_command.append(str(worktree_path))
        remove_result = _run_git_command(
            remove_command,
            cwd=repo_root,
            failure_code="worktree_clean_failed",
        )
        if remove_result.returncode != 0:
            detail = _stderr_or_stdout(remove_result) or f"failed to remove worktree: {worktree_path}"
            if "modified or untracked files" in detail:
                raise WorktreeCommandError("worktree_clean_dirty", detail)
            raise WorktreeCommandError("worktree_clean_failed", detail)

    if _git_branch_exists(repo_root, branch):
        branch_result = _run_git_command(
            ["git", "branch", "-D", branch],
            cwd=repo_root,
            failure_code="worktree_clean_failed",
        )
        if branch_result.returncode != 0:
            detail = _stderr_or_stdout(branch_result) or f"failed to delete branch: {branch}"
            raise WorktreeCommandError("worktree_clean_failed", detail)

    if registered:
        try:
            update_worktrees(repo_root, lambda current: _remove_worktree_entry(current, name))
        except WorktreeRegistryError as exc:
            raise WorktreeCommandError("worktree_registry_invalid", str(exc)) from exc

    return {
        "repo_root": str(repo_root),
        "name": name,
        "branch": branch,
        "path": str(worktree_path),
    }


def list_worktrees(root: Path) -> dict[str, object]:
    root = Path(root).resolve()
    if not root.exists():
        raise WorktreeCommandError("worktree_root_not_found", f"project root does not exist: {root}")
    if not root.is_dir():
        raise WorktreeCommandError("worktree_root_invalid", f"project root is not a directory: {root}")

    repo_root = _resolve_repo_root(root)
    registered_entries = _load_existing_entries(repo_root)
    git_entries = _load_git_worktrees(repo_root)
    reconciled_entries = _reconcile_worktrees(repo_root, registered_entries, git_entries)
    return {
        "repo_root": str(repo_root),
        "entries": reconciled_entries,
    }


def _load_existing_entries(repo_root: Path) -> list[dict[str, str]]:
    try:
        return load_worktrees(repo_root)
    except WorktreeRegistryError as exc:
        raise WorktreeCommandError("worktree_registry_invalid", str(exc)) from exc


def _find_registered_entry(entries: list[dict[str, str]], name: str) -> dict[str, str]:
    for item in entries:
        if item["name"] == name:
            return item
    raise WorktreeCommandError("worktree_not_registered", f"worktree is not registered: {name}")


def _resolve_repo_root(root: Path) -> Path:
    top_level_result = _run_git_command(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        failure_code="worktree_repo_unavailable",
    )
    if top_level_result.returncode != 0:
        detail = _stderr_or_stdout(top_level_result) or f"git repository not found from {root}"
        raise WorktreeCommandError("worktree_repo_unavailable", detail)

    common_dir_result = _run_git_command(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root,
        failure_code="worktree_repo_unavailable",
    )
    if common_dir_result.returncode == 0:
        common_dir = Path(common_dir_result.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = (root / common_dir).resolve()
        else:
            common_dir = common_dir.resolve()
        if common_dir.name == ".git":
            return common_dir.parent.resolve()

    return Path(top_level_result.stdout.strip()).resolve()


def _is_worktree_dirty(worktree_path: Path) -> bool:
    result = _run_git_command(
        ["git", "-C", str(worktree_path), "status", "--porcelain"],
        cwd=worktree_path,
        failure_code="worktree_clean_failed",
    )
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or f"failed to inspect worktree status: {worktree_path}"
        raise WorktreeCommandError("worktree_clean_failed", detail)
    return bool(result.stdout.strip())


def _git_branch_exists(repo_root: Path, branch: str) -> bool:
    result = _run_git_command(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo_root,
        failure_code="worktree_repo_unavailable",
    )
    return result.returncode == 0


def _expected_worktree_branch(name: str) -> str:
    return f"worktree-{name}"


def _find_git_entry_for_registered_worktree(repo_root: Path, registered_entry: dict[str, str]) -> dict[str, str]:
    registered_path = str(Path(registered_entry["path"]).resolve())
    git_entries = _load_git_worktrees(repo_root)
    for item in git_entries:
        if str(Path(item["path"]).resolve()) != registered_path:
            continue
        if not item["branch"] or item["branch"] != registered_entry["branch"]:
            raise WorktreeCommandError(
                "worktree_clean_registry_stale",
                (
                    "registered worktree diverges from git metadata: "
                    f"{registered_entry['name']} -> registry branch {registered_entry['branch']}, "
                    f"git branch {item['branch'] or '<detached>'}"
                ),
            )
        return item

    raise WorktreeCommandError(
        "worktree_clean_registry_stale",
        f"registered worktree is missing from git worktree list: {registered_entry['name']}",
    )


def _resolve_clean_target(repo_root: Path, registered_entry: dict[str, str], worktree_path: Path) -> dict[str, str]:
    expected_branch = _expected_worktree_branch(registered_entry["name"])
    try:
        git_entry = _find_git_entry_for_registered_worktree(repo_root, registered_entry)
    except WorktreeCommandError as exc:
        if exc.code != "worktree_clean_registry_stale":
            raise
        if worktree_path.exists():
            raise
        if registered_entry["branch"] != expected_branch:
            raise WorktreeCommandError(
                "worktree_clean_registry_stale",
                (
                    "registered worktree diverges from canonical branch metadata after checkout removal: "
                    f"{registered_entry['name']} -> registry branch {registered_entry['branch']}, "
                    f"expected branch {expected_branch}"
                ),
            ) from exc
        return {"mode": "removed", "branch": expected_branch}
    if registered_entry["branch"] != expected_branch or git_entry["branch"] != expected_branch:
        raise WorktreeCommandError(
            "worktree_clean_registry_stale",
            (
                "registered worktree diverges from canonical branch metadata: "
                f"{registered_entry['name']} -> registry branch {registered_entry['branch']}, "
                f"git branch {git_entry['branch'] or '<detached>'}, expected branch {expected_branch}"
            ),
        )
    return {"mode": "active", "branch": expected_branch}


def _resolve_unregistered_clean_target(repo_root: Path, name: str) -> dict[str, str]:
    expected_branch = _expected_worktree_branch(name)
    worktree_path = (repo_root / ".worktrees" / name).resolve()

    for item in _load_git_worktrees(repo_root):
        item_path = Path(item["path"]).resolve()
        if item_path != worktree_path:
            continue
        if item["branch"] != expected_branch:
            raise WorktreeCommandError(
                "worktree_clean_registry_stale",
                (
                    "unregistered worktree diverges from canonical branch metadata: "
                    f"{name} -> git branch {item['branch'] or '<detached>'}, "
                    f"expected branch {expected_branch}"
                ),
            )
        return {"mode": "unregistered", "branch": expected_branch, "path": str(worktree_path)}

    if worktree_path.exists():
        raise WorktreeCommandError(
            "worktree_clean_registry_stale",
            f"unregistered worktree exists on disk without git metadata: {name}",
        )

    if _git_branch_exists(repo_root, expected_branch):
        return {"mode": "removed", "branch": expected_branch, "path": str(worktree_path)}

    raise WorktreeCommandError("worktree_not_registered", f"worktree is not registered: {name}")


def _load_git_worktrees(repo_root: Path) -> list[dict[str, str]]:
    result = _run_git_command(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        failure_code="worktree_list_failed",
    )
    if result.returncode != 0:
        detail = _stderr_or_stdout(result) or "git worktree list failed"
        raise WorktreeCommandError("worktree_list_failed", detail)

    return _parse_git_worktree_list(repo_root, result.stdout)


def _parse_git_worktree_list(repo_root: Path, output: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for block in output.strip().split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        path_value: Path | None = None
        branch = ""
        detached = False
        for line in lines:
            if line.startswith("worktree "):
                path_value = Path(line[len("worktree ") :]).resolve()
            elif line.startswith("branch "):
                branch_value = line[len("branch ") :].strip()
                branch = branch_value.removeprefix("refs/heads/")
            elif line == "detached":
                detached = True

        if path_value is None:
            raise WorktreeCommandError("worktree_list_failed", "git worktree list returned malformed output")
        if not _is_managed_worktree_path(repo_root, path_value):
            continue

        entries.append(
            {
                "name": path_value.name,
                "path": str(path_value),
                "branch": "" if detached else branch,
            }
        )

    return entries


def _is_managed_worktree_path(repo_root: Path, candidate: Path) -> bool:
    expected_parent = (repo_root / ".worktrees").resolve()
    try:
        candidate.resolve().relative_to(expected_parent)
    except ValueError:
        return False
    return True


def _reconcile_worktrees(
    repo_root: Path,
    registered_entries: list[dict[str, str]],
    git_entries: list[dict[str, str]],
) -> list[dict[str, str]]:
    git_by_path = {str(Path(item["path"]).resolve()): item for item in git_entries}
    reconciled: list[dict[str, str]] = []

    for item in registered_entries:
        resolved_path = str(Path(item["path"]).resolve())
        git_entry = git_by_path.pop(resolved_path, None)
        branch = git_entry["branch"] if git_entry is not None else item["branch"]
        reconciled.append(
            {
                "name": item["name"],
                "path": resolved_path,
                "branch": branch,
                "status": "active" if git_entry is not None else "missing",
            }
        )

    for item in git_by_path.values():
        path_value = Path(item["path"]).resolve()
        if not _is_managed_worktree_path(repo_root, path_value):
            continue
        reconciled.append(
            {
                "name": path_value.name,
                "path": str(path_value),
                "branch": item["branch"],
                "status": "unregistered",
            }
        )

    return sorted(reconciled, key=lambda item: (item["name"], item["path"]))


def _remove_worktree_entry(entries: list[dict[str, str]], name: str) -> list[dict[str, str]]:
    remaining = [item for item in entries if item["name"] != name]
    if len(remaining) == len(entries):
        raise WorktreeRegistryError(f"worktree is not registered: {name}")
    return remaining


def _cleanup_failed_create(repo_root: Path, worktree_path: Path, branch: str) -> list[str]:
    cleanup_errors: list[str] = []

    remove_result = _run_git_command(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=repo_root,
        failure_code="worktree_cleanup_failed",
    )
    if remove_result.returncode != 0:
        cleanup_errors.append(_stderr_or_stdout(remove_result) or f"failed to remove worktree: {worktree_path}")

    branch_result = _run_git_command(
        ["git", "branch", "-D", branch],
        cwd=repo_root,
        failure_code="worktree_cleanup_failed",
    )
    if branch_result.returncode != 0:
        cleanup_errors.append(_stderr_or_stdout(branch_result) or f"failed to delete branch: {branch}")

    return cleanup_errors


def _run_git_command(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise WorktreeCommandError(failure_code, f"failed to execute {' '.join(command)}: {exc}") from exc


def _stderr_or_stdout(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip()
