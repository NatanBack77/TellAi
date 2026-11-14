"""'O que separa as alternativas': dominância de Pareto nos critérios com dado nos dois lados + propriedades.
Hypothesis não está instalado: propriedades com sementes fixas (parametrizado)."""
import copy
import json
import random

import pytest

from src.culturas.pareto import comparar_par, separar_alternativas

CRIT = ["clima", "diversidade", "leguminosa", "palha", "agua"]


def _alt(i, **notas):
    return {"id": i, "criterios": {k: notas.get(k) for k in CRIT}}


def _par(res, a, b):
    return next(p for p in res["pares"] if p["a"] == a and p["b"] == b)


def test_dominancia_empate_e_lacuna():
    A = _alt("A", clima=0.8, diversidade=1.0, leguminosa=0.5, palha=None, agua=None)
    B = _alt("B", clima=0.6, diversidade=1.0, leguminosa=0.2, palha=0.9, agua=None)
    res = separar_alternativas([A, B])
    p = _par(res, "A", "B")
    assert p["relacao"] == "a_domina" and p["a_melhor_em"] == ["clima", "leguminosa"] and p["empatam_em"] == ["diversidade"]
    assert p["lacuna_nos_dois"] == ["agua"] and p["lacuna_so_em_a"] == ["palha"] and p["comparacao_incompleta"] is True
    assert res["fronteira"] == ["A"] and res["posicao_pareto"]["B"]["dominada_por"] == ["A"]
    assert res["criterios_sem_dado_em_todas"] == ["agua"]
    assert any("Sem dado nas duas" in f for f in p["frases"]) and any("só para os critérios com dado nos dois" in f for f in p["frases"])


def test_troca_sem_dominancia_e_sem_criterio_comum_e_empate_total():
    r = separar_alternativas([_alt("A", clima=0.9, palha=0.1), _alt("B", clima=0.1, palha=0.9)])
    assert _par(r, "A", "B")["relacao"] == "sem_dominancia" and r["fronteira"] == ["A", "B"]
    r = separar_alternativas([_alt("A", clima=0.9), _alt("B", palha=0.9)])
    assert _par(r, "A", "B")["relacao"] == "sem_criterio_comum" and r["fronteira"] == ["A", "B"]
    r = separar_alternativas([_alt("A", clima=0.5), _alt("B", clima=0.5)])
    assert _par(r, "A", "B")["relacao"] == "empate_total"


def test_aceita_formatos_de_rotacao_e_do_motor():
    a = {"sequencia": ["milho", "guandu"], "criterios": {"palha": {"nota_media": 0.7, "lacuna": False}, "agua": {"nota_media": None, "lacuna": True}}}
    b = {"rotacao": ["milho", "sorgo"], "criterios": {"palha": {"nota": 0.2, "valor": 5}, "agua": {"nota": None, "lacuna": "sem dado"}}}
    r = separar_alternativas([a, b])
    p = r["pares"][0]
    assert p["relacao"] in ("a_domina", "b_domina") and p["lacuna_nos_dois"] == ["agua"]
    with pytest.raises(ValueError):
        separar_alternativas([{"id": "x", "criterios": {}}, {"id": "x", "criterios": {}}])


def test_nan_e_lacuna():
    r = separar_alternativas([_alt("A", clima=float("nan"), palha=0.4), _alt("B", clima=0.9, palha=0.3)])
    assert "clima" not in _par(r, "A", "B")["a_melhor_em"] + _par(r, "A", "B")["b_melhor_em"]


def _aleatorias(seed, n=5):
    r = random.Random(seed)
    return [_alt(f"alt{i}", **{k: (None if r.random() < 0.3 else round(r.random(), 1)) for k in CRIT}) for i in range(n)]


@pytest.mark.parametrize("seed", range(25))
def test_monotonia_melhorar_um_criterio_nunca_piora_a_posicao(seed):
    alts = _aleatorias(seed)
    rng = random.Random(seed + 1000)
    antes = separar_alternativas(alts)
    alvo = rng.choice(alts)
    com_dado = [k for k in CRIT if alvo["criterios"][k] is not None]
    if not com_dado:
        return
    k = rng.choice(com_dado)
    novas = copy.deepcopy(alts)
    nv = next(a for a in novas if a["id"] == alvo["id"])
    nv["criterios"][k] = nv["criterios"][k] + rng.random()               # melhora (nunca piora)
    depois = separar_alternativas(novas)
    i = alvo["id"]
    # posição Pareto: quem domina o alvo só pode diminuir (subconjunto)
    assert set(depois["posicao_pareto"][i]["dominada_por"]) <= set(antes["posicao_pareto"][i]["dominada_por"])
    # contra cada outra: o que o alvo ganha nunca diminui; o que o outro ganha nunca aumenta
    for o in alts:
        if o["id"] == i:
            continue
        def vis(res):
            a, b = sorted([i, o["id"]])
            p = _par(res, a, b)
            return (p["a_melhor_em"], p["b_melhor_em"]) if a == i else (p["b_melhor_em"], p["a_melhor_em"])
        (g0, p0), (g1, p1) = vis(antes), vis(depois)
        assert set(g0) <= set(g1) and set(p1) <= set(p0)


@pytest.mark.parametrize("seed", range(25))
def test_permutar_alternativas_nao_muda_o_resultado(seed):
    alts = _aleatorias(seed, n=6)
    base = separar_alternativas(alts)
    emb = random.Random(seed).sample(alts, len(alts))
    assert json.dumps(separar_alternativas(emb), sort_keys=True) == json.dumps(base, sort_keys=True)
    ordem_crit = random.Random(seed).sample(CRIT, len(CRIT))
    assert separar_alternativas(emb, criterios=ordem_crit) == separar_alternativas(alts, criterios=CRIT)


@pytest.mark.parametrize("seed", range(25))
def test_mesma_entrada_mesma_saida(seed):
    alts = _aleatorias(seed)
    assert separar_alternativas(alts) == separar_alternativas(copy.deepcopy(alts))


@pytest.mark.parametrize("seed", range(25))
def test_lacuna_nao_vira_vantagem(seed):
    alts = _aleatorias(seed)
    res = separar_alternativas(alts)
    por = {a["id"]: a["criterios"] for a in alts}
    for p in res["pares"]:
        for k in p["a_melhor_em"] + p["b_melhor_em"] + p["empatam_em"]:
            assert por[p["a"]][k] is not None and por[p["b"]][k] is not None        # só compara onde há dado nos dois
        for k in p["lacuna_so_em_a"]:
            assert por[p["a"]][k] is None and por[p["b"]][k] is not None
        for k in p["lacuna_nos_dois"]:
            assert por[p["a"]][k] is None and por[p["b"]][k] is None
        if p["relacao"] in ("a_domina", "b_domina") and (p["lacuna_so_em_a"] or p["lacuna_so_em_b"]):
            assert p["comparacao_incompleta"] is True
    # trocar um valor com dado por lacuna num lado nunca cria vantagem em critério nenhum para esse lado
    r = random.Random(seed)
    alvo = r.choice(alts)
    com = [k for k in CRIT if alvo["criterios"][k] is not None]
    if com:
        k = r.choice(com)
        novas = copy.deepcopy(alts)
        next(a for a in novas if a["id"] == alvo["id"])["criterios"][k] = None
        dep = separar_alternativas(novas)
        for p in dep["pares"]:
            if alvo["id"] in (p["a"], p["b"]):
                assert k not in p["a_melhor_em"] + p["b_melhor_em"] + p["empatam_em"]


def test_comparar_par_tolerancia():
    p = comparar_par({"x": 0.5}, {"x": 0.5 + 1e-12}, ["x"])
    assert p["relacao"] == "empate_total"


def test_integra_com_saida_da_rotacao():
    import pandas as pd
    from src.culturas import ciclo
    from src.culturas.parametros import Parametros
    from src.culturas.pareto import de_estrategias
    from src.culturas.rotacao import gerar_rotacoes
    from src.culturas.tabela_culturas import carregar
    from src.modelos.entrada import RAIZ
    cl = ciclo.ClimaPonto.de_dataframe(pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet"), "quixada_ce")
    r = gerar_rotacoes({"local": "x"}, "milho", carregar(), cl, Parametros(n_sorteios=500), prioridade="solo")
    s = de_estrategias(r["estrategias"])
    assert len(s["pares"]) == 3 and set(s["criterios"]) == set(r["criterios"])
    for p in s["pares"]:
        assert p["frases"]
