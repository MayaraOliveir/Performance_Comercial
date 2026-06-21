"""Exporta resultado de Promotor de Vendas para Excel visual."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.excel_writer import write_formatted_workbook


PROMOTOR_COLUMNS = [
    "Centro",
    "Rota",
    "TipoRota",
    "AderenciaRED",
    "AderenciaREDOriginal",
    "StatusAderenciaRED",
    "StatusGatilhoRED",
    "MetaRED",
    "RealizadoRED",
    "PerformanceRED",
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

DECIMAL_COLUMNS = [
    "AderenciaRED",
    "AderenciaREDOriginal",
    "PerformanceRED",
    "PerformanceRPT",
    "PesoRED",
    "PesoRPT",
    "AtingimentoRED",
    "AtingimentoRPT",
    "AtingimentoTotal",
    "EscalaAtingida",
]

STATUS_PERFORMANCE_COLORS = {
    "Irregular": "#FFC7CE",
    "Regular": "#FFEB9C",
    "Em linha": "#C6EFCE",
    "Alta": "#BDD7EE",
    "Sem cálculo": "#D9E1F2",
}

STATUS_COMPARACAO_COLORS = {
    "OK": "#C6EFCE",
    "Diferente": "#FFC7CE",
    "Python sem atingimento": "#FFEB9C",
    "Só no gabarito": "#FCE4D6",
    "Só no Python": "#BDD7EE",
    "OK - sem cálculo no gabarito": "#D9E1F2",
    "OK - sem cálculo nos dois": "#D9E1F2",
}


def run() -> Path:
    """Gera data/output/resultado_promotor_vendas.xlsx."""

    logger = configure_logger("pipeline.export_excel_promotor")
    paths_config = load_paths_config()
    processed = paths_config.values["processed"]
    facts_dir = processed["facts"]
    validation_dir = processed["validation"]
    output_path = paths_config.values["data"]["output"] / "resultado_promotor_vendas.xlsx"

    sheets = {
        "PROMOTOR DE VENDAS": _select_columns(
            read_csv(facts_dir / "fat_promotor_final.csv"),
            PROMOTOR_COLUMNS,
        ),
        "CALCULO DETALHADO": read_csv(facts_dir / "fat_promotor_calculo.csv"),
        "VALIDACAO GABARITO": read_csv(validation_dir / "validacao_promotor_gabarito.csv"),
        "RESUMO VALIDACAO": read_csv(validation_dir / "resumo_validacao_promotor.csv"),
        "DIFERENCAS": read_csv(validation_dir / "diferencas_promotor.csv"),
        "DIAGNOSTICO": read_csv(facts_dir / "diag_promotor.csv"),
    }

    decimal_columns = {sheet_name: DECIMAL_COLUMNS for sheet_name in sheets}
    status_formats = {
        "PROMOTOR DE VENDAS": {"StatusPerformance": STATUS_PERFORMANCE_COLORS},
        "VALIDACAO GABARITO": {"StatusComparacao": STATUS_COMPARACAO_COLORS},
    }

    output = write_formatted_workbook(
        sheets=sheets,
        output_path=output_path,
        decimal_columns=decimal_columns,
        status_formats=status_formats,
    )
    logger.info("excel_promotor_exportado", extra={"arquivo_saida": str(output)})
    return output


def _select_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return dataframe[[column for column in columns if column in dataframe.columns]].copy()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
