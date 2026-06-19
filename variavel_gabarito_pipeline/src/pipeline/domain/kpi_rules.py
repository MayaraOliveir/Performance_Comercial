"""Regras de KPI compartilhadas entre figuras comerciais."""


def normalize_kpi_name(name: str) -> str:
    """Normaliza nomes de KPI para comparacoes simples."""

    return " ".join(name.strip().upper().split())
