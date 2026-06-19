"""Executa todos os stagings das bases brutas."""

from __future__ import annotations

from pathlib import Path

from pipeline.core.logger import configure_logger
from pipeline.staging.aderencia_red import build_staging_aderencia_red
from pipeline.staging.agentes import build_staging_agentes
from pipeline.staging.escalonada import build_staging_escalonada
from pipeline.staging.indicadores import build_staging_indicadores
from pipeline.staging.metas import build_staging_metas
from pipeline.staging.pesos import build_staging_pesos
from pipeline.staging.red_mes_rota import build_staging_red_mes_rota


def run(paths_config_path: str | Path | None = None) -> list[Path]:
    """Executa os stagings na ordem definida para a pipeline."""

    logger = configure_logger("pipeline.staging")
    outputs: list[Path] = []

    logger.info("staging_inicio")
    outputs.append(build_staging_metas(paths_config_path))
    outputs.append(build_staging_indicadores(paths_config_path))
    outputs.append(build_staging_red_mes_rota(paths_config_path))
    outputs.extend(build_staging_agentes(paths_config_path))
    outputs.extend(build_staging_aderencia_red(paths_config_path))
    outputs.extend(build_staging_pesos(paths_config_path))
    outputs.append(build_staging_escalonada(paths_config_path))
    logger.info("staging_fim", extra={"qtd_arquivos_gerados": len(outputs)})

    return outputs


def main() -> None:
    run()


if __name__ == "__main__":
    main()
