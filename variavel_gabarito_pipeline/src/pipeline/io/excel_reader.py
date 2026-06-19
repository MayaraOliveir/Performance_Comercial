"""Leitura e inspecao de arquivos Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def inspect_excel_workbook(file_path: str | Path) -> list[dict[str, object]]:
    """Retorna metadados basicos de todas as abas de um arquivo Excel."""

    path = Path(file_path)
    rows: list[dict[str, object]] = []

    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        for sheet_name in workbook.sheet_names:
            dataframe = pd.read_excel(workbook, sheet_name=sheet_name)
            rows.append(
                {
                    "arquivo": path.name,
                    "aba": sheet_name,
                    "qtd_linhas": int(dataframe.shape[0]),
                    "qtd_colunas": int(dataframe.shape[1]),
                    "colunas_detectadas": "|".join(str(column) for column in dataframe.columns),
                }
            )

    return rows
