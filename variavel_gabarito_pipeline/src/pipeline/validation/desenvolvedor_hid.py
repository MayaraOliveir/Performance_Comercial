"""Validacao da figura Desenvolvedor HID contra o gabarito."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.staging.common import clean_text, to_number


SHEET_NAME = "DESENVOLVEDOR HID"
KPI_COLUMNS = {
    "VMS": {"meta": 15, "real": 16, "performance": 17, "peso": 18, "atingimento": 19},
    "CCH": {"meta": 21, "real": 22, "performance": 23, "peso": 24, "atingimento": 25},
    "CGD": {"meta": 27, "real": 28, "performance": 29, "peso": 30, "atingimento": 31},
    "CPW": {"meta": 33, "real": 34, "performance": 35, "peso": 36, "atingimento": 37},
}


def read_gabarito_desenvolvedor_hid(file_path: str | Path) -> pd.DataFrame:
    """Le a aba final de Desenvolvedor HID por posicao de colunas."""

    raw = pd.read_excel(file_path, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    result = pd.DataFrame(
        {
            "UF": _column(raw, 1).map(clean_text),
            "Gerencia": _column(raw, 2).map(clean_text),
            "Supervisor": _column(raw, 3).map(clean_text),
            "Rota": _column(raw, 4).map(clean_text),
            "Centro": _column(raw, 5).map(clean_text),
            "StatusPerformanceGabarito": _column(raw, 9).map(_normalize_text),
            "AtingimentoTotalGabarito": _column(raw, 11).map(_to_nullable_number),
            "EscalaAtingidaGabarito": _column(raw, 13).map(_to_nullable_number),
        }
    )
    result["ChaveCentroRota"] = result["Centro"].fillna("") + result["Rota"].fillna("")
    for kpi, positions in KPI_COLUMNS.items():
        result[f"Real{kpi}Gabarito"] = _column(raw, positions["real"]).map(_to_nullable_number)
        result[f"Peso{kpi}Gabarito"] = _column(raw, positions["peso"]).map(_to_nullable_number)
        result[f"Atingimento{kpi}Gabarito"] = _column(raw, positions["atingimento"]).map(_to_nullable_number)

    result = result[result["Centro"].notna() & result["Rota"].notna()].copy()
    result = result[result["StatusPerformanceGabarito"].notna()].copy()
    result = result[result["StatusPerformanceGabarito"] != "STATUS DA PERFORMANCE"].copy()
    return result.drop_duplicates("ChaveCentroRota").reset_index(drop=True)


def compare_desenvolvedor_hid_outputs(pipeline_result: pd.DataFrame, gabarito: pd.DataFrame) -> pd.DataFrame:
    """Compara a saida HID contra o gabarito."""

    left = pipeline_result.copy()
    left["StatusPerformanceNormalizado"] = left["StatusPerformance"].map(_normalize_text)
    compared = left.merge(gabarito, on="ChaveCentroRota", how="outer", suffixes=("", "Gabarito"), indicator=True)
    compared["StatusChave"] = compared["_merge"].map(
        {"both": "Comparavel", "left_only": "So na pipeline", "right_only": "So no gabarito"}
    )
    compared["Comparavel"] = compared["_merge"].eq("both")

    _add_numeric_comparison(compared, "AtingimentoTotal", "AtingimentoTotalGabarito", "AtingimentoTotal", 0.0001)
    _add_numeric_comparison(compared, "EscalaAtingida", "EscalaAtingidaGabarito", "EscalaAtingida", 0.0001)
    for kpi in KPI_COLUMNS:
        _add_numeric_comparison(compared, f"{kpi} Real", f"Real{kpi}Gabarito", f"Real{kpi}", 0.01)
        _add_numeric_comparison(compared, f"{kpi} Peso", f"Peso{kpi}Gabarito", f"Peso{kpi}", 0.0001)
        _add_numeric_comparison(compared, f"{kpi} Ating. Fin.", f"Atingimento{kpi}Gabarito", f"Atingimento{kpi}", 0.0001)

    compared["StatusPerformanceOK"] = (
        compared["StatusPerformanceNormalizado"].eq(compared["StatusPerformanceGabarito"])
        & compared["Comparavel"]
    )
    compared["DivergenciaCritica"] = compared.apply(_has_critical_difference, axis=1)
    return compared


def build_desenvolvedor_hid_validation_summary(compared: pd.DataFrame) -> pd.DataFrame:
    """Gera resumo da validacao HID."""

    comparable = compared[compared["Comparavel"]].copy()
    rows = [
        {"Metrica": "linhas_gabarito", "Valor": int(compared["_merge"].ne("left_only").sum())},
        {"Metrica": "linhas_pipeline", "Valor": int(compared["_merge"].ne("right_only").sum())},
        {"Metrica": "chaves_comparaveis", "Valor": len(comparable)},
        {"Metrica": "chaves_faltantes", "Valor": int(compared["_merge"].eq("right_only").sum())},
        {"Metrica": "chaves_extras", "Valor": int(compared["_merge"].eq("left_only").sum())},
        {"Metrica": "vms_real_ok", "Valor": int(comparable["StatusRealVMS"].eq("OK").sum())},
        {"Metrica": "atingimento_total_ok", "Valor": int(comparable["StatusAtingimentoTotal"].eq("OK").sum())},
        {"Metrica": "status_performance_ok", "Valor": int(comparable["StatusPerformanceOK"].sum())},
        {"Metrica": "divergencias_criticas", "Valor": int(compared["DivergenciaCritica"].sum())},
    ]
    for kpi in KPI_COLUMNS:
        rows.append({"Metrica": "peso_ok", "Valor": int(comparable[f"StatusPeso{kpi}"].eq("OK").sum()), "Categoria": kpi})
    return pd.DataFrame(rows)


def filter_critical_differences(compared: pd.DataFrame) -> pd.DataFrame:
    """Retorna divergencias criticas da validacao HID."""

    return compared[compared["DivergenciaCritica"]].reset_index(drop=True)


def _column(raw: pd.DataFrame, position: int) -> pd.Series:
    if raw.shape[1] <= position:
        return pd.Series(pd.NA, index=raw.index)
    return raw.iloc[:, position]


def _to_nullable_number(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.upper() in {"-", "NONE", "NAN", "NULL"}:
        return None
    return to_number(value)


def _normalize_text(value: object) -> str | None:
    return clean_text(value)


def _add_numeric_comparison(
    dataframe: pd.DataFrame,
    pipeline_column: str,
    gabarito_column: str,
    output_name: str,
    tolerance: float,
) -> None:
    left = dataframe[pipeline_column].map(_to_nullable_number) if pipeline_column in dataframe.columns else pd.Series(None, index=dataframe.index)
    right = dataframe[gabarito_column].map(_to_nullable_number) if gabarito_column in dataframe.columns else pd.Series(None, index=dataframe.index)
    dataframe[f"{output_name}PipelineNormalizado"] = left
    dataframe[f"{output_name}GabaritoNormalizado"] = right
    dataframe[f"Dif{output_name}"] = left - right
    dataframe[f"Status{output_name}"] = [
        _classify_numeric(left_value, right_value, tolerance)
        for left_value, right_value in zip(left, right, strict=False)
    ]


def _classify_numeric(left: object, right: object, tolerance: float) -> str:
    left_missing = pd.isna(left)
    right_missing = pd.isna(right)
    if left_missing and right_missing:
        return "OK"
    if left_missing or right_missing:
        return "DIVERGENTE_NULO_NUMERO"
    return "OK" if abs(float(left) - float(right)) <= tolerance else "DIVERGENTE"


def _has_critical_difference(row: pd.Series) -> bool:
    if not bool(row.get("Comparavel")):
        return False
    if not bool(row.get("StatusPerformanceOK")):
        return True
    fields = ["AtingimentoTotal", "EscalaAtingida", "RealVMS"]
    fields.extend(f"Peso{kpi}" for kpi in KPI_COLUMNS)
    for field in fields:
        if row.get(f"Status{field}") != "OK":
            return True
    return False
