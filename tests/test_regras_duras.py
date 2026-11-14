"""Regras duras do agricultor: nenhuma é violada nas alternativas (motor de 3 caminhos, rotação de 3 safras e MILP).
Hypothesis não está instalado: teste de propriedade com sementes fixas (parametrizado)."""
import random

import numpy as np
import pandas as pd
import pytest

from src.culturas import ciclo, regras_duras as rd
from src.culturas.motor import gerar_cenarios
from src.culturas.parametros import Parametros
from src.culturas.regras_duras import RegrasDuras, permite, verificar
from src.culturas.rotacao import gerar_rotacoes
from src.culturas.rotacao_milp import melhor_por_enumeracao, otimizar
from src.culturas.tabela_culturas import carregar
from src.modelos.entrada import RAIZ

P = Parametros(n_sorteios=500)
FAM = {"m": "G", "s": "G", "f": "L", "a": "L", "x": "E", "y": None, "z": None}


@pytest.fixture(scope="module")
def tab():
    return carregar()


@pytest.fixture(scope="module")
def clima():
    return ciclo.ClimaPonto.de_dataframe(pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet"), "quixada_ce")


def _fam(tab):
    return {c: tab[c]["atributos"]["familia_botanica"]["valor"] for c in tab}


def _regras_aleatorias(seed, ids, atual="milho"):
    r = random.Random(seed)
    outros = [c for c in ids if c != atual]
    prib = frozenset(r.sample(outros, r.randint(0, 6)))
    livres = [c for c in outros if c not in prib]
    return RegrasDuras(proibidas=prib, obrigatorias=frozenset(r.sample(livres, r.randint(0, 1))) if livres else frozenset(),
                       exigir_alguma_de=frozenset(r.sample(livres, min(len(livres), 2))) if r.random() < 0.3 else frozenset(),
                       max_seguidas_cultura=r.choice([None, 1, 2]), max_seguidas_familia=r.choice([None, 1, 2]))


# ---------- unidade: verificar
def test_verificar_cada_regra():
    assert verificar(["m", "f", "a"], FAM, RegrasDuras(proibidas={"a"})) == ["usa cultura proibida pelo agricultor: a"]
    assert permite(["m", "f"], FAM, RegrasDuras(proibidas={"m"}))                  # safra 1 (já plantada) não é checada
    assert verificar(["m", "f"], FAM, RegrasDuras(obrigatorias={"a"}))
    assert permite(["m", "f"], FAM, RegrasDuras(obrigatorias={"m"}))               # a atual conta
    assert verificar(["m", "s", "f"], FAM, RegrasDuras(exigir_alguma_de={"a", "x"}))
    assert permite(["m", "f", "x"], FAM, RegrasDuras(exigir_alguma_de={"a", "x"}))
    assert verificar(["m", "m", "m"], FAM, RegrasDuras(max_seguidas_cultura=2))
    assert permite(["m", "m", "f"], FAM, RegrasDuras(max_seguidas_cultura=2))
    assert permite(["m", "f", "m"], FAM, RegrasDuras(max_seguidas_cultura=1))
    assert verificar(["m", "s", "f"], FAM, RegrasDuras(max_seguidas_familia=1))     # milho e sorgo: mesma família
    assert permite(["m", "f", "s"], FAM, RegrasDuras(max_seguidas_familia=1))
    assert permite(["m", "y", "z"], FAM, RegrasDuras(max_seguidas_familia=1))       # família desconhecida: lacuna, não repetição
    assert permite(["m", "m", "m"], FAM, None) and permite(["m", "m", "m"], FAM, RegrasDuras())


def test_validacao_da_regra():
    with pytest.raises(ValueError):
        RegrasDuras(proibidas={"a"}, obrigatorias={"a"})
    with pytest.raises(ValueError):
        RegrasDuras(max_seguidas_cultura=0)
    with pytest.raises(ValueError):
        RegrasDuras(proibidas={"a", "x"}, exigir_alguma_de={"a", "x"})
    with pytest.raises(ValueError):
        rd.validar(RegrasDuras(proibidas={"cultura_inexistente"}), ["milho"])      # typo não pode virar regra ignorada
    assert RegrasDuras().vazia and "pousio" in RegrasDuras(aceita_pousio=True).nao_modelado()[0]


# ---------- sem regra, nada muda (padrões mantidos)
def test_sem_regras_resultado_identico(tab, clima):
    a = gerar_rotacoes({"local": "x"}, "milho", tab, clima, P)
    b = gerar_rotacoes({"local": "x"}, "milho", tab, clima, P, regras=RegrasDuras())
    assert [e["sequencia"] for e in a["estrategias"]] == [e["sequencia"] for e in b["estrategias"]]
    assert [e["score_mediana"] for e in a["estrategias"]] == [e["score_mediana"] for e in b["estrategias"]]
    assert a.get("regras_duras") is None
    c1 = gerar_cenarios({"local": "x"}, "milho", tab, clima=clima, params=P)
    c2 = gerar_cenarios({"local": "x"}, "milho", tab, clima=clima, params=P, regras=RegrasDuras())
    assert [c["rotacao"] for c in c1] == [c["rotacao"] for c in c2]


# ---------- propriedade: nenhuma alternativa viola (rotação de 3 safras e motor de 3 caminhos)
@pytest.mark.parametrize("seed", range(10))
def test_rotacao_nunca_viola_regra_dura(tab, clima, seed):
    reg = _regras_aleatorias(seed, list(tab))
    fam = _fam(tab)
    r = gerar_rotacoes({"local": "x"}, "milho", tab, clima, P, regras=reg)
    assert r["regras_duras"] is not None
    for e in r["estrategias"]:
        if e["papel"] == "alternativa":
            assert verificar(e["sequencia"], fam, reg) == [], (seed, e["sequencia"])
    assert r["regras_duras"]["n_descartadas"] >= 0
    if len(r["estrategias"]) > 0:
        assert r["estrategias"][0]["papel"] == "atual"


@pytest.mark.parametrize("seed", range(10))
def test_motor_3_caminhos_nunca_viola_regra_dura(tab, clima, seed):
    reg = _regras_aleatorias(seed + 100, list(tab))
    fam = _fam(tab)
    cen = gerar_cenarios({"local": "x"}, "milho", tab, clima=clima, params=P, regras=reg)
    assert cen[0]["rotacao"] == ["milho", "milho"]
    for c in cen[1:]:
        assert verificar(c["rotacao"], fam, reg) == [], (seed, c["rotacao"])


def test_proibida_some_e_o_motivo_aparece(tab, clima):
    base = [e["sequencia"] for e in gerar_rotacoes({"local": "x"}, "milho", tab, clima, P)["estrategias"]]
    prib = {c for s in base[1:] for c in s[1:]}
    r = gerar_rotacoes({"local": "x"}, "milho", tab, clima, P, regras=RegrasDuras(proibidas=prib))
    usadas = {c for e in r["estrategias"][1:] for c in e["sequencia"][1:]}
    assert not (usadas & prib)
    assert r["regras_duras"]["n_descartadas"] > 0 and r["regras_duras"]["descartadas_por_motivo"]
    c = gerar_cenarios({"local": "x"}, "milho", tab, clima=clima, params=P, regras=RegrasDuras(proibidas=prib))
    assert any("Regras do agricultor" in l for l in c[0]["lacunas"])


def test_obrigatoria_aparece_em_toda_alternativa(tab, clima):
    r = gerar_rotacoes({"local": "x"}, "milho", tab, clima, P, regras=RegrasDuras(obrigatorias={"feijao_caupi"}))
    assert r["estrategias"] and all("feijao_caupi" in e["sequencia"] for e in r["estrategias"][1:])


def test_rotacao_atual_que_viola_fica_marcada(tab, clima):
    r = gerar_rotacoes({"local": "x"}, "milho", tab, clima, P, regras=RegrasDuras(max_seguidas_cultura=2))
    assert r["estrategias"][0]["sequencia"] == ["milho"] * 3 and r["regras_duras"]["base_viola"]
    assert any("viola regra dura" in l for l in r["estrategias"][0]["lacunas"])
    assert all(e["sequencia"] != ["milho"] * 3 for e in r["estrategias"][1:])


def test_regras_que_eliminam_tudo_nao_inventam_alternativa(tab, clima):
    r = gerar_rotacoes({"local": "x"}, "milho", tab, clima, P, regras=RegrasDuras(proibidas=frozenset(c for c in tab if c != "milho")))
    assert r["estrategias"] == [] and r["regras_duras"]["n_descartadas"] > 0
    c = gerar_cenarios({"local": "x"}, "milho", tab, clima=clima, params=P, regras=RegrasDuras(proibidas=frozenset(c for c in tab if c != "milho")))
    assert [x["rotacao"] for x in c] == [["milho", "milho"]]
    with pytest.raises(ValueError):
        gerar_rotacoes({"local": "x"}, "milho", tab, clima, P, regras={"proibidas": ["cultura_inexistente"]})


def test_mesma_entrada_mesma_saida_e_ordem_da_tabela_nao_importa(tab, clima):
    reg = RegrasDuras(proibidas={"palma_forrageira"}, max_seguidas_cultura=2)
    f = lambda t: [e["sequencia"] for e in gerar_rotacoes({"local": "x"}, "milho", t, clima, P, regras=reg)["estrategias"]]
    ks = list(tab)
    random.Random(3).shuffle(ks)
    assert f(tab) == f(tab) == f({k: tab[k] for k in ks})
    g = lambda t: [c["rotacao"] for c in gerar_cenarios({"local": "x"}, "milho", t, clima=clima, params=P, regras=reg)]
    assert g(tab) == g({k: tab[k] for k in ks})


# ---------- MILP: ótimo com regras do agricultor = enumeração, e nunca viola
def _dados(seed, C=8, K=10):
    rng = np.random.default_rng(seed)
    cult = [f"c{i}" for i in range(C)]
    adeq = {c: np.clip(rng.normal(0.6, 0.25, K), 0, 1) for c in cult}
    fam = {c: ("Leguminosae" if i % 3 == 0 else f"F{i % 3}") for i, c in enumerate(cult)}
    pal = {c: (None if i == 2 else float(rng.integers(1000, 9000))) for i, c in enumerate(cult)}
    return cult, adeq, fam, pal


@pytest.mark.parametrize("seed", range(8))
def test_milp_regras_do_agricultor_igual_a_enumeracao_e_sem_violacao(seed):
    cult, adeq, fam, pal = _dados(seed)
    reg = _regras_aleatorias(seed, cult, atual="c1")
    T = 4 if seed % 2 else 3
    r = otimizar(cult, "c1", adeq, fam, pal, T=T, regras=reg)
    seq, v = melhor_por_enumeracao(cult, "c1", adeq, fam, pal, T=T, regras=reg)
    if seq is None:
        assert not r["viavel"]
        return
    assert r["viavel"] and r["otimo_provado"] and r["violacoes_regras"] == []
    assert verificar(r["sequencia"], fam, reg) == []
    from src.culturas.rotacao_milp import nota_sequencia
    assert nota_sequencia(r["sequencia"], cult, adeq, fam, pal) == pytest.approx(v, abs=1e-6)


def test_milp_regra_antiga_em_dict_continua_valendo():
    cult, adeq, fam, pal = _dados(0)
    r = otimizar(cult, "c1", adeq, fam, pal, T=3, regras={"sem_repetir_seguida": True, "min_leguminosas": 2})
    assert r["viavel"] and verificar(r["sequencia"], fam, {"sem_repetir_seguida": True, "min_leguminosas": 2}) == []
