"""Allow `python -m cli` as a thin wrapper around the installed CLI."""

from __future__ import annotations

from cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
