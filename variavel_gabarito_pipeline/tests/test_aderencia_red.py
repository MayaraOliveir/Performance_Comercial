from pathlib import Path

import pandas as pd

from pipeline.core.utils import list_excel_files
from pipeline.staging.aderencia_red import clean_route, transform_aderencia_red
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
    assert clean_route("ROTA-VA300CRBC", "CRBC") == "VA300"
    assert clean_route("ROTAVA300CRBC", "CRBC") == "VA300"


def test_transform_aderencia_red_creates_valid_value_and_status() -> None:
    dataframe = pd.DataFrame(
        {
            "centro": ["CRBC", "CRBC", "CENTRO", None],
            "rota": ["ROTA - VA300CRBC", "ROTA - VA301CRBC", "ROTA", "VA302"],
            "%": [0.8, 0.9, 0.1, 0.2],
            "%_1": [0.95, 2.0, 0.5, 0.7],
            "chave": ["x", "x", "x", "x"],
        }
    )

    result = transform_aderencia_red(dataframe)

    assert len(result) == 2
    assert result.loc[0, "ChaveCentroRota"] == "CRBCVA300"
    assert result.loc[0, "AderenciaRED"] == 0.95
    assert result.loc[0, "AderenciaREDValida"] == 0.95
    assert result.loc[0, "AderenciaSupervisor"] == 0.8
    assert result.loc[0, "StatusAderenciaRED"] == "OK"
    assert result.loc[1, "AderenciaRED"] == 2.0
    assert pd.isna(result.loc[1, "AderenciaREDValida"])
    assert result.loc[1, "StatusAderenciaRED"] == "Suspeita acima de 1.5"
