"""Leitura e padronizacao do gabarito de Promotor de Vendas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.utils import list_excel_files
from pipeline.staging.common import clean_text, create_chave_centro_rota, to_number


SHEET_NAME = "PROMOTOR DE VENDAS"
ROTA_POSITION = 4
CENTRO_POSITION = 5
STATUS_POSITION = 9
ATINGIMENTO_TOTAL_POSITION = 11
ESCALA_ATINGIDA_POSITION = 13
UF_POSITION = 1
GERENCIA_POSITION = 2
SUPERVISOR_POSITION = 3
ADERENCIA_RED_POSITION = 15
META_RED_POSITION = 16
REALIZADO_RED_POSITION = 17
PERFORMANCE_RED_POSITION = 18
PESO_RED_POSITION = 19
ATINGIMENTO_RED_POSITION = 20
META_RPT_POSITION = 22
REALIZADO_RPT_POSITION = 23
PERFORMANCE_RPT_POSITION = 24
PESO_RPT_POSITION = 25
ATINGIMENTO_RPT_POSITION = 26


def first_gabarito_file(raw_gabarito_dir: str | Path) -> Path:
    """Retorna o primeiro Excel encontrado na pasta de gabarito."""

    files = list_excel_files(raw_gabarito_dir)
    if not files:
        raise FileNotFoundError(f"Nenhum Excel encontrado em {raw_gabarito_dir}")
    return files[0]


def read_gabarito_promotor(file_path: str | Path) -> pd.DataFrame:
    """Le a aba de Promotor por posicao de colunas."""

    raw = pd.read_excel(file_path, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    return transform_gabarito_promotor(raw)


def transform_gabarito_promotor(raw: pd.DataFrame) -> pd.DataFrame:
    """Padroniza o gabarito oficial para comparacao com o Python."""

    unidade_original = _column(raw, CENTRO_POSITION)
    result = pd.DataFrame(
        {
            "UF": _column(raw, UF_POSITION).map(clean_text),
            "Gerencia": _column(raw, GERENCIA_POSITION).map(clean_text),
            "Supervisor": _column(raw, SUPERVISOR_POSITION).map(clean_text),
            "Rota": _column(raw, ROTA_POSITION).map(clean_text),
            "UnidadeOriginal": unidade_original,
            # manter compatibilidade: `Unidade` como cópia do original (preserva valor textual)
            "Unidade": unidade_original,
            "Centro": unidade_original.map(clean_text),
            "StatusGabarito": _column(raw, STATUS_POSITION).map(clean_text),
            "StatusPerformanceGabarito": _column(raw, STATUS_POSITION).map(clean_text),
            "AtingimentoTotalGabaritoOriginal": _column(raw, ATINGIMENTO_TOTAL_POSITION),
            "EscalaAtingidaGabaritoOriginal": _column(raw, ESCALA_ATINGIDA_POSITION),
            "AderenciaREDGabaritoOriginal": _column(raw, ADERENCIA_RED_POSITION),
            "MetaREDGabaritoOriginal": _column(raw, META_RED_POSITION),
            "RealizadoREDGabaritoOriginal": _column(raw, REALIZADO_RED_POSITION),
            "PerformanceREDGabaritoOriginal": _column(raw, PERFORMANCE_RED_POSITION),
            "PesoREDGabaritoOriginal": _column(raw, PESO_RED_POSITION),
            "AtingimentoREDGabaritoOriginal": _column(raw, ATINGIMENTO_RED_POSITION),
            "MetaRPTGabaritoOriginal": _column(raw, META_RPT_POSITION),
            "RealizadoRPTGabaritoOriginal": _column(raw, REALIZADO_RPT_POSITION),
            "PerformanceRPTGabaritoOriginal": _column(raw, PERFORMANCE_RPT_POSITION),
            "PesoRPTGabaritoOriginal": _column(raw, PESO_RPT_POSITION),
            "AtingimentoRPTGabaritoOriginal": _column(raw, ATINGIMENTO_RPT_POSITION),
        }
    )
    result["ChaveCentroRota"] = [
        create_chave_centro_rota(centro, rota)
        for centro, rota in zip(result["Centro"], result["Rota"], strict=False)
    ]
    result["AtingimentoTotalGabarito"] = result["AtingimentoTotalGabaritoOriginal"].map(to_number)
    result["EscalaAtingidaGabarito"] = result["EscalaAtingidaGabaritoOriginal"].map(to_number)
    result["AderenciaREDGabarito"] = result["AderenciaREDGabaritoOriginal"].map(to_number)
    result["MetaREDGabarito"] = result["MetaREDGabaritoOriginal"].map(to_number)
    result["RealizadoREDGabarito"] = result["RealizadoREDGabaritoOriginal"].map(to_number)
    result["PerformanceREDGabarito"] = result["PerformanceREDGabaritoOriginal"].map(to_number)
    result["PesoREDGabarito"] = result["PesoREDGabaritoOriginal"].map(to_number)
    result["AtingimentoREDGabarito"] = result["AtingimentoREDGabaritoOriginal"].map(to_number)
    result["MetaRPTGabarito"] = result["MetaRPTGabaritoOriginal"].map(to_number)
    result["RealizadoRPTGabarito"] = result["RealizadoRPTGabaritoOriginal"].map(to_number)
    result["PerformanceRPTGabarito"] = result["PerformanceRPTGabaritoOriginal"].map(to_number)
    result["PesoRPTGabarito"] = result["PesoRPTGabaritoOriginal"].map(to_number)
    result["AtingimentoRPTGabarito"] = result["AtingimentoRPTGabaritoOriginal"].map(to_number)
    result["StatusValorGabarito"] = result["AtingimentoTotalGabaritoOriginal"].map(status_valor_gabarito)

    result = result.dropna(subset=["ChaveCentroRota"])
    result = result[(result["Centro"] != "UNIDADE") & (result["Rota"] != "ROTA")]
    return result.drop_duplicates(subset=["ChaveCentroRota"]).reset_index(drop=True)


def _column(raw: pd.DataFrame, position: int) -> pd.Series:
    """Retorna coluna por posicao ou uma serie nula quando ausente."""

    if raw.shape[1] <= position:
        return pd.Series(pd.NA, index=raw.index)
    return raw.iloc[:, position]


def status_valor_gabarito(value: object) -> str:
    """Classifica se o gabarito possui calculo numerico de atingimento."""

    if is_blank_gabarito_value(value):
        return "Sem cálculo no gabarito"
    if to_number(value) is not None:
        return "Calculado no gabarito"
    return "Gabarito sem atingimento"


def is_blank_gabarito_value(value: object) -> bool:
    """Identifica '-', vazio, null textual e nulos."""

    if pd.isna(value):
        return True
    text = str(value).strip()
    return text == "" or text == "-" or text.upper() == "NULL"
