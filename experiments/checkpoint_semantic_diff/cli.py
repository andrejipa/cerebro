"""CLI for checkpoint semantic diff.

Usage:
  python -m experiments.checkpoint_semantic_diff.cli [project_root]

*project_root* defaults to the current working directory.  The experiment
expects a .cerebro/state.json at that root.

NON-AUTHORITATIVE: never writes to .cerebro/, never calls import-context,
never modifies canonical state.
"""
from __future__ import annotations
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    project_root = Path(args[0]).resolve() if args else Path.cwd()
    state_json = project_root / ".cerebro" / "state.json"

    if not state_json.exists():
        print(f"No .cerebro/state.json found at {project_root}")
        return 1

    from .extractor import extract_checkpoint, extract_sources, load_state
    from .scorer import score_alignment
    from .report import write_report

    state = load_state(state_json)
    checkpoint = extract_checkpoint(state)
    if checkpoint is None:
        print("No checkpoint found in state.json")
        return 1

    sources = extract_sources(state, project_root)
    alignments = score_alignment(checkpoint.full_text, sources)
    md_path, _ = write_report(
        checkpoint.full_text,
        alignments,
        checkpoint.updated_at,
        EXPERIMENT_DIR,
    )
    print(f"Checkpoint: {checkpoint.full_text[:80]}...")
    print(f"Sources: {len(sources)}")
    for a in alignments:
        avail = "" if a.source_available else " [unavailable]"
        print(f"  {a.alignment:12s} {a.path}{avail}  (jaccard={a.jaccard_score:.4f})")
    print(f"Report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
