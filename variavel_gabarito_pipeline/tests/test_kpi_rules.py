from pipeline.domain.kpi_rules import normalize_kpi_name
from pipeline.domain.performance import (
    calculate_performance,
    classify_status_performance,
    sum_ignoring_nulls,
)
from pipeline.staging.common import create_kpi_peso, create_tipo_calculo


def test_normalize_kpi_name_strips_uppercases_and_collapses_spaces() -> None:
    assert normalize_kpi_name("  positivacao   total  ") == "POSITIVACAO TOTAL"


def test_create_kpi_peso_groups_ruptura_indicators_as_oos() -> None:
    assert create_kpi_peso("rpt") == "OOS"
    assert create_kpi_peso(" ruptura ") == "OOS"
    assert create_kpi_peso("POSITIVACAO") == "POSITIVACAO"


def test_create_tipo_calculo_uses_menor_melhor_for_oos_group() -> None:
    assert create_tipo_calculo("OOS") == "menor_melhor"
    assert create_tipo_calculo("POSITIVACAO") == "maior_melhor"


def test_calculate_performance_maior_melhor() -> None:
    assert calculate_performance(meta=100, realizado=80, tipo_calculo="maior_melhor") == 0.8


def test_calculate_performance_menor_melhor() -> None:
    assert calculate_performance(meta=5, realizado=10, tipo_calculo="menor_melhor") == 0.5


def test_sum_ignoring_nulls_preserves_null_when_all_missing() -> None:
    assert sum_ignoring_nulls(0.2, None, 0.3) == 0.5
    assert sum_ignoring_nulls(None, None) is None


def test_classify_status_performance() -> None:
    assert classify_status_performance(None) == "Sem cálculo"
    assert classify_status_performance(0.70) == "Irregular"
    assert classify_status_performance(0.75) == "Regular"
    assert classify_status_performance(1.01) == "Alta"
    assert classify_status_performance(0.90) == "Em linha"
