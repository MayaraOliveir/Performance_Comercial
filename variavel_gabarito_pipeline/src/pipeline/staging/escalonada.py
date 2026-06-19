"""Staging de tabelas escalonadas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import first_excel_file, normalize_column_name, to_number


PROMOTOR_LABEL = "PROMOTOR / SUP. MERCHANDISING"


def transform_escalonada_promotor(raw_dataframe: pd.DataFrame) -> pd.DataFrame:
    """Extrai o bloco PROMOTOR / SUP. MERCHANDISING da escalonada."""

    block = _extract_promotor_block(raw_dataframe)
    block = block.rename(
        columns={
            "DE": "FaixaDe",
            "PARA": "FaixaAte",
            "ACELERADO": "Acelerado",
            "GANHA": "EscalaAtingida",
        }
    )

    for column in ["FaixaDe", "FaixaAte", "Acelerado", "EscalaAtingida"]:
        if column in block.columns:
            block[column] = block[column].map(to_number)

    invalid_range = block["FaixaDe"].between(1, 2, inclusive="both") & (block["FaixaAte"] > 10)
    block.loc[invalid_range, "FaixaAte"] = block.loc[invalid_range, "FaixaDe"] + 0.0099
    block["Figura"] = "PROMOTOR DE VENDAS"
    block = block.dropna(subset=["FaixaDe", "FaixaAte", "EscalaAtingida"])
    return block[["Figura", "FaixaDe", "FaixaAte", "Acelerado", "EscalaAtingida"]].reset_index(drop=True)


def _extract_promotor_block(raw_dataframe: pd.DataFrame) -> pd.DataFrame:
    promoter_position = _find_promoter_label(raw_dataframe)
    if promoter_position is None:
        raise ValueError(f"Bloco {PROMOTOR_LABEL!r} nao encontrado.")

    label_row, start_column = promoter_position
    header_row = _find_header_row(raw_dataframe, label_row + 1, start_column)
    columns = list(range(start_column, min(start_column + 4, raw_dataframe.shape[1])))
    block = raw_dataframe.iloc[header_row + 1 :, columns].copy()
    block.columns = ["DE", "PARA", "ACELERADO", "GANHA"][: len(columns)]
    return block.dropna(how="all")


def _find_promoter_label(raw_dataframe: pd.DataFrame) -> tuple[int, int] | None:
    for row_index in range(raw_dataframe.shape[0]):
        for column_index in range(raw_dataframe.shape[1]):
            value = normalize_column_name(raw_dataframe.iat[row_index, column_index])
            if "PROMOTOR" in value and "MERCHANDISING" in value:
                return row_index, column_index
    return None


def _find_header_row(raw_dataframe: pd.DataFrame, start_row: int, start_column: int) -> int:
    for row_index in range(start_row, min(start_row + 10, raw_dataframe.shape[0])):
        values = {
            normalize_column_name(value)
            for value in raw_dataframe.iloc[row_index, start_column : start_column + 6].tolist()
        }
        if {"DE", "PARA"}.issubset(values):
            return row_index
    return start_row


def build_staging_escalonada(paths_config_path: str | Path | None = None) -> Path:
    """Le escalonada bruta e salva stg_escalonada_promotor.csv."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.escalonada")
    input_file = first_excel_file(paths_config.values["raw_sources"], "escalonada")

    dataframe = pd.read_excel(input_file, header=None, engine="openpyxl")
    transformed = transform_escalonada_promotor(dataframe)
    output_path = paths_config.values["processed"]["staging"] / "stg_escalonada_promotor.csv"
    write_csv(transformed, output_path)

    logger.info(
        "staging_escalonada_concluido",
        extra={"arquivo": str(input_file), "linhas_lidas": len(dataframe), "linhas_salvas": len(transformed)},
    )
    return output_path
