"""Format and write CheckpointSemanticDiff report."""
from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_markdown(checkpoint_text: str, alignments: list, checkpoint_updated_at: str | None) -> str:
    lines = [
        "# Cerebro Checkpoint Semantic Diff",
        "",
        f"**Generated:** {_now_utc()}",
    ]
    if checkpoint_updated_at:
        lines.append(f"**Checkpoint updated:** {checkpoint_updated_at}")
    lines += [
        f"**Sources evaluated:** {len(alignments)}",
        "",
        "## Checkpoint Text",
        "",
        f"> {checkpoint_text[:300]}{'...' if len(checkpoint_text) > 300 else ''}",
        "",
        "## Source Alignment",
        "",
    ]
    if not alignments:
        lines.append("No registered sources found.")
    else:
        for a in alignments:
            availability = "" if a.source_available else " *(unavailable)*"
            lines.append(
                f"- **{a.alignment.upper()}** `{a.path}` (role={a.role}){availability}"
                f"  — jaccard={a.jaccard_score:.4f}, shared={a.shared_tokens} tokens"
            )
    lines += [
        "",
        "---",
        "*Non-authoritative. This report never modifies canonical state.*",
    ]
    return "\n".join(lines)


def write_report(
    checkpoint_text: str,
    alignments: list,
    checkpoint_updated_at: str | None,
    out_dir: Path,
) -> tuple[Path, Path]:
    """Write markdown and JSON reports to *out_dir*. Returns (md_path, json_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "checkpoint_semantic_diff_latest.md"
    json_path = out_dir / "checkpoint_semantic_diff_latest.json"
    md_path.write_text(
        to_markdown(checkpoint_text, alignments, checkpoint_updated_at),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps({
            "generated_at": _now_utc(),
            "checkpoint_updated_at": checkpoint_updated_at,
            "checkpoint_text_length": len(checkpoint_text),
            "sources_evaluated": len(alignments),
            "alignments": [
                {
                    "path": a.path,
                    "role": a.role,
                    "jaccard_score": a.jaccard_score,
                    "alignment": a.alignment,
                    "shared_tokens": a.shared_tokens,
                    "checkpoint_tokens": a.checkpoint_tokens,
                    "source_tokens": a.source_tokens,
                    "source_available": a.source_available,
                }
                for a in alignments
            ],
        }, indent=2),
        encoding="utf-8",
    )
    return md_path, json_path
