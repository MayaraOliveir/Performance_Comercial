"""Exporta Promotor de Vendas no formato visual do gabarito oficial."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv


OUTPUT_FILE = "promotor_vendas_formato_gabarito.xlsx"
MAIN_SHEET = "PROMOTOR DE VENDAS"
DECIMAL_FORMAT = "0.000000"

MAIN_COLUMNS = [
    "UF",
    "Gerência",
    "Supervisor",
    "Rota",
    "Unidade",
    "Status da Performance",
    "Ating. Total",
    "Escala atingida",
    "Aderência RED",
    "Meta",
    "Real",
    "Perf.%",
    "Peso",
    "Ating. Fin.",
    "Meta",
    "Real",
    "Perf.%",
    "Peso",
    "Ating. Fin.",
]

NUMERIC_COLUMNS = {
    "Ating. Total",
    "Escala atingida",
    "Aderência RED",
    "Meta",
    "Real",
    "Perf.%",
    "Peso",
    "Ating. Fin.",
}

STATUS_PERFORMANCE_COLORS = {
    "Irregular": "#FFC7CE",
    "Regular": "#FFEB9C",
    "Em linha": "#C6EFCE",
    "Alta": "#BDD7EE",
}

STATUS_COMPARACAO_COLORS = {
    "OK": "#C6EFCE",
    "Diferente": "#FFC7CE",
}


def run() -> Path:
    """Gera data/output/promotor_vendas_formato_gabarito.xlsx."""

    logger = configure_logger("pipeline.export_promotor_formato_gabarito")
    paths_config = load_paths_config()
    processed = paths_config.values["processed"]
    facts_dir = processed["facts"]
    staging_dir = processed["staging"]
    validation_dir = processed["validation"]
    output_path = paths_config.values["data"]["output"] / OUTPUT_FILE

    final = read_csv(facts_dir / "fat_promotor_final.csv")
    base = read_csv(facts_dir / "fat_promotor_base.csv")
    estrutura = read_csv(staging_dir / "stg_estrutura_promotor.csv")
    validacao = read_csv(validation_dir / "validacao_promotor_gabarito.csv")
    resumo_explicado = read_csv(validation_dir / "resumo_diferencas_promotor_explicado.csv")

    principal = build_promotor_gabarito_sheet(final, base, estrutura)
    diferencas = validacao[validacao["StatusComparacao"] != "OK"].copy()
    auditoria_rpt = final[
        final.get("FonteRealizadoRPT", pd.Series(index=final.index)).eq("fonte_rpt_nao_encontrada")
        | final["Diagnostico"].fillna("").str.contains("Sem fonte RealizadoRPT", regex=False)
    ].copy()

    sheets = {
        MAIN_SHEET: principal,
        "COMPARACAO": validacao,
        "DIFERENCAS": diferencas,
        "RESUMO_EXPLICADO": resumo_explicado,
        "BASE_PROMOTOR": base,
        "AUDITORIA_RPT": auditoria_rpt,
    }

    output = write_workbook(sheets, output_path)
    logger.info("promotor_formato_gabarito_exportado", extra={"arquivo_saida": str(output)})

    print(f"Arquivo gerado: {output}")
    print(f"PROMOTOR DE VENDAS: {len(principal)} linhas")
    print(f"DIFERENCAS: {len(diferencas)} linhas")
    print(f"Arquivo criado com sucesso: {output.exists()}")
    return output


def build_promotor_gabarito_sheet(
    final: pd.DataFrame,
    base: pd.DataFrame,
    estrutura: pd.DataFrame,
) -> pd.DataFrame:
    """Monta a aba principal na ordem visual do gabarito."""

    cadastro = _build_cadastro(base, estrutura)
    data = final.merge(cadastro, on="ChaveCentroRota", how="left", suffixes=("", "Cadastro"))

    output = pd.DataFrame()
    output["UF"] = _first_available(data, ["UF", "UFCadastro"])
    output["Gerência"] = _first_available(data, ["Gerência", "Gerencia", "GerenciaCadastro"])
    output["Supervisor"] = _first_available(data, ["Supervisor", "SupervisorCadastro"])
    output["Rota"] = data["Rota"]
    output["Unidade"] = data["Centro"]
    output["Status da Performance"] = data["StatusPerformance"]
    output["Ating. Total"] = data["AtingimentoTotal"]
    output["Escala atingida"] = data["EscalaAtingida"]
    output["Aderência RED"] = data["AderenciaRED"]

    red = data[["MetaRED", "RealizadoRED", "PerformanceRED", "PesoRED", "AtingimentoRED"]].copy()
    red.columns = ["Meta", "Real", "Perf.%", "Peso", "Ating. Fin."]
    rpt = data[["MetaRPT", "RealizadoRPT", "PerformanceRPT", "PesoRPT", "AtingimentoRPT"]].copy()
    rpt.columns = ["Meta", "Real", "Perf.%", "Peso", "Ating. Fin."]

    return pd.concat([output, red, rpt], axis=1)


def write_workbook(sheets: dict[str, pd.DataFrame], output_path: Path) -> Path:
    """Escreve workbook com filtros, formatos e cores."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        formats = _build_formats(workbook)

        for sheet_name, dataframe in sheets.items():
            safe_name = sheet_name[:31]
            work = dataframe.copy().replace({pd.NA: None}).fillna("-")
            startrow = 1 if sheet_name == MAIN_SHEET else 0
            work.to_excel(writer, sheet_name=safe_name, index=False, startrow=startrow)
            worksheet = writer.sheets[safe_name]
            if sheet_name == MAIN_SHEET:
                _write_grouped_header(worksheet, formats, len(work.columns))
            _format_sheet(worksheet, work, formats, header_row=startrow)

    return output_path


def _build_formats(workbook) -> dict[str, object]:
    return {
        "group": workbook.add_format(
            {"bold": True, "align": "center", "bg_color": "#D9EAF7", "border": 1}
        ),
        "header": workbook.add_format(
            {"bold": True, "bg_color": "#1F4E78", "font_color": "#FFFFFF", "border": 1}
        ),
        "decimal": workbook.add_format({"num_format": DECIMAL_FORMAT}),
        "irregular": workbook.add_format({"bg_color": STATUS_PERFORMANCE_COLORS["Irregular"]}),
        "regular": workbook.add_format({"bg_color": STATUS_PERFORMANCE_COLORS["Regular"]}),
        "em_linha": workbook.add_format({"bg_color": STATUS_PERFORMANCE_COLORS["Em linha"]}),
        "alta": workbook.add_format({"bg_color": STATUS_PERFORMANCE_COLORS["Alta"]}),
        "ok": workbook.add_format({"bg_color": STATUS_COMPARACAO_COLORS["OK"]}),
        "diferente": workbook.add_format({"bg_color": STATUS_COMPARACAO_COLORS["Diferente"]}),
        "rpt_missing": workbook.add_format({"bg_color": "#FFEB9C"}),
    }


def _write_grouped_header(worksheet, formats: dict[str, object], column_count: int) -> None:
    worksheet.merge_range(0, 0, 0, 8, "", formats["group"])
    worksheet.merge_range(0, 9, 0, 13, "RED", formats["group"])
    worksheet.merge_range(0, 14, 0, 18, "OOS / RUPTURA", formats["group"])
    if column_count > 19:
        worksheet.merge_range(0, 19, 0, column_count - 1, "", formats["group"])


def _format_sheet(worksheet, dataframe: pd.DataFrame, formats: dict[str, object], header_row: int = 0) -> None:
    max_row, max_col = dataframe.shape
    if max_col == 0:
        return

    worksheet.freeze_panes(header_row + 1, 0)
    worksheet.autofilter(header_row, 0, header_row + max_row, max_col - 1)

    for column_index, column_name in enumerate(dataframe.columns):
        worksheet.write(header_row, column_index, column_name, formats["header"])
        width = _column_width(dataframe.iloc[:, column_index], str(column_name))
        column_format = formats["decimal"] if _is_decimal_column(str(column_name)) else None
        worksheet.set_column(column_index, column_index, width, column_format)

    _apply_text_colors(
        worksheet,
        dataframe,
        "Status da Performance",
        {"Irregular": "irregular", "Regular": "regular", "Em linha": "em_linha", "Alta": "alta"},
        formats,
        header_row,
    )
    _apply_text_colors(
        worksheet,
        dataframe,
        "StatusComparacao",
        {"OK": "ok", "Diferente": "diferente"},
        formats,
        header_row,
    )
    _apply_text_colors(
        worksheet,
        dataframe,
        "FonteRealizadoRPT",
        {"fonte_rpt_nao_encontrada": "rpt_missing"},
        formats,
        header_row,
    )


def _apply_text_colors(
    worksheet,
    dataframe: pd.DataFrame,
    column_name: str,
    mapping: dict[str, str],
    formats: dict[str, object],
    header_row: int,
) -> None:
    if column_name not in dataframe.columns:
        return
    column_index = dataframe.columns.get_loc(column_name)
    for value, format_key in mapping.items():
        worksheet.conditional_format(
            header_row + 1,
            column_index,
            header_row + len(dataframe),
            column_index,
            {"type": "text", "criteria": "containing", "value": value, "format": formats[format_key]},
        )


def _build_cadastro(base: pd.DataFrame, estrutura: pd.DataFrame) -> pd.DataFrame:
    columns = ["ChaveCentroRota", "UF", "Gerencia", "Gerência", "Supervisor"]
    frames = []
    for dataframe in [base, estrutura]:
        available = [column for column in columns if column in dataframe.columns]
        if "ChaveCentroRota" in available:
            frames.append(dataframe[available].copy())
    if not frames:
        return pd.DataFrame(columns=columns)
    cadastro = frames[0]
    for frame in frames[1:]:
        cadastro = cadastro.combine_first(frame)
    return cadastro.drop_duplicates("ChaveCentroRota")


def _first_available(dataframe: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series("-", index=dataframe.index)
    for column in columns:
        if column in dataframe.columns:
            result = result.mask(result.eq("-") | result.isna(), dataframe[column])
    return result


def _is_decimal_column(column_name: str) -> bool:
    return column_name in NUMERIC_COLUMNS or any(
        keyword in column_name
        for keyword in ["Atingimento", "Escala", "Aderencia", "Aderência", "Performance", "Peso", "Meta", "Real"]
    )


def _column_width(series: pd.Series, column_name: str) -> int:
    values = series.fillna("-").astype(str)
    max_length = int(values.map(len).max()) if not values.empty else 0
    return min(max(max_length, len(column_name)) + 2, 60)


def main() -> None:
    run()


if __name__ == "__main__":
    main()
