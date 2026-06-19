"""Diagnosticos detalhados da validacao Promotor contra gabarito."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.core.logger import configure_logger
from pipeline.core.paths import load_paths_config
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv


DETAIL_COLUMNS = [
    "ChaveComparacao",
    "Centro",
    "Rota",
    "AtingimentoTotal",
    "AtingimentoTotalGabarito",
    "DifAtingimentoTotal",
    "EscalaAtingida",
    "EscalaAtingidaGabarito",
    "DifEscalaAtingida",
    "StatusPerformance",
    "StatusGabarito",
    "Diagnostico",
    "AderenciaRED",
    "AderenciaREDOriginal",
    "StatusAderenciaRED",
    "MetaRED",
    "RealizadoRED",
    "PerformanceRED",
    "PesoRED",
    "AtingimentoRED",
    "MetaRPT",
    "RealizadoRPT",
    "PerformanceRPT",
    "PesoRPT",
    "AtingimentoRPT",
]

SO_GABARITO_COLUMNS = [
    "ChaveComparacao",
    "CentroGabarito",
    "RotaGabarito",
    "StatusGabarito",
    "StatusValorGabarito",
    "AtingimentoTotalGabaritoOriginal",
    "AtingimentoTotalGabarito",
    "EscalaAtingidaGabaritoOriginal",
    "EscalaAtingidaGabarito",
]

SO_PYTHON_COLUMNS = [
    "ChaveComparacao",
    "Centro",
    "Rota",
    "TipoRota",
    "AtingimentoTotal",
    "EscalaAtingida",
    "StatusPerformance",
    "Diagnostico",
    "AderenciaRED",
    "AderenciaREDOriginal",
    "StatusAderenciaRED",
    "MetaRED",
    "RealizadoRED",
    "AtingimentoRED",
    "MetaRPT",
    "RealizadoRPT",
    "AtingimentoRPT",
]

CLASSIFIED_DIFFERENCE_COLUMNS = [
    "ChaveComparacao",
    "Centro",
    "Rota",
    "TipoDiferenca",
    "AtingimentoTotal",
    "AtingimentoTotalGabarito",
    "DifAtingimentoTotal",
    "EscalaAtingida",
    "EscalaAtingidaGabarito",
    "DifEscalaAtingida",
    "Diagnostico",
    "StatusPerformance",
    "StatusGabarito",
    "AderenciaRED",
    "AderenciaREDOriginal",
    "StatusAderenciaRED",
    "AtingimentoRED",
    "AtingimentoRPT",
    "MetaRED",
    "RealizadoRED",
    "MetaRPT",
    "RealizadoRPT",
]

SEM_FAIXA_COLUMNS = [
    "ChaveCentroRota",
    "Centro",
    "Rota",
    "AtingimentoTotal",
    "EscalaAtingida",
    "StatusPerformance",
    "Diagnostico",
    "AtingimentoTotalGabarito",
    "EscalaAtingidaGabarito",
]

TOLERANCE = 0.0001


def run() -> list[Path]:
    """Gera arquivos de diagnostico detalhado da validacao Promotor."""

    logger = configure_logger("pipeline.diagnostico_validacao_promotor")
    paths_config = load_paths_config()
    data = load_inputs(paths_config)
    enriched = build_enriched_validation(data["validacao"], data["fat_final"])

    validation_dir = paths_config.values["processed"]["validation"]
    diferentes = build_detail_report(enriched, "Diferente")
    python_sem = build_detail_report(enriched, "Python sem atingimento")
    so_gabarito = build_so_gabarito_report(enriched)
    so_python = build_so_python_report(enriched)
    resumo = build_summary(enriched)
    diferentes_classificado = build_classified_differences(enriched)
    sem_faixa = build_sem_faixa_report(enriched)
    resumo_tipo_diferenca = build_difference_type_summary(diferentes_classificado)

    outputs = [
        write_csv(diferentes, validation_dir / "diagnostico_diferentes_promotor.csv"),
        write_csv(python_sem, validation_dir / "diagnostico_python_sem_atingimento.csv"),
        write_csv(so_gabarito, validation_dir / "diagnostico_so_gabarito.csv"),
        write_csv(so_python, validation_dir / "diagnostico_so_python.csv"),
        write_csv(resumo, validation_dir / "resumo_diagnostico_validacao_promotor.csv"),
        write_csv(diferentes_classificado, validation_dir / "diagnostico_diferentes_classificado.csv"),
        write_csv(sem_faixa, validation_dir / "diagnostico_sem_faixa_escalonada.csv"),
        write_csv(resumo_tipo_diferenca, validation_dir / "resumo_tipo_diferenca.csv"),
    ]

    print_terminal_summary(diferentes, python_sem, so_gabarito)
    print_deep_terminal_summary(diferentes_classificado, sem_faixa, resumo_tipo_diferenca)
    logger.info(
        "diagnostico_validacao_promotor_concluido",
        extra={
            "linhas_diferentes": len(diferentes),
            "linhas_python_sem_atingimento": len(python_sem),
            "linhas_so_gabarito": len(so_gabarito),
            "linhas_so_python": len(so_python),
            "linhas_resumo": len(resumo),
            "linhas_diferentes_classificado": len(diferentes_classificado),
            "linhas_sem_faixa": len(sem_faixa),
            "linhas_resumo_tipo_diferenca": len(resumo_tipo_diferenca),
        },
    )
    return outputs


def load_inputs(paths_config) -> dict[str, pd.DataFrame]:
    """Carrega as entradas solicitadas para o diagnostico."""

    processed = paths_config.values["processed"]
    staging_dir = processed["staging"]
    facts_dir = processed["facts"]
    validation_dir = processed["validation"]
    return {
        "validacao": read_csv(validation_dir / "validacao_promotor_gabarito.csv"),
        "fat_final": read_csv(facts_dir / "fat_promotor_final.csv"),
        "fat_calculo": read_csv(facts_dir / "fat_promotor_calculo.csv"),
        "aderencia_red": read_csv(staging_dir / "stg_aderencia_red.csv"),
        "metas": read_csv(staging_dir / "stg_metas.csv"),
        "indicadores": read_csv(staging_dir / "stg_indicadores.csv"),
        "pesos": read_csv(staging_dir / "stg_pesos.csv"),
        "escalonada": read_csv(staging_dir / "stg_escalonada_promotor.csv"),
        "gabarito": read_csv(validation_dir / "stg_gabarito_promotor.csv"),
    }


def build_enriched_validation(validacao: pd.DataFrame, fat_final: pd.DataFrame) -> pd.DataFrame:
    """Enriquece a comparacao com colunas detalhadas do fato final."""

    detail_columns = [
        "ChaveCentroRota",
        "TipoRota",
        "AderenciaRED",
        "AderenciaREDOriginal",
        "StatusAderenciaRED",
        "MetaRED",
        "RealizadoRED",
        "PerformanceRED",
        "PesoRED",
        "AtingimentoRED",
        "MetaRPT",
        "RealizadoRPT",
        "PerformanceRPT",
        "PesoRPT",
        "AtingimentoRPT",
    ]
    available_detail_columns = [column for column in detail_columns if column in fat_final.columns]
    enriched = validacao.merge(
        fat_final[available_detail_columns],
        on="ChaveCentroRota",
        how="left",
    )
    enriched["ChaveComparacao"] = enriched["ChaveCentroRota"]
    enriched["CentroGabarito"] = enriched.get("CentroGabaritoCadastro")
    enriched["RotaGabarito"] = enriched.get("RotaGabaritoCadastro")
    return enriched


def build_detail_report(enriched: pd.DataFrame, status: str) -> pd.DataFrame:
    """Monta relatorio detalhado para um StatusComparacao."""

    report = enriched[enriched["StatusComparacao"] == status].copy()
    report = report.sort_values("DifAtingimentoTotal", ascending=False, na_position="last")
    return select_existing_columns(report, DETAIL_COLUMNS)


def build_so_gabarito_report(enriched: pd.DataFrame) -> pd.DataFrame:
    """Monta relatorio de rotas existentes apenas no gabarito."""

    report = enriched[enriched["StatusComparacao"] == "Só no gabarito"].copy()
    return select_existing_columns(report, SO_GABARITO_COLUMNS)


def build_so_python_report(enriched: pd.DataFrame) -> pd.DataFrame:
    """Monta relatorio de rotas existentes apenas no Python."""

    report = enriched[enriched["StatusComparacao"] == "Só no Python"].copy()
    return select_existing_columns(report, SO_PYTHON_COLUMNS)


def build_summary(enriched: pd.DataFrame) -> pd.DataFrame:
    """Agrupa divergencias por status e diagnostico."""

    work = enriched.copy()
    work["AbsDifAtingimento"] = work["DifAtingimentoTotal"].abs()
    return (
        work.groupby(["StatusComparacao", "Diagnostico"], dropna=False)
        .agg(
            QtdRotas=("ChaveCentroRota", "size"),
            MediaDifAtingimento=("AbsDifAtingimento", "mean"),
            MaiorDifAtingimento=("AbsDifAtingimento", "max"),
        )
        .reset_index()
        .sort_values(["StatusComparacao", "QtdRotas"], ascending=[True, False])
        .reset_index(drop=True)
    )


def build_classified_differences(enriched: pd.DataFrame) -> pd.DataFrame:
    """Classifica se a divergencia esta no atingimento ou apenas na escala."""

    report = enriched[enriched["StatusComparacao"] == "Diferente"].copy()
    report["AbsDifAtingimento"] = report["DifAtingimentoTotal"].abs()
    report["AbsDifEscala"] = report["DifEscalaAtingida"].abs()
    report["TipoDiferenca"] = [
        classify_difference_type(abs_atingimento, abs_escala)
        for abs_atingimento, abs_escala in zip(
            report["AbsDifAtingimento"],
            report["AbsDifEscala"],
            strict=False,
        )
    ]
    report = report.sort_values(
        ["TipoDiferenca", "DifAtingimentoTotal", "DifEscalaAtingida"],
        ascending=[True, False, False],
        na_position="last",
    )
    return select_existing_columns(report, CLASSIFIED_DIFFERENCE_COLUMNS)


def classify_difference_type(abs_dif_atingimento: object, abs_dif_escala: object) -> str:
    """Classifica o tipo de diferenca usando tolerancia numerica."""

    atingimento = 0 if pd.isna(abs_dif_atingimento) else float(abs_dif_atingimento)
    escala = 0 if pd.isna(abs_dif_escala) else float(abs_dif_escala)
    if atingimento <= TOLERANCE and escala > TOLERANCE:
        return "Diferença só na escala"
    if atingimento > TOLERANCE:
        return "Diferença no atingimento"
    return "Diferença sem classificação"


def build_sem_faixa_report(enriched: pd.DataFrame) -> pd.DataFrame:
    """Lista rotas cujo diagnostico contem Sem faixa escalonada."""

    report = enriched[
        enriched["Diagnostico"].fillna("").str.contains("Sem faixa escalonada", regex=False)
    ].copy()
    return select_existing_columns(report, SEM_FAIXA_COLUMNS)


def build_difference_type_summary(diferentes_classificado: pd.DataFrame) -> pd.DataFrame:
    """Agrupa diferencas por tipo e diagnostico."""

    work = diferentes_classificado.copy()
    work["AbsDifAtingimento"] = work["DifAtingimentoTotal"].abs()
    work["AbsDifEscala"] = work["DifEscalaAtingida"].abs()
    return (
        work.groupby(["TipoDiferenca", "Diagnostico"], dropna=False)
        .agg(
            QtdRotas=("ChaveComparacao", "size"),
            MediaDifAtingimento=("AbsDifAtingimento", "mean"),
            MaiorDifAtingimento=("AbsDifAtingimento", "max"),
            MediaDifEscala=("AbsDifEscala", "mean"),
            MaiorDifEscala=("AbsDifEscala", "max"),
        )
        .reset_index()
        .sort_values(["TipoDiferenca", "QtdRotas"], ascending=[True, False])
        .reset_index(drop=True)
    )


def print_terminal_summary(
    diferentes: pd.DataFrame,
    python_sem_atingimento: pd.DataFrame,
    so_gabarito: pd.DataFrame,
) -> None:
    """Imprime os principais achados no terminal."""

    print("Top 10 maiores diferenças:")
    top_differences = diferentes.copy()
    top_differences["AbsDifAtingimento"] = top_differences["DifAtingimentoTotal"].abs()
    top_columns = [
        "ChaveComparacao",
        "Centro",
        "Rota",
        "AtingimentoTotal",
        "AtingimentoTotalGabarito",
        "DifAtingimentoTotal",
        "Diagnostico",
    ]
    print(
        top_differences.sort_values("AbsDifAtingimento", ascending=False)
        .head(10)[top_columns]
        .to_string(index=False)
    )

    print("\nQuantidade por Diagnostico dentro de 'Diferente':")
    print(_count_by_diagnostic(diferentes).to_string(index=False))

    print("\nQuantidade por Diagnostico dentro de 'Python sem atingimento':")
    print(_count_by_diagnostic(python_sem_atingimento).to_string(index=False))

    sem_calculo_gabarito = (
        so_gabarito["StatusValorGabarito"].eq("Sem cálculo no gabarito").sum()
        if "StatusValorGabarito" in so_gabarito.columns
        else 0
    )
    print(f"\nSó no gabarito com StatusValorGabarito = 'Sem cálculo no gabarito': {sem_calculo_gabarito}")


def print_deep_terminal_summary(
    diferentes_classificado: pd.DataFrame,
    sem_faixa: pd.DataFrame,
    resumo_tipo_diferenca: pd.DataFrame,
) -> None:
    """Imprime os novos achados da investigacao aprofundada."""

    print("\nResumo por TipoDiferenca:")
    print(
        "Sem diferenças classificadas."
        if resumo_tipo_diferenca.empty
        else resumo_tipo_diferenca.to_string(index=False)
    )

    print("\nTop 20 diferenças de atingimento:")
    top_atingimento = diferentes_classificado[
        diferentes_classificado["TipoDiferenca"] == "Diferença no atingimento"
    ].copy()
    top_atingimento["AbsDifAtingimento"] = top_atingimento["DifAtingimentoTotal"].abs()
    print(
        _safe_to_string(
            top_atingimento.sort_values("AbsDifAtingimento", ascending=False).head(20),
            [
                "ChaveComparacao",
                "Centro",
                "Rota",
                "AtingimentoTotal",
                "AtingimentoTotalGabarito",
                "DifAtingimentoTotal",
                "Diagnostico",
            ],
        )
    )

    print("\nTop 20 diferenças só de escala:")
    top_escala = diferentes_classificado[
        diferentes_classificado["TipoDiferenca"] == "Diferença só na escala"
    ].copy()
    top_escala["AbsDifEscala"] = top_escala["DifEscalaAtingida"].abs()
    print(
        _safe_to_string(
            top_escala.sort_values("AbsDifEscala", ascending=False).head(20),
            [
                "ChaveComparacao",
                "Centro",
                "Rota",
                "EscalaAtingida",
                "EscalaAtingidaGabarito",
                "DifEscalaAtingida",
                "Diagnostico",
            ],
        )
    )

    print("\nRotas sem faixa escalonada:")
    print(
        _safe_to_string(
            sem_faixa,
            [
                "ChaveCentroRota",
                "Centro",
                "Rota",
                "AtingimentoTotal",
                "EscalaAtingidaGabarito",
            ],
        )
    )


def select_existing_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Seleciona colunas existentes na ordem desejada."""

    return dataframe[[column for column in columns if column in dataframe.columns]].reset_index(drop=True)


def _safe_to_string(dataframe: pd.DataFrame, columns: list[str]) -> str:
    """Formata DataFrame para terminal tolerando resultados vazios."""

    if dataframe.empty:
        return "Nenhuma linha encontrada."
    return select_existing_columns(dataframe, columns).to_string(index=False)


def _count_by_diagnostic(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "Diagnostico" not in dataframe.columns:
        return pd.DataFrame(columns=["Diagnostico", "QtdRotas"])
    return (
        dataframe.groupby("Diagnostico", dropna=False)
        .size()
        .reset_index(name="QtdRotas")
        .sort_values("QtdRotas", ascending=False)
        .reset_index(drop=True)
    )


def main() -> None:
    run()


if __name__ == "__main__":
    main()
