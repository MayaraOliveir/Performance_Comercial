"""Escrita de arquivos Excel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DECIMAL_FORMAT = "0.0000"


def write_excel(dataframe: pd.DataFrame, output_path: str | Path, sheet_name: str = "dados") -> Path:
    """Escreve um DataFrame em um arquivo Excel."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
    return path


def write_formatted_workbook(
    sheets: dict[str, pd.DataFrame],
    output_path: str | Path,
    decimal_columns: dict[str, list[str]] | None = None,
    status_formats: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Escreve um workbook Excel com filtros, congelamento, larguras e cores."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    decimal_columns = decimal_columns or {}
    status_formats = status_formats or {}

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#1F4E78",
                "font_color": "#FFFFFF",
                "border": 1,
            }
        )
        decimal_format = workbook.add_format({"num_format": DECIMAL_FORMAT})
        status_cell_formats = {
            color: workbook.add_format({"bg_color": color})
            for color in set(_all_status_colors(status_formats).values())
        }

        for sheet_name, dataframe in sheets.items():
            safe_sheet_name = sheet_name[:31]
            dataframe.to_excel(writer, sheet_name=safe_sheet_name, index=False, na_rep="-")
            worksheet = writer.sheets[safe_sheet_name]
            _format_worksheet(
                worksheet=worksheet,
                dataframe=dataframe,
                header_format=header_format,
                decimal_format=decimal_format,
                decimal_columns=decimal_columns.get(sheet_name, []),
                status_colors=status_formats.get(sheet_name, {}),
                status_cell_formats=status_cell_formats,
            )

    return path


def _format_worksheet(
    worksheet,
    dataframe: pd.DataFrame,
    header_format,
    decimal_format,
    decimal_columns: list[str],
    status_colors: dict[str, str],
    status_cell_formats: dict[str, object],
) -> None:
    max_row, max_col = dataframe.shape
    if max_col == 0:
        return

    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max_row, max_col - 1)

    for column_index, column_name in enumerate(dataframe.columns):
        worksheet.write(0, column_index, column_name, header_format)
        width = _calculate_column_width(dataframe[column_name], column_name)
        column_format = decimal_format if column_name in decimal_columns else None
        worksheet.set_column(column_index, column_index, width, column_format)

    for status_column, colors_by_value in status_colors.items():
        if status_column not in dataframe.columns:
            continue
        column_index = dataframe.columns.get_loc(status_column)
        for status_value, color_key in colors_by_value.items():
            worksheet.conditional_format(
                1,
                column_index,
                max_row,
                column_index,
                {
                    "type": "text",
                    "criteria": "containing",
                    "value": status_value,
                    "format": status_cell_formats[color_key],
                },
            )


def _calculate_column_width(series: pd.Series, column_name: str) -> int:
    values = series.fillna("-").astype(str)
    max_value_length = int(values.map(len).max()) if not values.empty else 0
    return min(max(max_value_length, len(column_name)) + 2, 60)


def _all_status_colors(status_formats: dict[str, dict[str, dict[str, str]]]) -> dict[str, str]:
    colors: dict[str, str] = {}
    for columns_mapping in status_formats.values():
        for status_mapping in columns_mapping.values():
            colors.update(status_mapping)
    return colors
