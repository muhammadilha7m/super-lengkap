"""Module entry point — allows ``python -m image_upscaler``."""

from __future__ import annotations


def main() -> None:
    from image_upscaler.app import run

    run()


if __name__ == "__main__":
    main()
