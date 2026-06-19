"""Staging da base RED por mes, centro e rota."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.exceptions import DataReadError
from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import (
    add_kpi_keys,
    rename_columns_by_aliases,
    require_columns,
    standardize_text_columns,
    to_number,
)


ALIASES = {
    "ANO_MES": {"ANO_MES"},
    "KPI": {"KPI"},
    "CENTRO": {"CENTRO"},
    "ROTA": {"ROTA"},
    "MetaArquivoREDMesRota": {"META"},
    "RealizadoREDMesRota": {"REALIZADO"},
    "DATA_ATUALIZACAO": {"DATA_ATUALIZACAO"},
    "data_importacao": {"DATA_IMPORTACAO"},
}


def transform_red_mes_rota(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Padroniza a base RED por mes e rota."""

    result = rename_columns_by_aliases(dataframe, ALIASES)
    require_columns(result, ["KPI", "CENTRO", "ROTA", "RealizadoREDMesRota"], "red_mes_rota")
    selected_columns = [column for column in ALIASES if column in result.columns]
    result = result[selected_columns].copy()

    result["Centro"] = result["CENTRO"]
    result["Rota"] = result["ROTA"]
    result = standardize_text_columns(result, ["KPI", "Centro", "Rota"])
    result["MetaArquivoREDMesRota"] = result["MetaArquivoREDMesRota"].map(to_number)
    result["RealizadoREDMesRota"] = result["RealizadoREDMesRota"].map(to_number)

    result = result[result["KPI"] == "RED"].copy()
    result = result.dropna(subset=["Centro", "Rota", "KPI"])
    return add_kpi_keys(result).reset_index(drop=True)


def build_staging_red_mes_rota(paths_config_path: str | Path | None = None) -> Path:
    """Le a base raw red_mes_rota e salva stg_red_mes_rota.csv."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.red_mes_rota")
    input_file = first_csv_file(paths_config.values["raw_sources"]["red_mes_rota"])

    dataframe = read_csv(input_file)
    transformed = transform_red_mes_rota(dataframe)
    output_path = paths_config.values["processed"]["staging"] / "stg_red_mes_rota.csv"
    write_csv(transformed, output_path)

    logger.info(
        "staging_red_mes_rota_concluido",
        extra={"arquivo": str(input_file), "linhas_lidas": len(dataframe), "linhas_salvas": len(transformed)},
    )
    return output_path


def first_csv_file(directory: str | Path) -> Path:
    """Retorna o primeiro CSV encontrado na pasta informada."""

    base_dir = Path(directory)
    files = sorted(
        [path for path in base_dir.iterdir() if path.is_file() and path.suffix.lower() == ".csv"],
        key=lambda item: item.as_posix().lower(),
    )
    if not files:
        raise DataReadError(f"Nenhum arquivo CSV encontrado em {base_dir}")
    return files[0]
