"""Valida componentes do calculo Promotor contra o gabarito oficial."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv
from pipeline.validation.gabarito_promotor import first_gabarito_file, read_gabarito_promotor


TOLERANCE = 0.0001
ROUNDING_TOLERANCE = 0.001
PA013_ROTA = "PA013"

COMPONENTS = [
    ("MetaRED", "MetaRED"),
    ("RealizadoRED", "RealizadoRED"),
    ("AderenciaRED", "AderenciaRED"),
    ("PerformanceRED", "PerformanceRED"),
    ("PesoRED", "PesoRED"),
    ("AtingimentoRED", "AtingimentoRED"),
    ("MetaRPT", "MetaRPT"),
    ("RealizadoRPT", "RealizadoRPT"),
    ("PerformanceRPT", "PerformanceRPT"),
    ("PesoRPT", "PesoRPT"),
    ("AtingimentoRPT", "AtingimentoRPT"),
    ("AtingimentoTotal", "AtingimentoTotal"),
    ("EscalaAtingida", "EscalaAtingida"),
]

SCALE_TO_PERCENT_COMPONENTS = {"MetaRED", "RealizadoRED", "MetaRPT", "RealizadoRPT"}

OUTPUT_COLUMNS = [
    "ChaveCentroRota",
    "Centro",
    "Rota",
    "TipoRota",
    "FonteEstrutura",
    "StatusComparacao",
    "MetaREDPython",
    "MetaREDGabarito",
    "DifMetaRED",
    "RealizadoREDPython",
    "RealizadoREDGabarito",
    "DifRealizadoRED",
    "AderenciaREDPython",
    "AderenciaREDGabarito",
    "DifAderenciaRED",
    "PerformanceREDPython",
    "PerformanceREDGabarito",
    "DifPerformanceRED",
    "PesoREDPython",
    "PesoREDGabarito",
    "DifPesoRED",
    "AtingimentoREDPython",
    "AtingimentoREDGabarito",
    "DifAtingimentoRED",
    "MetaRPTPython",
    "MetaRPTGabarito",
    "DifMetaRPT",
    "RealizadoRPTPython",
    "RealizadoRPTGabarito",
    "DifRealizadoRPT",
    "PerformanceRPTPython",
    "PerformanceRPTGabarito",
    "DifPerformanceRPT",
    "PesoRPTPython",
    "PesoRPTGabarito",
    "DifPesoRPT",
    "AtingimentoRPTPython",
    "AtingimentoRPTGabarito",
    "DifAtingimentoRPT",
    "AtingimentoTotalPython",
    "AtingimentoTotalGabarito",
    "DifAtingimentoTotal",
    "EscalaAtingidaPython",
    "EscalaAtingidaGabarito",
    "DifEscalaAtingida",
    "CausaProvavelDiferenca",
]


def run() -> list[Path]:
    """Gera validacao detalhada de componentes do Promotor."""

    logger = configure_logger("pipeline.validacao_componentes_promotor")
    paths_config = load_paths_config()
    processed = paths_config.values["processed"]
    facts_dir = processed["facts"]
    staging_dir = processed["staging"]
    validation_dir = processed["validation"]
    raw_gabarito_dir = paths_config.values["raw_sources"]["gabarito_validacao"]

    final = read_csv(facts_dir / "fat_promotor_final.csv")
    base = read_csv(facts_dir / "fat_promotor_base.csv")
    validacao = read_csv(validation_dir / "validacao_promotor_gabarito.csv")
    metas = read_csv(staging_dir / "stg_metas.csv")
    indicadores = read_csv(staging_dir / "stg_indicadores.csv")
    estrutura = read_csv(staging_dir / "stg_estrutura_promotor.csv")

    gabarito_file = first_gabarito_file(raw_gabarito_dir)
    gabarito = read_gabarito_promotor(gabarito_file)
    componentes = build_component_validation(final, base, gabarito, validacao)
    resumo = build_component_summary(componentes)
    diagnostico_pa013 = build_pa013_diagnostic(
        componentes=componentes,
        metas=metas,
        indicadores=indicadores,
        estrutura=estrutura,
        gabarito=gabarito,
        final=final,
    )

    outputs = [
        write_csv(gabarito, validation_dir / "stg_gabarito_promotor.csv"),
        write_csv(componentes, validation_dir / "validacao_componentes_promotor.csv"),
        write_csv(resumo, validation_dir / "resumo_validacao_componentes_promotor.csv"),
        write_csv(diagnostico_pa013, validation_dir / "diagnostico_pa013_promotor.csv"),
    ]
    logger.info(
        "validacao_componentes_promotor_concluida",
        extra={
            "arquivo_gabarito": str(gabarito_file),
            "linhas_componentes": len(componentes),
            "linhas_resumo": len(resumo),
            "linhas_pa013": len(diagnostico_pa013),
        },
    )
    print(f"validacao_componentes_promotor.csv: {len(componentes)} linhas")
    print(f"resumo_validacao_componentes_promotor.csv: {len(resumo)} linhas")
    print(f"diagnostico_pa013_promotor.csv: {len(diagnostico_pa013)} linhas")
    return outputs


def build_component_validation(
    final: pd.DataFrame,
    base: pd.DataFrame,
    gabarito: pd.DataFrame,
    validacao: pd.DataFrame,
) -> pd.DataFrame:
    """Monta comparacao lado a lado dos componentes Python x gabarito."""

    python = final.copy()
    if "FonteEstrutura" not in python.columns and "FonteEstrutura" in base.columns:
        python = python.merge(
            base[["ChaveCentroRota", "FonteEstrutura"]].drop_duplicates("ChaveCentroRota"),
            on="ChaveCentroRota",
            how="left",
        )

    status = validacao[["ChaveCentroRota", "StatusComparacao"]].drop_duplicates("ChaveCentroRota")
    result = python.merge(status, on="ChaveCentroRota", how="left")
    result = result.merge(
        gabarito[
            ["ChaveCentroRota"]
            + [f"{gabarito_name}Gabarito" for _, gabarito_name in COMPONENTS]
        ],
        on="ChaveCentroRota",
        how="left",
    )

    for python_name, gabarito_name in COMPONENTS:
        result[f"{python_name}Python"] = result[python_name] if python_name in result.columns else pd.NA
        gabarito_column = f"{gabarito_name}Gabarito"
        if python_name in SCALE_TO_PERCENT_COMPONENTS:
            result[gabarito_column] = _normalize_gabarito_scale(result[f"{python_name}Python"], result[gabarito_column])
        result[f"Dif{python_name}"] = _difference(result[f"{python_name}Python"], result[gabarito_column])

    result["CausaProvavelDiferenca"] = result.apply(classify_component_difference, axis=1)
    return result[[column for column in OUTPUT_COLUMNS if column in result.columns]].reset_index(drop=True)


def build_component_summary(componentes: pd.DataFrame) -> pd.DataFrame:
    """Gera resumo da validacao de componentes."""

    rows = [
        {"Metrica": "total_rotas", "Valor": len(componentes), "Categoria": pd.NA},
        {
            "Metrica": "quantidade_meta_red_diferente",
            "Valor": int(_diff_mask(componentes, "MetaRED").sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "quantidade_realizado_red_diferente",
            "Valor": int(_diff_mask(componentes, "RealizadoRED").sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "quantidade_aderencia_red_diferente",
            "Valor": int(_diff_mask(componentes, "AderenciaRED").sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "quantidade_meta_rpt_diferente",
            "Valor": int(_diff_mask(componentes, "MetaRPT").sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "quantidade_realizado_rpt_diferente",
            "Valor": int(_diff_mask(componentes, "RealizadoRPT").sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "quantidade_diferenca_so_escala",
            "Valor": int((componentes["CausaProvavelDiferenca"] == "Diferença apenas em escala").sum()),
            "Categoria": pd.NA,
        },
        {
            "Metrica": "quantidade_diferencas_pequenas_arredondamento",
            "Valor": int((componentes["CausaProvavelDiferenca"] == "Diferença de arredondamento").sum()),
            "Categoria": pd.NA,
        },
    ]
    for cause, count in componentes["CausaProvavelDiferenca"].value_counts(dropna=False).items():
        rows.append({"Metrica": "quantidade_por_causa", "Valor": int(count), "Categoria": cause})
    return pd.DataFrame(rows)


def build_pa013_diagnostic(
    componentes: pd.DataFrame,
    metas: pd.DataFrame,
    indicadores: pd.DataFrame,
    estrutura: pd.DataFrame,
    gabarito: pd.DataFrame,
    final: pd.DataFrame,
) -> pd.DataFrame:
    """Gera diagnostico especifico para a rota PA013."""

    rows: list[dict[str, object]] = []
    rows.extend(_rows_by_rota("stg_metas_rota_PA013", metas, PA013_ROTA))
    rows.extend(_rows_by_chaves("stg_metas_chave_exata_PA013", metas, _pa013_keys(componentes)))
    rows.extend(_rows_by_rota("stg_indicadores_rota_PA013", indicadores, PA013_ROTA))
    rows.extend(_rows_by_rota("stg_estrutura_promotor_rota_PA013", estrutura, PA013_ROTA))
    rows.extend(_rows_by_rota("gabarito_rota_PA013", gabarito, PA013_ROTA))
    rows.extend(_rows_by_rota("python_final_rota_PA013", final, PA013_ROTA))
    rows.extend(_rows_by_rota("validacao_componentes_rota_PA013", componentes, PA013_ROTA))
    return pd.DataFrame(rows)


def classify_component_difference(row: pd.Series) -> str:
    """Classifica a causa provavel da diferenca por prioridade."""

    if _component_differs(row, "MetaRED"):
        return "Diferença em MetaRED"
    if _component_differs(row, "RealizadoRED"):
        return "Diferença em RealizadoRED"
    if _component_differs(row, "AderenciaRED"):
        return "Diferença em AderenciaRED"
    if _component_differs(row, "PesoRED"):
        return "Diferença em PesoRED"
    if _component_differs(row, "MetaRPT"):
        return "Diferença em MetaRPT"
    if pd.isna(row.get("RealizadoRPTPython")) and not pd.isna(row.get("RealizadoRPTGabarito")):
        return "Diferença em RealizadoRPT / fonte ausente"
    if _component_differs(row, "RealizadoRPT"):
        return "Diferença em RealizadoRPT / fonte ausente"
    if _component_differs(row, "PesoRPT"):
        return "Diferença em PesoRPT"
    if _matches(row, "AtingimentoTotal") and _component_differs(row, "EscalaAtingida"):
        return "Diferença apenas em escala"
    if _all_small_differences(row):
        return "Diferença de arredondamento"
    return "Sem diferença de componentes identificada"


def _difference(left: pd.Series, right: pd.Series) -> pd.Series:
    return pd.to_numeric(left, errors="coerce") - pd.to_numeric(right, errors="coerce")


def _normalize_gabarito_scale(python_values: pd.Series, gabarito_values: pd.Series) -> pd.Series:
    """Alinha escala percentual do gabarito quando Python esta em pontos percentuais."""

    python_num = pd.to_numeric(python_values, errors="coerce")
    gabarito_num = pd.to_numeric(gabarito_values, errors="coerce")
    needs_scale = python_num.abs().gt(2) & gabarito_num.abs().le(2) & gabarito_num.notna()
    return gabarito_num.mask(needs_scale, gabarito_num * 100)


def _component_differs(row: pd.Series, component: str, tolerance: float = TOLERANCE) -> bool:
    left = row.get(f"{component}Python")
    right = row.get(f"{component}Gabarito")
    if pd.isna(left) and pd.isna(right):
        return False
    if pd.isna(left) or pd.isna(right):
        return True
    return abs(float(left) - float(right)) > tolerance


def _matches(row: pd.Series, component: str, tolerance: float = TOLERANCE) -> bool:
    return not _component_differs(row, component, tolerance)


def _all_small_differences(row: pd.Series) -> bool:
    diffs = [
        abs(float(row[column]))
        for column in row.index
        if column.startswith("Dif") and not pd.isna(row[column])
    ]
    return bool(diffs) and max(diffs) <= ROUNDING_TOLERANCE


def _diff_mask(dataframe: pd.DataFrame, component: str) -> pd.Series:
    return dataframe.apply(lambda row: _component_differs(row, component), axis=1)


def _pa013_keys(componentes: pd.DataFrame) -> set[str]:
    return set(componentes.loc[componentes["Rota"] == PA013_ROTA, "ChaveCentroRota"].dropna())


def _rows_by_rota(section: str, dataframe: pd.DataFrame, rota: str) -> list[dict[str, object]]:
    if "Rota" not in dataframe.columns:
        return [{"Secao": section, "Observacao": "coluna_rota_ausente"}]
    rows = dataframe[dataframe["Rota"] == rota].copy()
    return _records(section, rows)


def _rows_by_chaves(section: str, dataframe: pd.DataFrame, keys: set[str]) -> list[dict[str, object]]:
    if "ChaveCentroRota" not in dataframe.columns:
        return [{"Secao": section, "Observacao": "coluna_chave_ausente"}]
    rows = dataframe[dataframe["ChaveCentroRota"].isin(keys)].copy()
    return _records(section, rows)


def _records(section: str, dataframe: pd.DataFrame) -> list[dict[str, object]]:
    if dataframe.empty:
        return [{"Secao": section, "Observacao": "nenhuma_linha_encontrada"}]
    records = []
    for _, row in dataframe.iterrows():
        record = {"Secao": section}
        record.update(row.to_dict())
        records.append(record)
    return records


def main() -> None:
    run()


if __name__ == "__main__":
    main()
