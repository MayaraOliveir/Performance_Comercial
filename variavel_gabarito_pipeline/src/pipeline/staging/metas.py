"""Staging de metas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import (
    add_kpi_keys,
    first_excel_file,
    rename_columns_by_aliases,
    require_columns,
    standardize_text_columns,
    to_number,
)


ALIASES = {
    "CHAVE": {"CHAVE"},
    "KPI": {"KPI"},
    "Rota": {"ROTA"},
    "Centro": {"CENTRO"},
    "Meta": {"META"},
    "RealizadoArquivoMetas": {"REALIZADO"},
}


def transform_metas(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Padroniza a base de metas."""

    result = rename_columns_by_aliases(dataframe, ALIASES)
    require_columns(result, ["KPI", "Rota", "Centro"], "metas")
    selected_columns = [column for column in ALIASES if column in result.columns]
    result = result[selected_columns].copy()
    result = standardize_text_columns(result, ["CHAVE", "KPI", "Rota", "Centro"])

    for column in ["Meta", "RealizadoArquivoMetas"]:
        if column in result.columns:
            result[column] = result[column].map(to_number)

    return add_kpi_keys(result)


def build_staging_metas(paths_config_path: str | Path | None = None) -> Path:
    """Le metas brutas e salva stg_metas.csv."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.metas")
    input_file = first_excel_file(paths_config.values["raw_sources"], "metas")

    dataframe = pd.read_excel(input_file, engine="openpyxl")
    transformed = transform_metas(dataframe)
    output_path = paths_config.values["processed"]["staging"] / "stg_metas.csv"
    write_csv(transformed, output_path)

    logger.info(
        "staging_metas_concluido",
        extra={"arquivo": str(input_file), "linhas_lidas": len(dataframe), "linhas_salvas": len(transformed)},
    )
    return output_path
