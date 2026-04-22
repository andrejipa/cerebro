"""Schema and validation for `experiments/lifecycle.toml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
import tomllib

from . import SCHEMA_VERSION


EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = EXPERIMENTS_ROOT / "lifecycle.toml"

ALLOWED_STATUSES = {"active", "graduated", "archived"}

MIN_REVIEW_INTERVAL_DAYS = 1
MAX_REVIEW_INTERVAL_DAYS = 365

REQUIRED_FIELDS_BY_STATUS: dict[str, tuple[str, ...]] = {
    "active": ("last_reviewed", "next_review_due", "outcome_so_far"),
    "graduated": ("graduated_on", "graduated_to", "outcome_so_far"),
    "archived": ("archived_on", "outcome_so_far"),
}


class LifecycleError(ValueError):
    """Raised when the lifecycle ledger is malformed or inconsistent with the tree."""


@dataclass(frozen=True)
class Experiment:
    name: str
    status: str
    started: date
    outcome_so_far: str
    last_reviewed: date | None = None
    next_review_due: date | None = None
    graduated_on: date | None = None
    graduated_to: str | None = None
    archived_on: date | None = None


@dataclass(frozen=True)
class Lifecycle:
    schema_version: str
    default_review_interval_days: int
    experiments: tuple[Experiment, ...] = field(default_factory=tuple)

    def by_name(self, name: str) -> Experiment | None:
        for experiment in self.experiments:
            if experiment.name == name:
                return experiment
        return None

    def names(self) -> tuple[str, ...]:
        return tuple(experiment.name for experiment in self.experiments)


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LifecycleError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_date(value: Any, field_name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise LifecycleError(f"{field_name} must be an ISO-8601 date") from exc
    raise LifecycleError(f"{field_name} must be an ISO-8601 date")


def _validate_status(value: Any) -> str:
    status = _require_string(value, "status")
    if status not in ALLOWED_STATUSES:
        raise LifecycleError(f"unsupported status: {status!r}")
    return status


def _build_experiment(raw: Any) -> Experiment:
    if not isinstance(raw, dict):
        raise LifecycleError("each experiment entry must be a table")
    name = _require_string(raw.get("name"), "experiment.name")
    status = _validate_status(raw.get("status"))
    started = _require_date(raw.get("started"), f"{name}.started")
    outcome = _require_string(raw.get("outcome_so_far"), f"{name}.outcome_so_far")

    for required in REQUIRED_FIELDS_BY_STATUS[status]:
        if raw.get(required) in (None, ""):
            raise LifecycleError(f"{name}: status={status} requires `{required}`")

    last_reviewed = (
        _require_date(raw.get("last_reviewed"), f"{name}.last_reviewed")
        if status == "active"
        else None
    )
    next_review_due = (
        _require_date(raw.get("next_review_due"), f"{name}.next_review_due")
        if status == "active"
        else None
    )
    graduated_on = (
        _require_date(raw.get("graduated_on"), f"{name}.graduated_on")
        if status == "graduated"
        else None
    )
    graduated_to = (
        _require_string(raw.get("graduated_to"), f"{name}.graduated_to")
        if status == "graduated"
        else None
    )
    archived_on = (
        _require_date(raw.get("archived_on"), f"{name}.archived_on")
        if status == "archived"
        else None
    )

    if status == "active":
        assert last_reviewed is not None and next_review_due is not None
        if next_review_due <= last_reviewed:
            raise LifecycleError(
                f"{name}: next_review_due must be strictly after last_reviewed"
            )
        if last_reviewed < started:
            raise LifecycleError(
                f"{name}: last_reviewed cannot predate started"
            )
    if status == "graduated":
        assert graduated_on is not None
        if graduated_on < started:
            raise LifecycleError(f"{name}: graduated_on cannot predate started")
    if status == "archived":
        assert archived_on is not None
        if archived_on < started:
            raise LifecycleError(f"{name}: archived_on cannot predate started")

    return Experiment(
        name=name,
        status=status,
        started=started,
        outcome_so_far=outcome,
        last_reviewed=last_reviewed,
        next_review_due=next_review_due,
        graduated_on=graduated_on,
        graduated_to=graduated_to,
        archived_on=archived_on,
    )


def load_lifecycle(path: str | Path | None = None) -> Lifecycle:
    ledger_path = Path(path) if path is not None else LEDGER_PATH
    with ledger_path.open("rb") as handle:
        payload = tomllib.load(handle)

    if str(payload.get("schema_version")) != SCHEMA_VERSION:
        raise LifecycleError(
            f"unsupported schema_version: {payload.get('schema_version')!r}"
        )

    interval = payload.get("default_review_interval_days")
    if not isinstance(interval, int) or not (
        MIN_REVIEW_INTERVAL_DAYS <= interval <= MAX_REVIEW_INTERVAL_DAYS
    ):
        raise LifecycleError(
            "default_review_interval_days must be an integer within "
            f"[{MIN_REVIEW_INTERVAL_DAYS}, {MAX_REVIEW_INTERVAL_DAYS}]"
        )

    experiments_raw = payload.get("experiment", [])
    if not isinstance(experiments_raw, list) or not experiments_raw:
        raise LifecycleError("lifecycle must declare a non-empty [[experiment]] array")

    seen: set[str] = set()
    experiments: list[Experiment] = []
    for raw in experiments_raw:
        experiment = _build_experiment(raw)
        if experiment.name in seen:
            raise LifecycleError(f"duplicate experiment entry: {experiment.name}")
        seen.add(experiment.name)
        experiments.append(experiment)

    return Lifecycle(
        schema_version=SCHEMA_VERSION,
        default_review_interval_days=interval,
        experiments=tuple(experiments),
    )


def tracked_experiment_dirs(root: Path | None = None) -> tuple[str, ...]:
    """Return the names of every folder under `experiments/` that counts
    as an experiment.

    Excludes:
    - entries starting with `_` (infrastructure, e.g. `_lifecycle/`)
    - entries starting with `.`
    - `__pycache__`
    - non-directories
    """
    base = root if root is not None else EXPERIMENTS_ROOT
    names: list[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(("_", ".")):
            continue
        if child.name == "__pycache__":
            continue
        names.append(child.name)
    return tuple(names)


def overdue_active_experiments(
    lifecycle: Lifecycle, today: date | None = None
) -> tuple[Experiment, ...]:
    anchor = today if today is not None else date.today()
    return tuple(
        experiment
        for experiment in lifecycle.experiments
        if experiment.status == "active"
        and experiment.next_review_due is not None
        and experiment.next_review_due < anchor
    )


def review_gap(experiment: Experiment) -> timedelta | None:
    if experiment.status != "active":
        return None
    assert experiment.last_reviewed is not None and experiment.next_review_due is not None
    return experiment.next_review_due - experiment.last_reviewed
