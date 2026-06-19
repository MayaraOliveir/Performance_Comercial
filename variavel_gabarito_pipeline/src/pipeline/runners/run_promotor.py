"""Runner da figura Promotor de Vendas."""

from __future__ import annotations

from pathlib import Path

from pipeline.figures.promotor_vendas import run_promotor_calculation


def run() -> list[Path]:
    """Executa o calculo de Promotor de Vendas."""

    return run_promotor_calculation()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
