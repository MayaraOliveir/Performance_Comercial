"""Diagnosticos e motivos de divergencia."""

from __future__ import annotations

import pandas as pd


def build_promotor_diagnostics(row: pd.Series) -> str:
    """Monta diagnosticos uteis para o calculo de Promotor."""

    diagnostics: list[str] = []

    _append_if_missing(diagnostics, row, "MetaRED", "Sem meta RED")
    _append_if_missing(diagnostics, row, "RealizadoRED", "Sem realizado RED")
    _append_if_missing(diagnostics, row, "AderenciaRED", "Sem aderência RED")
    _append_if_missing(diagnostics, row, "PesoRED", "Sem peso RED")
    _append_if_missing(diagnostics, row, "MetaRPT", "Sem meta RPT")
    _append_if_missing(diagnostics, row, "RealizadoRPT", "Sem realizado RPT")
    _append_if_missing(diagnostics, row, "PesoRPT", "Sem peso RPT")

    if not pd.isna(row.get("AtingimentoTotal")) and pd.isna(row.get("EscalaAtingida")):
        diagnostics.append("Sem faixa escalonada")

    return "OK" if not diagnostics else " | ".join(diagnostics)


def summarize_diagnostics(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Gera resumo por diagnostico e status."""

    return (
        dataframe.groupby(["StatusPerformance", "Diagnostico"], dropna=False)
        .size()
        .reset_index(name="QtdRotas")
        .sort_values(["StatusPerformance", "QtdRotas"], ascending=[True, False])
        .reset_index(drop=True)
    )


def _append_if_missing(diagnostics: list[str], row: pd.Series, column: str, message: str) -> None:
    if pd.isna(row.get(column)):
        diagnostics.append(message)
