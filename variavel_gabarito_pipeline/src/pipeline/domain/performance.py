"""Calculos de performance e atingimento."""

from __future__ import annotations

import pandas as pd


def is_missing(value: object) -> bool:
    """Indica se um valor deve ser tratado como nulo."""

    return pd.isna(value)


def calculate_performance(meta: object, realizado: object, tipo_calculo: str) -> float | None:
    """Calcula performance para indicadores maior_melhor ou menor_melhor."""

    if is_missing(meta) or is_missing(realizado):
        return None

    meta_number = float(meta)
    realizado_number = float(realizado)

    if tipo_calculo == "maior_melhor":
        if meta_number == 0:
            return None
        return realizado_number / meta_number

    if tipo_calculo == "menor_melhor":
        if realizado_number == 0:
            return None
        return meta_number / realizado_number

    raise ValueError(f"Tipo de calculo invalido: {tipo_calculo}")


def calculate_weighted_achievement(performance: object, peso: object) -> float | None:
    """Multiplica performance pelo peso, preservando nulos."""

    if is_missing(performance) or is_missing(peso):
        return None
    return float(performance) * float(peso)


def sum_ignoring_nulls(*values: object) -> float | None:
    """Soma valores ignorando nulos, como SOMA do Excel."""

    valid_values = [float(value) for value in values if not is_missing(value)]
    if not valid_values:
        return None
    return sum(valid_values)


def classify_status_performance(atingimento_total: object) -> str:
    """Classifica a performance consolidada da rota."""

    if is_missing(atingimento_total):
        return "Sem cálculo"

    value = float(atingimento_total)
    if value < 0.71:
        return "Irregular"
    if value < 0.81:
        return "Regular"
    if value > 1:
        return "Alta"
    return "Em linha"
