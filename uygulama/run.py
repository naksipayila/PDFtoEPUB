"""Convenient GUI and CLI entry point."""

from __future__ import annotations

import sys

from app.cli import main as cli_main
from app.main import main as gui_main


def main() -> int:
    """Start the GUI unless a PDF path or CLI help was supplied."""
    arguments = sys.argv[1:]
    if not arguments or arguments == ["--smoke-test"] or arguments[0] == "--gui":
        return gui_main()
    return cli_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
