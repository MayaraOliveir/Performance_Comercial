"""Regras de aplicacao de tabelas escalonadas."""

from __future__ import annotations

import pandas as pd


def find_escalonada_value(atingimento_total: object, escalonada: pd.DataFrame) -> float | None:
    """Busca a escala atingida como VLOOKUP aproximado."""

    if pd.isna(atingimento_total):
        return None

    value = float(atingimento_total)
    matches = escalonada[escalonada["FaixaDe"] <= value].sort_values("FaixaDe")
    if matches.empty:
        return None
    return float(matches.iloc[-1]["EscalaAtingida"])


def apply_escalonada(dataframe: pd.DataFrame, escalonada: pd.DataFrame) -> pd.Series:
    """Aplica a tabela escalonada ao AtingimentoTotal de cada linha."""

    return dataframe["AtingimentoTotal"].map(lambda value: find_escalonada_value(value, escalonada))
