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
    promotor_base = build_promotor_base(
        estrutura_promotor=inputs["estrutura_promotor"],
        metas=inputs["metas"],
        indicadores=inputs["indicadores"],
    )
    facts_dir = paths_config.values["processed"]["facts"]
    validation_dir = paths_config.values["processed"]["validation"]
    promotor_base_path = write_csv(promotor_base, facts_dir / "fat_promotor_base.csv")
    promotor_base = read_csv(promotor_base_path)

    final = build_promotor_final(
        promotor_base=promotor_base,
        aderencia_red=inputs["aderencia_red"],
        pesos=inputs["pesos"],
        escalonada=inputs["escalonada"],
    )
    calculo = build_promotor_calculo(final)
    diagnostico = summarize_diagnostics(final)
    diagnostico_base = summarize_promotor_base(promotor_base)
    validacao_path = validation_dir / "validacao_promotor_gabarito.csv"
    validacao = read_csv(validacao_path) if validacao_path.exists() else None
    diagnostico_fonte_rpt = summarize_fonte_rpt_promotor(final, validacao)

    outputs = [
        promotor_base_path,
        write_csv(calculo, facts_dir / "fat_promotor_calculo.csv"),
        write_csv(final, facts_dir / "fat_promotor_final.csv"),
        write_csv(diagnostico, facts_dir / "diag_promotor.csv"),
        write_csv(diagnostico_base, validation_dir / "resumo_promotor_base.csv"),
        write_csv(diagnostico_fonte_rpt, validation_dir / "resumo_fonte_rpt_promotor.csv"),
    ]

    logger.info(
        "calculo_promotor_concluido",
        extra={
            "linhas_calculo": len(calculo),
            "linhas_final": len(final),
            "linhas_diagnostico": len(diagnostico),
            "linhas_base": len(promotor_base),
        },
    )
    return outputs


def build_promotor_base(
    estrutura_promotor: pd.DataFrame,
    metas: pd.DataFrame,
    indicadores: pd.DataFrame,
) -> pd.DataFrame:
    """Monta a base auditavel de elegibilidade, metas e realizados do Promotor."""

    base = _prepare_estrutura_base(estrutura_promotor)
    base = base.merge(_build_meta_metrics(metas, "RED", "RED"), on="ChaveCentroRota", how="left")
    base = base.merge(_build_meta_metrics(metas, "RPT", "RPT"), on="ChaveCentroRota", how="left")
    base = base.merge(_build_realizado_metrics(indicadores, "RED", "RED"), on="ChaveCentroRota", how="left")
    base = base.merge(_build_realizado_metrics(indicadores, "RPT", "RPT"), on="ChaveCentroRota", how="left")

    if "FonteEstrutura" not in base.columns:
        base["FonteEstrutura"] = "estrutura_mensal"
    base["FonteMeta"] = [
        _source_status("Metas", red, rpt)
        for red, rpt in zip(base["MetaRED"], base["MetaRPT"], strict=False)
    ]
    base["FonteRealizado"] = [
        _source_status("Indicadores", red, rpt)
        for red, rpt in zip(base["RealizadoRED"], base["RealizadoRPT"], strict=False)
    ]
    base["FonteRealizadoRED"] = base["RealizadoRED"].map(
        lambda value: _single_source_status("indicadores", value, "fonte_red_nao_encontrada")
    )
    base["FonteRealizadoRPT"] = base["RealizadoRPT"].map(
        lambda value: _single_source_status("indicadores", value, "fonte_rpt_nao_encontrada")
    )
    return base


def summarize_promotor_base(promotor_base: pd.DataFrame) -> pd.DataFrame:
    """Resume cobertura de metas e realizados na base intermediaria."""

    rows = [
        {"Metrica": "total_rotas_estrutura_promotor", "Valor": len(promotor_base), "Categoria": pd.NA},
        {"Metrica": "rotas_com_meta_red", "Valor": int(promotor_base["MetaRED"].notna().sum()), "Categoria": pd.NA},
        {
            "Metrica": "rotas_com_realizado_red",
            "Valor": int(promotor_base["RealizadoRED"].notna().sum()),
            "Categoria": pd.NA,
        },
        {"Metrica": "rotas_com_meta_rpt", "Valor": int(promotor_base["MetaRPT"].notna().sum()), "Categoria": pd.NA},
        {
            "Metrica": "rotas_com_realizado_rpt",
            "Valor": int(promotor_base["RealizadoRPT"].notna().sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "rotas_sem_meta",
            "Valor": int(promotor_base[["MetaRED", "MetaRPT"]].isna().all(axis=1).sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "rotas_sem_realizado",
            "Valor": int(promotor_base[["RealizadoRED", "RealizadoRPT"]].isna().all(axis=1).sum()),
            "Categoria": pd.NA,
        },
    ]
    for source, count in promotor_base["FonteMeta"].value_counts(dropna=False).items():
        rows.append({"Metrica": "quantidade_por_fonte_meta", "Valor": int(count), "Categoria": source})
    for source, count in promotor_base["FonteRealizado"].value_counts(dropna=False).items():
        rows.append({"Metrica": "quantidade_por_fonte_realizado", "Valor": int(count), "Categoria": source})
    if "FonteRealizadoRPT" in promotor_base.columns:
        for source, count in promotor_base["FonteRealizadoRPT"].value_counts(dropna=False).items():
            rows.append({"Metrica": "quantidade_por_fonte_realizado_rpt", "Valor": int(count), "Categoria": source})
    return pd.DataFrame(rows)


def summarize_fonte_rpt_promotor(
    final: pd.DataFrame,
    validation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Resume a disponibilidade da fonte oficial de RealizadoRPT."""

    pa = final[final["TipoRota"] == "PA"].copy()
    pa_sem_fonte = pa[pa["StatusRPT"] == "Sem fonte de realizado RPT"].copy()
    rows = [
        {"Metrica": "total_rotas_pa", "Valor": len(pa), "Categoria": pd.NA},
        {"Metrica": "rotas_pa_com_meta_rpt", "Valor": int(pa["MetaRPT"].notna().sum()), "Categoria": pd.NA},
        {
            "Metrica": "rotas_pa_com_realizado_rpt_encontrado",
            "Valor": int(pa["RealizadoRPT"].notna().sum()),
            "Categoria": pd.NA,
        },
        {"Metrica": "rotas_pa_sem_fonte_realizado_rpt", "Valor": len(pa_sem_fonte), "Categoria": pd.NA},
    ]
    if "FonteRealizadoRPT" in final.columns:
        for source, count in final["FonteRealizadoRPT"].value_counts(dropna=False).items():
            rows.append({"Metrica": "fonte_realizado_rpt_por_quantidade", "Valor": int(count), "Categoria": source})

    if validation is not None and not validation.empty:
        explained = validation.merge(pa_sem_fonte[["ChaveCentroRota"]], on="ChaveCentroRota", how="inner")
        explained = explained[explained["StatusComparacao"] != "OK"]
        rows.append(
            {
                "Metrica": "impacto_estimado_diferencas_pa_sem_realizado_rpt",
                "Valor": len(explained),
                "Categoria": "Diferença por ausência de fonte RealizadoRPT",
            }
        )
    return pd.DataFrame(rows)


def build_promotor_final(
    aderencia_red: pd.DataFrame,
    pesos: pd.DataFrame,
    escalonada: pd.DataFrame,
    promotor_base: pd.DataFrame | None = None,
    dim_rotas: pd.DataFrame | None = None,
    metas: pd.DataFrame | None = None,
    indicadores: pd.DataFrame | None = None,
    estrutura_promotor: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Monta uma linha consolidada por rota elegivel de Promotor."""

    if promotor_base is None:
        if estrutura_promotor is not None:
            promotor_base = build_promotor_base(
                estrutura_promotor=estrutura_promotor,
                metas=_empty_if_none(metas),
                indicadores=_empty_if_none(indicadores),
            )
        elif dim_rotas is not None:
            promotor_base = build_promotor_base(
                estrutura_promotor=dim_rotas,
                metas=_empty_if_none(metas),
                indicadores=_empty_if_none(indicadores),
            )
        else:
            raise ValueError("promotor_base ou estrutura_promotor/dim_rotas devem ser informados")

    base = promotor_base.copy()
    base["TipoRota"] = base["TipoRota"].fillna(base["Rota"].map(create_tipo_rota))
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
    base["StatusRPT"] = [
        _status_rpt(tipo_rota, meta, realizado, peso)
        for tipo_rota, meta, realizado, peso in zip(
            base["TipoRota"],
            base["MetaRPT"],
            base["RealizadoRPT"],
            base["PesoRPT"],
            strict=False,
        )
    ]
    base.loc[base["StatusRPT"] == "Não se aplica", "PerformanceRPT"] = pd.NA
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
        _calculate_rpt_achievement(tipo_rota, performance, peso)
        for tipo_rota, performance, peso in zip(
            base["TipoRota"],
            base["PerformanceRPT"],
            base["PesoRPT"],
            strict=False,
        )
    ]
    base["AtingimentoTotal"] = [
        _calculate_total_achievement(tipo_rota, red, rpt)
        for tipo_rota, red, rpt in zip(
            base["TipoRota"],
            base["AtingimentoRED"],
            base["AtingimentoRPT"],
            strict=False,
        )
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
        "FonteRealizadoRPT",
        "PerformanceRPT",
        "PesoRPT",
        "StatusRPT",
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
    red["StatusRPT"] = pd.NA

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
            "StatusRPT",
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
        "StatusRPT",
        "Atingimento",
        "AderenciaRED",
        "StatusGatilhoRED",
    ]
    return pd.concat([red[columns], rpt[columns]], ignore_index=True)


def _load_inputs(paths_config: PathsConfig) -> dict[str, pd.DataFrame]:
    staging_dir = paths_config.values["processed"]["staging"]
    indicadores_consolidado = staging_dir / "stg_indicadores_consolidado.csv"
    return {
        "metas": read_csv(staging_dir / "stg_metas.csv"),
        "indicadores": read_csv(
            indicadores_consolidado if indicadores_consolidado.exists() else staging_dir / "stg_indicadores.csv"
        ),
        "estrutura_promotor": read_csv(staging_dir / "stg_estrutura_promotor.csv"),
        "aderencia_red": read_csv(staging_dir / "stg_aderencia_red.csv"),
        "pesos": read_csv(staging_dir / "stg_pesos.csv"),
        "escalonada": read_csv(staging_dir / "stg_escalonada_promotor.csv"),
    }


def _prepare_estrutura_base(estrutura_promotor: pd.DataFrame) -> pd.DataFrame:
    selected_columns = [
        column
        for column in [
            "ChaveCentroRota",
            "UF",
            "Gerencia",
            "Supervisor",
            "Centro",
            "Rota",
            "TipoRota",
            "UnidadeOriginal",
            "FonteEstrutura",
            "MetaRED",
            "RealizadoRED",
            "MetaRPT",
            "RealizadoRPT",
        ]
        if column in estrutura_promotor.columns
    ]
    base = estrutura_promotor[selected_columns].copy()
    base = base.rename(
        columns={
            "MetaRED": "MetaREDEstruturaOriginal",
            "RealizadoRED": "RealizadoREDEstruturaOriginal",
            "MetaRPT": "MetaRPTEstruturaOriginal",
            "RealizadoRPT": "RealizadoRPTEstruturaOriginal",
        }
    )
    if "TipoRota" not in base.columns:
        base["TipoRota"] = base["Rota"].map(create_tipo_rota)
    base = base.dropna(subset=["ChaveCentroRota"])
    return base.drop_duplicates(subset=["ChaveCentroRota"]).reset_index(drop=True)


def _build_meta_metrics(metas: pd.DataFrame, source_kpi: str, output_suffix: str) -> pd.DataFrame:
    if metas.empty or "KPI" not in metas.columns:
        return pd.DataFrame(columns=["ChaveCentroRota", f"Meta{output_suffix}"])
    return _first_by_key(
        metas[metas["KPI"] == source_kpi],
        value_column="Meta",
        output_column=f"Meta{output_suffix}",
    )


def _build_realizado_metrics(indicadores: pd.DataFrame, source_kpi: str, output_suffix: str) -> pd.DataFrame:
    if indicadores.empty or "KPI" not in indicadores.columns:
        return pd.DataFrame(columns=["ChaveCentroRota", f"Realizado{output_suffix}"])
    value_column = "REALIZADO" if "REALIZADO" in indicadores.columns else "Realizado"
    if value_column not in indicadores.columns:
        return pd.DataFrame(columns=["ChaveCentroRota", f"Realizado{output_suffix}"])
    return _first_by_key(
        indicadores[indicadores["KPI"] == source_kpi],
        value_column=value_column,
        output_column=f"Realizado{output_suffix}",
    )


def _source_status(source_name: str, red_value: object, rpt_value: object) -> str:
    if not pd.isna(red_value) and not pd.isna(rpt_value):
        return source_name
    if not pd.isna(red_value):
        return f"{source_name} parcial RED"
    if not pd.isna(rpt_value):
        return f"{source_name} parcial RPT"
    return "Nao encontrada"


def _single_source_status(source_name: str, value: object, missing_status: str) -> str:
    return source_name if not pd.isna(value) else missing_status


def _empty_if_none(dataframe: pd.DataFrame | None) -> pd.DataFrame:
    return dataframe if dataframe is not None else pd.DataFrame()


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


def _status_rpt(tipo_rota: object, meta: object, realizado: object, peso: object) -> str:
    if tipo_rota != "PA":
        return "Não se aplica"
    if pd.isna(peso):
        return "Sem peso RPT"
    if float(peso) == 0:
        return "Não se aplica"
    if pd.isna(meta):
        return "Sem meta RPT"
    if pd.isna(realizado):
        return "Sem fonte de realizado RPT"
    return "Calculável"


def _calculate_rpt_achievement(tipo_rota: object, performance: object, peso: object) -> float | None:
    if tipo_rota != "PA":
        return 0.0
    if not pd.isna(peso) and float(peso) == 0:
        return 0.0
    return calculate_weighted_achievement(performance, peso)


def _calculate_total_achievement(tipo_rota: object, atingimento_red: object, atingimento_rpt: object) -> float | None:
    if tipo_rota != "PA":
        return sum_ignoring_nulls(atingimento_red)
    return sum_ignoring_nulls(atingimento_red, atingimento_rpt)
