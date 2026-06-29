"""Figura comercial DESENVOLVEDOR HID."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import PathsConfig, load_paths_config
from pipeline.domain.performance import calculate_performance, classify_status_performance
from pipeline.figures.base import CommercialFigure
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.staging.agentes import transform_agentes
from pipeline.staging.common import clean_text, first_excel_file, to_number


KPI_ORDER = ["VMS", "CCH", "CGD", "CPW"]
KPI_NAMES = {
    "VMS": "Volume Margem STILL",
    "CCH": "Cobertura de SKU's Prioritarios",
    "CGD": "Cobertura de GDM",
    "CPW": "Cobertura de Powerade",
}
PESOS = {"VMS": 0.40, "CCH": 0.20, "CGD": 0.15, "CPW": 0.25}
ROTA_HID = "RG600"
META_STATUS = "Meta nao cadastrada / sem meta validavel no gabarito"


class DesenvolvedorHID(CommercialFigure):
    """Orquestrador da apuracao de Desenvolvedor HID."""

    def run(self) -> list[Path]:
        return run_desenvolvedor_hid_calculation()


def run_desenvolvedor_hid_calculation(paths_config: PathsConfig | None = None) -> list[Path]:
    """Executa a pipeline final de Desenvolvedor HID."""

    paths_config = paths_config or load_paths_config()
    logger = configure_logger("pipeline.desenvolvedor_hid")
    agentes = _load_agentes(paths_config)
    indicadores = read_csv(paths_config.values["processed"]["staging"] / "stg_indicadores.csv")

    long = build_desenvolvedor_hid_long(agentes, indicadores)
    final = build_desenvolvedor_hid_final(long)

    output_dir = paths_config.values["data"]["processed"] / "figures"
    outputs = [
        write_csv(long, output_dir / "desenvolvedor_hid_long.csv"),
        write_csv(final, output_dir / "desenvolvedor_hid_final.csv"),
    ]
    _print_summary(final, long)
    logger.info(
        "calculo_desenvolvedor_hid_concluido",
        extra={"linhas_long": len(long), "linhas_final": len(final)},
    )
    return outputs


def build_desenvolvedor_hid_long(agentes: pd.DataFrame, indicadores: pd.DataFrame) -> pd.DataFrame:
    """Monta base longa por Centro+Rota+KPI."""

    population = _prepare_population(agentes)
    metric_source = _prepare_indicadores(indicadores)
    rows: list[dict[str, object]] = []
    for _, route in population.iterrows():
        for kpi in KPI_ORDER:
            key = f"{route['ChaveCentroRota']}{kpi}"
            realizado = metric_source.get(key)
            rows.append(
                {
                    "Centro": route["Centro"],
                    "Rota": route["Rota"],
                    "ChaveCentroRota": route["ChaveCentroRota"],
                    "Nome": route.get("Nome"),
                    "DescricaoFuncao": route.get("DescricaoFuncao"),
                    "KPI": kpi,
                    "NomeKPI": KPI_NAMES[kpi],
                    "Meta": pd.NA,
                    "Realizado": realizado,
                    "Performance": pd.NA,
                    "Peso": PESOS[kpi],
                    "AtingimentoKPI": 0.0,
                    "FonteMeta": "Nao definida",
                    "StatusMeta": META_STATUS,
                    "FonteRealizado": "stg_indicadores.csv" if not pd.isna(realizado) else "Realizado nao encontrado",
                    "StatusCalculoKPI": "Atingimento zerado por ausencia de meta",
                }
            )
    return pd.DataFrame(rows)


def build_desenvolvedor_hid_final(long: pd.DataFrame) -> pd.DataFrame:
    """Monta saida final no layout do gabarito."""

    rows: list[dict[str, object]] = []
    for key, group in long.groupby("ChaveCentroRota", sort=True):
        first = group.iloc[0]
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
            "Status da Performance": "Irregular",
            "Ating. Total": 0.0,
            "Escala atingida": 0.0,
            "StatusPerformance": "Irregular",
            "AtingimentoTotal": 0.0,
            "EscalaAtingida": 0.0,
        }
        for kpi in KPI_ORDER:
            metric = group[group["KPI"] == kpi].iloc[0]
            row[f"{kpi} Meta"] = pd.NA
            row[f"{kpi} Real"] = metric.get("Realizado")
            row[f"{kpi} Perf.%"] = pd.NA
            row[f"{kpi} Peso"] = metric.get("Peso")
            row[f"{kpi} Ating. Fin."] = 0.0
            row[f"{kpi} FonteMeta"] = metric.get("FonteMeta")
            row[f"{kpi} StatusMeta"] = metric.get("StatusMeta")
            row[f"{kpi} FonteRealizado"] = metric.get("FonteRealizado")
            row[f"{kpi} StatusCalculoKPI"] = metric.get("StatusCalculoKPI")
        rows.append(row)
    return pd.DataFrame(rows)


def _load_agentes(paths_config: PathsConfig) -> pd.DataFrame:
    input_file = first_excel_file(paths_config.values["raw_sources"], "agentes")
    raw = pd.read_excel(input_file, engine="openpyxl")
    agentes, _ = transform_agentes(raw)
    return agentes


def _prepare_population(agentes: pd.DataFrame) -> pd.DataFrame:
    result = agentes[agentes["Rota"].map(clean_text).eq(ROTA_HID)].copy()
    result = result.drop_duplicates(subset=["ChaveCentroRota"]).sort_values("ChaveCentroRota")
    return result.reset_index(drop=True)


def _prepare_indicadores(indicadores: pd.DataFrame) -> dict[str, float]:
    value_column = "REALIZADO" if "REALIZADO" in indicadores.columns else "Realizado"
    source = indicadores[indicadores["KPI"].map(clean_text).isin(KPI_ORDER)].copy()
    source[value_column] = source[value_column].map(to_number)
    source["ChaveIndicadorHID"] = source["ChaveCentroRota"].fillna("") + source["KPI"].map(clean_text).fillna("")
    return source.drop_duplicates("ChaveIndicadorHID").set_index("ChaveIndicadorHID")[value_column].to_dict()


def _print_summary(final: pd.DataFrame, long: pd.DataFrame) -> None:
    print("Desenvolvedor HID")
    print(f"linhas final: {len(final)}")
    print(f"chaves: {final['ChaveCentroRota'].nunique()}")
    print("realizados encontrados por KPI:")
    for kpi, group in long.groupby("KPI"):
        print(f"  {kpi}: {int(group['Realizado'].notna().sum())}/{len(group)}")
    print(f"status performance: {classify_status_performance(0)}")
