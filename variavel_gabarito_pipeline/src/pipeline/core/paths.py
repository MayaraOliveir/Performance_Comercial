"""Carregamento e resolucao de caminhos configurados em YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pipeline.core.exceptions import ConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATHS_CONFIG = PROJECT_ROOT / "config" / "paths.yaml"


@dataclass(frozen=True)
class PathsConfig:
    """Configuracao de caminhos da pipeline."""

    project_root: Path
    values: dict[str, Any]

    def get_path(self, key: str) -> Path:
        """Retorna um caminho de primeiro nivel resolvido a partir do projeto."""

        value = self.values.get(key)
        if value is None:
            raise ConfigurationError(f"Caminho nao configurado: {key}")
        if not isinstance(value, Path):
            raise ConfigurationError(f"Valor de caminho invalido para {key}: {value!r}")
        return value


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Carrega um arquivo YAML como dicionario."""

    yaml_path = Path(path)
    if not yaml_path.exists():
        raise ConfigurationError(f"Arquivo de configuracao nao encontrado: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuracao YAML deve ser um mapa: {yaml_path}")

    return data


def load_paths_config(config_path: str | Path = DEFAULT_PATHS_CONFIG) -> PathsConfig:
    """Carrega paths.yaml e resolve caminhos relativos ao project_root."""

    raw_config = load_yaml(config_path)
    config_file = Path(config_path).resolve()
    configured_root = Path(raw_config.get("project_root", "."))
    project_root = configured_root if configured_root.is_absolute() else (config_file.parent / configured_root)
    project_root = project_root.resolve()

    resolved = _resolve_paths(raw_config, project_root)
    resolved["project_root"] = project_root

    return PathsConfig(project_root=project_root, values=resolved)


def _resolve_paths(value: Any, project_root: Path) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_paths(item, project_root) for key, item in value.items()}

    if isinstance(value, str):
        path = Path(value)
        return path if path.is_absolute() else (project_root / path).resolve()

    return value
