"""Runner de validacao da figura Desenvolvedor HID contra o gabarito."""

from __future__ import annotations

from pathlib import Path

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import first_excel_file
from pipeline.validation.desenvolvedor_hid import (
    build_desenvolvedor_hid_validation_summary,
    compare_desenvolvedor_hid_outputs,
    filter_critical_differences,
    read_gabarito_desenvolvedor_hid,
)


def run() -> list[Path]:
    """Executa validacao de Desenvolvedor HID."""

    logger = configure_logger("pipeline.validacao_desenvolvedor_hid")
    paths_config = load_paths_config()
    processed_dir = paths_config.values["data"]["processed"]
    validation_dir = paths_config.values["processed"]["validation"]
    gabarito_file = first_excel_file(paths_config.values["raw_sources"], "gabarito_validacao")

    pipeline_result = read_csv(processed_dir / "figures" / "desenvolvedor_hid_final.csv")
    gabarito = read_gabarito_desenvolvedor_hid(gabarito_file)
    compared = compare_desenvolvedor_hid_outputs(pipeline_result, gabarito)
    summary = build_desenvolvedor_hid_validation_summary(compared)
    differences = filter_critical_differences(compared)

    outputs = [
        write_csv(gabarito, validation_dir / "stg_gabarito_desenvolvedor_hid.csv"),
        write_csv(compared, validation_dir / "validacao_desenvolvedor_hid_gabarito.csv"),
        write_csv(summary, validation_dir / "resumo_validacao_desenvolvedor_hid.csv"),
        write_csv(differences, validation_dir / "diferencas_criticas_desenvolvedor_hid.csv"),
    ]

    _print_summary(summary)
    logger.info(
        "validacao_desenvolvedor_hid_concluida",
        extra={"linhas_validacao": len(compared), "divergencias_criticas": len(differences)},
    )
    return outputs


def _print_summary(summary) -> None:
    print("Validacao Desenvolvedor HID")
    for _, row in summary.iterrows():
        categoria = f" ({row['Categoria']})" if "Categoria" in summary.columns and not row.get("Categoria") != row.get("Categoria") else ""
        print(f"{row['Metrica']}{categoria}: {row['Valor']}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
