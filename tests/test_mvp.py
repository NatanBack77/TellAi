"""Testes do MVP (src/app/mvp.py e a tela). Usam os dados REAIS do repositório (clima, diagnóstico); pulam se faltarem."""
from pathlib import Path

import pytest

from src.app import mvp as M

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "src/app/app.py")
tem_dados = (RAIZ / "data/processed/clima_diario.parquet").is_file() and (RAIZ / "data/processed/pontos.csv").is_file()
tem_diag = (RAIZ / "data/processed/diagnostico/diagnostico.json").is_file()
pytestmark = pytest.mark.skipif(not tem_dados, reason="dados locais ausentes")
LOCAL = "quixada_ce"


def test_nome_do_ponto_e_lista():
    assert M.nome_do_ponto("varzea_alegre_ce") == "Varzea Alegre (CE)"
    assert M.nome_do_ponto("sao_joao_do_jaguaribe_ce") == "Sao Joao do Jaguaribe (CE)"
    p = M.carregar_pontos()
    assert len(p) == 195 and (p["uf"] == "CE").sum() == 184 and p["celula_power"].nunique() == 59


def test_renda_nao_altera_o_ranking_e_vira_lacuna():
    a = M.calcular(LOCAL, "milho", "sem", n_sorteios=500, com_evidencias=False)
    b = M.calcular(LOCAL, "milho", "renda", n_sorteios=500, com_evidencias=False)
    assert [c["rotacao"] for c in a["cenarios"]] == [c["rotacao"] for c in b["cenarios"]]
    assert [c["faixa_incerteza"]["p_top3"] for c in a["cenarios"][1:]] == [c["faixa_incerteza"]["p_top3"] for c in b["cenarios"][1:]]
    assert any("preço" in l for c in b["cenarios"] for l in c["lacunas"])
    assert not any("preço" in l for c in a["cenarios"] for l in c["lacunas"])
    assert "NÃO altera o ranking" in M.PRIORIDADES["renda"]["regra"]


def test_prioridade_solo_usa_bloco_completo_e_muda_o_resultado():
    p = M.parametros("solo", 500)
    assert p.bloco_ranking == "completo" and p.ordem_pesos[0] == "palha"
    s = M.calcular(LOCAL, "milho", "solo", n_sorteios=500, com_evidencias=False)
    n = M.calcular(LOCAL, "milho", "sem", n_sorteios=500, com_evidencias=False)
    assert {c["rotacao"][1] for c in s["cenarios"]} != {c["rotacao"][1] for c in n["cenarios"]}
    c = s["cenarios"][1]
    assert M.bloco_ranking(c, "solo") is c["faixa_incerteza"]["complemento_n_palha"]
    v = M.visao_faixa(c, "solo")["faixa_incerteza"]
    assert v["p_top3"] == c["faixa_incerteza"]["complemento_n_palha"]["p_top3"]
    # a cultura atual não tem ranking: não pode herdar o p_top3 do bloco principal
    assert "p_top3" not in M.visao_faixa(s["cenarios"][0], "solo")["faixa_incerteza"]


def test_tres_estrategias_atual_primeiro_e_empate_sem_posicao_falsa():
    r = M.calcular(LOCAL, "milho", "sem", n_sorteios=500, com_evidencias=False)
    assert len(r["cenarios"]) == 3 and r["cenarios"][0]["atual"] and not r["cenarios"][1]["atual"]
    d = M.descricao_estrategia(r["cenarios"][1], "sem")
    assert d["empatadas"], "neste local as alternativas estão em empate técnico"
    assert d["incerteza"]["empate"] and "Quem decide" in d["incerteza"]["empate"][0]
    assert all(x["texto"] is None or x["fonte"] for x in d["criterios"])   # todo dado exibido traz fonte


def test_sem_cache_de_evidencias_vira_lacuna(tmp_path, monkeypatch):
    monkeypatch.setenv("SULCO_MVP_DIR", str(tmp_path))
    M.carregar_evidencias.cache_clear()
    try:
        r = M.calcular(LOCAL, "milho", "sem", n_sorteios=500)
        assert all(c["trechos"] == [] for c in r["cenarios"])
        assert any("evidencias_rag.json" in l for l in r["cenarios"][1]["lacunas"])
    finally:
        monkeypatch.undo()
        M.carregar_evidencias.cache_clear()


def test_perturbar_nao_modifica_o_original_e_neutro_igual_ao_base():
    c = M.clima_ponto(LOCAL)
    chuva0, tmed0 = c.chuva.copy(), c.tmed.copy()
    c2 = M.perturbar(c, 0.7, 2.0)
    assert (c.chuva == chuva0).all() or ((c.chuva != c.chuva) == (chuva0 != chuva0)).all()
    assert abs(float((c2.tmed - c.tmed).mean()) - 2.0) < 1e-9
    cc = M.cenario_clima(LOCAL, "milho", "sem", 1.0, 0.0,
                         base=M.calcular(LOCAL, "milho", "sem", n_sorteios=500, com_evidencias=False))
    for x in cc["linhas"]:
        assert x["adeq_base"] == x["adeq_cenario"] and not x["fora_chuva"] and not x["fora_temp"]
    assert not cc["extrapolacao"]
    with pytest.raises(ValueError):
        M.perturbar(c, -0.1, 0)


def test_cenario_extremo_avisa_extrapolacao():
    base = M.calcular(LOCAL, "milho", "sem", n_sorteios=500, com_evidencias=False)
    cc = M.cenario_clima(LOCAL, "milho", "sem", M.CHUVA_FATOR_MIN, M.TEMP_DELTA_MAX, base=base)
    assert cc["extrapolacao"] and any("EXTRAPOLAÇÃO" in a for a in cc["avisos"])
    sec = next(x for x in cc["linhas"] if x["atual"])
    assert sec["adeq_cenario"] < sec["adeq_base"]


def test_quinzenas_do_ciclo():
    assert M.quinzenas_do_ciclo(0, 10) == [1] and M.quinzenas_do_ciclo(0, 20) == [1, 2] and M.quinzenas_do_ciclo(350, 30)[0] == 24 and M.quinzenas_do_ciclo(0, 400) == list(range(1, 25))


@pytest.mark.skipif(not tem_diag, reason="diagnóstico real ausente")
def test_diagnostico_real_em_frases_e_lacuna_para_ponto_desconhecido():
    d = M.diagnostico_local(LOCAL)
    assert d["confianca"] in ("baixa", "media", "alta") and "RELATIVO ao local" in d["solo_nu"]["frase"]
    assert "convenção do app" in d["estresse_frase"] and d["veranicos"]["frase"]
    assert M.diagnostico_local("nao_existe_xx") is None


def test_numeros_de_limites_vem_do_arquivo():
    a = M.numeros_avaliacao_195()
    assert a["disponivel"] and abs(a["persistencia_confirmacao_ridge"] - 0.2385) < 1e-9
    assert any("Cobertura conformal" in l for l in a["linhas"])
    n = M.contagens_dados()
    assert (n["pontos"], n["pontos_ce"], n["celulas_power"]) == (195, 184, 59)


# ------------------------------------------------------------------------------ tela (AppTest)
def _textos(at):
    partes = [m.value for m in at.markdown] + [w.value for w in at.warning] + [e.value for e in at.error] \
        + [i.value for i in at.info] + [c.value for c in at.caption] + [m.value for m in at.metric]
    return "\n".join(str(p) for p in partes)


def test_app_fluxo_completo_sem_excecao():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    t = _textos(at)
    for k in ("250 m a 50 km", "Quando o campo costuma ficar nu", "Atual: ", "Alternativa A", "Alternativa B",
              "Lacunas", "Riscos para revisão local", "técnico local", "NÃO é previsão"):
        assert k.lower() in t.lower(), k
    for chave, valor in (("local", "sobral_ce"), ("cultura", "feijao_caupi")):
        at.selectbox(key=chave).set_value(valor).run()
        assert not at.exception
    at.radio(key="prioridade").set_value("renda").run()
    assert not at.exception and any("preço" in w.value for w in at.warning)
    at.radio(key="prioridade").set_value("solo").run()
    at.slider(key="fator_chuva").set_value(70).run()
    at.slider(key="delta_t").set_value(3.0).run()
    assert not at.exception and "EXTRAPOLAÇÃO" in _textos(at)
    at.sidebar.radio(key="pagina").set_value("Glossário").run()
    assert not at.exception and "NDVI" in _textos(at)


def test_resposta_por_selecao_abaixo_de_5_segundos():
    import time

    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    M.limpar_caches()
    for chave, valor in (("local", "crato_ce"), ("cultura", "sorgo")):
        t0 = time.perf_counter()
        at.selectbox(key=chave).set_value(valor).run()
        assert time.perf_counter() - t0 < 5.0, chave


def test_rotacao_3_safras_na_tela_com_entradas_do_agricultor():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    t = _textos(at)
    assert any("3b. Rotação em 3 safras" in x.value for x in at.subheader)
    for k in ("Alternativa 1", "Alternativa 2", "pragas", "técnico local"):
        assert k.lower() in t.lower(), k
    at.selectbox(key="textura").set_value("arenoso").run()
    at.selectbox(key="rot2").set_value("feijao_caupi").run()          # só a 2ª: avisa que falta a 3ª, não quebra
    assert not at.exception
    at.selectbox(key="rot3").set_value("milho").run()
    assert not at.exception
    assert "rotação informada por você" in _textos(at)
    at.checkbox(key="zarc").set_value(True).run()
    assert not at.exception


def test_calcular_rotacao_renda_e_lacuna_e_nao_altera():
    a = M.calcular_rotacao("quixada_ce", "milho", "sem", n_sorteios=800)
    b = M.calcular_rotacao("quixada_ce", "milho", "renda", n_sorteios=800)
    assert [e["sequencia"] for e in a["estrategias"]] == [e["sequencia"] for e in b["estrategias"]]
    assert a["n_simuladas"] <= 81 and a["segundos"] < 5.0
