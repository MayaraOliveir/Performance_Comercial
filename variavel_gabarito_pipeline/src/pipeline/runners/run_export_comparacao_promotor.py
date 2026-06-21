"""Exporta workbook de comparacao visual do Promotor de Vendas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv


OUTPUT_FILE = "comparacao_promotor_vendas.xlsx"
DECIMAL_FORMAT = "0.000000"

BASE_PROMOTOR_COLUMNS = [
    "Centro",
    "Rota",
    "ChaveCentroRota",
    "TipoRota",
    "FonteEstrutura",
    "MetaRED",
    "FonteMetaRED",
    "RealizadoRED",
    "FonteRealizadoRED",
    "MetaRPT",
    "RealizadoRPT",
    "FonteRealizadoRPT",
    "UF",
    "Gerencia",
    "Supervisor",
    "UnidadeOriginal",
    "MetaREDEstruturaOriginal",
    "RealizadoREDEstruturaOriginal",
    "MetaRPTEstruturaOriginal",
    "RealizadoRPTEstruturaOriginal",
]

RESULTADO_PROMOTOR_COLUMNS = [
    "Centro",
    "Rota",
    "TipoRota",
    "FonteEstrutura",
    "AderenciaRED",
    "StatusAderenciaRED",
    "MetaRED",
    "RealizadoRED",
    "PerformanceRED",
    "PesoRED",
    "AtingimentoRED",
    "MetaRPT",
    "RealizadoRPT",
    "FonteRealizadoRPT",
    "StatusRPT",
    "PerformanceRPT",
    "PesoRPT",
    "AtingimentoRPT",
    "AtingimentoTotal",
    "EscalaAtingida",
    "StatusPerformance",
    "Diagnostico",
]

EXECUTIVE_ORDER = [
    "OK",
    "Diferença por ausência de fonte RealizadoRPT",
    "Diferença por meta não localizada na fonte oficial",
    "Diferença por MetaRPT ausente na fonte oficial",
    "total_diferencas",
    "total_geral",
]

DECIMAL_KEYWORDS = (
    "Meta",
    "Realizado",
    "Aderencia",
    "Performance",
    "Peso",
    "Atingimento",
    "Escala",
    "Dif",
    "Media",
    "Maior",
)

STATUS_COMPARACAO_COLORS = {
    "OK": "#C6EFCE",
    "Diferente": "#FFC7CE",
}

TIPO_DIFERENCA_COLORS = {
    "Diferença por ausência de fonte RealizadoRPT": "#FFEB9C",
    "Diferença por meta não localizada na fonte oficial": "#F4B183",
    "Diferença por MetaRPT ausente na fonte oficial": "#BDD7EE",
}

FONTE_RPT_COLORS = {
    "fonte_rpt_nao_encontrada": "#FFEB9C",
}

FONTE_ESTRUTURA_COLORS = {
    "gabarito_fallback": "#D9E1F2",
    "estrutura_mensal": "#C6EFCE",
}


def run() -> Path:
    """Gera data/output/comparacao_promotor_vendas.xlsx."""

    logger = configure_logger("pipeline.export_comparacao_promotor")
    paths_config = load_paths_config()
    processed = paths_config.values["processed"]
    validation_dir = processed["validation"]
    facts_dir = processed["facts"]
    output_path = paths_config.values["data"]["output"] / OUTPUT_FILE

    resumo_explicado = read_csv(validation_dir / "resumo_diferencas_promotor_explicado.csv")
    resumo_tipo = read_csv(validation_dir / "resumo_tipo_diferenca.csv")
    validacao = read_csv(validation_dir / "validacao_promotor_gabarito.csv")
    base_promotor = _prepare_base_promotor(read_csv(facts_dir / "fat_promotor_base.csv"))
    resultado_promotor = _prepare_resultado_promotor(
        read_csv(facts_dir / "fat_promotor_final.csv"),
        base_promotor,
    )
    diagnostico_8 = read_csv(validation_dir / "diagnostico_8_diferencas_promotor.csv")
    diagnostico_7 = read_csv(validation_dir / "diagnostico_7_rotas_sem_meta_promotor.csv")
    diagnostico_fssapa186 = read_csv(validation_dir / "diagnostico_fssapa186.csv")
    resumo_fonte_rpt = read_csv(validation_dir / "resumo_fonte_rpt_promotor.csv")
    resumo_base = read_csv(validation_dir / "resumo_promotor_base.csv")
    resumo_estrutura = read_csv(validation_dir / "resumo_estrutura_promotor.csv")

    sheets = {
        "RESUMO_EXECUTIVO": _order_executive_summary(resumo_explicado),
        "VALIDACAO_COMPLETA": validacao,
        "DIFERENCAS_281": validacao[validacao["StatusComparacao"] != "OK"].copy(),
        "DIFERENCAS_EXPLICADAS": _combine_explained_summaries(resumo_explicado, resumo_tipo),
        "BASE_PROMOTOR": _select_columns(base_promotor, BASE_PROMOTOR_COLUMNS),
        "RESULTADO_PROMOTOR": _select_columns(resultado_promotor, RESULTADO_PROMOTOR_COLUMNS),
        "AUSENCIA_RPT": resultado_promotor[
            resultado_promotor["FonteRealizadoRPT"].eq("fonte_rpt_nao_encontrada")
            | resultado_promotor["Diagnostico"].fillna("").str.contains("Sem fonte RealizadoRPT", regex=False)
        ].copy(),
        "META_NAO_LOCALIZADA": diagnostico_7,
        "FSSAPA186": diagnostico_fssapa186,
        "RESUMOS_TECNICOS": _combine_technical_summaries(
            resumo_fonte_rpt,
            resumo_base,
            resumo_estrutura,
        ),
    }

    output = write_comparison_workbook(sheets, output_path)
    logger.info("excel_comparacao_promotor_exportado", extra={"arquivo_saida": str(output)})

    print(f"Arquivo gerado: {output}")
    for sheet_name, dataframe in sheets.items():
        print(f"{sheet_name}: {len(dataframe)} linhas")
    print(f"Arquivo criado com sucesso: {output.exists()}")
    return output


def write_comparison_workbook(sheets: dict[str, pd.DataFrame], output_path: Path) -> Path:
    """Escreve workbook formatado para conferencia visual."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        formats = _build_formats(workbook)

        for sheet_name, dataframe in sheets.items():
            safe_name = sheet_name[:31]
            work = dataframe.copy().replace({pd.NA: None}).fillna("-")
            work.to_excel(writer, sheet_name=safe_name, index=False)
            worksheet = writer.sheets[safe_name]
            _format_sheet(worksheet, work, formats)

    return output_path


def _build_formats(workbook) -> dict[str, object]:
    return {
        "header": workbook.add_format(
            {"bold": True, "bg_color": "#1F4E78", "font_color": "#FFFFFF", "border": 1}
        ),
        "decimal": workbook.add_format({"num_format": DECIMAL_FORMAT}),
        "ok": workbook.add_format({"bg_color": STATUS_COMPARACAO_COLORS["OK"]}),
        "diferente": workbook.add_format({"bg_color": STATUS_COMPARACAO_COLORS["Diferente"]}),
        "rpt_missing": workbook.add_format({"bg_color": "#FFEB9C"}),
        "meta_missing": workbook.add_format({"bg_color": "#F4B183"}),
        "metarpt_missing": workbook.add_format({"bg_color": "#BDD7EE"}),
        "fallback": workbook.add_format({"bg_color": "#D9E1F2"}),
        "monthly": workbook.add_format({"bg_color": "#C6EFCE"}),
    }


def _format_sheet(worksheet, dataframe: pd.DataFrame, formats: dict[str, object]) -> None:
    max_row, max_col = dataframe.shape
    if max_col == 0:
        return

    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max_row, max_col - 1)

    for column_index, column_name in enumerate(dataframe.columns):
        worksheet.write(0, column_index, column_name, formats["header"])
        width = _column_width(dataframe[column_name], column_name)
        column_format = formats["decimal"] if _is_decimal_column(column_name) else None
        worksheet.set_column(column_index, column_index, width, column_format)

    _apply_text_colors(worksheet, dataframe, "StatusComparacao", {"OK": "ok", "Diferente": "diferente"}, formats)
    _apply_text_colors(
        worksheet,
        dataframe,
        "TipoDiferenca",
        {
            "Diferença por ausência de fonte RealizadoRPT": "rpt_missing",
            "Diferença por meta não localizada na fonte oficial": "meta_missing",
            "Diferença por MetaRPT ausente na fonte oficial": "metarpt_missing",
        },
        formats,
    )
    _apply_text_colors(
        worksheet,
        dataframe,
        "FonteRealizadoRPT",
        {"fonte_rpt_nao_encontrada": "rpt_missing"},
        formats,
    )
    _apply_text_colors(
        worksheet,
        dataframe,
        "FonteEstrutura",
        {"gabarito_fallback": "fallback", "estrutura_mensal": "monthly"},
        formats,
    )


def _apply_text_colors(
    worksheet,
    dataframe: pd.DataFrame,
    column_name: str,
    mapping: dict[str, str],
    formats: dict[str, object],
) -> None:
    if column_name not in dataframe.columns:
        return
    max_row = len(dataframe)
    column_index = dataframe.columns.get_loc(column_name)
    for value, format_key in mapping.items():
        worksheet.conditional_format(
            1,
            column_index,
            max_row,
            column_index,
            {"type": "text", "criteria": "containing", "value": value, "format": formats[format_key]},
        )


def _prepare_base_promotor(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    if "FonteMetaRED" not in result.columns:
        result["FonteMetaRED"] = result["MetaRED"].map(
            lambda value: "metas" if not pd.isna(value) else "fonte_meta_red_nao_encontrada"
        )
    return result


def _prepare_resultado_promotor(final: pd.DataFrame, base_promotor: pd.DataFrame) -> pd.DataFrame:
    result = final.copy()
    if "FonteEstrutura" not in result.columns and "FonteEstrutura" in base_promotor.columns:
        result = result.merge(
            base_promotor[["ChaveCentroRota", "FonteEstrutura"]].drop_duplicates("ChaveCentroRota"),
            on="ChaveCentroRota",
            how="left",
        )
    return result


def _order_executive_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    result["_ordem"] = result["Categoria"].map({value: index for index, value in enumerate(EXECUTIVE_ORDER)})
    result = result[result["Categoria"].isin(EXECUTIVE_ORDER)].sort_values("_ordem")
    return result.drop(columns=["_ordem"])


def _combine_explained_summaries(resumo_explicado: pd.DataFrame, resumo_tipo: pd.DataFrame) -> pd.DataFrame:
    resumo_a = resumo_explicado.copy()
    resumo_a.insert(0, "FonteResumo", "resumo_diferencas_promotor_explicado")
    resumo_b = resumo_tipo.copy()
    resumo_b.insert(0, "FonteResumo", "resumo_tipo_diferenca")
    return pd.concat([resumo_a, resumo_b], ignore_index=True, sort=False)


def _combine_technical_summaries(
    resumo_fonte_rpt: pd.DataFrame,
    resumo_base: pd.DataFrame,
    resumo_estrutura: pd.DataFrame,
) -> pd.DataFrame:
    frames = []
    for name, dataframe in [
        ("resumo_fonte_rpt_promotor", resumo_fonte_rpt),
        ("resumo_promotor_base", resumo_base),
        ("resumo_estrutura_promotor", resumo_estrutura),
    ]:
        work = dataframe.copy()
        work.insert(0, "FonteResumo", name)
        frames.append(work)
    return pd.concat(frames, ignore_index=True, sort=False)


def _select_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return dataframe[[column for column in columns if column in dataframe.columns]].copy()


def _is_decimal_column(column_name: str) -> bool:
    return any(keyword in column_name for keyword in DECIMAL_KEYWORDS)


def _column_width(series: pd.Series, column_name: str) -> int:
    values = series.fillna("-").astype(str)
    max_length = int(values.map(len).max()) if not values.empty else 0
    return min(max(max_length, len(column_name)) + 2, 70)


def main() -> None:
    run()


if __name__ == "__main__":
    main()
