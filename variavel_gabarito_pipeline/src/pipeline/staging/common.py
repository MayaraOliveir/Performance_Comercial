"""Utilitarios compartilhados da camada de staging."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

from pipeline.core.exceptions import DataReadError
from pipeline.core.utils import list_excel_files


NULL_TOKENS = {"", "-", "NULL", "NAN", "NONE"}
OOS_KPIS = {"RPT", "RUPTURA", "OOS"}


def clean_text(value: object) -> str | None:
    """Padroniza texto com strip + upper e converte tokens vazios para nulo."""

    if pd.isna(value):
        return None

    text = str(value).strip()
    if text.upper() in NULL_TOKENS:
        return None

    return text.upper()


def normalize_column_name(value: object) -> str:
    """Normaliza nomes de coluna para comparacao tolerante."""

    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper().strip()
    text = re.sub(r"[^A-Z0-9%]+", "_", text)
    return text.strip("_")


def to_number(value: object) -> float | None:
    """Converte numeros vindos do Excel, aceitando virgula decimal e percentual."""

    if pd.isna(value):
        return None
    if isinstance(value, int | float):
        return float(value)

    text = str(value).strip()
    if text.upper() in NULL_TOKENS:
        return None

    is_percent = "%" in text
    text = text.replace("%", "").replace(" ", "")

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")

    try:
        number = float(text)
    except ValueError:
        return None

    return number / 100 if is_percent and number > 1 else number


def standardize_text_columns(dataframe: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Aplica clean_text nas colunas informadas quando existirem."""

    result = dataframe.copy()
    for column in columns:
        if column in result.columns:
            result[column] = result[column].map(clean_text)
    return result


def create_chave_centro_rota(centro: object, rota: object) -> str | None:
    """Cria a chave Centro + Rota usando textos ja padronizados."""

    centro_text = clean_text(centro)
    rota_text = clean_text(rota)
    if not centro_text or not rota_text:
        return None
    return f"{centro_text}{rota_text}"


def create_tipo_rota(rota: object) -> str | None:
    """Retorna os dois primeiros caracteres da rota."""

    rota_text = clean_text(rota)
    return rota_text[:2] if rota_text else None


def create_kpi_peso(kpi: object) -> str | None:
    """Agrupa KPIs de ruptura em OOS para busca de pesos."""

    kpi_text = clean_text(kpi)
    if not kpi_text:
        return None
    return "OOS" if kpi_text in OOS_KPIS else kpi_text


def create_tipo_calculo(kpi: object) -> str | None:
    """Define se o indicador e maior_melhor ou menor_melhor."""

    kpi_text = clean_text(kpi)
    if not kpi_text:
        return None
    return "menor_melhor" if kpi_text in OOS_KPIS else "maior_melhor"


def first_excel_file(raw_sources: dict[str, Path], source_key: str) -> Path:
    """Retorna o primeiro Excel encontrado para uma fonte raw."""

    source_path = raw_sources[source_key]
    files = list_excel_files(source_path)
    if not files:
        raise DataReadError(f"Nenhum arquivo Excel encontrado em {source_path}")
    return files[0]


def rename_columns_by_aliases(
    dataframe: pd.DataFrame,
    aliases: dict[str, set[str]],
) -> pd.DataFrame:
    """Renomeia colunas por aliases normalizados."""

    rename_map: dict[str, str] = {}
    for column in dataframe.columns:
        normalized = normalize_column_name(column)
        for target, accepted_names in aliases.items():
            if normalized in accepted_names:
                rename_map[column] = target
                break
    return dataframe.rename(columns=rename_map)


def require_columns(dataframe: pd.DataFrame, columns: Iterable[str], context: str) -> None:
    """Valida a presenca de colunas obrigatorias."""

    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise DataReadError(f"Colunas obrigatorias ausentes em {context}: {', '.join(missing)}")


def read_excel_with_detected_header(
    file_path: str | Path,
    required_aliases: set[str],
    max_scan_rows: int = 30,
) -> pd.DataFrame:
    """Le uma planilha tentando encontrar uma linha de cabecalho flexivel."""

    raw = pd.read_excel(file_path, header=None, engine="openpyxl")
    for index in range(min(max_scan_rows, len(raw))):
        normalized_values = {normalize_column_name(value) for value in raw.iloc[index].tolist()}
        if required_aliases.intersection(normalized_values):
            header = raw.iloc[index].tolist()
            dataframe = raw.iloc[index + 1 :].copy()
            dataframe.columns = header
            dataframe = dataframe.dropna(how="all")
            return dataframe.reset_index(drop=True)

    return pd.read_excel(file_path, engine="openpyxl")


def add_kpi_keys(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Adiciona chaves e atributos derivados de Centro, Rota e KPI."""

    result = dataframe.copy()
    result["ChaveCentroRota"] = [
        create_chave_centro_rota(centro, rota)
        for centro, rota in zip(result["Centro"], result["Rota"], strict=False)
    ]
    result["ChaveIndicador"] = (
        result["Centro"].fillna("") + result["Rota"].fillna("") + result["KPI"].fillna("")
    )
    result["TipoRota"] = result["Rota"].map(create_tipo_rota)
    result["KpiPeso"] = result["KPI"].map(create_kpi_peso)
    result["TipoCalculo"] = result["KPI"].map(create_tipo_calculo)
    return result
