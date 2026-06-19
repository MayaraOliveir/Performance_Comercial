"""Comparadores de saidas da pipeline contra gabaritos."""

from __future__ import annotations

import pandas as pd


TOLERANCE = 0.0001


def compare_promotor_outputs(
    python_result: pd.DataFrame,
    gabarito: pd.DataFrame,
    tolerance: float = TOLERANCE,
) -> pd.DataFrame:
    """Compara o resultado Python de Promotor contra o gabarito oficial."""

    python_columns = [
        "ChaveCentroRota",
        "Centro",
        "Rota",
        "AtingimentoTotal",
        "EscalaAtingida",
        "StatusPerformance",
        "Diagnostico",
    ]
    python_prepared = python_result[[column for column in python_columns if column in python_result.columns]].copy()
    gabarito_prepared = gabarito.copy()

    compared = python_prepared.merge(
        gabarito_prepared,
        on="ChaveCentroRota",
        how="outer",
        suffixes=("", "GabaritoCadastro"),
        indicator=True,
    )
    compared["DifAtingimentoTotal"] = compared["AtingimentoTotal"] - compared["AtingimentoTotalGabarito"]
    compared["DifEscalaAtingida"] = compared["EscalaAtingida"] - compared["EscalaAtingidaGabarito"]
    compared["StatusComparacao"] = [
        classify_comparison(row, tolerance)
        for _, row in compared.iterrows()
    ]
    return compared


def classify_comparison(row: pd.Series, tolerance: float = TOLERANCE) -> str:
    """Classifica uma linha comparada."""

    if row["_merge"] == "left_only":
        return "Só no Python"
    if row["_merge"] == "right_only":
        return "Só no gabarito"

    python_total = row.get("AtingimentoTotal")
    gabarito_total = row.get("AtingimentoTotalGabarito")
    python_escala = row.get("EscalaAtingida")
    gabarito_escala = row.get("EscalaAtingidaGabarito")
    status_gabarito = row.get("StatusValorGabarito")

    python_total_missing = pd.isna(python_total)
    gabarito_total_missing = pd.isna(gabarito_total)
    gabarito_sem_calculo = status_gabarito == "Sem cálculo no gabarito"

    if python_total_missing and gabarito_sem_calculo:
        return "OK - sem cálculo nos dois"
    if python_total_missing and not gabarito_total_missing:
        return "Python sem atingimento"
    if not python_total_missing and gabarito_sem_calculo:
        return "Python calculou e gabarito não"
    if not python_total_missing and gabarito_total_missing:
        return "Gabarito sem atingimento"
    if python_total_missing and gabarito_total_missing:
        return "Gabarito sem atingimento"

    total_ok = abs(float(python_total) - float(gabarito_total)) <= tolerance
    escala_ok = _numbers_match_or_both_missing(python_escala, gabarito_escala, tolerance)
    return "OK" if total_ok and escala_ok else "Diferente"


def build_validation_summary(compared: pd.DataFrame) -> pd.DataFrame:
    """Agrupa a validacao por status de comparacao."""

    work = compared.copy()
    work["AbsDifAtingimento"] = work["DifAtingimentoTotal"].abs()
    work["AbsDifEscala"] = work["DifEscalaAtingida"].abs()
    return (
        work.groupby("StatusComparacao", dropna=False)
        .agg(
            QtdRotas=("StatusComparacao", "size"),
            MediaDiferencaAtingimento=("AbsDifAtingimento", "mean"),
            MaiorDiferencaAtingimento=("AbsDifAtingimento", "max"),
            MediaDiferencaEscala=("AbsDifEscala", "mean"),
            MaiorDiferencaEscala=("AbsDifEscala", "max"),
        )
        .reset_index()
        .sort_values("QtdRotas", ascending=False)
        .reset_index(drop=True)
    )


def filter_differences(compared: pd.DataFrame) -> pd.DataFrame:
    """Retorna apenas linhas que nao bateram."""

    return compared[compared["StatusComparacao"] != "OK"].reset_index(drop=True)


def _numbers_match_or_both_missing(left: object, right: object, tolerance: float) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if pd.isna(left) or pd.isna(right):
        return False
    return abs(float(left) - float(right)) <= tolerance
