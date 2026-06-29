"""Runner do diagnostico da figura Desenvolvedor CF."""

from __future__ import annotations

from pathlib import Path

from pipeline.figures.desenvolvedor_cf_diagnostic import run_desenvolvedor_cf_diagnostic


def run() -> list[Path]:
    """Executa diagnostico de Desenvolvedor CF, sem gerar pipeline final produtiva."""

    return run_desenvolvedor_cf_diagnostic()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
