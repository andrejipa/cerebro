from __future__ import annotations


def build_failure_analysis(variant_results: dict[str, dict]) -> dict[str, list[str]]:
    failures = {
        "embeddings_helped": [],
        "embeddings_hurt": [],
        "lexical_better": [],
        "doc_beats_code": [],
        "historical_pull": [],
    }

    baseline_queries = {}
    for project in variant_results["A"]["projects"]:
        for query in project["queries"]:
            baseline_queries[(project["name"], query["id"])] = query

    for variant in ("B", "C", "D"):
        for project in variant_results[variant]["projects"]:
            for query in project["queries"]:
                baseline = baseline_queries[(project["name"], query["id"])]
                if variant in {"C", "D"}:
                    if query["metrics"]["hit_at_3"] and not baseline["metrics"]["hit_at_3"]:
                        failures["embeddings_helped"].append(f"{variant}:{query['id']}")
                    if not query["metrics"]["hit_at_3"] and baseline["metrics"]["hit_at_3"]:
                        failures["embeddings_hurt"].append(f"{variant}:{query['id']}")
                if baseline["metrics"]["hit_at_3"] and not query["metrics"]["hit_at_3"]:
                    failures["lexical_better"].append(f"{variant}:{query['id']}")
                if query["metrics"]["code_doc_confusion"]:
                    failures["doc_beats_code"].append(f"{variant}:{query['id']}")
                if query["metrics"]["historical_error"]:
                    failures["historical_pull"].append(f"{variant}:{query['id']}")

    return failures
