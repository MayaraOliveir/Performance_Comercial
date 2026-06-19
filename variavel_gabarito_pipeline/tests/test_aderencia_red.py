from pathlib import Path

from pipeline.core.utils import list_excel_files
from pipeline.staging.aderencia_red import clean_route
from pipeline.staging.common import clean_text, create_chave_centro_rota, to_number


def test_list_excel_files_filters_excel_and_temp_files(tmp_path: Path) -> None:
    valid_file = tmp_path / "aderencia.xlsx"
    temp_file = tmp_path / "~$aderencia.xlsx"
    text_file = tmp_path / "aderencia.txt"

    valid_file.touch()
    temp_file.touch()
    text_file.touch()

    assert list_excel_files(tmp_path) == [valid_file]


def test_clean_text_normalizes_empty_tokens() -> None:
    assert clean_text("  rota  ") == "ROTA"
    assert clean_text("-") is None
    assert clean_text("null") is None


def test_to_number_accepts_comma_decimal_and_percent() -> None:
    assert to_number("1,25") == 1.25
    assert to_number("87,5%") == 0.875
    assert to_number("-") is None


def test_create_chave_centro_rota_concatenates_standardized_values() -> None:
    assert create_chave_centro_rota(" crbc ", " va300 ") == "CRBCVA300"


def test_clean_route_removes_prefix_and_center_suffix() -> None:
    assert clean_route("ROTA - VA300CRBC", "CRBC") == "VA300"
