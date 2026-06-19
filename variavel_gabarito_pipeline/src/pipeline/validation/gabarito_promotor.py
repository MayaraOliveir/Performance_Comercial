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

    result = pd.DataFrame(
        {
            "Rota": raw.iloc[:, ROTA_POSITION].map(clean_text),
            "Centro": raw.iloc[:, CENTRO_POSITION].map(clean_text),
            "StatusGabarito": raw.iloc[:, STATUS_POSITION].map(clean_text),
            "AtingimentoTotalGabaritoOriginal": raw.iloc[:, ATINGIMENTO_TOTAL_POSITION],
            "EscalaAtingidaGabaritoOriginal": raw.iloc[:, ESCALA_ATINGIDA_POSITION],
        }
    )
    result["ChaveCentroRota"] = [
        create_chave_centro_rota(centro, rota)
        for centro, rota in zip(result["Centro"], result["Rota"], strict=False)
    ]
    result["AtingimentoTotalGabarito"] = result["AtingimentoTotalGabaritoOriginal"].map(to_number)
    result["EscalaAtingidaGabarito"] = result["EscalaAtingidaGabaritoOriginal"].map(to_number)
    result["StatusValorGabarito"] = result["AtingimentoTotalGabaritoOriginal"].map(status_valor_gabarito)

    result = result.dropna(subset=["ChaveCentroRota"])
    result = result[(result["Centro"] != "UNIDADE") & (result["Rota"] != "ROTA")]
    return result.drop_duplicates(subset=["ChaveCentroRota"]).reset_index(drop=True)


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
