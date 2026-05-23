from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import shutil
import unicodedata

from .analysis.failure_report import build_failure_analysis
from .dataset import load_dataset
from .indexer import build_experiment_temp_root, build_project_index, build_reusable_index_cache_root
from .query_runner import run_query_variants
from .report import write_reports


DATASET_PATH = Path(__file__).with_name("eval_dataset.yaml")
REPORT_JSON_PATH = Path(__file__).with_name("report_round2_latest.json")
REPORT_MD_PATH = Path(__file__).with_name("report_round2_latest.md")
VARIANTS = ("A", "B", "C", "D")
IGNORED_EXPECTED_TOKENS = {"md", "txt", "sql", "ts", "tsx", "py", "json", "yaml", "yml", "html", "pdf", "csv", "xlsx"}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    cleaned: list[str] = []
    for char in normalized:
        if char.isalnum() or char in {"_", "/", "\\"}:
            cleaned.append(char)
        else:
            cleaned.append(" ")
    return "".join(cleaned)


def _normalize_tokens(value: str) -> list[str]:
    return [token for token in _normalize(value).replace("/", " ").replace("\\", " ").split() if token]


def _filtered_path_tokens(value: str) -> list[str]:
    return [token for token in _normalize_tokens(value) if token not in IGNORED_EXPECTED_TOKENS]


def _token_matches(result_token: str, expected_token: str) -> bool:
    if result_token == expected_token:
        return True
    if "_" not in expected_token:
        return False
    return (
        result_token.startswith(expected_token + "_")
        or result_token.endswith("_" + expected_token)
        or f"_{expected_token}_" in result_token
    )


def expected_path_matches(result_path: str, expected_fragment: str) -> bool:
    expected_normalized = _normalize(expected_fragment).strip()
    if not expected_normalized:
        return False
    result_segments = [segment.strip() for segment in _normalize(result_path).replace("\\", "/").split("/") if segment.strip()]
    expected_segments = [segment.strip() for segment in expected_normalized.replace("\\", "/").split("/") if segment.strip()]
    if expected_segments and len(expected_segments) <= len(result_segments):
        last_start = len(result_segments) - len(expected_segments) + 1
        for start in range(last_start):
            if all(result_segments[start + offset] == expected_segments[offset] for offset in range(len(expected_segments))):
                return True
    expected_tokens = _filtered_path_tokens(expected_fragment)
    if not expected_tokens:
        return False
    result_tokens = _filtered_path_tokens(result_path)
    return all(
        any(_token_matches(result_token, expected_token) for result_token in result_tokens)
        for expected_token in expected_tokens
    )


def _expected_match(result_path: str, expected_exact: list[str], expected_fragments: list[str]) -> bool:
    for expected in expected_exact:
        if _normalize(result_path) == _normalize(expected):
            return True
    return any(expected_path_matches(result_path, expected) for expected in expected_fragments)


def _negative_path_matches(result_path: str, negative_fragment: str) -> bool:
    return expected_path_matches(result_path, negative_fragment)


def _query_metrics(results: list[dict], query: dict) -> dict:
    top_three = results[:3]
    expected_exact = list(query.get("expected_paths_exact", []))
    expected_fragments = list(query.get("expected_paths", []))
    primary_targets = expected_exact if expected_exact else expected_fragments
    negative_paths = list(query.get("negative_paths", []))
    preferred_scope = query.get("preferred_scope")
    query_type = query.get("query_type")

    matched_targets_top_three: set[str] = set()
    matching_results = 0
    historical_errors = 0
    lateral_doc_errors = 0
    code_doc_confusions = 0
    first_hit_rank = 0
    top_one_path = results[0]["path"] if results else ""

    for rank, result in enumerate(results, start=1):
        matched_this_result = False
        matched_targets_this_result: set[str] = set()
        if expected_exact:
            for expected in expected_exact:
                if _normalize(result["path"]) == _normalize(expected):
                    matched_targets_this_result.add(expected)
        else:
            for expected in expected_fragments:
                if expected_path_matches(result["path"], expected):
                    matched_targets_this_result.add(expected)
        if matched_targets_this_result:
            matched_this_result = True
        if matched_this_result:
            if rank <= 3:
                matching_results += 1
                matched_targets_top_three.update(matched_targets_this_result)
            if first_hit_rank == 0:
                first_hit_rank = rank
        if rank > 3:
            continue
        if preferred_scope != "historical" and result["scope"] == "historical" and not matched_this_result:
            historical_errors += 1
        if any(_negative_path_matches(result["path"], negative) for negative in negative_paths):
            lateral_doc_errors += 1
        if preferred_scope == "code" and result["scope"] == "documentation" and not matched_this_result:
            code_doc_confusions += 1

    expected_target_count = max(1, len(primary_targets))
    recall_at_3 = min(len(matched_targets_top_three), expected_target_count) / expected_target_count
    precision_at_3 = matching_results / 3.0
    hit_at_3 = matching_results > 0
    mrr = 0.0 if first_hit_rank == 0 else 1.0 / first_hit_rank

    if query_type == "historical_lookup":
        historical_errors = 0

    return {
        "recall_at_3": recall_at_3,
        "precision_at_3": precision_at_3,
        "hit_at_3": hit_at_3,
        "mrr": mrr,
        "historical_error": historical_errors > 0,
        "historical_error_count": historical_errors,
        "lateral_doc_error": lateral_doc_errors > 0,
        "lateral_doc_error_count": lateral_doc_errors,
        "code_doc_confusion": code_doc_confusions > 0,
        "code_doc_confusion_count": code_doc_confusions,
        "top_one_path": top_one_path,
        "matched_expected_count": len(matched_targets_top_three),
    }


def _aggregate_metrics(entries: list[dict]) -> dict:
    if not entries:
        return {
            "recall_at_3": 0.0,
            "precision_at_3": 0.0,
            "hit_at_3": 0.0,
            "mrr": 0.0,
            "historical_error_rate": 0.0,
            "lateral_doc_error_rate": 0.0,
            "code_doc_confusion_rate": 0.0,
        }
    count = len(entries)
    return {
        "recall_at_3": sum(entry["metrics"]["recall_at_3"] for entry in entries) / count,
        "precision_at_3": sum(entry["metrics"]["precision_at_3"] for entry in entries) / count,
        "hit_at_3": sum(1 for entry in entries if entry["metrics"]["hit_at_3"]) / count,
        "mrr": sum(entry["metrics"]["mrr"] for entry in entries) / count,
        "historical_error_rate": sum(entry["metrics"]["historical_error_count"] for entry in entries) / count,
        "lateral_doc_error_rate": sum(entry["metrics"]["lateral_doc_error_count"] for entry in entries) / count,
        "code_doc_confusion_rate": sum(entry["metrics"]["code_doc_confusion_count"] for entry in entries) / count,
    }


def _aggregate_grouped(entries: list[dict], key: str) -> dict:
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        grouped[entry[key] or "unspecified"].append(entry)
    return {group_key: _aggregate_metrics(group_entries) for group_key, group_entries in sorted(grouped.items())}


def evaluate_dataset(
    dataset_path: str | Path = DATASET_PATH,
    variants: tuple[str, ...] = VARIANTS,
    *,
    index_cache_root: str | Path | None = None,
) -> dict:
    dataset = load_dataset(dataset_path)
    roots = [project["root"] for project in dataset["projects"]]
    temp_root = build_experiment_temp_root(roots)
    cache_root = build_reusable_index_cache_root(roots) if index_cache_root is None else index_cache_root

    try:
        project_indexes = {
            project["name"]: build_project_index(
                project["name"],
                project["root"],
                temp_root,
                cache_root=cache_root,
            )
            for project in dataset["projects"]
        }
        query_outputs_cache: dict[tuple[str, str], dict[str, dict]] = {}
        variant_results: dict[str, dict] = {}
        for variant in variants:
            project_reports: list[dict] = []
            all_query_reports: list[dict] = []
            for project in dataset["projects"]:
                project_index = project_indexes[project["name"]]
                query_reports: list[dict] = []
                for query in project["queries"]:
                    cache_key = (project["name"], query["id"])
                    if cache_key not in query_outputs_cache:
                        query_outputs_cache[cache_key] = run_query_variants(
                            project_index,
                            query=query["query"],
                            preferred_scope=query.get("preferred_scope"),
                            query_type=query.get("query_type"),
                            top_k=5,
                            variants=variants,
                        )
                    output = query_outputs_cache[cache_key][variant]
                    metrics = _query_metrics(output["results"], query)
                    query_report = {
                        "id": query["id"],
                        "query": query["query"],
                        "preferred_scope": query.get("preferred_scope"),
                        "expected_scope": query.get("expected_scope"),
                        "expected_paths": list(query.get("expected_paths", [])),
                        "expected_paths_exact": list(query.get("expected_paths_exact", [])),
                        "negative_paths": list(query.get("negative_paths", [])),
                        "difficulty": query.get("difficulty"),
                        "query_type": query.get("query_type"),
                        "notes": query.get("notes", ""),
                        "results": output["results"],
                        "metrics": metrics,
                        "project_name": project["name"],
                        "scope_bucket": query.get("preferred_scope") or "unspecified",
                    }
                    query_reports.append(query_report)
                    all_query_reports.append(query_report)
                project_reports.append(
                    {
                        "name": project["name"],
                        "root": project["root"],
                        "metrics": _aggregate_metrics(query_reports),
                        "queries": query_reports,
                    }
                )

            variant_results[variant] = {
                "metrics": _aggregate_metrics(all_query_reports),
                "projects": project_reports,
                "by_scope": _aggregate_grouped(all_query_reports, "scope_bucket"),
                "by_query_type": _aggregate_grouped(all_query_reports, "query_type"),
            }

        results = {
            "experimental": True,
            "authority": "derived-assistive",
            "non_authoritative": True,
            "read_only": True,
            "dataset_path": str(Path(dataset_path).resolve()),
            "temp_root": temp_root,
            "variants": variant_results,
            "failure_analysis": build_failure_analysis(variant_results),
        }
        return results
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def main() -> None:
    results = evaluate_dataset()
    write_reports(results, markdown_path=REPORT_MD_PATH, json_path=REPORT_JSON_PATH)
    print(json.dumps({variant: data["metrics"] for variant, data in results["variants"].items()}, indent=2))


if __name__ == "__main__":
    main()
