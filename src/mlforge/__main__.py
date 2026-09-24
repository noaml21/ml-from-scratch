"""Noninteractive options and lazy composition of the local terminal workbench."""

import argparse
from importlib.metadata import version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mlforge",
        description="Build useful machine learning models locally.",
        epilog="Your data stays on your machine.",
    )
    parser.add_argument("--version", action="version", version=version("mlforge"))
    parser.parse_args(argv)
    from mlforge.application.service import Service
    from mlforge.tui.app import MLForgeApp

    MLForgeApp(Service()).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
