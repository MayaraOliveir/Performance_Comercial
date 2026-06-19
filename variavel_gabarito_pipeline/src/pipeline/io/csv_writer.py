"""Escrita de arquivos CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv(dataframe: pd.DataFrame, output_path: str | Path) -> Path:
    """Escreve um DataFrame em CSV UTF-8 com separador virgula."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False, encoding="utf-8")
    return path
