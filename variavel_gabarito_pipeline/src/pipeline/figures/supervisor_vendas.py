"""Figura comercial SUPERVISOR DE VENDAS."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import PathsConfig, load_paths_config
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
from pipeline.staging.common import clean_text, create_chave_centro_rota, first_excel_file, to_number
from pipeline.staging.estrutura_supervisor_vendas import META_COLUMNS


KPI_ORDER = ["MKO", "MKR", "MKD", "MCN", "RED", "FRD", "EFV"]
PERCENTUAL_KPIS = {"RED", "FRD", "EFV"}
GATED_KPIS = {"RED", "FRD"}
META_ORIGEM = "Estrutura Supervisor Vendas materializada no gabarito"


class SupervisorVendas(CommercialFigure):
    """Orquestrador da apuracao de Supervisor de Vendas."""

    def run(self) -> list[Path]:
        paths_config = load_paths_config()
        return run_supervisor_vendas_calculation(paths_config)


def run_supervisor_vendas_calculation(paths_config: PathsConfig | None = None) -> list[Path]:
    """Executa a pipeline de Supervisor de Vendas em duas camadas."""

    paths_config = paths_config or load_paths_config()
    logger = configure_logger("pipeline.supervisor_vendas")
    inputs = _load_inputs(paths_config)

    base = build_supervisor_vendas_base(
        estrutura=inputs["estrutura"],
        indicadores=inputs["indicadores"],
        metas=inputs["metas"],
        aderencia_red=inputs["aderencia_red"],
    )
    final = build_supervisor_vendas_final(
        base=base,
        pesos=inputs["pesos"],
        escalonada=inputs["escalonada"],
    )
    calculo = build_supervisor_vendas_calculo(final)
    auditoria_realizados = build_auditoria_realizados(calculo)
    auditoria_metas = build_auditoria_metas(calculo)
    resumo = summarize_supervisor_vendas(base, final, auditoria_realizados, auditoria_metas)

    facts_dir = paths_config.values["processed"]["facts"]
    validation_dir = paths_config.values["processed"]["validation"]
    outputs = [
        write_csv(base, facts_dir / "fat_supervisor_vendas_base.csv"),
        write_csv(calculo, facts_dir / "fat_supervisor_vendas_calculo.csv"),
        write_csv(final, facts_dir / "fat_supervisor_vendas_final.csv"),
        write_csv(auditoria_realizados, validation_dir / "auditoria_supervisor_vendas_realizados.csv"),
        write_csv(auditoria_metas, validation_dir / "auditoria_supervisor_vendas_metas.csv"),
        write_csv(resumo, validation_dir / "resumo_supervisor_vendas.csv"),
    ]
    _print_summary(base, final, auditoria_realizados, auditoria_metas)
    logger.info(
        "calculo_supervisor_vendas_concluido",
        extra={"linhas_base": len(base), "linhas_calculo": len(calculo), "linhas_final": len(final)},
    )
    return outputs


def build_supervisor_vendas_base(
    estrutura: pd.DataFrame,
    indicadores: pd.DataFrame,
    metas: pd.DataFrame,
    aderencia_red: pd.DataFrame,
) -> pd.DataFrame:
    """Monta a base fiel ao gabarito com colunas auditadas em paralelo."""

    base = estrutura.copy()
    base = base.merge(_prepare_aderencia(aderencia_red), on=["Centro", "Supervisao"], how="left")
    base = _fill_aderencia_by_supervisor(base, aderencia_red)

    for kpi in KPI_ORDER:
        base = base.merge(_metric_from_metas(metas, kpi), on="ChaveRotaSup", how="left")
        base = base.merge(_metric_from_indicadores(indicadores, kpi), on="ChaveRotaSup", how="left")
        meta_stg = f"Meta{kpi}StgMetas"
        meta_adj = f"Meta{kpi}StgMetasAjustada"
        real_stg = f"Realizado{kpi}StgIndicadores"
        real_adj = f"Realizado{kpi}StgIndicadoresAjustado"
        base[meta_adj] = base[meta_stg] / 100 if kpi in PERCENTUAL_KPIS else base[meta_stg]
        base[real_adj] = base[real_stg] / 100 if kpi in PERCENTUAL_KPIS else base[real_stg]
        base[f"DifMeta{kpi}"] = base[meta_adj] - base[f"Meta{kpi}Estrutura"]
        base[f"DifPercMeta{kpi}"] = [
            _percent_diff(diff, target)
            for diff, target in zip(base[f"DifMeta{kpi}"], base[f"Meta{kpi}Estrutura"], strict=False)
        ]
        base[f"DifRealizado{kpi}"] = base[real_adj] - base[f"Realizado{kpi}Estrutura"]
        base[f"StatusAuditoriaMeta{kpi}"] = [
            _status_auditoria_meta(estrutura_value, audited_value)
            for estrutura_value, audited_value in zip(
                base[f"Meta{kpi}Estrutura"],
                base[meta_adj],
                strict=False,
            )
        ]
        base[f"StatusAuditoriaRealizado{kpi}"] = [
            _status_auditoria_realizado(estrutura_value, audited_value)
            for estrutura_value, audited_value in zip(
                base[f"Realizado{kpi}Estrutura"],
                base[real_adj],
                strict=False,
            )
        ]

    base["MetaOrigem"] = META_ORIGEM
    base["MetaObservacao"] = "Metas auditadas contra stg_metas, mas calculo usa a estrutura materializada."
    return base


def build_supervisor_vendas_final(
    base: pd.DataFrame,
    pesos: pd.DataFrame,
    escalonada: pd.DataFrame,
) -> pd.DataFrame:
    """Calcula a figura final usando metas e realizados da estrutura."""

    result = base.copy()
    result["AderenciaREDNumerica"] = result["AderenciaRED"].map(to_number)
    for kpi in KPI_ORDER:
        result[f"Peso{kpi}"] = [
            _find_peso(pesos, tipo, kpi)
            for tipo in result["TipoSupervisor"]
        ]
        result[f"StatusPeso{kpi}"] = result[f"Peso{kpi}"].map(lambda value: "Peso encontrado" if not pd.isna(value) else "Peso nao encontrado")
        result[f"Performance{kpi}"] = [
            calculate_performance(meta, realizado, "maior_melhor")
            for meta, realizado in zip(
                result[f"Meta{kpi}Estrutura"],
                result[f"Realizado{kpi}Estrutura"],
                strict=False,
            )
        ]
        result[f"Atingimento{kpi}"] = [
            _calculate_kpi_achievement(kpi, performance, peso, aderencia)
            for performance, peso, aderencia in zip(
                result[f"Performance{kpi}"],
                result[f"Peso{kpi}"],
                result["AderenciaREDNumerica"],
                strict=False,
            )
        ]

    result["AtingimentoTotal"] = [
        sum_ignoring_nulls(*(row[f"Atingimento{kpi}"] for kpi in KPI_ORDER))
        for _, row in result.iterrows()
    ]
    result["EscalaAtingida"] = apply_escalonada(result, escalonada)
    result["StatusPerformance"] = result["AtingimentoTotal"].map(classify_status_performance)
    result["StatusGatilhoRED"] = result["AderenciaRED"].map(_status_gatilho_red)
    result["Diagnostico"] = result.apply(_build_row_diagnostic, axis=1)

    output_columns = _identity_columns() + [
        "AderenciaRED",
        "AderenciaREDNumerica",
        "StatusAderenciaRED",
        "StatusGatilhoRED",
        "AtingimentoTotal",
        "EscalaAtingida",
        "StatusPerformance",
        "Diagnostico",
    ]
    for kpi in KPI_ORDER:
        output_columns.extend(
            [
                f"Meta{kpi}Estrutura",
                f"Realizado{kpi}Estrutura",
                f"Meta{kpi}StgMetas",
                f"Meta{kpi}StgMetasAjustada",
                f"DifMeta{kpi}",
                f"DifPercMeta{kpi}",
                f"StatusAuditoriaMeta{kpi}",
                f"Realizado{kpi}StgIndicadores",
                f"Realizado{kpi}StgIndicadoresAjustado",
                f"DifRealizado{kpi}",
                f"StatusAuditoriaRealizado{kpi}",
                f"Performance{kpi}",
                f"Peso{kpi}",
                f"StatusPeso{kpi}",
                f"Atingimento{kpi}",
            ]
        )
    return result[[column for column in output_columns if column in result.columns]]


def build_supervisor_vendas_calculo(final: pd.DataFrame) -> pd.DataFrame:
    """Gera base longa por supervisor e KPI para auditoria."""

    rows: list[dict[str, object]] = []
    for _, row in final.iterrows():
        for kpi in KPI_ORDER:
            rows.append(
                {
                    **{column: row.get(column) for column in _identity_columns()},
                    "KPI": kpi,
                    "MetaEstrutura": row.get(f"Meta{kpi}Estrutura"),
                    "RealizadoEstrutura": row.get(f"Realizado{kpi}Estrutura"),
                    "MetaStgMetas": row.get(f"Meta{kpi}StgMetas"),
                    "MetaStgMetasAjustada": row.get(f"Meta{kpi}StgMetasAjustada"),
                    "DifMeta": row.get(f"DifMeta{kpi}"),
                    "DifPercMeta": row.get(f"DifPercMeta{kpi}"),
                    "StatusAuditoriaMeta": row.get(f"StatusAuditoriaMeta{kpi}"),
                    "RealizadoStgIndicadores": row.get(f"Realizado{kpi}StgIndicadores"),
                    "RealizadoStgIndicadoresAjustado": row.get(f"Realizado{kpi}StgIndicadoresAjustado"),
                    "DifRealizado": row.get(f"DifRealizado{kpi}"),
                    "StatusAuditoriaRealizado": row.get(f"StatusAuditoriaRealizado{kpi}"),
                    "Performance": row.get(f"Performance{kpi}"),
                    "Peso": row.get(f"Peso{kpi}"),
                    "StatusPeso": row.get(f"StatusPeso{kpi}"),
                    "Atingimento": row.get(f"Atingimento{kpi}"),
                    "AderenciaRED": row.get("AderenciaRED"),
                    "AderenciaREDNumerica": row.get("AderenciaREDNumerica"),
                    "StatusGatilhoRED": row.get("StatusGatilhoRED"),
                    "AtingimentoTotal": row.get("AtingimentoTotal"),
                    "EscalaAtingida": row.get("EscalaAtingida"),
                    "StatusPerformance": row.get("StatusPerformance"),
                    "MetaOrigem": META_ORIGEM,
                }
            )
    return pd.DataFrame(rows)


def build_auditoria_realizados(calculo: pd.DataFrame) -> pd.DataFrame:
    """Seleciona colunas de auditoria dos realizados."""

    columns = _identity_columns() + [
        "KPI",
        "RealizadoEstrutura",
        "RealizadoStgIndicadores",
        "RealizadoStgIndicadoresAjustado",
        "DifRealizado",
        "StatusAuditoriaRealizado",
    ]
    return calculo[[column for column in columns if column in calculo.columns]]


def build_auditoria_metas(calculo: pd.DataFrame) -> pd.DataFrame:
    """Seleciona colunas de auditoria das metas."""

    result = calculo.copy()
    result["MetaRastreavel"] = result["StatusAuditoriaMeta"].eq("OK")
    result["MetaObservacao"] = result["StatusAuditoriaMeta"].map(_meta_observacao)
    columns = _identity_columns() + [
        "KPI",
        "MetaEstrutura",
        "MetaStgMetas",
        "MetaStgMetasAjustada",
        "DifMeta",
        "DifPercMeta",
        "StatusAuditoriaMeta",
        "MetaOrigem",
        "MetaRastreavel",
        "MetaObservacao",
    ]
    return result[[column for column in columns if column in result.columns]]


def summarize_supervisor_vendas(
    base: pd.DataFrame,
    final: pd.DataFrame,
    auditoria_realizados: pd.DataFrame,
    auditoria_metas: pd.DataFrame,
) -> pd.DataFrame:
    """Gera resumo operacional e de auditoria."""

    rows = [
        {"Metrica": "linhas_estrutura", "Valor": len(base), "Categoria": pd.NA},
        {"Metrica": "chaves_supervisor_unicas", "Valor": base["ChaveSupervisor"].nunique(), "Categoria": pd.NA},
        {
            "Metrica": "linhas_com_duplicidade_origem",
            "Valor": int((base["QtdDuplicidadeChaveSupervisor"] > 1).sum()),
            "Categoria": pd.NA,
        },
        {"Metrica": "linhas_final", "Valor": len(final), "Categoria": pd.NA},
        {"Metrica": "aderencia_encontrada", "Valor": int(base["AderenciaRED"].notna().sum()), "Categoria": pd.NA},
        {"Metrica": "aderencia_nula", "Valor": int(base["AderenciaRED"].isna().sum()), "Categoria": pd.NA},
    ]
    for status, count in final["StatusPerformance"].value_counts(dropna=False).items():
        rows.append({"Metrica": "distribuicao_status_performance", "Valor": int(count), "Categoria": status})
    for kpi, group in auditoria_realizados.groupby("KPI", dropna=False):
        ok = int(group["StatusAuditoriaRealizado"].eq("OK").sum())
        rows.append({"Metrica": "auditoria_realizados_ok_pct", "Valor": _pct(ok, len(group)), "Categoria": kpi})
    for kpi, group in auditoria_metas.groupby("KPI", dropna=False):
        ok = int(group["StatusAuditoriaMeta"].eq("OK").sum())
        rows.append({"Metrica": "auditoria_metas_ok_pct", "Valor": _pct(ok, len(group)), "Categoria": kpi})
    return pd.DataFrame(rows)


def _load_inputs(paths_config: PathsConfig) -> dict[str, pd.DataFrame]:
    staging_dir = paths_config.values["processed"]["staging"]
    return {
        "estrutura": read_csv(staging_dir / "stg_estrutura_supervisor_vendas.csv"),
        "pesos": read_csv(staging_dir / "stg_pesos_supervisor_vendas.csv"),
        "metas": read_csv(staging_dir / "stg_metas.csv"),
        "indicadores": read_csv(staging_dir / "stg_indicadores.csv"),
        "aderencia_red": read_csv(staging_dir / "stg_aderencia_red.csv"),
        "escalonada": read_escalonada_supervisor_vendas(first_excel_file(paths_config.values["raw_sources"], "gabarito_validacao")),
    }


def read_escalonada_supervisor_vendas(file_path: str | Path) -> pd.DataFrame:
    """Extrai o bloco Vendedor/Operador/Sup. Vendas da aba Escalonada."""

    raw = pd.read_excel(file_path, sheet_name="Escalonada", header=None, engine="openpyxl")
    block = raw.iloc[3:64, 1:5].copy()
    block.columns = ["FaixaDe", "FaixaAte", "Acelerado", "EscalaAtingida"]
    for column in block.columns:
        block[column] = block[column].map(to_number)
    return block.dropna(subset=["FaixaDe", "EscalaAtingida"]).reset_index(drop=True)


def _metric_from_metas(metas: pd.DataFrame, kpi: str) -> pd.DataFrame:
    result = _first_metric(metas, kpi, "Meta", f"Meta{kpi}StgMetas")
    return result.rename(columns={"ChaveCentroRota": "ChaveRotaSup"})


def _metric_from_indicadores(indicadores: pd.DataFrame, kpi: str) -> pd.DataFrame:
    value_column = "REALIZADO" if "REALIZADO" in indicadores.columns else "Realizado"
    result = _first_metric(indicadores, kpi, value_column, f"Realizado{kpi}StgIndicadores")
    return result.rename(columns={"ChaveCentroRota": "ChaveRotaSup"})


def _first_metric(dataframe: pd.DataFrame, kpi: str, value_column: str, output_column: str) -> pd.DataFrame:
    if dataframe.empty or value_column not in dataframe.columns or "KPI" not in dataframe.columns:
        return pd.DataFrame(columns=["ChaveCentroRota", output_column])
    source = dataframe[dataframe["KPI"].map(clean_text) == kpi].copy()
    if "ChaveCentroRota" not in source.columns:
        source["ChaveCentroRota"] = [
            create_chave_centro_rota(centro, rota)
            for centro, rota in zip(source["Centro"], source["Rota"], strict=False)
        ]
    source[value_column] = source[value_column].map(to_number)
    return (
        source.dropna(subset=["ChaveCentroRota"])
        .sort_values("ChaveCentroRota")
        .groupby("ChaveCentroRota", as_index=False)[value_column]
        .first()
        .rename(columns={value_column: output_column})
    )


def _prepare_aderencia(aderencia_red: pd.DataFrame) -> pd.DataFrame:
    if aderencia_red.empty or "SupervisorDescricao" not in aderencia_red.columns:
        return pd.DataFrame(columns=["Centro", "Supervisao", "AderenciaRED", "StatusAderenciaRED", "FonteAderenciaRED"])
    value_column = "AderenciaSupervisor" if "AderenciaSupervisor" in aderencia_red.columns else "AderenciaRED"
    result = aderencia_red.copy()
    result["Centro"] = result["Centro"].map(clean_text)
    result["Supervisao"] = result["SupervisorDescricao"].map(clean_text)
    result["AderenciaRED"] = result[value_column].map(to_number)
    result["StatusAderenciaRED"] = "Encontrada por Centro+Supervisao"
    result["FonteAderenciaRED"] = "stg_aderencia_red.csv"
    return result[["Centro", "Supervisao", "AderenciaRED", "StatusAderenciaRED", "FonteAderenciaRED"]].drop_duplicates(
        subset=["Centro", "Supervisao"]
    )


def _fill_aderencia_by_supervisor(base: pd.DataFrame, aderencia_red: pd.DataFrame) -> pd.DataFrame:
    if base["AderenciaRED"].notna().all() or aderencia_red.empty or "SupervisorDescricao" not in aderencia_red.columns:
        base["StatusAderenciaRED"] = base["StatusAderenciaRED"].fillna("Nao encontrada")
        return base
    value_column = "AderenciaSupervisor" if "AderenciaSupervisor" in aderencia_red.columns else "AderenciaRED"
    fallback = aderencia_red.copy()
    fallback["Supervisao"] = fallback["SupervisorDescricao"].map(clean_text)
    fallback = fallback.drop_duplicates(subset=["Supervisao"])
    map_value = dict(zip(fallback["Supervisao"], fallback[value_column].map(to_number), strict=False))
    missing = base["AderenciaRED"].isna()
    base.loc[missing, "AderenciaRED"] = base.loc[missing, "Supervisao"].map(map_value)
    filled = missing & base["AderenciaRED"].notna()
    base.loc[filled, "StatusAderenciaRED"] = "Encontrada por Supervisao"
    base["StatusAderenciaRED"] = base["StatusAderenciaRED"].fillna("Nao encontrada")
    base["FonteAderenciaRED"] = base["FonteAderenciaRED"].fillna("stg_aderencia_red.csv")
    return base


def _find_peso(pesos: pd.DataFrame, tipo_supervisor: object, kpi: str) -> float | None:
    tipo = "" if pd.isna(tipo_supervisor) else str(tipo_supervisor)
    candidates = [f"{tipo}{kpi}", kpi]
    for chave in candidates:
        match = pesos[pesos["ChavePeso"] == chave]
        if not match.empty:
            return float(match.iloc[0]["Peso"])
    return None


def _calculate_kpi_achievement(kpi: str, performance: object, peso: object, aderencia: object) -> float | None:
    if kpi in GATED_KPIS:
        aderencia_numerica = to_number(aderencia)
        if aderencia_numerica is not None and float(aderencia_numerica) < 0.85:
            return 0.0
    return calculate_weighted_achievement(performance, peso)


def _status_gatilho_red(aderencia: object) -> str:
    aderencia_numerica = to_number(aderencia)
    if aderencia_numerica is None:
        return "Sem aderencia numerica - gabarito calcula normalmente"
    if float(aderencia_numerica) < 0.85:
        return "Zerado por aderencia RED < 85%"
    return "Aderencia numerica >= 85%"


def _status_auditoria_realizado(estrutura_value: object, audited_value: object) -> str:
    if pd.isna(estrutura_value):
        return "Nao se aplica"
    if pd.isna(audited_value):
        return "Fonte nao encontrada"
    return "OK" if abs(float(estrutura_value) - float(audited_value)) <= 0.01 else "Diferente"


def _status_auditoria_meta(estrutura_value: object, audited_value: object) -> str:
    if pd.isna(estrutura_value):
        return "Nao se aplica"
    if pd.isna(audited_value):
        return "Fonte nao encontrada"
    return "OK" if abs(float(estrutura_value) - float(audited_value)) <= 0.01 else "Nao rastreavel em stg_metas"


def _percent_diff(diff: object, target: object) -> float | None:
    if pd.isna(diff) or pd.isna(target) or float(target) == 0:
        return None
    return float(diff) / abs(float(target))


def _meta_observacao(status: object) -> str:
    if status == "OK":
        return "Meta bate com stg_metas pela chave Centro+RotaSup+KPI."
    if status == "Nao se aplica":
        return "KPI sem meta na estrutura."
    return "Meta usada no calculo vem da estrutura materializada; origem externa nao identificada."


def _build_row_diagnostic(row: pd.Series) -> str:
    diagnostics: list[str] = []
    if pd.isna(row.get("AderenciaRED")):
        diagnostics.append("Sem aderencia RED")
    for kpi in KPI_ORDER:
        if pd.isna(row.get(f"Peso{kpi}")) and not pd.isna(row.get(f"Meta{kpi}Estrutura")):
            diagnostics.append(f"Sem peso {kpi}")
    if row.get("StatusDuplicidadeChaveSupervisor") == "Duplicada na estrutura":
        diagnostics.append("ChaveSupervisor duplicada na estrutura; mantida primeira ocorrencia")
    return "; ".join(diagnostics) if diagnostics else "OK"


def _identity_columns() -> list[str]:
    return [
        "ChaveSupervisor",
        "ChaveRotaSup",
        "CHAVE",
        "CHAVE2",
        "UF",
        "Gerencia",
        "Supervisao",
        "Centro",
        "RotaSup",
        "TipoRotaSup",
        "TipoSupervisor",
        "Nome",
        "Cargo",
        "FonteEstrutura",
        "StatusDuplicidadeChaveSupervisor",
        "QtdDuplicidadeChaveSupervisor",
    ]


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(100 * numerator / denominator, 2)


def _print_summary(
    base: pd.DataFrame,
    final: pd.DataFrame,
    auditoria_realizados: pd.DataFrame,
    auditoria_metas: pd.DataFrame,
) -> None:
    print("Supervisor de Vendas")
    print(f"linhas estrutura: {len(base)}")
    print(f"chaves supervisor unicas: {base['ChaveSupervisor'].nunique()}")
    print(f"duplicidades: {int((base['QtdDuplicidadeChaveSupervisor'] > 1).sum())}")
    peso_columns = [f"Peso{kpi}" for kpi in KPI_ORDER]
    print(f"pesos nulos: {int(final[peso_columns].isna().sum().sum())}")
    print(f"aderencia encontrada: {int(base['AderenciaRED'].notna().sum())}")
    print(f"aderencia nula: {int(base['AderenciaRED'].isna().sum())}")
    print("auditoria realizados OK por KPI:")
    for kpi, group in auditoria_realizados.groupby("KPI"):
        print(f"  {kpi}: {_pct(int(group['StatusAuditoriaRealizado'].eq('OK').sum()), len(group))}%")
    print("auditoria metas OK por KPI:")
    for kpi, group in auditoria_metas.groupby("KPI"):
        print(f"  {kpi}: {_pct(int(group['StatusAuditoriaMeta'].eq('OK').sum()), len(group))}%")
    print(f"linhas final geradas: {len(final)}")
    print("distribuicao de status:")
    for status, count in final["StatusPerformance"].value_counts(dropna=False).items():
        print(f"  {status}: {count}")
