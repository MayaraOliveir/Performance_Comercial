"""Validacao da figura Supervisor de Vendas contra o gabarito."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.staging.common import clean_text, to_number


SHEET_NAME = "SUPERVISOR DE VENDAS"
KPI_COLUMNS = {
    "MKO": {"performance": 18, "peso": 19, "atingimento": 20},
    "MKR": {"performance": 24, "peso": 25, "atingimento": 26},
    "MKD": {"performance": 30, "peso": 31, "atingimento": 32},
    "MCN": {"performance": 36, "peso": 37, "atingimento": 38},
    "RED": {"performance": 43, "peso": 44, "atingimento": 45},
    "FRD": {"performance": 50, "peso": 51, "atingimento": 52},
    "EFV": {"performance": 56, "peso": 57, "atingimento": 58},
}
TOLERANCES = {
    "AtingimentoTotal": 0.0001,
    "EscalaAtingida": 0.0001,
    "Performance": 0.0001,
    "Atingimento": 0.0001,
}


def read_gabarito_supervisor_vendas(file_path: str | Path) -> pd.DataFrame:
    """Le a aba final de Supervisor de Vendas por posicao de colunas."""

    raw = pd.read_excel(file_path, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    result = pd.DataFrame(
        {
            "UF": _column(raw, 2).map(clean_text),
            "Gerencia": _column(raw, 3).map(clean_text),
            "Supervisao": _column(raw, 4).map(clean_text),
            "CentroOriginal": _column(raw, 5),
            "Centro": _column(raw, 5).map(clean_text),
            "RotaSup": _column(raw, 6).map(clean_text),
            "Nome": _column(raw, 7).map(clean_text),
            "StatusPerformanceGabarito": _column(raw, 10).map(_normalize_text),
            "AtingimentoTotalGabaritoOriginal": _column(raw, 12),
            "EscalaAtingidaGabaritoOriginal": _column(raw, 14),
        }
    )
    for kpi, positions in KPI_COLUMNS.items():
        result[f"Performance{kpi}GabaritoOriginal"] = _column(raw, positions["performance"])
        result[f"Peso{kpi}GabaritoOriginal"] = _column(raw, positions["peso"])
        result[f"Atingimento{kpi}GabaritoOriginal"] = _column(raw, positions["atingimento"])
        result[f"Performance{kpi}Gabarito"] = result[f"Performance{kpi}GabaritoOriginal"].map(_to_nullable_number)
        result[f"Peso{kpi}Gabarito"] = result[f"Peso{kpi}GabaritoOriginal"].map(_to_nullable_number)
        result[f"Atingimento{kpi}Gabarito"] = result[f"Atingimento{kpi}GabaritoOriginal"].map(_to_nullable_number)

    result["AtingimentoTotalGabarito"] = result["AtingimentoTotalGabaritoOriginal"].map(_to_nullable_number)
    result["EscalaAtingidaGabarito"] = result["EscalaAtingidaGabaritoOriginal"].map(_to_nullable_number)
    result["CentroErroExcelGabarito"] = result["CentroOriginal"].map(_is_excel_error)
    result["ChaveSupervisorGabarito"] = result["Centro"].fillna("") + result["Supervisao"].fillna("")
    result["ChaveSupervisorComparacao"] = [
        _comparison_key(centro, supervisao, erro)
        for centro, supervisao, erro in zip(
            result["Centro"],
            result["Supervisao"],
            result["CentroErroExcelGabarito"],
            strict=False,
        )
    ]
    result = result[result["Supervisao"].notna() & result["StatusPerformanceGabarito"].notna()].copy()
    result = result[result["StatusPerformanceGabarito"] != "STATUS DA PERFORMANCE"].copy()
    return result.drop_duplicates(subset=["ChaveSupervisorComparacao"]).reset_index(drop=True)


def compare_supervisor_vendas_outputs(pipeline_result: pd.DataFrame, gabarito: pd.DataFrame) -> pd.DataFrame:
    """Compara pipeline Supervisor de Vendas contra a aba final do gabarito."""

    left = pipeline_result.copy()
    left["CentroErroExcelPipeline"] = left["Centro"].map(_is_excel_error)
    left["ChaveSupervisorComparacao"] = [
        _comparison_key(centro, supervisao, erro)
        for centro, supervisao, erro in zip(
            left.get("Centro", pd.Series(pd.NA, index=left.index)),
            left.get("Supervisao", pd.Series(pd.NA, index=left.index)),
            left["CentroErroExcelPipeline"],
            strict=False,
        )
    ]
    left["StatusPerformanceNormalizado"] = left["StatusPerformance"].map(_normalize_text)

    keep_columns = [
        "ChaveSupervisor",
        "ChaveSupervisorComparacao",
        "Centro",
        "Supervisao",
        "RotaSup",
        "AtingimentoTotal",
        "EscalaAtingida",
        "StatusPerformance",
        "StatusPerformanceNormalizado",
    ]
    for kpi in KPI_COLUMNS:
        keep_columns.extend([f"Performance{kpi}", f"Peso{kpi}", f"Atingimento{kpi}"])
    left = left[[column for column in keep_columns if column in left.columns]].copy()

    compared = left.merge(
        gabarito,
        on="ChaveSupervisorComparacao",
        how="outer",
        suffixes=("", "GabaritoCadastro"),
        indicator=True,
    )
    compared["ExcecaoCentroErroExcel"] = compared.apply(_is_center_error_exception, axis=1)
    compared["StatusComparacaoChave"] = compared.apply(_classify_key_status, axis=1)
    compared["Comparavel"] = compared["_merge"].eq("both") & ~compared["ExcecaoCentroErroExcel"]

    _add_numeric_comparison(
        compared,
        "AtingimentoTotal",
        "AtingimentoTotalGabarito",
        "AtingimentoTotal",
        TOLERANCES["AtingimentoTotal"],
        zero_equivalent=True,
    )
    _add_numeric_comparison(
        compared,
        "EscalaAtingida",
        "EscalaAtingidaGabarito",
        "EscalaAtingida",
        TOLERANCES["EscalaAtingida"],
        zero_equivalent=True,
    )
    for kpi in KPI_COLUMNS:
        _add_numeric_comparison(
            compared,
            f"Performance{kpi}",
            f"Performance{kpi}Gabarito",
            f"Performance{kpi}",
            TOLERANCES["Performance"],
            zero_equivalent=True,
        )
        _add_numeric_comparison(
            compared,
            f"Peso{kpi}",
            f"Peso{kpi}Gabarito",
            f"Peso{kpi}",
            TOLERANCES["Performance"],
            zero_equivalent=True,
        )
        _add_numeric_comparison(
            compared,
            f"Atingimento{kpi}",
            f"Atingimento{kpi}Gabarito",
            f"Atingimento{kpi}",
            TOLERANCES["Atingimento"],
            zero_equivalent=True,
        )

    compared["StatusPerformanceOK"] = (
        compared["StatusPerformanceNormalizado"].eq(compared["StatusPerformanceGabarito"])
        & compared["Comparavel"]
    )
    compared["DivergenciaCritica"] = compared.apply(_has_critical_difference, axis=1)
    return compared


def build_supervisor_validation_summary(compared: pd.DataFrame) -> pd.DataFrame:
    """Resume a validacao com contagens pedidas no diagnostico."""

    comparable = compared[compared["Comparavel"]].copy()
    total_comparable = len(comparable)
    strict_ok = int(comparable["StatusAtingimentoTotal"].eq("OK").sum())
    equivalent_ok = int(comparable["StatusAtingimentoTotal"].isin(["OK", "OK_EQUIVALENTE_ZERO"]).sum())
    status_ok = int(comparable["StatusPerformanceOK"].sum())
    rows = [
        {"Metrica": "linhas_gabarito", "Valor": int(compared["_merge"].ne("left_only").sum())},
        {"Metrica": "linhas_pipeline", "Valor": int(compared["_merge"].ne("right_only").sum())},
        {"Metrica": "chaves_comparaveis", "Valor": total_comparable},
        {"Metrica": "chaves_excecao_centro_erro_excel", "Valor": int(compared["ExcecaoCentroErroExcel"].sum())},
        {"Metrica": "atingimento_total_ok_estrito", "Valor": strict_ok},
        {"Metrica": "atingimento_total_ok_equivalente", "Valor": equivalent_ok},
        {"Metrica": "status_performance_ok", "Valor": status_ok},
        {"Metrica": "divergencias_criticas_restantes", "Valor": int(compared["DivergenciaCritica"].sum())},
    ]
    if total_comparable:
        rows.extend(
            [
                {"Metrica": "atingimento_total_pct_ok_estrito", "Valor": strict_ok / total_comparable},
                {"Metrica": "atingimento_total_pct_ok_equivalente", "Valor": equivalent_ok / total_comparable},
                {"Metrica": "status_performance_pct_ok", "Valor": status_ok / total_comparable},
            ]
        )
    return pd.DataFrame(rows)


def filter_critical_differences(compared: pd.DataFrame) -> pd.DataFrame:
    """Retorna apenas divergencias criticas, preservando equivalencias diagnosticadas."""

    return compared[compared["DivergenciaCritica"]].reset_index(drop=True)


def _column(raw: pd.DataFrame, position: int) -> pd.Series:
    if raw.shape[1] <= position:
        return pd.Series(pd.NA, index=raw.index)
    return raw.iloc[:, position]


def _comparison_key(centro: object, supervisao: object, centro_error: object = False) -> str | None:
    supervisao_text = clean_text(supervisao)
    if not supervisao_text:
        return None
    if bool(centro_error):
        return f"ERRO_CENTRO::{supervisao_text}"
    centro_text = clean_text(centro)
    if not centro_text:
        return f"ERRO_CENTRO::{supervisao_text}"
    return f"{centro_text}{supervisao_text}"


def _to_nullable_number(value: object) -> float | None:
    if _is_null_like(value):
        return None
    return to_number(value)


def _is_null_like(value: object) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip()
    if text == "":
        return True
    return text.upper() in {"-", "NONE", "NAN", "NULL"} or _is_excel_error(text)


def _is_excel_error(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().upper()
    return text.startswith("#N/") or text in {
        "#N/A",
        "#N/D",
        "#DIV/0!",
        "#VALUE!",
        "#REF!",
        "#NAME?",
        "#NULL!",
        "#NUM!",
    }


def _normalize_text(value: object) -> str | None:
    text = clean_text(value)
    return text


def _add_numeric_comparison(
    dataframe: pd.DataFrame,
    pipeline_column: str,
    gabarito_column: str,
    output_name: str,
    tolerance: float,
    zero_equivalent: bool,
) -> None:
    left = dataframe[pipeline_column].map(_to_nullable_number) if pipeline_column in dataframe.columns else pd.Series(None, index=dataframe.index)
    right = dataframe[gabarito_column].map(_to_nullable_number) if gabarito_column in dataframe.columns else pd.Series(None, index=dataframe.index)
    dataframe[f"{output_name}PipelineNormalizado"] = left
    dataframe[f"{output_name}GabaritoNormalizado"] = right
    dataframe[f"Dif{output_name}"] = left - right
    dataframe[f"Status{output_name}"] = [
        _classify_numeric(left_value, right_value, tolerance, zero_equivalent)
        for left_value, right_value in zip(left, right, strict=False)
    ]


def _classify_numeric(left: object, right: object, tolerance: float, zero_equivalent: bool) -> str:
    left_missing = pd.isna(left)
    right_missing = pd.isna(right)
    if left_missing and right_missing:
        return "OK"
    if zero_equivalent and left_missing and _is_effective_zero(right, tolerance):
        return "OK_EQUIVALENTE_ZERO"
    if zero_equivalent and right_missing and _is_effective_zero(left, tolerance):
        return "OK_EQUIVALENTE_ZERO"
    if left_missing or right_missing:
        return "DIVERGENTE_NULO_NUMERO"
    return "OK" if abs(float(left) - float(right)) <= tolerance else "DIVERGENTE"


def _is_effective_zero(value: object, tolerance: float) -> bool:
    if pd.isna(value):
        return False
    return abs(float(value)) <= tolerance


def _is_center_error_exception(row: pd.Series) -> bool:
    return (
        row.get("ChaveSupervisorComparacao") is not None
        and str(row.get("ChaveSupervisorComparacao")).startswith("ERRO_CENTRO::")
    )


def _classify_key_status(row: pd.Series) -> str:
    if row.get("ExcecaoCentroErroExcel"):
        return "Nao comparavel por erro Excel no centro"
    if row.get("_merge") == "both":
        return "Comparavel"
    if row.get("_merge") == "left_only":
        return "So na pipeline"
    return "So no gabarito"


def _has_critical_difference(row: pd.Series) -> bool:
    if not bool(row.get("Comparavel")):
        return False
    if not bool(row.get("StatusPerformanceOK")):
        return True
    fields = ["AtingimentoTotal", "EscalaAtingida"]
    fields.extend(f"Performance{kpi}" for kpi in KPI_COLUMNS)
    fields.extend(f"Atingimento{kpi}" for kpi in KPI_COLUMNS)
    for field in fields:
        if row.get(f"Status{field}") not in {"OK", "OK_EQUIVALENTE_ZERO"}:
            return True
    return False
