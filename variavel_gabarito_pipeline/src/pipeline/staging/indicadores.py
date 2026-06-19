"""Staging de indicadores."""

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
    "ANO_MES": {"ANO_MES"},
    "KPI": {"KPI"},
    "CENTRO": {"CENTRO"},
    "ROTA": {"ROTA"},
    "META": {"META"},
    "REALIZADO": {"REALIZADO"},
    "DATA_ATUALIZACAO": {"DATA_ATUALIZACAO"},
    "data_importacao": {"DATA_IMPORTACAO"},
}


def transform_indicadores(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Padroniza a base de indicadores."""

    result = rename_columns_by_aliases(dataframe, ALIASES)
    require_columns(result, ["KPI", "CENTRO", "ROTA"], "indicadores")
    selected_columns = [column for column in ALIASES if column in result.columns]
    result = result[selected_columns].copy()

    result["Centro"] = result["CENTRO"]
    result["Rota"] = result["ROTA"]
    result = standardize_text_columns(result, ["KPI", "Centro", "Rota"])

    for column in ["META", "REALIZADO"]:
        if column in result.columns:
            result[column] = result[column].map(to_number)

    result = result.dropna(subset=["Centro", "Rota", "KPI"])
    return add_kpi_keys(result)


def build_staging_indicadores(paths_config_path: str | Path | None = None) -> Path:
    """Le indicadores brutos e salva stg_indicadores.csv."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.indicadores")
    input_file = first_excel_file(paths_config.values["raw_sources"], "indicadores")

    dataframe = pd.read_excel(input_file, engine="openpyxl")
    transformed = transform_indicadores(dataframe)
    output_path = paths_config.values["processed"]["staging"] / "stg_indicadores.csv"
    write_csv(transformed, output_path)

    logger.info(
        "staging_indicadores_concluido",
        extra={"arquivo": str(input_file), "linhas_lidas": len(dataframe), "linhas_salvas": len(transformed)},
    )
    return output_path
