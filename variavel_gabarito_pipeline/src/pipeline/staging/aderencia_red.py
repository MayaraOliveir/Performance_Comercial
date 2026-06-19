"""Staging de aderencia RED."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import (
    clean_text,
    create_chave_centro_rota,
    first_excel_file,
    normalize_column_name,
    read_excel_with_detected_header,
    rename_columns_by_aliases,
    require_columns,
    standardize_text_columns,
    to_number,
)


ALIASES = {
    "Centro": {"CENTRO"},
    "Rota": {"ROTA"},
    "CHAVE": {"CHAVE"},
    "SupervisorDescricao": {"SUPERVISOR_DESCRICAO", "SUPERVISOR_DESCRIÇÃO"},
}


def transform_aderencia_red(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Padroniza a aderencia RED por rota."""

    aderencia_column_index = _detect_aderencia_column_index(dataframe)
    result = rename_columns_by_aliases(dataframe, ALIASES)
    if aderencia_column_index is not None:
        result["AderenciaRED"] = dataframe.iloc[:, aderencia_column_index]
    require_columns(result, ["Centro", "Rota", "AderenciaRED"], "aderencia_red")

    selected_columns = [column for column in [*ALIASES, "AderenciaRED"] if column in result.columns]
    result = result[selected_columns].copy()
    result = standardize_text_columns(result, ["Centro", "Rota", "SupervisorDescricao"])
    result["Rota"] = [
        clean_route(rota, centro)
        for rota, centro in zip(result.get("Rota"), result.get("Centro"), strict=False)
    ]
    result["AderenciaRED"] = result["AderenciaRED"].map(to_number)
    result["ChaveCentroRota"] = [
        create_chave_centro_rota(centro, rota)
        for centro, rota in zip(result["Centro"], result["Rota"], strict=False)
    ]
    result = result.dropna(subset=["ChaveCentroRota"])
    return result.drop_duplicates(subset=["ChaveCentroRota"]).reset_index(drop=True)


def clean_route(rota: object, centro: object) -> str | None:
    """Limpa rotas no formato 'ROTA - VA300CRBC'."""

    rota_text = clean_text(rota)
    centro_text = clean_text(centro)
    if not rota_text:
        return None

    rota_text = re.sub(r"^ROTA\s*-\s*", "", rota_text).strip()
    if centro_text and rota_text.endswith(centro_text):
        rota_text = rota_text[: -len(centro_text)]

    return rota_text.strip() or None


def _detect_aderencia_column_index(dataframe: pd.DataFrame) -> int | None:
    priority = ["%_1", "PERCENTUAL_1", "ADERENCIA_RED", "ADERENCIA", "%"]
    for candidate in priority:
        for index, column in enumerate(dataframe.columns):
            if normalize_column_name(column) == candidate:
                return index
    return None


def build_staging_aderencia_red(paths_config_path: str | Path | None = None) -> Path:
    """Le aderencia RED bruta e salva stg_aderencia_red.csv."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.aderencia_red")
    input_file = first_excel_file(paths_config.values["raw_sources"], "aderencia_red")

    dataframe = read_excel_with_detected_header(input_file, {"CENTRO", "ROTA", "CHAVE", "%", "%_1"})
    transformed = transform_aderencia_red(dataframe)
    output_path = paths_config.values["processed"]["staging"] / "stg_aderencia_red.csv"
    write_csv(transformed, output_path)

    logger.info(
        "staging_aderencia_red_concluido",
        extra={"arquivo": str(input_file), "linhas_lidas": len(dataframe), "linhas_salvas": len(transformed)},
    )
    return output_path
