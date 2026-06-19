import pytest

from pipeline.figures.base import FigureContext
from pipeline.figures.promotor_vendas import PromotorVendas


def test_promotor_vendas_is_explicitly_not_implemented_yet() -> None:
    figure = PromotorVendas(
        FigureContext(figure_key="promotor_vendas", figure_name="PROMOTOR DE VENDAS")
    )

    with pytest.raises(NotImplementedError):
        figure.run()
