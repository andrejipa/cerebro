"""Pytest configuration for experiments/ — Python 3.10 compatibility shims."""
import builtins
import sys

if sys.version_info < (3, 11) and not hasattr(builtins, "ExceptionGroup"):
    class ExceptionGroup(Exception):  # noqa: N818
        """Minimal Python 3.10 shim for the built-in ExceptionGroup (3.11+)."""
        def __init__(self, message: str, exceptions: list) -> None:
            super().__init__(message)
            self.exceptions = list(exceptions)

        def __repr__(self) -> str:
            return f"ExceptionGroup({self.args[0]!r}, {self.exceptions!r})"

    builtins.ExceptionGroup = ExceptionGroup  # type: ignore[attr-defined]
