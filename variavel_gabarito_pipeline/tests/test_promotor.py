import pandas as pd

from pipeline.figures.promotor_vendas import build_promotor_final


def test_promotor_red_gate_below_85_sets_red_achievement_to_zero() -> None:
    final = build_promotor_final(
        dim_rotas=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCVA300"],
                "Centro": ["CRBC"],
                "Rota": ["VA300"],
                "TipoRota": ["VA"],
            }
        ),
        metas=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCVA300", "CRBCVA300"],
                "KPI": ["RED", "RPT"],
                "Meta": [100.0, 5.0],
                "RealizadoArquivoMetas": [90.0, 10.0],
            }
        ),
        indicadores=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCVA300"],
                "KPI": ["RED"],
                "REALIZADO": [90.0],
            }
        ),
        aderencia_red=pd.DataFrame(
            {
                "ChaveCentroRota": ["CRBCVA300"],
                "AderenciaRED": [0.84],
            }
        ),
        pesos=pd.DataFrame(
            {
                "TipoRota": ["VA", "VA"],
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
