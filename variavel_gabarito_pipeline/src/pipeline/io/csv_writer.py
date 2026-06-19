"""Escrita de arquivos CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv(dataframe: pd.DataFrame, output_path: str | Path) -> Path:
    """Escreve um DataFrame em CSV no padrao Excel/Power BI Brasil."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, sep=";", encoding="utf-8-sig", index=False)
    return path
