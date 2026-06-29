"""Runner de validacao do Supervisor de Vendas contra gabarito."""

from __future__ import annotations

from pathlib import Path

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.validation.gabarito_promotor import first_gabarito_file
from pipeline.validation.supervisor_vendas import (
    build_supervisor_validation_summary,
    compare_supervisor_vendas_outputs,
    filter_critical_differences,
    read_gabarito_supervisor_vendas,
)


def run() -> list[Path]:
    """Executa a validacao de Supervisor de Vendas contra a aba final do gabarito."""

    logger = configure_logger("pipeline.validacao_supervisor_vendas")
    paths_config = load_paths_config()
    facts_dir = paths_config.values["processed"]["facts"]
    validation_dir = paths_config.values["processed"]["validation"]
    raw_gabarito_dir = paths_config.values["raw_sources"]["gabarito_validacao"]

    pipeline_result = read_csv(facts_dir / "fat_supervisor_vendas_final.csv")
    gabarito_file = first_gabarito_file(raw_gabarito_dir)
    gabarito = read_gabarito_supervisor_vendas(gabarito_file)
    compared = compare_supervisor_vendas_outputs(pipeline_result, gabarito)
    summary = build_supervisor_validation_summary(compared)
    critical_differences = filter_critical_differences(compared)

    outputs = [
        write_csv(gabarito, validation_dir / "stg_gabarito_supervisor_vendas.csv"),
        write_csv(compared, validation_dir / "validacao_supervisor_vendas_gabarito.csv"),
        write_csv(summary, validation_dir / "resumo_validacao_supervisor_vendas.csv"),
        write_csv(critical_differences, validation_dir / "diferencas_criticas_supervisor_vendas.csv"),
    ]
    logger.info(
        "validacao_supervisor_vendas_concluida",
        extra={
            "arquivo_gabarito": str(gabarito_file),
            "linhas_pipeline": len(pipeline_result),
            "linhas_gabarito": len(gabarito),
            "linhas_comparacao": len(compared),
            "linhas_diferencas_criticas": len(critical_differences),
        },
    )
    return outputs


def main() -> None:
    outputs = run()
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
