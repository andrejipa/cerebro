from __future__ import annotations

from pathlib import Path
import json


DEFAULT_DIFFICULTY = "medium"
DEFAULT_QUERY_TYPE = "continuity"
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
ALLOWED_QUERY_TYPES = {
    "continuity",
    "routing",
    "code_logic",
    "canonical_state",
    "historical_lookup",
}


def infer_query_type(query: str, preferred_scope: str | None) -> str:
    lowered = query.lower()
    if preferred_scope == "historical" or "historic" in lowered:
        return "historical_lookup"
    if preferred_scope == "code":
        return "code_logic"
    if "manda hoje" in lowered or "vigente" in lowered or "estado atual" in lowered:
        return "canonical_state"
    if "onde" in lowered or "fica" in lowered:
        return "routing"
    return DEFAULT_QUERY_TYPE


def load_dataset(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    if "projects" not in data:
        raise ValueError("Dataset must contain a top-level 'projects' key")

    normalized_projects: list[dict] = []
    seen_project_names: set[str] = set()
    for project in data["projects"]:
        project_name = project["name"]
        if project_name in seen_project_names:
            raise ValueError(f"Duplicate project name: {project_name}")
        seen_project_names.add(project_name)
        normalized_queries: list[dict] = []
        seen_query_ids: set[str] = set()
        for query in project["queries"]:
            query_id = query["id"]
            if query_id in seen_query_ids:
                raise ValueError(f"Duplicate query id '{query_id}' in project '{project_name}'")
            seen_query_ids.add(query_id)
            difficulty = query.get("difficulty", DEFAULT_DIFFICULTY)
            if difficulty not in ALLOWED_DIFFICULTIES:
                raise ValueError(f"Unsupported difficulty: {difficulty}")
            query_type = query.get(
                "query_type",
                infer_query_type(query["query"], query.get("preferred_scope")),
            )
            if query_type not in ALLOWED_QUERY_TYPES:
                raise ValueError(f"Unsupported query_type: {query_type}")

            normalized_queries.append(
                {
                    **query,
                    "expected_paths": list(query.get("expected_paths", [])),
                    "expected_paths_exact": list(query.get("expected_paths_exact", [])),
                    "expected_scope": query.get("expected_scope", query.get("preferred_scope")),
                    "negative_paths": list(query.get("negative_paths", [])),
                    "difficulty": difficulty,
                    "query_type": query_type,
                }
            )
        normalized_projects.append({**project, "queries": normalized_queries})
    return {"projects": normalized_projects}
