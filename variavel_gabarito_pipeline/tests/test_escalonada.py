from pathlib import Path

import pandas as pd

from pipeline.domain.escalonada import find_escalonada_value
from pipeline.core.paths import load_paths_config


def test_load_paths_config_resolves_relative_paths(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "paths.yaml"
    config_file.write_text(
        "\n".join(
            [
                "project_root: ..",
                "inventario_arquivos: data/processed/inventario_arquivos.csv",
                "raw_sources:",
                "  escalonada: data/raw/escalonada",
            ]
        ),
        encoding="utf-8",
    )

    paths_config = load_paths_config(config_file)

    assert paths_config.project_root == tmp_path.resolve()
    assert paths_config.values["inventario_arquivos"] == (
        tmp_path / "data" / "processed" / "inventario_arquivos.csv"
    ).resolve()
    assert paths_config.values["raw_sources"]["escalonada"] == (
        tmp_path / "data" / "raw" / "escalonada"
    ).resolve()


def test_find_escalonada_value_returns_matching_range() -> None:
    escalonada = pd.DataFrame(
        {
            "FaixaDe": [0.0, 0.8, 0.9],
            "FaixaAte": [0.799999, 0.899999, 0.999999],
            "EscalaAtingida": [0.0, 0.7, 0.8],
        }
    )

    assert find_escalonada_value(0.85, escalonada) == 0.7
    assert find_escalonada_value(1.5, escalonada) == 0.8


def test_find_escalonada_value_uses_largest_faixa_de_less_or_equal_value() -> None:
    escalonada = pd.DataFrame(
        {
            "FaixaDe": [0.0, 0.8, 1.0],
            "FaixaAte": [0.7, 0.9, 1.1],
            "EscalaAtingida": [0.0, 0.7, 1.0],
        }
    )

    assert find_escalonada_value(0.95, escalonada) == 0.7
    assert find_escalonada_value(1.5, escalonada) == 1.0
