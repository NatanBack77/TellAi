"""Testes do código IBGE em pontos.csv (a parte ZARC ainda não foi implementada; ver docs/13_ZARC.md)."""
from pathlib import Path

import pandas as pd

PONTOS = Path(__file__).resolve().parents[1] / "data" / "processed" / "pontos.csv"
SEM_CODIGO_CONHECIDO = {"sobral_ce"}  # coordenada do ponto cai fora do polígono IBGE (ver docs/13_ZARC.md)


def _df():
    return pd.read_csv(PONTOS, dtype={"ibge": str}, keep_default_na=False)


def test_colunas_originais_preservadas():
    assert list(_df().columns) == ["ponto_id", "lat", "lon", "celula_power", "ibge"]


def test_ibge_unicos_e_validos_no_ce():
    d = _df()
    ce = d[d["ponto_id"].str.endswith("_ce")]
    assert len(ce) == 184
    com = ce[ce["ibge"] != ""]
    assert set(ce[ce["ibge"] == ""]["ponto_id"]) <= SEM_CODIGO_CONHECIDO
    assert com["ibge"].is_unique
    assert com["ibge"].str.fullmatch(r"23\d{5}").all()
    assert len(com) == 184 - len(SEM_CODIGO_CONHECIDO)


def test_ibge_todos_sete_digitos_ou_vazio():
    assert _df()["ibge"].str.fullmatch(r"\d{7}|").all()
