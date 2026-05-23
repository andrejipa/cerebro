from __future__ import annotations

from pathlib import Path


LATERAL_DOCUMENTATION_MARKERS = {
    "logs",
    "tmp",
    "temporarios",
    "descarte",
    "acervo",
    "cerebro_base",
    "reconstrucao_historica",
    "90_versoes_antigas",
    "backups_criticos",
    "nao_enviar",
}

HISTORICAL_MARKERS = {
    "backup",
    "historico",
    "history",
    "old",
    "legacy",
    "snapshot",
    "snapshots",
    "arquivo",
    "archive",
    "acervo",
    "versoes_antigas",
    "temporarios",
    "descarte",
}

DOCUMENTATION_MARKERS = {
    "readme",
    "contexto",
    "canon",
    "checklist",
    "estado_atual",
    "entrada",
    "retomada",
    "guia",
    "indice",
    "dossie",
    "workflow",
    "pendencias",
}

CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".sql",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".rb",
    ".php",
    ".ps1",
    ".sh",
}

DOC_EXTENSIONS = {
    ".md",
    ".txt",
    ".html",
    ".pdf",
}

MIXED_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".csv",
    ".tsv",
    ".toml",
    ".ini",
    ".cfg",
    ".base",
    ".rels",
}


def classify_scope(path: str) -> tuple[str, list[str]]:
    normalized = path.replace("/", "\\").lower()
    ext = Path(path).suffix.lower()
    flags: list[str] = []

    if any(marker in normalized for marker in HISTORICAL_MARKERS):
        flags.append("scope_historical_marker")
        return "historical", flags

    if ext in CODE_EXTENSIONS:
        flags.append("scope_code_extension")
        return "code", flags

    if ext in DOC_EXTENSIONS or any(marker in normalized for marker in DOCUMENTATION_MARKERS):
        flags.append("scope_documentation_marker")
        return "documentation", flags

    if ext in MIXED_EXTENSIONS:
        flags.append("scope_mixed_extension")
        return "mixed", flags

    flags.append("scope_default_mixed")
    return "mixed", flags


def is_historical_path(path: str) -> bool:
    normalized = path.replace("/", "\\").lower()
    return any(marker in normalized for marker in HISTORICAL_MARKERS)


def is_lateral_documentation_path(path: str) -> bool:
    normalized = path.replace("/", "\\").lower()
    return any(marker in normalized for marker in LATERAL_DOCUMENTATION_MARKERS)


def scope_filter_allows(preferred_scope: str | None, result_scope: str) -> bool:
    if not preferred_scope:
        return True
    if preferred_scope == result_scope:
        return True
    if preferred_scope in {"documentation", "code", "historical"} and result_scope == "mixed":
        return True
    return False
