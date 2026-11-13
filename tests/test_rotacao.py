import numpy as np
import pandas as pd
import pytest

from src.culturas import ciclo
from src.culturas.parametros import Parametros
from src.culturas.rotacao import CRITERIOS, HORIZONTE, ORDEM_PRIORIDADE, contexto_pam, gerar_rotacoes
from src.culturas.tabela_culturas import carregar
from src.modelos.entrada import RAIZ


@pytest.fixture(scope="module")
def tab():
    return carregar()


@pytest.fixture(scope="module")
def clima():
    d = pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet")
    return ciclo.ClimaPonto.de_dataframe(d, "quixada_ce")


@pytest.fixture(scope="module")
def res(tab, clima):
    return gerar_rotacoes({"local": "quixada_ce"}, "milho", tab, clima, Parametros(n_sorteios=1500), prioridade="solo")


def test_tres_estrategias_comecando_na_cultura_atual(res):
    e = res["estrategias"]
    assert len(e) == 3 and e[0]["papel"] == "atual"
    for x in e:
        assert len(x["sequencia"]) == HORIZONTE and x["sequencia"][0] == "milho"
        assert x["faixa_score"][0] <= x["score_mediana"] <= x["faixa_score"][1]
    assert e[0]["sequencia"] == ["milho"] * HORIZONTE          # sem rotação informada: repete a cultura atual


def test_alternativas_distintas_e_nao_repetem_a_atual(res):
    a, b = res["estrategias"][1], res["estrategias"][2]
    assert a["sequencia"] != b["sequencia"] and frozenset(a["sequencia"][1:]) != frozenset(b["sequencia"][1:])
    assert all(len(set(x["sequencia"])) > 1 for x in (a, b))


def test_monocultura_nao_ganha_das_rotacoes(res):
    e = res["estrategias"]
    assert e[0]["score_mediana"] < min(e[1]["score_mediana"], e[2]["score_mediana"])


def test_lacunas_e_riscos_sempre_presentes(res):
    for x in res["estrategias"]:
        assert any("pragas" in l for l in x["lacunas"]) and any("renda" in l for l in x["lacunas"])
        assert x["riscos_revisao_local"] and "técnico local" in res["aviso"]
    assert res["suposicoes"] and res["horizonte_safras"] == 3


def test_dado_ausente_vira_lacuna_nao_nota(res):
    for x in res["estrategias"]:
        if any(c in ("mandioca", "feijao_caupi", "gergelim", "mamona") for c in x["sequencia"]):
            assert x["criterios"]["palha"]["lacuna"] is True          # essas culturas não têm palha na tabela
    assert set(res["criterios"]) == set(CRITERIOS)


def test_rotacao_informada_vira_a_estrategia_atual(tab, clima):
    r = gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000),
                       rotacao_atual=["milho", "feijao_caupi", "milho"])
    e0 = r["estrategias"][0]
    assert e0["sequencia"] == ["milho", "feijao_caupi", "milho"] and e0["rotacao_informada_pelo_usuario"] is True
    with pytest.raises(ValueError):
        gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000), rotacao_atual=["feijao_caupi", "milho", "milho"])


def test_prioridade_renda_nao_altera_o_resultado(tab, clima):
    a = gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000), prioridade="sem")
    b = gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000), prioridade="renda")
    assert [e["sequencia"] for e in a["estrategias"]] == [e["sequencia"] for e in b["estrategias"]]
    assert ORDEM_PRIORIDADE["renda"] is None
    with pytest.raises(ValueError):
        gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000), prioridade="lucro")


def test_reprodutivel(tab, clima):
    f = lambda: gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000), prioridade="agua")
    assert [e["sequencia"] for e in f()["estrategias"]] == [e["sequencia"] for e in f()["estrategias"]]


def test_solo_informado_gera_aviso_e_nao_muda_nota(tab, clima):
    a = gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000))
    b = gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1000),
                       solo_usuario={"textura": "arenoso", "materia_organica": "baixa"})
    assert [e["score_mediana"] for e in a["estrategias"]] == [e["score_mediana"] for e in b["estrategias"]]
    assert any("arenoso" in r for r in b["estrategias"][1]["riscos_revisao_local"])
    assert not any("arenoso" in r for r in a["estrategias"][1]["riscos_revisao_local"])


def test_contexto_pam_so_informa(tab):
    pts = pd.read_csv(RAIZ / "data/processed/pontos.csv").set_index("ponto_id")
    c = contexto_pam(int(pts.loc["quixada_ce", "ibge"]))
    assert "milho" in c and c["milho"]["area_colhida_ha"] >= 0
    assert contexto_pam(None) == {}
