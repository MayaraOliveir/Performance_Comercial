"""Diagnostico das colunas da base bruta de aderencia RED."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.core.utils import list_excel_files
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import normalize_column_name, to_number


HEADER_ROWS_TO_TEST = range(0, 12)
SPECIAL_PERCENT_NAMES = {
    "%",
    "%_1",
    "ADERENCIA",
    "ADERENCIARED",
    "ADERENCIA_RED",
}


def run() -> Path:
    """Executa o diagnostico e grava o CSV de validacao."""

    logger = configure_logger("pipeline.diagnostico_aderencia_red")
    paths_config = load_paths_config()
    input_files = list_excel_files(paths_config.values["raw_sources"]["aderencia_red"])
    if not input_files:
        raise FileNotFoundError("Nenhum Excel encontrado em data/raw/aderencia_red.")

    input_file = input_files[0]
    rows = build_diagnostic_rows(input_file)
    diagnostic = pd.DataFrame(rows)
    output_path = paths_config.values["processed"]["validation"] / "diagnostico_aderencia_red_colunas.csv"
    write_csv(diagnostic, output_path)

    candidates = diagnostic[diagnostic["parece_percentual_valida"]].copy()
    logger.info(
        "diagnostico_aderencia_red_concluido",
        extra={
            "arquivo": str(input_file),
            "linhas_relatorio": len(diagnostic),
            "colunas_candidatas": len(candidates),
            "arquivo_saida": str(output_path),
        },
    )
    print_candidate_columns(candidates)
    return output_path


def build_diagnostic_rows(file_path: str | Path) -> list[dict[str, object]]:
    """Cria linhas de diagnostico para todas as abas e cabecalhos testados."""

    excel_file = pd.ExcelFile(file_path, engine="openpyxl")
    rows: list[dict[str, object]] = []
    for sheet_name in excel_file.sheet_names:
        raw_sheet = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
        for header_row in HEADER_ROWS_TO_TEST:
            if header_row >= len(raw_sheet):
                continue
            dataframe = dataframe_from_header_row(raw_sheet, header_row)
            rows.extend(profile_dataframe_columns(dataframe, sheet_name, header_row))
    return rows


def dataframe_from_header_row(raw_sheet: pd.DataFrame, header_row: int) -> pd.DataFrame:
    """Monta um DataFrame usando a linha informada como cabecalho."""

    dataframe = raw_sheet.iloc[header_row + 1 :].copy()
    dataframe.columns = make_unique_columns(raw_sheet.iloc[header_row].tolist())
    return dataframe.dropna(how="all").reset_index(drop=True)


def make_unique_columns(columns: Iterable[object]) -> list[str]:
    """Garante nomes de colunas unicos mesmo quando o Excel repete cabecalhos."""

    seen: dict[str, int] = {}
    result: list[str] = []
    for index, column in enumerate(columns):
        base_name = _column_name(column, index)
        count = seen.get(base_name, 0)
        seen[base_name] = count + 1
        result.append(base_name if count == 0 else f"{base_name}_{count}")
    return result


def profile_dataframe_columns(
    dataframe: pd.DataFrame,
    sheet_name: str,
    header_row: int,
) -> list[dict[str, object]]:
    """Calcula metadados de preenchimento e numeros por coluna."""

    rows: list[dict[str, object]] = []
    for column in dataframe.columns:
        series = dataframe[column]
        numeric_values = series.map(to_number).dropna()
        non_null = series.dropna()
        examples = non_null.astype(str).head(5).tolist()
        rows.append(
            {
                "aba": sheet_name,
                "linha_cabecalho_testada": header_row,
                "nome_coluna": column,
                "nome_coluna_normalizado": normalize_column_name(column),
                "coluna_especial_percentual": is_special_percent_column(column),
                "qtd_nao_nulos": int(non_null.shape[0]),
                "qtd_numericos": int(numeric_values.shape[0]),
                "minimo": float(numeric_values.min()) if not numeric_values.empty else pd.NA,
                "maximo": float(numeric_values.max()) if not numeric_values.empty else pd.NA,
                "exemplos_valores": " | ".join(examples),
                "parece_percentual_valida": looks_like_valid_percent_column(column, numeric_values),
            }
        )
    return rows


def looks_like_valid_percent_column(column: object, numeric_values: pd.Series) -> bool:
    """Indica se a coluna parece conter percentuais validos."""

    if numeric_values.empty:
        return False

    normalized = normalize_column_name(column)
    in_percent_range = numeric_values.between(0, 1.5, inclusive="both").mean() >= 0.8
    has_enough_values = numeric_values.shape[0] >= 10
    is_named_as_percent = is_special_percent_column(column) or "%" in normalized or "ADERENCIA" in normalized
    return bool(has_enough_values and in_percent_range and is_named_as_percent)


def is_special_percent_column(column: object) -> bool:
    """Marca colunas com nomes esperados de aderencia/percentual."""

    return normalize_column_name(column) in SPECIAL_PERCENT_NAMES


def print_candidate_columns(candidates: pd.DataFrame) -> None:
    """Imprime no terminal as colunas que parecem percentuais validas."""

    if candidates.empty:
        print("Nenhuma coluna candidata a percentual valido foi encontrada.")
        return

    print("Colunas que parecem percentuais validas:")
    selected = candidates.sort_values(
        ["qtd_numericos", "aba", "linha_cabecalho_testada"],
        ascending=[False, True, True],
    )
    for row in selected.itertuples(index=False):
        print(
            f"- aba={row.aba} | header={row.linha_cabecalho_testada} | "
            f"coluna={row.nome_coluna} | numericos={row.qtd_numericos} | "
            f"min={row.minimo} | max={row.maximo} | exemplos={row.exemplos_valores}"
        )


def _column_name(column: object, index: int) -> str:
    if pd.isna(column):
        return f"Unnamed: {index}"
    text = str(column).strip()
    return text if text else f"Unnamed: {index}"


def main() -> None:
    run()


if __name__ == "__main__":
    main()
