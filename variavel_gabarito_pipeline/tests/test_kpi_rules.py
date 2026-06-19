from pipeline.domain.kpi_rules import normalize_kpi_name
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
