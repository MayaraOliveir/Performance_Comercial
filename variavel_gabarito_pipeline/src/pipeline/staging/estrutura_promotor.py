"""Staging da fonte mensal Estrutura Promotor."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.exceptions import DataReadError
from pipeline.core.logger import configure_logger
from pipeline.core.paths import PROJECT_ROOT, load_paths_config, load_yaml
from pipeline.core.utils import list_excel_files
from pipeline.io.csv_writer import write_csv
from pipeline.staging.common import (
    clean_text,
    create_chave_centro_rota,
    create_tipo_rota,
    normalize_column_name,
    to_number,
)


SHEET_NAME = "Estrutura Promotor"
HEADER_ROW = 2
HEADER_SCAN_ROWS = 30
ROTA_POSITION = 4
CENTRO_POSITION = 5
CHAVE_POSITION = 11
META_RED_POSITION = 12
REALIZADO_RED_POSITION = 13
META_RPT_POSITION = 14
REALIZADO_RPT_POSITION = 15

ALIASES = {
    "UF": {"UF"},
    "Gerencia": {"GERENCIA", "GERENCIA_REGIONAL", "GERENCIA_DE_VENDAS"},
    "Supervisor": {"SUPERVISOR", "SUPERVISOR_DESCRICAO", "SUPERVISOR_DESCRIÇÃO"},
    "Rota": {"ROTA"},
    "Centro": {"CENTRO", "UNIDADE"},
    "ChaveArquivo": {"CHAVE", "CHAVECENTROROTA", "CHAVE_CENTRO_ROTA"},
    "MetaRED": {"META_RED", "METARED"},
    "RealizadoRED": {"REAL_RED", "REALIZADO_RED", "REALRED", "REALIZADORED"},
    "MetaRPT": {"META_RPT", "METARPT", "META2"},
    "RealizadoRPT": {"REAL_RPT", "REALIZADO_RPT", "REALRPT", "REALIZADORPT", "REAL2"},
}


DEFAULT_FIGURAS_CONFIG = PROJECT_ROOT / "config" / "figuras.yaml"


def transform_estrutura_promotor(
    raw: pd.DataFrame,
    fonte_estrutura: str = "estrutura_mensal",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Padroniza a Estrutura Promotor e cria a dimensao oficial de rotas."""

    source = _with_detected_header(raw)
    mapped = _map_columns(source)

    result = pd.DataFrame(index=mapped.index)
    for column in ["UF", "Gerencia", "Supervisor"]:
        if column in mapped.columns:
            result[column] = mapped[column].map(clean_text)

    unidade_original = mapped["Centro"] if "Centro" in mapped.columns else pd.Series(pd.NA, index=mapped.index)
    result["UnidadeOriginal"] = unidade_original
    result["Centro"] = unidade_original.map(clean_text)
    result["Rota"] = mapped["Rota"].map(clean_text)

    if "ChaveArquivo" in mapped.columns:
        result["ChaveArquivo"] = mapped["ChaveArquivo"].map(clean_text)
    for column in ["MetaRED", "RealizadoRED", "MetaRPT", "RealizadoRPT"]:
        if column in mapped.columns:
            result[column] = mapped[column].map(to_number)

    result["ChaveCentroRota"] = [
        create_chave_centro_rota(centro, rota)
        for centro, rota in zip(result["Centro"], result["Rota"], strict=False)
    ]
    result["TipoRota"] = result["Rota"].map(create_tipo_rota)
    result["FonteEstrutura"] = fonte_estrutura
    result = result.dropna(subset=["ChaveCentroRota"])
    result = result[(result["Centro"] != "CENTRO") & (result["Rota"] != "ROTA")]

    duplicates = result[result.duplicated(subset=["ChaveCentroRota"], keep=False)].copy()
    result = result.drop_duplicates(subset=["ChaveCentroRota"]).sort_values("ChaveCentroRota").reset_index(drop=True)

    dim_columns = [
        column
        for column in ["ChaveCentroRota", "UF", "Gerencia", "Supervisor", "Centro", "Rota", "TipoRota", "UnidadeOriginal"]
        if column in result.columns
    ]
    if "FonteEstrutura" in result.columns:
        dim_columns.append("FonteEstrutura")
    dim_rotas = result[dim_columns].copy()
    diagnostics = build_resumo_estrutura_promotor(
        result,
        duplicates,
        raw_line_count=len(raw),
        fonte_estrutura=fonte_estrutura,
    )
    return result, dim_rotas, diagnostics


def build_resumo_estrutura_promotor(
    estrutura: pd.DataFrame,
    duplicates: pd.DataFrame,
    raw_line_count: int | None = None,
    fonte_estrutura: str | None = None,
) -> pd.DataFrame:
    """Cria diagnostico da fonte mensal Estrutura Promotor."""

    total_linhas = raw_line_count if raw_line_count is not None else len(estrutura)
    rows = [
        {"Metrica": "fonte_estrutura_usada", "Valor": fonte_estrutura or _first_source(estrutura), "TipoRota": pd.NA},
        {"Metrica": "total_linhas_estrutura", "Valor": total_linhas, "TipoRota": pd.NA},
        {"Metrica": "total_chaves_unicas", "Valor": estrutura["ChaveCentroRota"].nunique(), "TipoRota": pd.NA},
        {"Metrica": "duplicidades_chave", "Valor": len(duplicates), "TipoRota": pd.NA},
        {"Metrica": "centro_nulo", "Valor": int(estrutura["Centro"].isna().sum()), "TipoRota": pd.NA},
        {"Metrica": "rota_nula", "Valor": int(estrutura["Rota"].isna().sum()), "TipoRota": pd.NA},
    ]
    by_tipo = estrutura.groupby("TipoRota", dropna=False).size().reset_index(name="Valor")
    rows.extend(
        {"Metrica": "quantidade_por_tipo_rota", "Valor": row["Valor"], "TipoRota": row["TipoRota"]}
        for _, row in by_tipo.iterrows()
    )
    return pd.DataFrame(rows)


def build_staging_estrutura_promotor(
    paths_config_path: str | Path | None = None,
    figuras_config_path: str | Path | None = None,
) -> list[Path]:
    """Le a Estrutura Promotor mensal e salva staging, dimensao e diagnostico."""

    paths_config = load_paths_config(paths_config_path) if paths_config_path else load_paths_config()
    logger = configure_logger("pipeline.staging.estrutura_promotor")
    source = resolve_estrutura_promotor_source(paths_config, figuras_config_path)
    input_file = source["path"]
    fonte_estrutura = source["fonte"]
    if fonte_estrutura == "gabarito_fallback":
        logger.warning(
            "estrutura_promotor_usando_gabarito_fallback",
            extra={"arquivo": str(input_file), "fonte_estrutura": fonte_estrutura},
        )

    raw = read_estrutura_promotor_excel(input_file)
    estrutura, dim_rotas, diagnostics = transform_estrutura_promotor(raw, fonte_estrutura=fonte_estrutura)

    staging_dir = paths_config.values["processed"]["staging"]
    dimensions_dir = paths_config.values["processed"]["dimensions"]
    validation_dir = paths_config.values["processed"]["validation"]
    outputs = [
        write_csv(estrutura, staging_dir / "stg_estrutura_promotor.csv"),
        write_csv(dim_rotas, dimensions_dir / "dim_rotas_promotor.csv"),
        write_csv(diagnostics, validation_dir / "resumo_estrutura_promotor.csv"),
    ]

    logger.info(
        "staging_estrutura_promotor_concluido",
        extra={
            "arquivo": str(input_file),
            "fonte_estrutura": fonte_estrutura,
            "linhas_lidas": len(raw),
            "linhas_salvas": len(estrutura),
            "rotas_promotor": len(dim_rotas),
        },
    )
    return outputs


def resolve_estrutura_promotor_source(
    paths_config,
    figuras_config_path: str | Path | None = None,
) -> dict[str, Path | str]:
    """Resolve a fonte da Estrutura Promotor conforme modo producao/desenvolvimento."""

    monthly_files = list_excel_files(paths_config.values["raw_sources"]["estrutura_promotor"])
    if monthly_files:
        return {"path": monthly_files[0], "fonte": "estrutura_mensal"}

    if allow_gabarito_fallback_estrutura(figuras_config_path):
        gabarito_files = list_excel_files(paths_config.values["raw_sources"]["gabarito_validacao"])
        if not gabarito_files:
            raise DataReadError("Estrutura Promotor mensal não encontrada e nenhum gabarito disponível para fallback.")
        return {"path": gabarito_files[0], "fonte": "gabarito_fallback"}

    raise DataReadError(
        "Estrutura Promotor mensal não encontrada. Para desenvolvimento, habilite "
        "allow_gabarito_fallback_estrutura=true."
    )


def allow_gabarito_fallback_estrutura(figuras_config_path: str | Path | None = None) -> bool:
    """Le a flag temporaria de fallback da figura Promotor."""

    path = Path(figuras_config_path) if figuras_config_path else DEFAULT_FIGURAS_CONFIG
    config = load_yaml(path)
    promotor = config.get("figuras", {}).get("promotor_vendas", {})
    return bool(promotor.get("allow_gabarito_fallback_estrutura", False))


def read_estrutura_promotor_excel(file_path: str | Path) -> pd.DataFrame:
    """Le a aba Estrutura Promotor quando existir; caso contrario usa a primeira aba."""

    excel = pd.ExcelFile(file_path, engine="openpyxl")
    sheet_name = SHEET_NAME if SHEET_NAME in excel.sheet_names else excel.sheet_names[0]
    return pd.read_excel(file_path, sheet_name=sheet_name, header=None, engine="openpyxl")


def first_estrutura_promotor_file(raw_estrutura_dir: str | Path) -> Path:
    """Retorna o primeiro Excel da pasta mensal Estrutura Promotor."""

    files = list_excel_files(raw_estrutura_dir)
    if not files:
        raise DataReadError(f"Nenhum Excel encontrado em {raw_estrutura_dir}")
    return files[0]


def _first_source(estrutura: pd.DataFrame) -> str | None:
    if "FonteEstrutura" not in estrutura.columns or estrutura.empty:
        return None
    return estrutura["FonteEstrutura"].dropna().astype(str).iloc[0]


def _with_detected_header(raw: pd.DataFrame) -> pd.DataFrame:
    for index in range(min(HEADER_SCAN_ROWS, len(raw))):
        normalized_values = {normalize_column_name(value) for value in raw.iloc[index].tolist()}
        if {"ROTA", "CENTRO"}.issubset(normalized_values) or {"ROTA", "UNIDADE"}.issubset(normalized_values):
            data = raw.iloc[index + 1 :].copy()
            data.columns = raw.iloc[index].tolist()
            return data.dropna(how="all").reset_index(drop=True)

    if raw.shape[1] <= REALIZADO_RPT_POSITION:
        raise DataReadError("Estrutura Promotor sem colunas minimas esperadas")
    data = raw.iloc[HEADER_ROW + 1 :].copy()
    data.columns = raw.iloc[HEADER_ROW].tolist()
    return data.dropna(how="all").reset_index(drop=True)


def _map_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[object, str] = {}
    seen_targets: set[str] = set()
    for column in dataframe.columns:
        normalized = normalize_column_name(column)
        for target, accepted_names in ALIASES.items():
            if normalized in accepted_names and target not in seen_targets:
                rename_map[column] = target
                seen_targets.add(target)
                break

    mapped = dataframe.rename(columns=rename_map)
    if "Rota" not in mapped.columns or "Centro" not in mapped.columns:
        mapped = _map_official_positions(dataframe)
    elif dataframe.shape[1] > REALIZADO_RPT_POSITION:
        positional_columns = {
            "ChaveArquivo": CHAVE_POSITION,
            "MetaRED": META_RED_POSITION,
            "RealizadoRED": REALIZADO_RED_POSITION,
            "MetaRPT": META_RPT_POSITION,
            "RealizadoRPT": REALIZADO_RPT_POSITION,
        }
        for target, position in positional_columns.items():
            if target not in mapped.columns:
                mapped[target] = dataframe.iloc[:, position]

    if "Rota" not in mapped.columns or "Centro" not in mapped.columns:
        raise DataReadError("Estrutura Promotor sem Rota e Centro/Unidade")

    return mapped


def _map_official_positions(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.shape[1] <= REALIZADO_RPT_POSITION:
        return dataframe

    result = dataframe.copy()
    positional_map = {
        result.columns[ROTA_POSITION]: "Rota",
        result.columns[CENTRO_POSITION]: "Centro",
        result.columns[CHAVE_POSITION]: "ChaveArquivo",
        result.columns[META_RED_POSITION]: "MetaRED",
        result.columns[REALIZADO_RED_POSITION]: "RealizadoRED",
        result.columns[META_RPT_POSITION]: "MetaRPT",
        result.columns[REALIZADO_RPT_POSITION]: "RealizadoRPT",
    }
    return result.rename(columns=positional_map)
