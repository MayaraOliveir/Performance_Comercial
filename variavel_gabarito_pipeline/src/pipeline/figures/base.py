"""Contrato base para implementacao de figuras comerciais."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class FigureContext:
    """Contexto de execucao de uma figura comercial."""

    figure_key: str
    figure_name: str


class CommercialFigure(ABC):
    """Interface comum para figuras comerciais."""

    def __init__(self, context: FigureContext) -> None:
        self.context = context

    @abstractmethod
    def run(self) -> None:
        """Executa a apuracao da figura."""
