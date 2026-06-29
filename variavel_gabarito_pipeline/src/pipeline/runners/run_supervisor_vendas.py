"""Runner da figura Supervisor de Vendas."""

from __future__ import annotations

from pathlib import Path

from pipeline.figures.supervisor_vendas import run_supervisor_vendas_calculation
from pipeline.staging.estrutura_supervisor_vendas import build_staging_estrutura_supervisor_vendas
from pipeline.staging.pesos_supervisor_vendas import build_staging_pesos_supervisor_vendas


def run() -> list[Path]:
    """Executa staging especifico e calculo de Supervisor de Vendas."""

    outputs: list[Path] = []
    outputs.extend(build_staging_estrutura_supervisor_vendas())
    outputs.extend(build_staging_pesos_supervisor_vendas())
    outputs.extend(run_supervisor_vendas_calculation())
    return outputs


def main() -> None:
    run()


if __name__ == "__main__":
    main()
