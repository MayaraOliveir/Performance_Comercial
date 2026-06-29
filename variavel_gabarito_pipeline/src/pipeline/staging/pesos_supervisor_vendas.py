"""Staging de pesos da figura Supervisor de Vendas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import clean_text, first_excel_file, to_number


SHEET_NAME = "Apoio Sup. Vendas"
FIRST_ROW = 1
LAST_ROW = 24
FIRST_COL = 13
LAST_COL = 16


def transform_pesos_supervisor_vendas(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extrai pesos do bloco N:Q da aba Apoio Sup. Vendas."""

    block = raw.iloc[FIRST_ROW : LAST_ROW + 1, FIRST_COL : LAST_COL + 1].copy()
    block.columns = ["ChavePesoArquivo", "TipoSupervisor", "KPI", "Peso"]
    result = block[["TipoSupervisor", "KPI", "Peso"]].copy()
    result["TipoSupervisor"] = result["TipoSupervisor"].map(clean_text).fillna("")
    result["KPI"] = result["KPI"].map(clean_text)
    result["Peso"] = result["Peso"].map(to_number)
    result = result.dropna(subset=["KPI", "Peso"]).copy()
    result["ChavePeso"] = result["TipoSupervisor"].fillna("") + result["KPI"].fillna("")
    result["TipoPeso"] = result["TipoSupervisor"].map(lambda value: "Geral" if value == "" else value)
    result["FontePeso"] = f"{SHEET_NAME}!N:Q"
    result = result.drop_duplicates(subset=["ChavePeso"], keep="first").reset_index(drop=True)

    diagnostics = (
        result.groupby("TipoPeso", dropna=False)
        .agg(qtd_kpis=("KPI", "nunique"), soma_pesos=("Peso", "sum"))
        .reset_index()
    )
    return result[["TipoSupervisor", "TipoPeso", "KPI", "Peso", "ChavePeso", "FontePeso"]], diagnostics


def build_staging_pesos_supervisor_vendas(paths_config_path: str | Path | None = None) -> list[Path]:
    """Le o gabarito e salva os pesos especificos de Supervisor de Vendas."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.pesos_supervisor_vendas")
    input_file = first_excel_file(paths_config.values["raw_sources"], "gabarito_validacao")
    raw = pd.read_excel(input_file, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    transformed, diagnostics = transform_pesos_supervisor_vendas(raw)

    staging_dir = paths_config.values["processed"]["staging"]
    outputs = [
        write_csv(transformed, staging_dir / "stg_pesos_supervisor_vendas.csv"),
        write_csv(diagnostics, staging_dir / "diag_pesos_supervisor_vendas.csv"),
    ]
    logger.info(
        "staging_pesos_supervisor_vendas_concluido",
        extra={"arquivo": str(input_file), "linhas_salvas": len(transformed)},
    )
    return outputs
