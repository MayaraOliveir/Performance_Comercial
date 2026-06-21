import pandas as pd

from pipeline.figures.promotor_vendas import build_promotor_base, build_promotor_final
from pipeline.staging.estrutura_promotor import transform_estrutura_promotor


def _build_final_for_route(
    tipo_rota: str,
    metas: pd.DataFrame,
    indicadores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rota = f"{tipo_rota}300"
    chave = f"CRBC{rota}"
    return build_promotor_final(
        dim_rotas=pd.DataFrame(
            {
                "ChaveCentroRota": [chave],
                "Centro": ["CRBC"],
                "Rota": [rota],
                "TipoRota": [tipo_rota],
            }
        ),
        metas=metas.assign(ChaveCentroRota=chave),
        indicadores=(
            indicadores.assign(ChaveCentroRota=chave)
            if indicadores is not None
            else pd.DataFrame(columns=["ChaveCentroRota", "KPI", "REALIZADO"])
        ),
        aderencia_red=pd.DataFrame(
            {
                "ChaveCentroRota": [chave],
                "AderenciaRED": [0.90],
            }
        ),
        pesos=pd.DataFrame(
            {
                "TipoRota": [tipo_rota, tipo_rota],
                "KpiPeso": ["RED", "OOS"],
                "Peso": [0.85, 0.15],
            }
        ),
        escalonada=pd.DataFrame(
            {
                "FaixaDe": [0.0],
                "FaixaAte": [2.0],
                "EscalaAtingida": [0.7],
            }
        ),
    )


def test_pa_with_meta_and_realizado_rpt_calculates_rpt_normally() -> None:
    final = _build_final_for_route(
        "PA",
        pd.DataFrame(
            {
                "KPI": ["RED", "RPT"],
                "Meta": [100.0, 5.0],
                "RealizadoArquivoMetas": [90.0, 10.0],
            }
        ),
        pd.DataFrame({"KPI": ["RED", "RPT"], "REALIZADO": [90.0, 10.0]}),
    )

    row = final.iloc[0]
    assert row["StatusRPT"] == "Calculável"
    assert row["AtingimentoRPT"] == 0.075
    assert row["AtingimentoTotal"] == 0.84


def test_pa_without_meta_rpt_generates_diagnostic() -> None:
    final = _build_final_for_route(
        "PA",
        pd.DataFrame(
            {
                "KPI": ["RED"],
                "Meta": [100.0],
                "RealizadoArquivoMetas": [90.0],
            }
        ),
        pd.DataFrame({"KPI": ["RED"], "REALIZADO": [90.0]}),
    )

    assert "Sem meta RPT" in final.iloc[0]["Diagnostico"]


def test_pa_without_realizado_rpt_generates_diagnostic() -> None:
    final = _build_final_for_route(
        "PA",
        pd.DataFrame(
            {
                "KPI": ["RED", "RPT"],
                "Meta": [100.0, 5.0],
                "RealizadoArquivoMetas": [90.0, pd.NA],
            }
        ),
        pd.DataFrame({"KPI": ["RED"], "REALIZADO": [90.0]}),
    )

    row = final.iloc[0]
    assert row["StatusRPT"] == "Sem fonte de realizado RPT"
    assert "Sem fonte RealizadoRPT" in row["Diagnostico"]


def test_pb_without_rpt_does_not_generate_rpt_diagnostic_and_uses_only_red() -> None:
    final = _build_final_for_route(
        "PB",
        pd.DataFrame(
            {
                "KPI": ["RED"],
                "Meta": [100.0],
                "RealizadoArquivoMetas": [90.0],
            }
        ),
        pd.DataFrame({"KPI": ["RED"], "REALIZADO": [90.0]}),
    )

    row = final.iloc[0]
    assert "Sem meta RPT" not in row["Diagnostico"]
    assert "Sem realizado RPT" not in row["Diagnostico"]
    assert row["StatusRPT"] == "Não se aplica"
    assert row["AtingimentoRPT"] == 0.0
    assert row["AtingimentoTotal"] == row["AtingimentoRED"]


def test_route_without_red_and_rpt_has_zero_total_and_irregular_status() -> None:
    final = _build_final_for_route(
        "PA",
        pd.DataFrame(
            {
                "KPI": [],
                "Meta": [],
                "RealizadoArquivoMetas": [],
            }
        ),
    )

    row = final.iloc[0]
    assert row["AtingimentoTotal"] == 0.0
    assert row["StatusPerformance"] == "Irregular"


def test_rpt_with_zero_weight_does_not_change_total() -> None:
    final = build_promotor_final(
        dim_rotas=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPC300"],
                "Centro": ["CRBC"],
                "Rota": ["PC300"],
                "TipoRota": ["PC"],
            }
        ),
        metas=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPC300", "CRBCPC300"],
                "KPI": ["RED", "RPT"],
                "Meta": [100.0, 5.0],
                "RealizadoArquivoMetas": [90.0, 10.0],
            }
        ),
        indicadores=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPC300", "CRBCPC300"],
                "KPI": ["RED", "RPT"],
                "REALIZADO": [90.0, 10.0],
            }
        ),
        aderencia_red=pd.DataFrame({"ChaveCentroRota": ["CRBCPC300"], "AderenciaRED": [0.9]}),
        pesos=pd.DataFrame({"TipoRota": ["PC", "PC"], "KpiPeso": ["RED", "OOS"], "Peso": [1.0, 0.0]}),
        escalonada=pd.DataFrame({"FaixaDe": [0.0], "FaixaAte": [2.0], "EscalaAtingida": [0.0]}),
    )

    row = final.iloc[0]
    assert row["AtingimentoRPT"] == 0.0
    assert row["AtingimentoTotal"] == row["AtingimentoRED"]


def test_promotor_dimension_comes_from_estrutura_promotor_not_agents() -> None:
    raw = pd.DataFrame([[pd.NA] * 16 for _ in range(4)])
    raw.iloc[2, 4] = "Rota"
    raw.iloc[2, 5] = "Centro"
    raw.iloc[2, 11] = "CHAVE"
    raw.iloc[2, 12] = "META"
    raw.iloc[2, 13] = "REAL"
    raw.iloc[2, 14] = "META2"
    raw.iloc[2, 15] = "REAL2"
    raw.iloc[3, 4] = "PB001"
    raw.iloc[3, 5] = "CRBC"
    raw.iloc[3, 11] = "CRBCPB001"
    raw.iloc[3, 12] = 0.65
    raw.iloc[3, 13] = 0.7

    estrutura, dim_rotas, _ = transform_estrutura_promotor(raw)

    assert len(estrutura) == 1
    assert dim_rotas.loc[0, "ChaveCentroRota"] == "CRBCPB001"
    assert dim_rotas.loc[0, "TipoRota"] == "PB"


def test_promotor_red_gate_below_85_sets_red_achievement_to_zero() -> None:
    final = build_promotor_final(
        dim_rotas=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300"],
                "Centro": ["CRBC"],
                "Rota": ["PA300"],
                "TipoRota": ["PA"],
            }
        ),
        metas=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300", "CRBCPA300"],
                "KPI": ["RED", "RPT"],
                "Meta": [100.0, 5.0],
                "RealizadoArquivoMetas": [90.0, 10.0],
            }
        ),
        indicadores=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300", "CRBCPA300"],
                "KPI": ["RED", "RPT"],
                "REALIZADO": [90.0, 10.0],
            }
        ),
        aderencia_red=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300"],
                "AderenciaRED": [0.84],
            }
        ),
        pesos=pd.DataFrame(
            {
                "TipoRota": ["PA", "PA"],
                "KpiPeso": ["RED", "OOS"],
                "Peso": [0.85, 0.15],
            }
        ),
        escalonada=pd.DataFrame(
            {
                "FaixaDe": [0.0],
                "FaixaAte": [1.0],
                "EscalaAtingida": [0.7],
            }
        ),
    )

    row = final.iloc[0]
    assert row["StatusGatilhoRED"] == "Aderência abaixo de 85%"
    assert row["AtingimentoRED"] == 0.0
    assert row["AtingimentoRPT"] == 0.075
    assert row["AtingimentoTotal"] == 0.075


def test_promotor_base_uses_estrutura_for_route_and_metas_for_meta() -> None:
    base = build_promotor_base(
        estrutura_promotor=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300"],
                "Centro": ["CRBC"],
                "Rota": ["PA300"],
                "TipoRota": ["PA"],
                "MetaRED": [0.10],
            }
        ),
        metas=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300"],
                "KPI": ["RED"],
                "Meta": [0.65],
            }
        ),
        indicadores=pd.DataFrame(columns=["ChaveCentroRota", "KPI", "REALIZADO"]),
    )

    row = base.iloc[0]
    assert row["MetaRED"] == 0.65
    assert row["MetaREDEstruturaOriginal"] == 0.10
    assert row["FonteEstrutura"] == "estrutura_mensal"


def test_promotor_base_uses_indicadores_for_realizado() -> None:
    base = build_promotor_base(
        estrutura_promotor=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300"],
                "Centro": ["CRBC"],
                "Rota": ["PA300"],
                "TipoRota": ["PA"],
                "RealizadoRED": [0.10],
            }
        ),
        metas=pd.DataFrame(columns=["ChaveCentroRota", "KPI", "Meta"]),
        indicadores=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300"],
                "KPI": ["RED"],
                "REALIZADO": [0.88],
            }
        ),
    )

    row = base.iloc[0]
    assert row["RealizadoRED"] == 0.88
    assert row["RealizadoREDEstruturaOriginal"] == 0.10
    assert row["FonteRealizado"] == "Indicadores parcial RED"
    assert row["FonteRealizadoRPT"] == "fonte_rpt_nao_encontrada"


def test_promotor_base_keeps_audit_columns() -> None:
    base = build_promotor_base(
        estrutura_promotor=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPB300"],
                "Centro": ["CRBC"],
                "Rota": ["PB300"],
                "TipoRota": ["PB"],
                "MetaRED": [0.10],
                "RealizadoRED": [0.20],
                "MetaRPT": [0.30],
                "RealizadoRPT": [0.40],
            }
        ),
        metas=pd.DataFrame(columns=["ChaveCentroRota", "KPI", "Meta"]),
        indicadores=pd.DataFrame(columns=["ChaveCentroRota", "KPI", "REALIZADO"]),
    )

    for column in [
        "FonteEstrutura",
        "FonteMeta",
        "FonteRealizado",
        "FonteRealizadoRED",
        "FonteRealizadoRPT",
        "MetaREDEstruturaOriginal",
        "RealizadoREDEstruturaOriginal",
        "MetaRPTEstruturaOriginal",
        "RealizadoRPTEstruturaOriginal",
    ]:
        assert column in base.columns


def test_promotor_calculation_uses_promotor_base_values() -> None:
    promotor_base = pd.DataFrame(
        {
            "ChaveCentroRota": ["CRBCPA300"],
            "Centro": ["CRBC"],
            "Rota": ["PA300"],
            "TipoRota": ["PA"],
            "MetaRED": [100.0],
            "RealizadoRED": [90.0],
            "MetaRPT": [5.0],
            "RealizadoRPT": [10.0],
            "FonteEstrutura": ["Estrutura Promotor"],
            "FonteMeta": ["Metas"],
            "FonteRealizado": ["Indicadores"],
        }
    )
    final = build_promotor_final(
        promotor_base=promotor_base,
        aderencia_red=pd.DataFrame({"ChaveCentroRota": ["CRBCPA300"], "AderenciaRED": [0.9]}),
        pesos=pd.DataFrame({"TipoRota": ["PA", "PA"], "KpiPeso": ["RED", "OOS"], "Peso": [0.85, 0.15]}),
        escalonada=pd.DataFrame({"FaixaDe": [0.0], "FaixaAte": [2.0], "EscalaAtingida": [0.7]}),
    )

    row = final.iloc[0]
    assert row["AtingimentoRED"] == 0.765
    assert row["AtingimentoRPT"] == 0.075
    assert row["AtingimentoTotal"] == 0.84


def test_pa_with_positive_rpt_weight_and_missing_realizado_has_explicit_status() -> None:
    final = build_promotor_final(
        promotor_base=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCPA300"],
                "Centro": ["CRBC"],
                "Rota": ["PA300"],
                "TipoRota": ["PA"],
                "MetaRED": [100.0],
                "RealizadoRED": [90.0],
                "MetaRPT": [5.0],
                "RealizadoRPT": [pd.NA],
                "FonteRealizadoRPT": ["fonte_rpt_nao_encontrada"],
            }
        ),
        aderencia_red=pd.DataFrame({"ChaveCentroRota": ["CRBCPA300"], "AderenciaRED": [0.9]}),
        pesos=pd.DataFrame({"TipoRota": ["PA", "PA"], "KpiPeso": ["RED", "OOS"], "Peso": [0.85, 0.15]}),
        escalonada=pd.DataFrame({"FaixaDe": [0.0], "FaixaAte": [2.0], "EscalaAtingida": [0.7]}),
    )

    row = final.iloc[0]
    assert row["StatusRPT"] == "Sem fonte de realizado RPT"
    assert pd.isna(row["RealizadoRPT"])
    assert "Sem fonte RealizadoRPT" in row["Diagnostico"]
