"""Noninteractive command bootstrap; full-screen composition follows in P06."""

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
    parser.exit(
        2, "MLForge is under construction; the terminal workflow is not ready.\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
