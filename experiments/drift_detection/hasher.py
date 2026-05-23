"""AST-based file hashing — structural hash independent of whitespace/comments."""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path


def _normalize_ast(node: ast.AST) -> str:
    """Produce a stable string representation of an AST, ignoring line numbers
    and column offsets so only structural changes register as drift."""
    parts = [type(node).__name__]
    for field_name, value in ast.iter_fields(node):
        if field_name in ("lineno", "col_offset", "end_lineno", "end_col_offset",
                          "type_comment"):
            continue
        if isinstance(value, list):
            parts.append(f"{field_name}=[" + ",".join(_normalize_ast(v) if isinstance(v, ast.AST) else repr(v) for v in value) + "]")
        elif isinstance(value, ast.AST):
            parts.append(f"{field_name}={_normalize_ast(value)}")
        else:
            parts.append(f"{field_name}={repr(value)}")
    return f"({','.join(parts)})"


def ast_hash(path: Path) -> str | None:
    """Return SHA-256 of the normalized AST, or None if file cannot be parsed."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
        normalized = _normalize_ast(tree)
        return hashlib.sha256(normalized.encode()).hexdigest()
    except SyntaxError:
        return None
    except Exception:
        return None
