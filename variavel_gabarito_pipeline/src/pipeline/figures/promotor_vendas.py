"""Figura comercial PROMOTOR DE VENDAS."""

from __future__ import annotations

from pipeline.figures.base import CommercialFigure


class PromotorVendas(CommercialFigure):
    """Orquestrador futuro da apuracao de Promotor de Vendas."""

    def run(self) -> None:
        raise NotImplementedError("Calculo de Promotor de Vendas ainda nao implementado.")
