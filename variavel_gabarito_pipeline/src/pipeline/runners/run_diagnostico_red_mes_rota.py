"""Diagnostico da base red_mes_rota contra o resultado Promotor atual."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv


TOLERANCE = 0.0001


def run() -> list[Path]:
    """Compara stg_red_mes_rota com fat_promotor_final sem alterar o calculo."""

    logger = configure_logger("pipeline.diagnostico_red_mes_rota")
    paths_config = load_paths_config()
    processed = paths_config.values["processed"]
    staging_dir = processed["staging"]
    facts_dir = processed["facts"]
    validation_dir = processed["validation"]

    promotor = read_csv(facts_dir / "fat_promotor_final.csv")
    red_mes_rota = read_csv(staging_dir / "stg_red_mes_rota.csv")
    diagnostic = build_diagnostic(promotor, red_mes_rota)
    summary = build_summary(diagnostic, len(promotor))

    outputs = [
        write_csv(diagnostic, validation_dir / "diagnostico_red_mes_rota_vs_promotor.csv"),
        write_csv(summary, validation_dir / "resumo_red_mes_rota_vs_promotor.csv"),
    ]
    logger.info(
        "diagnostico_red_mes_rota_concluido",
        extra={
            "rotas_promotor": len(promotor),
            "rotas_encontradas": int((diagnostic["StatusPresenca"] == "Existe nos dois").sum()),
            "rotas_nao_encontradas": int((diagnostic["StatusPresenca"] == "Só no Promotor").sum()),
        },
    )
    print_summary(summary)
    return outputs


def build_diagnostic(promotor: pd.DataFrame, red_mes_rota: pd.DataFrame) -> pd.DataFrame:
    """Gera diagnostico por rota comparando realizado RED."""

    promotor_base = promotor[
        ["ChaveCentroRota", "Centro", "Rota", "RealizadoRED"]
    ].drop_duplicates(subset=["ChaveCentroRota"])
    red_base = (
        red_mes_rota[["ChaveCentroRota", "RealizadoREDMesRota"]]
        .dropna(subset=["ChaveCentroRota"])
        .drop_duplicates(subset=["ChaveCentroRota"])
    )
    result = promotor_base.merge(red_base, on="ChaveCentroRota", how="left", indicator=True)
    result["StatusPresenca"] = result["_merge"].map(
        {
            "both": "Existe nos dois",
            "left_only": "Só no Promotor",
            "right_only": "Só na red_mes_rota",
        }
    )
    result["DifRealizadoREDAbs"] = (
        result["RealizadoRED"] - result["RealizadoREDMesRota"]
    ).abs()
    result["TemDiferenca"] = result["DifRealizadoREDAbs"] > TOLERANCE
    return result[
        [
            "ChaveCentroRota",
            "Centro",
            "Rota",
            "StatusPresenca",
            "RealizadoRED",
            "RealizadoREDMesRota",
            "DifRealizadoREDAbs",
            "TemDiferenca",
        ]
    ].reset_index(drop=True)


def build_summary(diagnostic: pd.DataFrame, total_promotor: int) -> pd.DataFrame:
    """Gera resumo agregado do diagnostico."""

    compared = diagnostic[diagnostic["StatusPresenca"] == "Existe nos dois"]
    differences = compared[compared["TemDiferenca"]]
    return pd.DataFrame(
        [
            {
                "TotalRotasPromotor": total_promotor,
                "RotasEncontradasRedMesRota": int(len(compared)),
                "RotasNaoEncontradasRedMesRota": int((diagnostic["StatusPresenca"] == "Só no Promotor").sum()),
                "TotalRotasComparadas": int(len(compared)),
                "QtdComDiferenca": int(len(differences)),
                "MediaDiferenca": compared["DifRealizadoREDAbs"].mean(),
                "MaiorDiferenca": compared["DifRealizadoREDAbs"].max(),
            }
        ]
    )


def print_summary(summary: pd.DataFrame) -> None:
    """Imprime resumo no terminal."""

    print("Resumo red_mes_rota vs Promotor:")
    print(summary.to_string(index=False))


def main() -> None:
    run()


if __name__ == "__main__":
    main()
