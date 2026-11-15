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
    assert M.nome_do_ponto("varzea_alegre_ce") == "Várzea Alegre (CE)"          # nome oficial (coluna `nome` de pontos.csv, D4)
    assert M.nome_do_ponto("sao_joao_do_jaguaribe_ce") == "São João do Jaguaribe (CE)"
    assert M.nome_do_ponto("sobral_ce") == "Sobral (CE)" and M.nome_do_ponto("petrolina_pe") == "Petrolina (PE)"
    assert M.nome_do_ponto("ponto_sem_csv_ce") == "Ponto Sem Csv (CE)"          # fora de pontos.csv: derivado do id
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
    assert "Alternativa A" not in _textos(at)          # sem cultura escolhida não há caminhos (e não há cultura padrão)
    at.multiselect(key="culturas").set_value(["milho"]).run()
    assert not at.exception
    t = _textos(at)
    for k in ("250 m a 50 km", "Quando o campo costuma ficar nu", "Atual: ", "Alternativa A", "Alternativa B",
              "Lacunas", "Riscos para revisão local", "técnico local", "NÃO é previsão"):
        assert k.lower() in t.lower(), k
    at.selectbox(key="local").set_value("sobral_ce").run()
    at.multiselect(key="culturas").set_value(["feijao_caupi"]).run()
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
    at.multiselect(key="culturas").set_value(["milho"]).run()       # partida a frio (primeira cultura do município): fora da medida
    for chave, valor in (("local", "crato_ce"), ("culturas", ["sorgo"])):
        t0 = time.perf_counter()
        (at.multiselect if chave == "culturas" else at.selectbox)(key=chave).set_value(valor).run()
        assert time.perf_counter() - t0 < 5.0, chave


def test_rotacao_3_safras_na_tela_com_entradas_do_agricultor():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
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


def test_calcular_rotacao_renda_usa_receita_bruta_do_ibge_e_nao_mexe_nas_outras_prioridades():
    a = M.calcular_rotacao("quixada_ce", "milho", "sem", n_sorteios=800)
    b = M.calcular_rotacao("quixada_ce", "milho", "renda", n_sorteios=800)
    assert a["n_simuladas"] <= 81 and a["segundos"] < 5.0
    assert not a["usa_renda"] and b["usa_renda"]                     # renda só entra na prioridade 'renda' e se houver valor do IBGE
    assert any("renda" in k for e in b["estrategias"] for k in e["criterios"])


def test_solo_estimado_plausivel_e_rotulado():
    e = M.solo_estimado("quixada_ce")
    assert e is not None and 0 < e["argila_pct"] < 60 and 0 < e["areia_pct"] < 100 and 3.5 < e["ph_agua"] < 9.5
    assert e["textura"] in ("arenoso", "médio", "argiloso") and "Não é análise de solo" in e["aviso"]
    assert M.solo_estimado("ponto_que_nao_existe") is None


def test_solo_estimado_media_ponderada_pela_espessura_e_aviso_de_pixels():
    import pandas as pd
    d = pd.read_parquet(RAIZ / "data/processed/solo.parquet").set_index("ponto_id")
    r = d.loc["quixada_ce"]
    esperado = (r["clay_0-5cm"] * 5 + r["clay_5-15cm"] * 10 + r["clay_15-30cm"] * 15) / 30       # espessuras 5, 10 e 15 cm
    e = M.solo_estimado("quixada_ce")
    assert abs(e["argila_pct"] - esperado) < 1e-9
    assert abs(e["argila_pct"] - (r["clay_0-5cm"] + r["clay_5-15cm"] + r["clay_15-30cm"]) / 3) > 1e-3     # não é a média simples
    assert e["fracao_pixels_validos"] == pytest.approx(float(r["fracao_pixels_validos"]))
    p = M.solo_estimado("petrolina_pe")                     # 5% da janela com dado: aviso próprio
    assert p["fracao_pixels_validos"] < M.LIMITE_FRACAO_PIXELS and p["aviso_pixels"] and "Poucos pixels" in p["aviso_pixels"]
    ok = d[(d["fracao_pixels_validos"] >= M.LIMITE_FRACAO_PIXELS) & d["pixel_central_valido"]].index[0]
    assert M.solo_estimado(ok)["aviso_pixels"] is None


def test_rotacao_usa_solo_estimado_se_nao_informado_e_o_informado_prevalece():
    a = M.calcular_rotacao("quixada_ce", "milho", "sem", n_sorteios=500)
    assert a["solo_informado"]["origem"].startswith("estimado") and a["solo_estimado"] is not None
    b = M.calcular_rotacao("quixada_ce", "milho", "sem", textura="arenoso", n_sorteios=500)
    assert b["solo_informado"]["origem"] == "informado" and b["solo_informado"]["textura"] == "arenoso"
    assert any("arenoso informado" in r for r in b["estrategias"][1]["riscos_revisao_local"])


# ------------------------------------------------------------------------------ AP3, A5, A6, A7
def test_limites_nao_diz_mais_que_nao_ha_solo_nem_zarc_e_cita_o_relatorio_atual():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.radio(key="pagina").set_value("Limites dos dados").run()
    assert not at.exception
    t = _textos(at).lower()
    assert "solo, evapotranspiração nem zoneamento" not in t and "não há dado de preço, custo, mercado, pragas, doenças, solo" not in t
    assert "soilgrids" in t and "zarc" in t and "data/processed/modelos/relatorio_modelos.md" in t
    assert any("modelo preditivo" in x.value.lower() for x in at.markdown)


def test_camadas_do_mapa_so_com_dado_de_arquivo_e_lacuna_cinza():
    import numpy as np

    from src.app import camadas as C
    ids = list(M.carregar_pontos()["ponto_id"])
    assert len(ids) == 195
    for cam, ano in (("solo_nu", None), ("solo_nu", 2015), ("declive", None), ("quadra", None), ("quadra", 2012)):
        v = C.valores(cam, ano)
        assert v["disponivel"] and v["serie"].reindex(ids).notna().sum() > 150, (cam, ano)
        cores, info = C.cores(v["serie"], ids)
        assert len(cores) == 195 and info["min"] <= info["max"]
    assert C.valores("declive", 2015)["ano_usado"] is None            # camada sem ano ignora o ano
    nan = C.valores("solo_nu", 1900)                                   # ano sem dado: tudo cinza, nada inventado
    assert nan["serie"].reindex(ids).isna().all()
    assert all(c == C.COR_SEM_DADO for c in C.cores(nan["serie"], ids)[0])
    ev = C.valores("erosao", None)
    assert ev["disponivel"] == C.erosao_disponivel()                  # sem módulo: lacuna; com módulo: soma de notas 0 a 8 por ponto
    if ev["disponivel"]:
        assert 0 <= ev["serie"].min() and ev["serie"].max() <= 8


def test_mapa_troca_de_camada_e_ano_sem_excecao_e_rapido():
    import time

    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    for camada, ano in (("solo_nu", None), ("declive", None), ("quadra", 2012), ("erosao", None)):
        t0 = time.perf_counter()
        at.selectbox(key="camada").set_value(camada).run()
        if camada in ("solo_nu", "quadra"):
            at.select_slider(key="ano_mapa").set_value(ano if ano else "todos os anos").run()
        assert not at.exception, camada
        assert time.perf_counter() - t0 < 5.0, camada
    assert any("sem dado" in x.value.lower() or "lacuna" in x.value.lower() for x in list(at.warning) + list(at.caption))


def test_filtros_do_agricultor_nao_inventam_efeito():
    from src.app import filtros as F
    f = F.Filtros(manejo="irrigado", agua_irrigacao_mm=100, equipamento=F.EQUIPAMENTOS[1], mercado=F.MERCADOS[1])
    r = F.avaliar(f, "quixada_ce", "feijao_comum", chuva_ciclo_mm=300.0, demanda_mm=500.0)
    st_ = {i["filtro"]: i["status"] for i in r["itens"]}
    assert st_["Equipamento"] == "lacuna"                              # sem dado de máquina: nunca atende nem reprova
    assert st_["Água disponível"] == "nao_atende" and "faltam cerca de 100 mm" in [i for i in r["itens"] if i["filtro"] == "Água disponível"][0]["texto"]
    assert F.zarc_irrigado(F.geocodigo("quixada_ce"), "feijao_comum")["tem"] is True
    assert F.zarc_irrigado(F.geocodigo("quixada_ce"), "milho")["tem"] is None   # ZARC irrigado não traz: lacuna, não "proibido"
    assert F.avaliar(f, "quixada_ce", "milho", None, None)["itens"][1]["status"] == "lacuna"
    assert not F.Filtros().ativos()


def test_tela_com_filtros_ligados():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    at.radio(key="manejo").set_value("irrigado").run()
    at.number_input(key="agua_irrig").set_value(300).run()
    at.selectbox(key="equip").set_value("trator e implementos").run()
    at.selectbox(key="mercado").set_value("só culturas já colhidas no meu município (IBGE)").run()
    assert not at.exception
    t = _textos(at)
    assert "Seus filtros sobre os três caminhos" in t and "não é modelado" in t and "LACUNA" in t


def test_glossario_novos_termos_e_trechos_verdadeiros_do_acervo():
    import re
    import shutil
    import subprocess
    import unicodedata
    termos = {t for t, _ in M.GLOSSARIO}
    for k in ("Fixadoras de nitrogênio", "Adubação verde", "Raízes profundas", "Evapotranspiração", "Balanço hídrico", "Risco de erosão"):
        assert k in termos and k in M.TRECHOS_GLOSSARIO, k
    antes = M.BALANCO_NA_TELA
    try:
        M.BALANCO_NA_TELA = False                                   # sem a seção na tela: o glossário não pode dizer que o app calcula ET
        txt = dict((a, b) for a, b, _ in M.glossario_atual())
        assert "NÃO calcula" in txt["Evapotranspiração"] and "ainda não faz" in txt["Balanço hídrico"]
        M.BALANCO_NA_TELA = True                                    # com a seção: só ETo de REFERÊNCIA, Kc é lacuna
        txt = dict((a, b) for a, b, _ in M.glossario_atual())
        assert "REFERÊNCIA" in txt["Evapotranspiração"] and "Kc" in txt["Evapotranspiração"] and "NÃO é o balanço do solo" in txt["Balanço hídrico"]
    finally:
        M.BALANCO_NA_TELA = antes
    if shutil.which("pdftotext") is None:
        return
    norm = lambda s: re.sub(r"\s+", "", re.sub(r"-\s+", "", unicodedata.normalize("NFKC", s).replace("\xad", ""))).lower()
    for k, v in M.TRECHOS_GLOSSARIO.items():
        pdf = RAIZ / "docs_rag" / v["arquivo"]
        pg = str(v["pagina"])
        out = subprocess.run(["pdftotext", "-f", pg, "-l", pg, "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
        assert norm(v["trecho"]) in norm(out), f"trecho de '{k}' não está em {v['arquivo']} p.{pg}"


def test_pagina_glossario_mostra_trechos():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.radio(key="pagina").set_value("Glossário").run()
    assert not at.exception
    t = _textos(at)
    assert "Fixadoras de nitrogênio" in t and "embrapa_cap3_sistema_plantio_direto.pdf, p. 2" in t


def test_secoes_integradas_aparecem_com_avisos_e_lacunas():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    assert not at.exception
    tx = _textos(at)
    for k in ("5. Risco de erosão", "RELATIVOS entre os 195 pontos", "5b. Calor e chuva extrema", "5c. Chuva menos evapotranspiração",
              "NÃO o consumo da cultura", "Kc", "5d. Receita bruta por hectare", "NÃO é lucro", "valores correntes", "técnico local"):
        assert k.lower() in tx.lower() or k.lower() in " ".join(x.value.lower() for x in at.subheader), k
    assert any("Valor forrageiro" in e.label for e in at.expander)
    assert "Atenção ao rótulo" in tx and "SiBCS" in tx
    at.radio(key="prioridade").set_value("renda").run()
    assert not at.exception
    at.sidebar.radio(key="pagina").set_value("Limites dos dados").run()
    lim = _textos(at).lower()
    assert not at.exception and "o app ainda não calcula balanço hídrico" not in lim and "veja a seção própria" in lim
