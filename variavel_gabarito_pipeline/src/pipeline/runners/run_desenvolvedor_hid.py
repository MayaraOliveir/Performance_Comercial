"""Runner da figura Desenvolvedor HID."""

from __future__ import annotations

from pathlib import Path

from pipeline.figures.desenvolvedor_hid import run_desenvolvedor_hid_calculation


def run() -> list[Path]:
    """Executa o calculo final de Desenvolvedor HID."""

    return run_desenvolvedor_hid_calculation()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
