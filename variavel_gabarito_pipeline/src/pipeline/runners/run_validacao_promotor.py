"""Runner de validacao do Promotor de Vendas contra gabarito."""

from __future__ import annotations

from pathlib import Path

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.validation.comparador import (
    build_validation_summary,
    compare_promotor_outputs,
    filter_differences,
)
from pipeline.validation.gabarito_promotor import first_gabarito_file, read_gabarito_promotor


def run() -> list[Path]:
    """Executa a validacao de Promotor contra o gabarito oficial."""

    logger = configure_logger("pipeline.validacao_promotor")
    paths_config = load_paths_config()
    facts_dir = paths_config.values["processed"]["facts"]
    validation_dir = paths_config.values["processed"]["validation"]
    raw_gabarito_dir = paths_config.values["raw_sources"]["gabarito_validacao"]

    python_result = read_csv(facts_dir / "fat_promotor_final.csv")
    gabarito_file = first_gabarito_file(raw_gabarito_dir)
    gabarito = read_gabarito_promotor(gabarito_file)
    compared = compare_promotor_outputs(python_result, gabarito)
    summary = build_validation_summary(compared)
    differences = filter_differences(compared)

    outputs = [
        write_csv(gabarito, validation_dir / "stg_gabarito_promotor.csv"),
        write_csv(compared, validation_dir / "validacao_promotor_gabarito.csv"),
        write_csv(summary, validation_dir / "resumo_validacao_promotor.csv"),
        write_csv(differences, validation_dir / "diferencas_promotor.csv"),
    ]
    logger.info(
        "validacao_promotor_concluida",
        extra={
            "arquivo_gabarito": str(gabarito_file),
            "linhas_python": len(python_result),
            "linhas_gabarito": len(gabarito),
            "linhas_comparacao": len(compared),
            "linhas_diferencas": len(differences),
        },
    )
    return outputs


def main() -> None:
    run()


if __name__ == "__main__":
    main()
