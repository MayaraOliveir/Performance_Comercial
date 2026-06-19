from pathlib import Path

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
