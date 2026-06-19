"""Figura comercial PROMOTOR DE VENDAS."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import PathsConfig, load_paths_config
from pipeline.domain.diagnosticos import build_promotor_diagnostics, summarize_diagnostics
from pipeline.domain.escalonada import apply_escalonada
from pipeline.domain.performance import (
    calculate_performance,
    calculate_weighted_achievement,
    classify_status_performance,
    sum_ignoring_nulls,
)
from pipeline.figures.base import CommercialFigure
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import create_tipo_rota


class PromotorVendas(CommercialFigure):
    """Orquestrador da apuracao de Promotor de Vendas."""

    def run(self) -> list[Path]:
        paths_config = load_paths_config()
        return run_promotor_calculation(paths_config)


def run_promotor_calculation(paths_config: PathsConfig | None = None) -> list[Path]:
    """Executa o calculo de Promotor de Vendas a partir das bases tratadas."""

    paths_config = paths_config or load_paths_config()
    logger = configure_logger("pipeline.promotor_vendas")

    inputs = _load_inputs(paths_config)
    final = build_promotor_final(
        dim_rotas=inputs["dim_rotas"],
        metas=inputs["metas"],
        indicadores=inputs["indicadores"],
        aderencia_red=inputs["aderencia_red"],
        pesos=inputs["pesos"],
        escalonada=inputs["escalonada"],
    )
    calculo = build_promotor_calculo(final)
    diagnostico = summarize_diagnostics(final)

    facts_dir = paths_config.values["processed"]["facts"]
    outputs = [
        write_csv(calculo, facts_dir / "fat_promotor_calculo.csv"),
        write_csv(final, facts_dir / "fat_promotor_final.csv"),
        write_csv(diagnostico, facts_dir / "diag_promotor.csv"),
    ]

    logger.info(
        "calculo_promotor_concluido",
        extra={
            "linhas_calculo": len(calculo),
            "linhas_final": len(final),
            "linhas_diagnostico": len(diagnostico),
        },
    )
    return outputs


def build_promotor_final(
    dim_rotas: pd.DataFrame,
    metas: pd.DataFrame,
    indicadores: pd.DataFrame,
    aderencia_red: pd.DataFrame,
    pesos: pd.DataFrame,
    escalonada: pd.DataFrame,
) -> pd.DataFrame:
    """Monta uma linha consolidada por rota elegivel de Promotor."""

    base = dim_rotas[["ChaveCentroRota", "Centro", "Rota", "TipoRota"]].copy()
    base["TipoRota"] = base["TipoRota"].fillna(base["Rota"].map(create_tipo_rota))
    base = base.drop_duplicates(subset=["ChaveCentroRota"]).reset_index(drop=True)

    base = base.merge(_build_kpi_metrics(metas, indicadores, "RED", "RED"), on="ChaveCentroRota", how="left")
    base = base.merge(_build_kpi_metrics(metas, indicadores, "RPT", "RPT"), on="ChaveCentroRota", how="left")
    base = base.merge(_prepare_aderencia(aderencia_red), on="ChaveCentroRota", how="left")
    base = base.merge(_prepare_peso(pesos, "RED", "PesoRED"), on="TipoRota", how="left")
    base = base.merge(_prepare_peso(pesos, "OOS", "PesoRPT"), on="TipoRota", how="left")

    base["PerformanceRED"] = [
        calculate_performance(meta, realizado, "maior_melhor")
        for meta, realizado in zip(base["MetaRED"], base["RealizadoRED"], strict=False)
    ]
    base["PerformanceRPT"] = [
        calculate_performance(meta, realizado, "menor_melhor")
        for meta, realizado in zip(base["MetaRPT"], base["RealizadoRPT"], strict=False)
    ]
    base["StatusGatilhoRED"] = base["AderenciaRED"].map(_status_gatilho_red)
    base["AtingimentoRED"] = [
        _calculate_red_achievement(performance, peso, aderencia)
        for performance, peso, aderencia in zip(
            base["PerformanceRED"],
            base["PesoRED"],
            base["AderenciaRED"],
            strict=False,
        )
    ]
    base["AtingimentoRPT"] = [
        calculate_weighted_achievement(performance, peso)
        for performance, peso in zip(base["PerformanceRPT"], base["PesoRPT"], strict=False)
    ]
    base["AtingimentoTotal"] = [
        sum_ignoring_nulls(red, rpt)
        for red, rpt in zip(base["AtingimentoRED"], base["AtingimentoRPT"], strict=False)
    ]
    base["EscalaAtingida"] = apply_escalonada(base, escalonada)
    base["StatusPerformance"] = base["AtingimentoTotal"].map(classify_status_performance)
    base["Diagnostico"] = base.apply(build_promotor_diagnostics, axis=1)

    output_columns = [
        "ChaveCentroRota",
        "Centro",
        "Rota",
        "TipoRota",
        "MetaRED",
        "RealizadoRED",
        "PerformanceRED",
        "AderenciaRED",
        "AderenciaREDOriginal",
        "StatusAderenciaRED",
        "StatusGatilhoRED",
        "PesoRED",
        "AtingimentoRED",
        "MetaRPT",
        "RealizadoRPT",
        "PerformanceRPT",
        "PesoRPT",
        "AtingimentoRPT",
        "AtingimentoTotal",
        "EscalaAtingida",
        "StatusPerformance",
        "Diagnostico",
    ]
    return base[[column for column in output_columns if column in base.columns]]


def build_promotor_calculo(final: pd.DataFrame) -> pd.DataFrame:
    """Gera fato longo por rota e KPI para auditoria."""

    red = final[
        [
            "ChaveCentroRota",
            "Centro",
            "Rota",
            "TipoRota",
            "MetaRED",
            "RealizadoRED",
            "PerformanceRED",
            "PesoRED",
            "AtingimentoRED",
            "AderenciaRED",
            "StatusGatilhoRED",
        ]
    ].rename(
        columns={
            "MetaRED": "Meta",
            "RealizadoRED": "Realizado",
            "PerformanceRED": "Performance",
            "PesoRED": "Peso",
            "AtingimentoRED": "Atingimento",
        }
    )
    red["KPI"] = "RED"

    rpt = final[
        [
            "ChaveCentroRota",
            "Centro",
            "Rota",
            "TipoRota",
            "MetaRPT",
            "RealizadoRPT",
            "PerformanceRPT",
            "PesoRPT",
            "AtingimentoRPT",
        ]
    ].rename(
        columns={
            "MetaRPT": "Meta",
            "RealizadoRPT": "Realizado",
            "PerformanceRPT": "Performance",
            "PesoRPT": "Peso",
            "AtingimentoRPT": "Atingimento",
        }
    )
    rpt["KPI"] = "RPT"
    rpt["AderenciaRED"] = pd.NA
    rpt["StatusGatilhoRED"] = pd.NA

    columns = [
        "ChaveCentroRota",
        "Centro",
        "Rota",
        "TipoRota",
        "KPI",
        "Meta",
        "Realizado",
        "Performance",
        "Peso",
        "Atingimento",
        "AderenciaRED",
        "StatusGatilhoRED",
    ]
    return pd.concat([red[columns], rpt[columns]], ignore_index=True)


def _load_inputs(paths_config: PathsConfig) -> dict[str, pd.DataFrame]:
    staging_dir = paths_config.values["processed"]["staging"]
    dimensions_dir = paths_config.values["processed"]["dimensions"]
    return {
        "metas": read_csv(staging_dir / "stg_metas.csv"),
        "indicadores": read_csv(staging_dir / "stg_indicadores.csv"),
        "agentes_promotor": read_csv(staging_dir / "stg_agentes_promotor.csv"),
        "dim_rotas": read_csv(dimensions_dir / "dim_rotas_promotor.csv"),
        "aderencia_red": read_csv(staging_dir / "stg_aderencia_red.csv"),
        "pesos": read_csv(staging_dir / "stg_pesos.csv"),
        "escalonada": read_csv(staging_dir / "stg_escalonada_promotor.csv"),
    }


def _build_kpi_metrics(
    metas: pd.DataFrame,
    indicadores: pd.DataFrame,
    source_kpi: str,
    output_suffix: str,
) -> pd.DataFrame:
    meta = _first_by_key(
        metas[metas["KPI"] == source_kpi],
        value_column="Meta",
        output_column=f"Meta{output_suffix}",
    )
    realizado_indicadores = _first_by_key(
        indicadores[indicadores["KPI"] == source_kpi],
        value_column="REALIZADO",
        output_column=f"Realizado{output_suffix}Indicadores",
    )
    realizado_metas = _first_by_key(
        metas[metas["KPI"] == source_kpi],
        value_column="RealizadoArquivoMetas",
        output_column=f"Realizado{output_suffix}Metas",
    )

    metrics = meta.merge(realizado_indicadores, on="ChaveCentroRota", how="outer")
    metrics = metrics.merge(realizado_metas, on="ChaveCentroRota", how="outer")
    metrics[f"Realizado{output_suffix}"] = metrics[f"Realizado{output_suffix}Indicadores"].combine_first(
        metrics[f"Realizado{output_suffix}Metas"]
    )
    return metrics[["ChaveCentroRota", f"Meta{output_suffix}", f"Realizado{output_suffix}"]]


def _first_by_key(dataframe: pd.DataFrame, value_column: str, output_column: str) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame(columns=["ChaveCentroRota", output_column])
    return (
        dataframe.dropna(subset=["ChaveCentroRota"])
        .sort_values("ChaveCentroRota")
        .groupby("ChaveCentroRota", as_index=False)[value_column]
        .first()
        .rename(columns={value_column: output_column})
    )


def _prepare_aderencia(aderencia_red: pd.DataFrame) -> pd.DataFrame:
    result = aderencia_red.copy()
    if "AderenciaREDValida" in result.columns:
        result["AderenciaREDOriginal"] = result["AderenciaRED"]
        result["AderenciaRED"] = result["AderenciaREDValida"]

    selected_columns = ["ChaveCentroRota", "AderenciaRED"]
    if "AderenciaREDOriginal" in result.columns:
        selected_columns.append("AderenciaREDOriginal")
    if "StatusAderenciaRED" in result.columns:
        selected_columns.append("StatusAderenciaRED")

    return result[selected_columns].drop_duplicates(subset=["ChaveCentroRota"]).reset_index(drop=True)


def _prepare_peso(pesos: pd.DataFrame, kpi_peso: str, output_column: str) -> pd.DataFrame:
    result = pesos[pesos["KpiPeso"] == kpi_peso][["TipoRota", "Peso"]].copy()
    return result.drop_duplicates(subset=["TipoRota"]).rename(columns={"Peso": output_column})


def _status_gatilho_red(aderencia: object) -> str:
    if pd.isna(aderencia):
        return "Sem aderência RED"
    if float(aderencia) < 0.85:
        return "Aderência abaixo de 85%"
    return "Aderência OK"


def _calculate_red_achievement(performance: object, peso: object, aderencia: object) -> float | None:
    if pd.isna(aderencia):
        return None
    if float(aderencia) < 0.85:
        return 0.0
    return calculate_weighted_achievement(performance, peso)
