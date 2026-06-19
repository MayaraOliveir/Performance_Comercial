import pandas as pd

from pipeline.validation.comparador import classify_comparison
from pipeline.validation.gabarito_promotor import status_valor_gabarito, transform_gabarito_promotor


def test_gabarito_dash_becomes_null_and_sem_calculo() -> None:
    raw = pd.DataFrame([[None] * 14])
    raw.iloc[0, 4] = "VA300"
    raw.iloc[0, 5] = "CRBC"
    raw.iloc[0, 11] = "-"
    raw.iloc[0, 13] = "-"

    result = transform_gabarito_promotor(raw)

    assert pd.isna(result.loc[0, "AtingimentoTotalGabarito"])
    assert result.loc[0, "StatusValorGabarito"] == "Sem cálculo no gabarito"


def test_status_valor_gabarito_detects_calculated_value() -> None:
    assert status_valor_gabarito("0,85") == "Calculado no gabarito"
    assert status_valor_gabarito("-") == "Sem cálculo no gabarito"


def test_comparison_ok_with_tolerance() -> None:
    row = pd.Series(
        {
            "_merge": "both",
            "AtingimentoTotal": 0.85001,
            "AtingimentoTotalGabarito": 0.85,
            "EscalaAtingida": 0.7,
            "EscalaAtingidaGabarito": 0.70001,
            "StatusValorGabarito": "Calculado no gabarito",
        }
    )

    assert classify_comparison(row) == "OK"


def test_comparison_different_when_outside_tolerance() -> None:
    row = pd.Series(
        {
            "_merge": "both",
            "AtingimentoTotal": 0.9,
            "AtingimentoTotalGabarito": 0.85,
            "EscalaAtingida": 0.7,
            "EscalaAtingidaGabarito": 0.7,
            "StatusValorGabarito": "Calculado no gabarito",
        }
    )

    assert classify_comparison(row) == "Diferente"


def test_comparison_ok_sem_calculo_nos_dois() -> None:
    row = pd.Series(
        {
            "_merge": "both",
            "AtingimentoTotal": pd.NA,
            "AtingimentoTotalGabarito": pd.NA,
            "EscalaAtingida": pd.NA,
            "EscalaAtingidaGabarito": pd.NA,
            "StatusValorGabarito": "Sem cálculo no gabarito",
        }
    )

    assert classify_comparison(row) == "OK - sem cálculo nos dois"


def test_comparison_python_calculou_e_gabarito_nao() -> None:
    row = pd.Series(
        {
            "_merge": "both",
            "AtingimentoTotal": 0.8,
            "AtingimentoTotalGabarito": pd.NA,
            "EscalaAtingida": 0.7,
            "EscalaAtingidaGabarito": pd.NA,
            "StatusValorGabarito": "Sem cálculo no gabarito",
        }
    )

    assert classify_comparison(row) == "Python calculou e gabarito não"
