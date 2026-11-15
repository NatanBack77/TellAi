"""'Meu calendário' no app: lógica da linha do tempo (sem Streamlit), perfil JSON com `plantios` e AppTest da página. Hoje = 14/11/2026 (injetado). Sem rede, sem IA."""
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.app import calendario_app as CA
from src.app import mvp as M
from src.app import perfil as P
from src.culturas import calendario_plantio as CP

HOJE = date(2026, 11, 14)
APP = str(Path(__file__).resolve().parents[1] / "src/app/app.py")
CULT = list(M.culturas_disponiveis())


def calc(plantios, **dados):
    return CP.calcular("quixada_ce", plantios, HOJE, **dados)


# ------------------------------------------------------------------------------------------------ linha do tempo e lista (sem Streamlit)
def test_formulario_vira_plantio_validado_e_recusa_o_invalido():
    p = CA.novo_plantio("milho", 2, "comeco", None, 90, "sequeiro", CULT)
    assert p == {"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}, "ciclo_dias": 90, "manejo": "sequeiro"}
    assert CA.novo_plantio("sorgo", 3, None, 2025, 0, "irrigado", CULT) == {"cultura": "sorgo", "quando": {"mes": 3, "ano": 2025}, "ciclo_dias": None, "manejo": "irrigado"}
    for ruim in (("melancia", 2, None, None, None), ("milho", 13, None, None, None), ("milho", 2, None, None, 5)):
        with pytest.raises(ValueError):
            CA.novo_plantio(ruim[0], ruim[1], ruim[2], ruim[3], ruim[4], "sequeiro", CULT)


def test_juntar_plantios_nao_repete_e_limita():
    a = CA.novo_plantio("milho", 2, None, None, None, "sequeiro", CULT)
    b = CA.novo_plantio("sorgo", 3, None, None, None, "sequeiro", CULT)
    assert CA.juntar_plantios([a], [a, b], CULT) == [a, b]
    muitos = [CA.novo_plantio("milho", m, None, None, None, "sequeiro", CULT) for m in range(1, 13)] + [b]
    assert len(CA.juntar_plantios(muitos[:12], [b], CULT)) == 12
    with pytest.raises(ValueError):
        CA.juntar_plantios([{"cultura": "x", "quando": {"mes": 2}}], [], CULT)


def test_linha_do_tempo_tem_plantio_fases_colheita_janela_e_solo_nu():
    r = calc([{"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}}], blocos=set())["plantios"][0]
    rows = CA.linha_do_tempo(r, HOJE)
    etapas = [x["etapa"] for x in rows]
    assert etapas[0] == "Plantio" and etapas.count("Fases (referência)") == 4 and "Colheita esperada" in etapas and "Janela do zoneamento" in etapas
    assert all(isinstance(x["inicio"], datetime) and x["fim"] > x["inicio"] and x["etapa"] in CA.ETAPAS for x in rows)
    fases = [x for x in rows if x["etapa"] == "Fases (referência)"]
    assert [x["detalhe"] for x in fases] == ["Fase inicial", "Crescimento", "Meio do ciclo", "Fim do ciclo"]
    assert (fases[1]["inicio"] - fases[0]["inicio"]).days == 25 and (fases[-1]["fim"] - fases[0]["inicio"]).days == 140          # estágios da FAO: 25+40+45+30
    colh = [x for x in rows if x["etapa"] == "Colheita esperada"][0]
    assert colh["inicio"] == datetime(2026, 6, 6) and colh["fim"] == datetime(2026, 8, 10)
    assert sum(x["etapa"] == "Terra descoberta depois" for x in rows) <= 1
    assert "passou do ciclo" in CA.resumo_fase(r)


def test_linha_do_tempo_sem_fases_da_fao_e_com_ciclo_informado_e_planejamento():
    guandu = calc([{"cultura": "guandu", "quando": {"data": "2026-10-01"}}], blocos=set())["plantios"][0]
    g = [x for x in CA.linha_do_tempo(guandu, HOJE) if x["etapa"] == "Fases (referência)"]
    assert len(g) == 1 and g[0]["detalhe"] == "Ciclo todo (sem as fases)" and (g[0]["fim"] - g[0]["inicio"]).days == 228
    inf = calc([{"cultura": "milho", "quando": {"data": "2026-10-01"}, "ciclo_dias": 90}], blocos=set())["plantios"][0]
    assert [x for x in CA.linha_do_tempo(inf, HOJE) if x["etapa"] == "Fases (referência)"][0]["detalhe"] == "Ciclo que você informou"
    plan = calc([{"cultura": "milho", "quando": {"data": "2026-12-01"}}], blocos=set())["plantios"][0]
    assert CA.linha_do_tempo(plan, HOJE)[0]["etapa"] == "Plantio" and "Planejamento" in CA.resumo_fase(plan)
    esc = calc([{"cultura": "milho", "quando": {"data": "2029-12-01"}}], blocos=set())["plantios"][0]
    assert CA.linha_do_tempo(esc, HOJE) == [] and "mais um dado" in CA.resumo_fase(esc)


# ------------------------------------------------------------------------------------------------ perfil JSON com `plantios`
PLANTIOS = [{"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}, "ciclo_dias": 100, "manejo": "sequeiro"},
            {"cultura": "feijao_caupi", "quando": {"data": "2026-03-10"}, "ciclo_dias": None, "manejo": "sequeiro"}]


def test_perfil_guarda_e_le_plantios_com_validacao_de_schema_e_sem_identificador():
    ss = {"local": "quixada_ce", "culturas": ["milho"], "plantios": PLANTIOS}
    p = P.do_estado(ss)
    assert p["plantios"] == PLANTIOS and P.vazio()["plantios"] == []
    valido = P.validar(p, CULT, list(M.carregar_pontos()["ponto_id"]))
    txt = P.para_json(valido)
    volta = P.de_json(txt, CULT, list(M.carregar_pontos()["ponto_id"]))
    assert volta["plantios"] == PLANTIOS
    novo = {}
    P.para_estado(novo, volta)
    assert novo["plantios"] == PLANTIOS
    chat = P.para_chat(volta)
    assert chat["plantios"] == PLANTIOS and "municipio" not in chat
    assert "quixada" not in json.dumps(chat["plantios"])                  # o plantio não carrega nome, município nem coordenada
    assert P.validar({"plantios": PLANTIOS}, CULT, como_chat=True)["plantios"] == PLANTIOS


@pytest.mark.parametrize("ruim", [[{"cultura": "melancia", "quando": {"mes": 2}}], [{"cultura": "milho", "quando": {"mes": 20}}], [{"cultura": "milho", "quando": {"mes": 2}, "nome": "Zé"}],
                                  "milho", [{"cultura": "milho", "quando": {"mes": 2}, "ciclo_dias": 3}], [{"cultura": "milho", "quando": {"mes": 2}}] * 13])
def test_perfil_recusa_plantios_fora_do_schema(ruim):
    with pytest.raises(P.PerfilErro) as e:
        P.validar({"plantios": ruim}, CULT)
    assert any("plantios" in x for x in e.value.erros)
    with pytest.raises(P.PerfilErro):
        P.de_json(json.dumps({"plantios": ruim}), CULT)


def test_perfil_antigo_sem_plantios_continua_valido():
    assert P.validar({}, CULT)["plantios"] == [] and P.validar({"prioridade": "agua"}, CULT)["prioridade"] == "agua"


# ------------------------------------------------------------------------------------------------ AppTest da página
@pytest.fixture
def pagina(monkeypatch):
    monkeypatch.setattr(CA, "hoje", lambda: HOJE)
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.radio(key="pagina").set_value("Meu calendário").run()
    assert not at.exception
    return at


def textos(at):
    partes = [m.value for m in at.markdown] + [w.value for w in at.warning] + [e.value for e in at.error] + [i.value for i in at.info] + [c.value for c in at.caption] \
        + [s.value for s in at.success]
    return "\n".join(str(p) for p in partes)


def botao(at, rotulo):
    return next(b for b in at.button if b.label == rotulo)


def test_pagina_abre_sem_plantio_e_diz_que_nao_e_ordem(pagina):
    t = textos(pagina)
    assert "NÃO é ordem nem previsão" in t and "referência de OUTRAS regiões" in t and "Ainda não há plantios" in t
    assert "Meu calendário" in pagina.sidebar.radio(key="pagina").options


def test_formulario_adiciona_plantio_e_mostra_linha_do_tempo_com_lacunas_visiveis(pagina):
    pagina.selectbox(key="cal_cultura").set_value("milho")
    pagina.selectbox(key="cal_mes").set_value(2)
    pagina.radio(key="cal_parte").set_value("comeco")
    botao(pagina, "Adicionar plantio").click().run()
    assert not pagina.exception
    assert pagina.session_state["plantios"] == [{"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}, "ciclo_dias": None, "manejo": "sequeiro"}]
    t = textos(pagina)
    assert "Milho: plantado começo de fevereiro de 2026" in t and "Pela referência da FAO (de outras regiões)" in t
    assert "Sua semente pode ser diferente" in t and "zoneamento" in t and "choveram" in t and "Converse com o técnico" in t
    graficos = pagina.get("arrow_vega_lite_chart") or pagina.get("vega_lite_chart") or pagina.get("arrow_data_frame")
    assert pagina.get("arrow_vega_lite_chart") or pagina.get("vega_lite_chart"), "a linha do tempo (gráfico) não apareceu"
    assert graficos
    botao(pagina, "Tirar").click().run()
    assert pagina.session_state["plantios"] == [] and "Ainda não há plantios" in textos(pagina)


def test_ciclo_da_semente_do_formulario_sobrepoe_a_referencia(pagina):
    pagina.selectbox(key="cal_cultura").set_value("feijao_caupi")
    pagina.selectbox(key="cal_mes").set_value(3)
    pagina.number_input(key="cal_ciclo").set_value(70)
    botao(pagina, "Adicionar plantio").click().run()
    assert pagina.session_state["plantios"][0]["ciclo_dias"] == 70
    t = textos(pagina)
    assert "Pelo ciclo que você informou, de 70 dias" in t and "Sua semente pode ser diferente" not in t.split("Pelo ciclo que você informou")[1].split("\n")[0]


def test_conversa_na_pagina_entende_a_frase_e_o_botao_ver_no_calendario_traz_o_plantio(pagina):
    pagina.text_input(key="cal_fala").input("plantei sorgo em março").run()
    botao(pagina, "Enviar").click().run()
    assert not pagina.exception
    assert "Foi no começo, no meio ou no fim do mês?" in textos(pagina)
    for fala in ("meio", "não sei", "sim"):
        pagina.text_input(key="cal_fala").input(fala).run()
        botao(pagina, "Enviar").click().run()
    est = pagina.session_state["cal_estado"]
    assert est["plantios"] == [{"cultura": "sorgo", "quando": {"mes": 3, "ano": None, "parte": "meio"}, "ciclo_dias": None, "manejo": "sequeiro"}]
    assert est["ponto_id"] == "quixada_ce" and "Em que município" not in textos(pagina)        # o local vem da página: não pergunta de novo
    botao(pagina, "Ver no calendário").click().run()
    assert pagina.session_state["plantios"][0]["cultura"] == "sorgo" and "Sorgo: plantado meio de março de 2026" in textos(pagina)


def test_pagina_pergunte_mostra_o_botao_quando_a_conversa_guardou_plantios(monkeypatch):
    monkeypatch.setattr(CA, "hoje", lambda: HOJE)
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["cal_estado"] = {"plantios": [PLANTIOS[0]]}
    at.run()
    at.sidebar.radio(key="pagina").set_value("Pergunte ao Sulco").run()
    assert not at.exception
    botao(at, "Ver no calendário").click().run()
    assert at.session_state["pagina"] == "Meu calendário" and at.session_state["plantios"] == [PLANTIOS[0]]
