"""Staging de pesos."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import (
    clean_text,
    first_excel_file,
    normalize_column_name,
    read_excel_with_detected_header,
    to_number,
)


def transform_pesos(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extrai pesos por TipoRota e KPI de um arquivo de apoio."""

    blocks = _extract_weight_blocks(dataframe)
    if not blocks:
        blocks = [_extract_weight_block_from_columns(dataframe)]

    result = pd.concat([block for block in blocks if not block.empty], ignore_index=True)
    if result.empty:
        result = pd.DataFrame(columns=["TipoRota", "KPI", "Peso", "KpiPeso", "ChaveTipoKPI"])

    result["TipoRota"] = result["TipoRota"].map(clean_text)
    result["KPI"] = result["KPI"].map(clean_text)
    result["Peso"] = result["Peso"].map(to_number)
    result["KpiPeso"] = result["KPI"]
    result["ChaveTipoKPI"] = result["TipoRota"].fillna("") + result["KpiPeso"].fillna("")
    result = result.dropna(subset=["TipoRota", "KPI", "Peso"])
    result = result.drop_duplicates(subset=["ChaveTipoKPI"]).reset_index(drop=True)

    diagnostico = (
        result.groupby("TipoRota", dropna=False)
        .agg(qtd_kpis=("KPI", "nunique"), soma_pesos=("Peso", "sum"))
        .reset_index()
    )
    return result, diagnostico


def _extract_weight_blocks(dataframe: pd.DataFrame) -> list[pd.DataFrame]:
    normalized_columns = [normalize_column_name(column) for column in dataframe.columns]
    blocks: list[pd.DataFrame] = []
    for index, column_name in enumerate(normalized_columns):
        if column_name != "TIPO_ROTA":
            continue
        if index + 2 >= len(dataframe.columns):
            continue
        next_columns = normalized_columns[index + 1 : index + 3]
        if next_columns == ["KPI", "PESO"]:
            block = dataframe.iloc[:, [index, index + 1, index + 2]].copy()
            block.columns = ["TipoRota", "KPI", "Peso"]
            blocks.append(block)
    return blocks


def _extract_weight_block_from_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    column_map = {normalize_column_name(column): column for column in dataframe.columns}
    required = ["TIPO_ROTA", "KPI", "PESO"]
    if not all(column in column_map for column in required):
        return pd.DataFrame(columns=["TipoRota", "KPI", "Peso"])
    return dataframe[[column_map["TIPO_ROTA"], column_map["KPI"], column_map["PESO"]]].rename(
        columns={
            column_map["TIPO_ROTA"]: "TipoRota",
            column_map["KPI"]: "KPI",
            column_map["PESO"]: "Peso",
        }
    )


def build_staging_pesos(paths_config_path: str | Path | None = None) -> list[Path]:
    """Le pesos brutos e salva stg_pesos.csv e diagnostico."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.pesos")
    input_file = first_excel_file(paths_config.values["raw_sources"], "pesos")

    dataframe = read_excel_with_detected_header(input_file, {"TIPO_ROTA", "KPI", "PESO"})
    transformed, diagnostico = transform_pesos(dataframe)
    staging_dir = paths_config.values["processed"]["staging"]
    outputs = [
        write_csv(transformed, staging_dir / "stg_pesos.csv"),
        write_csv(diagnostico, staging_dir / "diag_pesos.csv"),
    ]

    logger.info(
        "staging_pesos_concluido",
        extra={"arquivo": str(input_file), "linhas_lidas": len(dataframe), "linhas_salvas": len(transformed)},
    )
    return outputs
