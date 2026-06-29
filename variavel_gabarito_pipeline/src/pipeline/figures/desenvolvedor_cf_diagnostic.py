"""Diagnostico da figura DESENVOLVEDOR CF, sem pipeline final produtiva."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import PathsConfig, load_paths_config
from pipeline.domain.performance import calculate_performance, calculate_weighted_achievement, sum_ignoring_nulls
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.staging.agentes import transform_agentes
from pipeline.staging.common import clean_text, first_excel_file, to_number


KPI_ORDER = ["MKO", "MCN", "RED", "PRC", "SEG", "MIS"]
PESOS = {"MKO": 0.30, "MCN": 0.10, "RED": 0.20, "PRC": 0.20, "SEG": 0.10, "MIS": 0.10}
BLOCKED_KPIS = {"MKO", "MCN", "RED", "PRC"}
FIXED_METAS = {"SEG": 70.0, "MIS": 1.0}
STATUS_FIGURA = "Bloqueada para calculo final: fonte de metas ajustadas MKO/MCN/RED/PRC ausente"
BUSINESS_QUESTION = (
    "Qual arquivo, processo ou sistema gera as metas ajustadas de Desenvolvedor CF por Centro + Rota RB + KPI "
    "para MKO, MCN, RED e PRC?"
)


def run_desenvolvedor_cf_diagnostic(paths_config: PathsConfig | None = None) -> list[Path]:
    """Gera arquivos diagnosticos de Desenvolvedor CF sem preencher metas bloqueadas pela estrutura."""

    paths_config = paths_config or load_paths_config()
    logger = configure_logger("pipeline.desenvolvedor_cf_diagnostic")
    agentes = _load_agentes(paths_config)
    indicadores = read_csv(paths_config.values["processed"]["staging"] / "stg_indicadores.csv")
    aderencia_red = read_csv(paths_config.values["processed"]["staging"] / "stg_aderencia_red.csv")
    oracle = read_oracle_estrutura_cf(first_excel_file(paths_config.values["raw_sources"], "gabarito_validacao"))

    long = build_desenvolvedor_cf_long_diagnostic(agentes, indicadores, aderencia_red)
    layout = build_desenvolvedor_cf_layout_diagnostic(long)
    resumo = build_desenvolvedor_cf_summary(long, layout, oracle)
    report = build_desenvolvedor_cf_markdown_report(resumo)

    diagnostics_dir = paths_config.values["data"]["processed"] / "diagnostics"
    reports_dir = paths_config.project_root / "reports" / "validation"
    outputs = [
        write_csv(long, diagnostics_dir / "desenvolvedor_cf_long_diagnostic.csv"),
        write_csv(layout, diagnostics_dir / "desenvolvedor_cf_layout_diagnostic.csv"),
        write_csv(resumo, diagnostics_dir / "resumo_desenvolvedor_cf_diagnostic.csv"),
    ]
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "desenvolvedor_cf_diagnostic.md"
    report_path.write_text(report, encoding="utf-8")
    outputs.append(report_path)

    _print_summary(long, layout, resumo)
    logger.info(
        "diagnostico_desenvolvedor_cf_concluido",
        extra={"linhas_long": len(long), "linhas_layout": len(layout)},
    )
    return outputs


def build_desenvolvedor_cf_long_diagnostic(
    agentes: pd.DataFrame,
    indicadores: pd.DataFrame,
    aderencia_red: pd.DataFrame,
) -> pd.DataFrame:
    """Monta diagnostico longo por Centro+Rota+KPI."""

    population = _prepare_cf_population(agentes)
    real_source = _prepare_indicadores(indicadores)
    adherence = _prepare_aderencia(aderencia_red)
    rows: list[dict[str, object]] = []
    for _, route in population.iterrows():
        aderencia = adherence.get(route["ChaveCentroRota"])
        for kpi in KPI_ORDER:
            meta = _meta_for_kpi(kpi)
            realizado = real_source.get(f"{route['ChaveCentroRota']}{kpi}")
            performance = calculate_performance(meta, realizado, "maior_melhor") if not pd.isna(meta) else None
            atingimento = _calculate_achievement(kpi, performance, PESOS[kpi], aderencia)
            rows.append(
                {
                    "Centro": route["Centro"],
                    "Rota": route["Rota"],
                    "ChaveCentroRota": route["ChaveCentroRota"],
                    "Nome": route.get("Nome"),
                    "DescricaoFuncao": route.get("DescricaoFuncao"),
                    "FontePopulacao": route["FontePopulacao"],
                    "StatusPopulacao": route["StatusPopulacao"],
                    "KPI": kpi,
                    "Meta": meta,
                    "Realizado": realizado,
                    "AderenciaRED": aderencia,
                    "Performance": performance,
                    "Peso": PESOS[kpi],
                    "AtingimentoKPI": 0.0 if pd.isna(atingimento) else atingimento,
                    "FonteMeta": _fonte_meta(kpi),
                    "StatusMeta": _status_meta(kpi),
                    "FonteRealizado": "stg_indicadores.csv" if not pd.isna(realizado) else "Realizado nao encontrado",
                    "StatusCalculoKPI": _status_calculo(kpi, meta, realizado),
                    "StatusFigura": STATUS_FIGURA,
                }
            )
    return pd.DataFrame(rows)


def build_desenvolvedor_cf_layout_diagnostic(long: pd.DataFrame) -> pd.DataFrame:
    """Monta layout diagnostico, sem carater de resultado final produtivo."""

    rows: list[dict[str, object]] = []
    for key, group in long.groupby("ChaveCentroRota", sort=True):
        first = group.iloc[0]
        total = sum_ignoring_nulls(*(group[f].iloc[0] for f in [])) if False else float(group["AtingimentoKPI"].sum())
        row: dict[str, object] = {
            "UF": pd.NA,
            "Gerencia": pd.NA,
            "Supervisor": pd.NA,
            "Rota": first["Rota"],
            "Unidade": first["Centro"],
            "Centro": first["Centro"],
            "ChaveCentroRota": key,
            "Matricula": pd.NA,
            "Nome": first.get("Nome"),
            "AderenciaRED": first.get("AderenciaRED"),
            "AtingimentoTotalDiagnosticoParcial": total,
            "StatusFigura": STATUS_FIGURA,
            "PerguntaNegocio": BUSINESS_QUESTION,
            "FontePopulacao": first.get("FontePopulacao"),
            "StatusPopulacao": first.get("StatusPopulacao"),
        }
        for kpi in KPI_ORDER:
            metric = group[group["KPI"] == kpi].iloc[0]
            row[f"{kpi} Meta"] = metric.get("Meta")
            row[f"{kpi} Real"] = metric.get("Realizado")
            row[f"{kpi} Perf.%"] = metric.get("Performance")
            row[f"{kpi} Peso"] = metric.get("Peso")
            row[f"{kpi} Ating. Fin."] = metric.get("AtingimentoKPI")
            row[f"{kpi} FonteMeta"] = metric.get("FonteMeta")
            row[f"{kpi} StatusMeta"] = metric.get("StatusMeta")
            row[f"{kpi} FonteRealizado"] = metric.get("FonteRealizado")
            row[f"{kpi} StatusCalculoKPI"] = metric.get("StatusCalculoKPI")
        rows.append(row)
    return pd.DataFrame(rows)


def build_desenvolvedor_cf_summary(
    long: pd.DataFrame,
    layout: pd.DataFrame,
    oracle: pd.DataFrame,
) -> pd.DataFrame:
    """Resume populacao, metas, realizados e comparacao contra o oraculo."""

    oracle_keys = set(oracle["ChaveCentroRota"].dropna())
    layout_keys = set(layout["ChaveCentroRota"].dropna())
    rows = [
        {"Metrica": "chaves_diagnostico", "Valor": len(layout_keys), "Categoria": pd.NA},
        {"Metrica": "chaves_oraculo_estrutura_cf", "Valor": len(oracle_keys), "Categoria": pd.NA},
        {"Metrica": "chaves_em_comum_com_oraculo", "Valor": len(layout_keys & oracle_keys), "Categoria": pd.NA},
        {"Metrica": "chaves_faltantes_vs_oraculo", "Valor": len(oracle_keys - layout_keys), "Categoria": pd.NA},
        {"Metrica": "chaves_extras_vs_oraculo", "Valor": len(layout_keys - oracle_keys), "Categoria": pd.NA},
        {"Metrica": "chave_incluida_excecao_CSAJRB000", "Valor": int("CSAJRB000" in layout_keys), "Categoria": pd.NA},
        {"Metrica": "chave_excluida_excecao_CARIRB000", "Valor": int("CARIRB000" not in layout_keys), "Categoria": pd.NA},
        {"Metrica": "status_figura", "Valor": STATUS_FIGURA, "Categoria": pd.NA},
        {"Metrica": "pergunta_negocio", "Valor": BUSINESS_QUESTION, "Categoria": pd.NA},
    ]
    for kpi, group in long.groupby("KPI", sort=True):
        rows.append({"Metrica": "realizados_encontrados", "Valor": int(group["Realizado"].notna().sum()), "Categoria": kpi})
        rows.append({"Metrica": "metas_preenchidas", "Valor": int(group["Meta"].notna().sum()), "Categoria": kpi})
        rows.append({"Metrica": "metas_bloqueadas", "Valor": int(group["StatusMeta"].str.contains("Bloqueado").sum()), "Categoria": kpi})
    for status, count in layout["StatusPopulacao"].value_counts(dropna=False).items():
        rows.append({"Metrica": "status_populacao", "Valor": int(count), "Categoria": status})
    return pd.DataFrame(rows)


def read_oracle_estrutura_cf(file_path: str | Path) -> pd.DataFrame:
    """Le a estrutura oculta apenas como oraculo de diagnostico."""

    raw = pd.read_excel(file_path, sheet_name="Estrutura Desenvolvedor CF", header=2, engine="openpyxl")
    raw = raw.dropna(how="all").copy()
    result = pd.DataFrame(
        {
            "Centro": raw.get("Centro", pd.Series(pd.NA, index=raw.index)).map(clean_text),
            "Rota": raw.get("Rota", pd.Series(pd.NA, index=raw.index)).map(clean_text),
        }
    )
    result["ChaveCentroRota"] = result["Centro"].fillna("") + result["Rota"].fillna("")
    return result[result["ChaveCentroRota"].str.len() > 0].drop_duplicates("ChaveCentroRota")


def build_desenvolvedor_cf_markdown_report(resumo: pd.DataFrame) -> str:
    """Cria relatorio curto do diagnostico CF."""

    def metric(name: str) -> object:
        match = resumo[resumo["Metrica"].eq(name)]
        return match.iloc[0]["Valor"] if not match.empty else ""

    return "\n".join(
        [
            "# Diagnostico Desenvolvedor CF",
            "",
            "Pipeline diagnostica, nao produtiva. A aba Estrutura Desenvolvedor CF foi usada somente como oraculo de comparacao.",
            "",
            f"- Chaves diagnostico: {metric('chaves_diagnostico')}",
            f"- Chaves no oraculo Estrutura CF: {metric('chaves_oraculo_estrutura_cf')}",
            f"- Chaves em comum: {metric('chaves_em_comum_com_oraculo')}",
            f"- Faltantes vs oraculo: {metric('chaves_faltantes_vs_oraculo')}",
            f"- Extras vs oraculo: {metric('chaves_extras_vs_oraculo')}",
            "",
            "Metas:",
            "- MKO, MCN, RED e PRC permanecem bloqueadas por ausencia da fonte real de metas ajustadas.",
            "- SEG usa meta 70.",
            "- MIS usa meta 1.",
            "",
            f"Status: {STATUS_FIGURA}",
            "",
            f"Pergunta ao negocio: {BUSINESS_QUESTION}",
            "",
            "Confirmacao: nenhuma meta de CF foi preenchida usando Estrutura Desenvolvedor CF.",
            "",
        ]
    )


def _load_agentes(paths_config: PathsConfig) -> pd.DataFrame:
    input_file = first_excel_file(paths_config.values["raw_sources"], "agentes")
    raw = pd.read_excel(input_file, engine="openpyxl")
    agentes, _ = transform_agentes(raw)
    return agentes


def _prepare_cf_population(agentes: pd.DataFrame) -> pd.DataFrame:
    source = agentes[agentes["Rota"].map(lambda value: str(value).upper().startswith("RB") if not pd.isna(value) else False)].copy()
    source = source[~source["Rota"].eq("RB900")].copy()
    source = source[~source["ChaveCentroRota"].eq("CARIRB000")].copy()
    source = source.drop_duplicates("ChaveCentroRota")
    source["FontePopulacao"] = "AGENTES | rota RB | exclui RB900"
    source["StatusPopulacao"] = "OK"
    if "CSAJRB000" not in set(source["ChaveCentroRota"]):
        source = pd.concat(
            [
                source,
                pd.DataFrame(
                    [
                        {
                            "Centro": "CSAJ",
                            "Rota": "RB000",
                            "ChaveCentroRota": "CSAJRB000",
                            "TipoRota": "RB",
                            "Nome": pd.NA,
                            "DescricaoFuncao": pd.NA,
                            "FontePopulacao": "Excecao controlada",
                            "StatusPopulacao": "Presente no gabarito/indicadores e ausente em AGENTES",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    return source.sort_values("ChaveCentroRota").reset_index(drop=True)


def _prepare_indicadores(indicadores: pd.DataFrame) -> dict[str, float]:
    value_column = "REALIZADO" if "REALIZADO" in indicadores.columns else "Realizado"
    source = indicadores[indicadores["KPI"].map(clean_text).isin(KPI_ORDER)].copy()
    source[value_column] = source[value_column].map(to_number)
    source["ChaveIndicadorCF"] = source["ChaveCentroRota"].fillna("") + source["KPI"].map(clean_text).fillna("")
    return source.drop_duplicates("ChaveIndicadorCF").set_index("ChaveIndicadorCF")[value_column].to_dict()


def _prepare_aderencia(aderencia_red: pd.DataFrame) -> dict[str, float]:
    value_column = "AderenciaREDValida" if "AderenciaREDValida" in aderencia_red.columns else "AderenciaRED"
    source = aderencia_red.copy()
    source[value_column] = source[value_column].map(to_number)
    return source.drop_duplicates("ChaveCentroRota").set_index("ChaveCentroRota")[value_column].to_dict()


def _meta_for_kpi(kpi: str) -> float | object:
    if kpi in FIXED_METAS:
        return FIXED_METAS[kpi]
    return pd.NA


def _fonte_meta(kpi: str) -> str:
    if kpi in FIXED_METAS:
        return "Regra validada / stg_metas"
    return "Fonte de meta ajustada ausente"


def _status_meta(kpi: str) -> str:
    if kpi in FIXED_METAS:
        return "OK - meta reproduzida com seguranca"
    return "Bloqueado: origem real da meta ajustada nao encontrada"


def _status_calculo(kpi: str, meta: object, realizado: object) -> str:
    if kpi in BLOCKED_KPIS:
        return "Nao calculado: fonte de meta ajustada ausente"
    if pd.isna(meta):
        return "Nao calculado: meta ausente"
    if pd.isna(realizado):
        return "Nao calculado: realizado ausente"
    return "Calculado para diagnostico"


def _calculate_achievement(kpi: str, performance: object, peso: object, aderencia_red: object) -> float | None:
    if kpi == "RED":
        aderencia = to_number(aderencia_red)
        if aderencia is not None and aderencia < 0.85:
            return 0.0
    return calculate_weighted_achievement(performance, peso)


def _print_summary(long: pd.DataFrame, layout: pd.DataFrame, resumo: pd.DataFrame) -> None:
    print("Desenvolvedor CF diagnostico")
    print(f"chaves diagnostico: {len(layout)}")
    print("realizados encontrados por KPI:")
    for kpi, group in long.groupby("KPI"):
        print(f"  {kpi}: {int(group['Realizado'].notna().sum())}/{len(group)}")
    print("metas preenchidas por KPI:")
    for kpi, group in long.groupby("KPI"):
        print(f"  {kpi}: {int(group['Meta'].notna().sum())}/{len(group)}")
    print(STATUS_FIGURA)
