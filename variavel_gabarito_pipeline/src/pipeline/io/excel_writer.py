"""Escrita de arquivos Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_excel(dataframe: pd.DataFrame, output_path: str | Path, sheet_name: str = "dados") -> Path:
    """Escreve um DataFrame em um arquivo Excel."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
    return path
