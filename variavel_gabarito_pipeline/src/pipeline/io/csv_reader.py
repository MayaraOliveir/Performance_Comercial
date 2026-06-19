"""Leitura padronizada de arquivos CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_csv(input_path: str | Path) -> pd.DataFrame:
    """Le um CSV no padrao Excel/Power BI Brasil."""

    return pd.read_csv(Path(input_path), sep=";", encoding="utf-8-sig")
