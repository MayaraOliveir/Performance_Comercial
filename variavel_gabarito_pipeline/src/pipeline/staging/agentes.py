"""Staging de agentes."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import (
    create_chave_centro_rota,
    create_tipo_rota,
    first_excel_file,
    rename_columns_by_aliases,
    require_columns,
    standardize_text_columns,
)


ALIASES = {
    "Centro": {"CENTRO"},
    "Rota": {"ROTA"},
    "Nome": {"NOME"},
    "DescricaoFuncao": {"DESCRICAO_DA_FUNCAO", "DESCRICAO_FUNCAO", "FUNCAO"},
}


def transform_agentes(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Padroniza agentes e gera recortes de Promotor."""

    result = rename_columns_by_aliases(dataframe, ALIASES)
    require_columns(result, ["Centro", "Rota", "DescricaoFuncao"], "agentes")
    selected_columns = [column for column in ALIASES if column in result.columns]
    result = result[selected_columns].copy()
    result = standardize_text_columns(result, ["Centro", "Rota", "Nome", "DescricaoFuncao"])
    result["ChaveCentroRota"] = [
        create_chave_centro_rota(centro, rota)
        for centro, rota in zip(result["Centro"], result["Rota"], strict=False)
    ]
    result["TipoRota"] = result["Rota"].map(create_tipo_rota)
    result["Figura"] = result["DescricaoFuncao"].map(_classify_figure)

    promotor = result[result["Figura"] == "PROMOTOR DE VENDAS"].copy()
    dim_rotas = (
        promotor.dropna(subset=["ChaveCentroRota"])
        .drop_duplicates(subset=["ChaveCentroRota"])
        [["ChaveCentroRota", "Centro", "Rota", "TipoRota"]]
        .sort_values("ChaveCentroRota")
        .reset_index(drop=True)
    )
    return result, promotor, dim_rotas


def _classify_figure(descricao_funcao: object) -> str:
    text = "" if pd.isna(descricao_funcao) else str(descricao_funcao)
    return "PROMOTOR DE VENDAS" if "PROMOTOR DE VENDAS" in text else "OUTROS"


def build_staging_agentes(paths_config_path: str | Path | None = None) -> list[Path]:
    """Le agentes brutos e salva staging e dimensao de rotas de Promotor."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.agentes")
    input_file = first_excel_file(paths_config.values["raw_sources"], "agentes")

    dataframe = pd.read_excel(input_file, engine="openpyxl")
    agentes, promotor, dim_rotas = transform_agentes(dataframe)

    staging_dir = paths_config.values["processed"]["staging"]
    dimensions_dir = paths_config.values["processed"]["dimensions"]
    outputs = [
        write_csv(agentes, staging_dir / "stg_agentes.csv"),
        write_csv(promotor, staging_dir / "stg_agentes_promotor.csv"),
        write_csv(dim_rotas, dimensions_dir / "dim_rotas_promotor.csv"),
    ]

    logger.info(
        "staging_agentes_concluido",
        extra={
            "arquivo": str(input_file),
            "linhas_lidas": len(dataframe),
            "linhas_salvas": len(agentes),
            "linhas_promotor": len(promotor),
            "rotas_promotor": len(dim_rotas),
        },
    )
    return outputs
