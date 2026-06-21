import pandas as pd
import pytest
from types import SimpleNamespace

from pipeline.core.exceptions import DataReadError
from pipeline.staging.estrutura_promotor import resolve_estrutura_promotor_source, transform_estrutura_promotor


def test_unidade_is_standardized_to_centro() -> None:
    raw = pd.DataFrame(
        [
            ["Unidade", "Rota"],
            [" crbc ", " pb001 "],
        ]
    )

    estrutura, _, _ = transform_estrutura_promotor(raw)

    assert estrutura.loc[0, "Centro"] == "CRBC"
    assert estrutura.loc[0, "UnidadeOriginal"] == " crbc "


def test_chave_centro_rota_uses_centro_plus_rota() -> None:
    raw = pd.DataFrame(
        [
            ["Centro", "Rota"],
            ["CRBC", "PA300"],
        ]
    )

    estrutura, _, _ = transform_estrutura_promotor(raw)

    assert estrutura.loc[0, "ChaveCentroRota"] == "CRBCPA300"


def test_duplicates_are_removed_by_chave_centro_rota() -> None:
    raw = pd.DataFrame(
        [
            ["Centro", "Rota"],
            ["CRBC", "PB001"],
            ["CRBC", "PB001"],
        ]
    )

    estrutura, dim_rotas, diagnostics = transform_estrutura_promotor(raw)

    assert len(estrutura) == 1
    assert len(dim_rotas) == 1
    assert diagnostics.loc[diagnostics["Metrica"] == "duplicidades_chave", "Valor"].iloc[0] == 2


def test_tipo_rota_is_inferred_from_rota_prefix() -> None:
    raw = pd.DataFrame(
        [
            ["Centro", "Rota"],
            ["CRBC", "PF777"],
        ]
    )

    _, dim_rotas, _ = transform_estrutura_promotor(raw)

    assert dim_rotas.loc[0, "TipoRota"] == "PF"


def test_dim_rotas_promotor_does_not_depend_on_agents() -> None:
    raw = pd.DataFrame(
        [
            ["Centro", "Rota", "Supervisor"],
            ["CRBC", "PB001", "MARIA"],
        ]
    )

    _, dim_rotas, _ = transform_estrutura_promotor(raw)

    assert list(dim_rotas["ChaveCentroRota"]) == ["CRBCPB001"]
    assert "DescricaoFuncao" not in dim_rotas.columns


def test_pipeline_accepts_new_monthly_structure_format() -> None:
    raw = pd.DataFrame(
        [
            ["UF", "Gerencia", "Supervisor", "Unidade", "Rota", "MetaRED", "RealizadoRED"],
            ["CE", "G1", "S1", "CRBC", "PA300", "0,8", "0,9"],
        ]
    )

    estrutura, dim_rotas, diagnostics = transform_estrutura_promotor(raw)

    assert len(estrutura) == 1
    assert dim_rotas.loc[0, "ChaveCentroRota"] == "CRBCPA300"
    assert estrutura.loc[0, "MetaRED"] == 0.8
    assert estrutura.loc[0, "FonteEstrutura"] == "estrutura_mensal"
    assert diagnostics.loc[diagnostics["Metrica"] == "total_chaves_unicas", "Valor"].iloc[0] == 1


def test_uses_monthly_structure_when_file_exists(tmp_path) -> None:
    raw_estrutura = tmp_path / "estrutura_promotor"
    raw_gabarito = tmp_path / "gabarito_validacao"
    raw_estrutura.mkdir()
    raw_gabarito.mkdir()
    _write_excel(raw_estrutura / "estrutura.xlsx")
    _write_figuras_config(tmp_path / "figuras.yaml", allow_fallback=True)

    source = resolve_estrutura_promotor_source(
        _paths(raw_estrutura, raw_gabarito),
        tmp_path / "figuras.yaml",
    )

    assert source["path"] == raw_estrutura / "estrutura.xlsx"
    assert source["fonte"] == "estrutura_mensal"


def test_uses_gabarito_fallback_when_monthly_file_is_missing_and_config_allows(tmp_path) -> None:
    raw_estrutura = tmp_path / "estrutura_promotor"
    raw_gabarito = tmp_path / "gabarito_validacao"
    raw_estrutura.mkdir()
    raw_gabarito.mkdir()
    _write_excel(raw_gabarito / "gabarito.xlsx")
    _write_figuras_config(tmp_path / "figuras.yaml", allow_fallback=True)

    source = resolve_estrutura_promotor_source(
        _paths(raw_estrutura, raw_gabarito),
        tmp_path / "figuras.yaml",
    )

    assert source["path"] == raw_gabarito / "gabarito.xlsx"
    assert source["fonte"] == "gabarito_fallback"


def test_fails_when_monthly_file_is_missing_and_config_disallows_fallback(tmp_path) -> None:
    raw_estrutura = tmp_path / "estrutura_promotor"
    raw_gabarito = tmp_path / "gabarito_validacao"
    raw_estrutura.mkdir()
    raw_gabarito.mkdir()
    _write_figuras_config(tmp_path / "figuras.yaml", allow_fallback=False)

    with pytest.raises(DataReadError, match="Estrutura Promotor mensal não encontrada"):
        resolve_estrutura_promotor_source(_paths(raw_estrutura, raw_gabarito), tmp_path / "figuras.yaml")


def test_never_uses_agents_as_promotor_structure_fallback(tmp_path) -> None:
    raw_estrutura = tmp_path / "estrutura_promotor"
    raw_gabarito = tmp_path / "gabarito_validacao"
    raw_agentes = tmp_path / "agentes"
    raw_estrutura.mkdir()
    raw_gabarito.mkdir()
    raw_agentes.mkdir()
    _write_excel(raw_agentes / "agentes.xlsx")
    _write_figuras_config(tmp_path / "figuras.yaml", allow_fallback=True)

    with pytest.raises(DataReadError):
        resolve_estrutura_promotor_source(
            _paths(raw_estrutura, raw_gabarito, raw_agentes),
            tmp_path / "figuras.yaml",
        )


def test_fonte_estrutura_is_correct_for_monthly_and_fallback() -> None:
    raw = pd.DataFrame([["Centro", "Rota"], ["CRBC", "PA300"]])

    monthly, _, monthly_diag = transform_estrutura_promotor(raw, fonte_estrutura="estrutura_mensal")
    fallback, _, fallback_diag = transform_estrutura_promotor(raw, fonte_estrutura="gabarito_fallback")

    assert monthly.loc[0, "FonteEstrutura"] == "estrutura_mensal"
    assert fallback.loc[0, "FonteEstrutura"] == "gabarito_fallback"
    assert monthly_diag.loc[monthly_diag["Metrica"] == "fonte_estrutura_usada", "Valor"].iloc[0] == "estrutura_mensal"
    assert fallback_diag.loc[fallback_diag["Metrica"] == "fonte_estrutura_usada", "Valor"].iloc[0] == "gabarito_fallback"


def _write_excel(path) -> None:
    pd.DataFrame({"A": [1]}).to_excel(path, index=False)


def _write_figuras_config(path, allow_fallback: bool) -> None:
    path.write_text(
        "figuras:\n"
        "  promotor_vendas:\n"
        f"    allow_gabarito_fallback_estrutura: {'true' if allow_fallback else 'false'}\n",
        encoding="utf-8",
    )


def _paths(raw_estrutura, raw_gabarito, raw_agentes=None):
    raw_sources = {
        "estrutura_promotor": raw_estrutura,
        "gabarito_validacao": raw_gabarito,
    }
    if raw_agentes is not None:
        raw_sources["agentes"] = raw_agentes
    return SimpleNamespace(values={"raw_sources": raw_sources})
