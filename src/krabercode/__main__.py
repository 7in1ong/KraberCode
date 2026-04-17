"""
KraberCode CLI entry point.
"""

import sys
from krabercode.cli.commands import app


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()