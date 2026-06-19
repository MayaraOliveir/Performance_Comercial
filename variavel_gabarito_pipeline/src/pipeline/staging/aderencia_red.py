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

    aderencia_column_index = _detect_column_index(dataframe, ["%_1"])
    aderencia_supervisor_index = _detect_column_index(dataframe, ["%"])
    result = rename_columns_by_aliases(dataframe, ALIASES)
    if aderencia_column_index is not None:
        result["AderenciaRED"] = dataframe.iloc[:, aderencia_column_index]
    if aderencia_supervisor_index is not None:
        result["AderenciaSupervisor"] = dataframe.iloc[:, aderencia_supervisor_index]
    require_columns(result, ["Centro", "Rota", "AderenciaRED"], "aderencia_red")

    selected_columns = [
        column
        for column in [*ALIASES, "AderenciaSupervisor", "AderenciaRED"]
        if column in result.columns
    ]
    result = result[selected_columns].copy()
    result = standardize_text_columns(result, ["Centro", "Rota", "SupervisorDescricao"])
    result["Rota"] = [
        clean_route(rota, centro)
        for rota, centro in zip(result.get("Rota"), result.get("Centro"), strict=False)
    ]
    result["AderenciaRED"] = result["AderenciaRED"].map(to_number)
    if "AderenciaSupervisor" in result.columns:
        result["AderenciaSupervisor"] = result["AderenciaSupervisor"].map(to_number)
    result["StatusAderenciaRED"] = result["AderenciaRED"].map(classify_status_aderencia_red)
    result["AderenciaREDValida"] = result["AderenciaRED"].where(result["AderenciaRED"] <= 1.5)
    result["ChaveCentroRota"] = [
        create_chave_centro_rota(centro, rota)
        for centro, rota in zip(result["Centro"], result["Rota"], strict=False)
    ]
    result = remove_invalid_rows(result)
    return result.drop_duplicates(subset=["ChaveCentroRota"]).reset_index(drop=True)


def clean_route(rota: object, centro: object) -> str | None:
    """Limpa rotas no formato 'ROTA - VA300CRBC'."""

    rota_text = clean_text(rota)
    centro_text = clean_text(centro)
    if not rota_text:
        return None

    rota_text = re.sub(r"^ROTA\s*-\s*", "", rota_text).strip()
    rota_text = re.sub(r"^ROTA-\s*", "", rota_text).strip()
    rota_text = re.sub(r"^ROTA\s*", "", rota_text).strip()
    if rota_text == "ROTA":
        return None
    if centro_text and rota_text.endswith(centro_text):
        rota_text = rota_text[: -len(centro_text)]

    return rota_text.strip() or None


def classify_status_aderencia_red(value: object) -> str:
    """Classifica a qualidade do percentual de aderencia RED."""

    if pd.isna(value):
        return "Nula"
    number = float(value)
    if number > 1.5:
        return "Suspeita acima de 1.5"
    if 0 <= number <= 1.5:
        return "OK"
    return "Suspeita abaixo de 0"


def remove_invalid_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas sem centro/rota validos para cruzamento."""

    result = dataframe.dropna(subset=["Centro", "Rota", "ChaveCentroRota"]).copy()
    return result[
        (result["Centro"] != "CENTRO")
        & (result["Rota"] != "ROTA")
    ].reset_index(drop=True)


def build_diagnostic(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Gera diagnostico agregado da aderencia RED por status."""

    return (
        dataframe.groupby("StatusAderenciaRED", dropna=False)
        .agg(
            QtdLinhas=("StatusAderenciaRED", "size"),
            MinAderenciaRED=("AderenciaRED", "min"),
            MaxAderenciaRED=("AderenciaRED", "max"),
            QtdChaves=("ChaveCentroRota", "nunique"),
        )
        .reset_index()
        .sort_values("StatusAderenciaRED")
        .reset_index(drop=True)
    )


def read_aderencia_red_excel(file_path: str | Path) -> pd.DataFrame:
    """Le a aderencia RED priorizando o cabecalho diagnosticado na linha 2."""

    raw = pd.read_excel(file_path, header=None, engine="openpyxl")
    if _row_has_expected_header(raw, 2):
        dataframe = raw.iloc[3:].copy()
        dataframe.columns = _make_unique_columns(raw.iloc[2].tolist())
        return dataframe.dropna(how="all").reset_index(drop=True)

    for header_row in range(min(30, len(raw))):
        if _row_has_expected_header(raw, header_row):
            dataframe = raw.iloc[header_row + 1 :].copy()
            dataframe.columns = _make_unique_columns(raw.iloc[header_row].tolist())
            return dataframe.dropna(how="all").reset_index(drop=True)

    return pd.read_excel(file_path, engine="openpyxl")


def _detect_column_index(dataframe: pd.DataFrame, priority: list[str]) -> int | None:
    for candidate in priority:
        for index, column in enumerate(dataframe.columns):
            if normalize_column_name(column) == candidate:
                return index
    return None


def _row_has_expected_header(raw: pd.DataFrame, row_index: int) -> bool:
    values = [normalize_column_name(value) for value in raw.iloc[row_index].tolist()]
    has_base_columns = {"CENTRO", "CHAVE", "ROTA"}.issubset(set(values))
    has_route_percent = "%_1" in values or values.count("%") >= 2
    return has_base_columns and has_route_percent


def _make_unique_columns(columns: list[object]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for index, column in enumerate(columns):
        text = f"Unnamed: {index}" if pd.isna(column) or str(column).strip() == "" else str(column).strip()
        count = seen.get(text, 0)
        seen[text] = count + 1
        result.append(text if count == 0 else f"{text}_{count}")
    return result


def build_staging_aderencia_red(paths_config_path: str | Path | None = None) -> list[Path]:
    """Le aderencia RED bruta e salva stg_aderencia_red.csv."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.aderencia_red")
    input_file = first_excel_file(paths_config.values["raw_sources"], "aderencia_red")

    dataframe = read_aderencia_red_excel(input_file)
    transformed = transform_aderencia_red(dataframe)
    diagnostic = build_diagnostic(transformed)
    output_path = paths_config.values["processed"]["staging"] / "stg_aderencia_red.csv"
    diagnostic_path = paths_config.values["processed"]["staging"] / "diag_aderencia_red.csv"
    write_csv(transformed, output_path)
    write_csv(diagnostic, diagnostic_path)

    logger.info(
        "staging_aderencia_red_concluido",
        extra={
            "arquivo": str(input_file),
            "linhas_lidas": len(dataframe),
            "linhas_salvas": len(transformed),
            "linhas_diagnostico": len(diagnostic),
        },
    )
    return [output_path, diagnostic_path]
