"""Gera inventario de arquivos Excel das pastas raw configuradas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.core.utils import list_excel_files
from pipeline.io.csv_writer import write_csv
from pipeline.io.excel_reader import inspect_excel_workbook


INVENTORY_COLUMNS = [
    "arquivo",
    "pasta_origem",
    "aba",
    "qtd_linhas",
    "qtd_colunas",
    "colunas_detectadas",
]


def build_inventory(paths_config_path: str | Path | None = None) -> pd.DataFrame:
    """Monta o inventario de arquivos Excel das fontes raw."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.inventario")
    rows: list[dict[str, object]] = []

    raw_sources = paths_config.values.get("raw_sources", {})
    if not isinstance(raw_sources, dict):
        raise ValueError("Configuracao raw_sources deve ser um mapa de nome para pasta.")

    for source_name, source_path in raw_sources.items():
        excel_files = list_excel_files(source_path)
        logger.info(
            "arquivos_excel_detectados",
            extra={"pasta_origem": source_name, "qtd_arquivos": len(excel_files)},
        )

        for file_path in excel_files:
            try:
                workbook_rows = inspect_excel_workbook(file_path)
            except Exception as exc:  # noqa: BLE001 - inventario deve seguir mesmo com arquivo ruim
                logger.exception(
                    "falha_ao_inspecionar_excel",
                    extra={"arquivo": str(file_path), "pasta_origem": source_name},
                )
                rows.append(
                    {
                        "arquivo": file_path.name,
                        "pasta_origem": source_name,
                        "aba": "",
                        "qtd_linhas": 0,
                        "qtd_colunas": 0,
                        "colunas_detectadas": f"ERRO: {exc}",
                    }
                )
                continue

            for row in workbook_rows:
                row["pasta_origem"] = source_name
                rows.append(row)

    return pd.DataFrame(rows, columns=INVENTORY_COLUMNS)


def run(paths_config_path: str | Path | None = None) -> Path:
    """Executa o inventario e grava o CSV configurado."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    dataframe = build_inventory(paths_config_path)
    output_path = paths_config.values["inventario_arquivos"]
    return write_csv(dataframe, output_path)


def main() -> None:
    output_path = run()
    logger = configure_logger("pipeline.inventario")
    logger.info("inventario_gerado", extra={"arquivo_saida": str(output_path)})


if __name__ == "__main__":
    main()
