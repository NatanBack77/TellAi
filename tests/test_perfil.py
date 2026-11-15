"""Perfil do agricultor: cultura opcional (sem padrão), regras duras ligadas ao motor/rotação/plano/API, campos que só registram, JSON, cartão, chat.
Dados REAIS do repositório (pulam se faltarem); a suíte bloqueia rede e usa chave falsa."""
import copy
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import cartao as CT
from src.app import ligacao_conversa as LC
from src.app import mvp as M
from src.app import perfil as P
from src.culturas.regras_duras import RegrasDuras

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "src/app/app.py")
pytestmark = pytest.mark.skipif(not (RAIZ / "data/processed/clima_diario.parquet").is_file(), reason="dados locais ausentes")
CULT = list(M.culturas_disponiveis())
PONTOS = list(M.carregar_pontos()["ponto_id"])


def _textos(at):
    partes = [m.value for m in at.markdown] + [w.value for w in at.warning] + [e.value for e in at.error] + [i.value for i in at.info] \
        + [c.value for c in at.caption] + [m.value for m in at.metric]
    return "\n".join(str(p) for p in partes)


def _alternativas(c):
    return [x["rotacao"][1] for x in c["cenarios"] if not x["atual"]]


# ------------------------------------------------------------------------------------------ cultura opcional, sem padrão
def test_sem_cultura_so_retrato_e_convite_sem_caminhos():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert at.multiselect(key="culturas").value == []                       # nenhuma cultura padrão
    t = _textos(at)
    assert "Conte no chat o que você planta" in t and "Quando o campo costuma ficar nu" in t and "250 m a 50 km" in t
    for ausente in ("Alternativa A", "3b. Rotação", "Cartão do município", "E se a chuva"):
        assert ausente not in t and not any(ausente in s.value for s in at.subheader), ausente
    assert not at.session_state["_cenario_atual"] if "_cenario_atual" in at.session_state else True
    assert len(at.get("download_button")) == 1                              # só o 'Baixar meu perfil'
    at.checkbox(key="quer_conversar").check().run()                          # 'ainda não sei' registra, mas também não cria caminhos
    assert not at.exception and "Alternativa A" not in _textos(at)


def test_escolhendo_cultura_aparecem_caminhos_e_primeira_e_a_base():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["feijao_caupi", "sorgo"]).run()      # 1ª escolha: partida a frio (o tempo é medido em outro teste)
    assert not at.exception
    t = _textos(at)
    assert "Alternativa A" in t and any("3b. Rotação" in s.value for s in at.subheader)
    assert at.session_state["_cenario_atual"][1] == "feijao_caupi"          # primeira = base dos caminhos
    assert at.session_state["_perfil"]["tambem_considero"] == ["sorgo"]
    assert at.session_state["_perfil_chat"]["tambem_considero"] == ["sorgo"]


def test_tempo_por_selecao_com_regras_abaixo_de_5s():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    for chave, valor in (("regra_nao", ["feijao_caupi"]), ("regra_incluir", ["sorgo"]), ("regra_max", 2)):
        t0 = time.perf_counter()
        (at.number_input if chave == "regra_max" else at.multiselect)(key=chave).set_value(valor).run()
        dt = time.perf_counter() - t0
        assert not at.exception and dt < 5.0, (chave, dt)


# ------------------------------------------------------------------------------------------ regras duras aplicadas
def test_alternativa_proibida_nunca_aparece_nos_tres_caminhos_rotacao_e_plano():
    base = M.calcular("quixada_ce", "milho", "sem")
    alt = _alternativas(base)[0]
    rd = RegrasDuras(proibidas=[alt])
    c = M.calcular("quixada_ce", "milho", "sem", regras=rd)
    assert alt not in _alternativas(c) and len(c["cenarios"]) == 3 and c["descartes"]["n_descartadas"] == 1
    r = M.calcular_rotacao("quixada_ce", "milho", n_sorteios=300, regras=rd)
    assert r["estrategias"] and all(alt not in [x["cultura"] for x in e["culturas"]][1:] for e in r["estrategias"])
    assert r["regras_duras"]["n_descartadas"] > 0
    pl = M.calcular_plano("quixada_ce", "milho", regras_agricultor=rd, n_sorteios=30)
    assert pl["top"] and all(alt not in x["sequencia"][1:] for x in pl["top"])


def test_precisa_incluir_e_maximo_de_seguidas():
    r = M.calcular_rotacao("quixada_ce", "milho", n_sorteios=300, regras=RegrasDuras(obrigatorias=["feijao_caupi"]))
    for e in r["estrategias"][1:]:
        assert "feijao_caupi" in [x["cultura"] for x in e["culturas"]]
    r2 = M.calcular_rotacao("quixada_ce", "milho", n_sorteios=300, regras=RegrasDuras(max_seguidas_cultura=1))
    assert r2["regras_duras"]["base_viola"]                                   # milho, milho, milho viola
    assert r2["estrategias"][0]["papel"] == "atual"                           # a rotação atual NUNCA some


def test_regras_que_descartam_tudo_mensagem_e_so_a_cultura_atual():
    todas = [c for c in CULT if c != "milho"]
    c = M.calcular("quixada_ce", "milho", "sem", regras=RegrasDuras(proibidas=todas))
    assert c["descartes"]["todas_descartadas"] and [x["rotacao"] for x in c["cenarios"]] == [["milho", "milho"]]
    r = M.calcular_rotacao("quixada_ce", "milho", n_sorteios=300, regras=RegrasDuras(proibidas=todas))
    assert r["estrategias"] == [] and r["regras_duras"]["n_descartadas"] > 0
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    at.multiselect(key="regra_nao").set_value(todas).run()
    assert not at.exception
    t = _textos(at)
    assert "descartaram TODAS" in t and "Fica só a sua rotação atual" in t
    at.multiselect(key="regra_nao").set_value([]).run()
    assert "descartaram TODAS" not in _textos(at)


def test_regras_em_conflito_param_os_caminhos_com_mensagem():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    at.multiselect(key="regra_nao").set_value(["sorgo"]).run()
    at.multiselect(key="regra_incluir").set_value(["sorgo"]).run()
    assert not at.exception and any("conflito nas suas regras" in e.value for e in at.error)
    assert "Alternativa A" not in _textos(at)


def test_tela_avisa_rotacao_atual_que_viola_a_regra_e_pousio_nao_modelado():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    at.number_input(key="regra_max").set_value(1).run()
    at.checkbox(key="regra_pousio").check().run()
    assert not at.exception
    assert any("não respeita uma das suas regras" in w.value for w in at.warning)
    assert "Pousio não é modelado" in _textos(at)


def test_sem_regra_resultado_identico():
    a = M.calcular_rotacao("quixada_ce", "milho", n_sorteios=300)
    b = M.calcular_rotacao("quixada_ce", "milho", n_sorteios=300, regras=P.regras_para_motor(RegrasDuras(aceita_pousio=True)))
    assert [e["nomes"] for e in a["estrategias"]] == [e["nomes"] for e in b["estrategias"]]
    assert [e["score_mediana"] for e in a["estrategias"]] == [e["score_mediana"] for e in b["estrategias"]]


# ------------------------------------------------------------------------------------------ só registra: sem efeito
def test_informativos_nao_mudam_o_resultado_na_tela():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect(key="culturas").set_value(["milho"]).run()
    antes = [d.value.to_dict() for d in at.dataframe]
    cen_antes = [(c["rotacao"], c["score"]) for c in M.calcular("quixada_ce", "milho", "sem")["cenarios"]]
    at.number_input(key="inf_area").set_value(12.5).run()
    at.selectbox(key="inf_mes").set_value(3).run()
    at.selectbox(key="inf_declive").set_value("forte").run()
    at.selectbox(key="inf_mercado").set_value("não").run()
    assert not at.exception
    assert [d.value.to_dict() for d in at.dataframe] == antes
    assert at.session_state["_perfil"]["informativos"] == {"area_ha": 12.5, "mes_plantio": 3, "declive": "forte", "acesso_mercado": "não"}
    assert cen_antes == [(c["rotacao"], c["score"]) for c in M.calcular("quixada_ce", "milho", "sem")["cenarios"]]
    p = P.validar({"informativos": at.session_state["_perfil"]["informativos"]}, CULT)
    assert P.regras_para_motor(P.regras_duras(p)) is None                      # informativos não viram regra


def test_comparar_epoca_so_compara_sem_recomendar():
    f = P.comparar_epoca(3, "05/02")
    assert f == "Você costuma plantar em março; para os dados do local a melhor época é fevereiro."
    assert "recomend" not in f.lower() and "deve" not in f.lower()
    assert "o mesmo mês" in P.comparar_epoca(2, "05/02") and P.comparar_epoca(None, "05/02") is None and P.comparar_epoca(3, None) is None


# ------------------------------------------------------------------------------------------ JSON do perfil
def _perfil_cheio():
    p = P.vazio()
    p.update(municipio="quixada_ce", cultura_atual="milho", tambem_considero=["sorgo"], prioridade="agua", manejo="irrigado", agua_irrigacao_mm=300,
             textura="arenoso", materia_organica="baixa", safra_2="feijao_caupi", safra_3="milho")
    p["regras"] = {"proibidas": ["gergelim"], "obrigatorias": ["feijao_caupi"], "max_seguidas_cultura": 2, "aceita_pousio": True}
    p["informativos"] = {"area_ha": 3.5, "mes_plantio": 2, "declive": "suave", "acesso_mercado": "não sei"}
    return p


def test_json_ida_e_volta_e_estado_do_app():
    p = _perfil_cheio()
    assert P.de_json(P.para_json(p), CULT, PONTOS) == p
    ss = {}
    P.para_estado(ss, p)
    assert P.do_estado(ss) == p
    assert json.loads(P.para_json(P.vazio()))["schema"] == P.SCHEMA
    assert P.de_json(P.para_json(P.vazio()), CULT, PONTOS) == P.vazio()


@pytest.mark.parametrize("mut", [
    lambda p: p.update(extra=1), lambda p: p.update(municipio="atlantida_xx"), lambda p: p.update(cultura_atual="banana_xx"),
    lambda p: p.update(prioridade="lucro"), lambda p: p.update(agua_irrigacao_mm=-5), lambda p: p.update(agua_irrigacao_mm=True),
    lambda p: p.update(agua_irrigacao_mm=float("nan")), lambda p: p["regras"].update(proibidas=["xx"]),
    lambda p: p["regras"].update(proibidas=["milho"], obrigatorias=["milho"]), lambda p: p["regras"].update(max_seguidas_cultura=0),
    lambda p: p["regras"].update(max_seguidas_cultura=True), lambda p: p["regras"].update(aceita_pousio="sim"),
    lambda p: p["regras"].update(outra=1), lambda p: p["informativos"].update(mes_plantio=13), lambda p: p["informativos"].update(area_ha=0),
    lambda p: p["informativos"].update(declive="vertical"), lambda p: p["informativos"].update(acesso_mercado=True),
    lambda p: p.update(regras=[]), lambda p: p.update(tambem_considero="sorgo"), lambda p: p.update(schema="outro.v9"),
    lambda p: p.update(cultura_atual=None, tambem_considero=["sorgo"]),
])
def test_json_invalido_e_recusado(mut):
    p = _perfil_cheio()
    mut(p)
    with pytest.raises(P.PerfilErro):
        P.validar(copy.deepcopy(p), CULT, PONTOS)


def test_json_ilegivel_grande_e_codigo_nao_executa():
    for ruim in ("{nao e json", "[]", "null", '"texto"', b"\xff\xfe\x00", "__import__('os').system('echo oi')", '{"__import__": "os"}'):
        with pytest.raises(P.PerfilErro):
            P.de_json(ruim, CULT, PONTOS)
    with pytest.raises(P.PerfilErro, match="grande demais"):
        P.de_json(json.dumps({"x": "a" * P.TAMANHO_MAX_BYTES}), CULT, PONTOS)


def test_carregar_perfil_pelo_app_aplica_nos_campos():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    P.para_estado(at.session_state, {**_perfil_cheio(), "municipio": "crato_ce"})
    at.run()
    assert not at.exception
    assert at.multiselect(key="culturas").value == ["milho", "sorgo"] and at.selectbox(key="local").value == "crato_ce"
    assert at.multiselect(key="regra_nao").value == ["gergelim"] and at.number_input(key="regra_max").value == 2


# ------------------------------------------------------------------------------------------ cartão
def test_cartao_mostra_o_que_o_agricultor_informou():
    p = _perfil_cheio()
    c = CT.montar_cartao("quixada_ce", "milho", "agua", perfil=p)
    t = CT.cartao_texto(c)
    assert "O que você informou" in t
    assert "Área do talhão: 3,5 ha" in t and P.ROTULO_SO_REGISTRA in t and "melhor época é" in t and "Culturas que você não quer plantar" in t
    assert "Pousio não é modelado" in t and "Também considero plantar" in t and "rende mais" not in t.lower()
    sem = CT.cartao_texto(CT.montar_cartao("quixada_ce", "milho", "agua"))
    assert "O que você informou" not in sem


# ------------------------------------------------------------------------------------------ API
api = TestClient(__import__("src.api.main", fromlist=["app"]).app)


def test_api_cenarios_com_regras():
    body = {"ponto_id": "quixada_ce", "cultura_atual": "milho", "prioridade": "sem", "n_sorteios": 500, "com_evidencias": False}
    base = api.post("/cenarios", json=body).json()
    assert base["regras_duras"] is None
    alt = [c["rotacao"][1] for c in base["cenarios"] if not c["atual"]][0]
    r = api.post("/cenarios", json={**body, "regras": {"proibidas": [alt], "aceita_pousio": True}})
    assert r.status_code == 200
    j = r.json()
    assert alt not in [c["rotacao"][1] for c in j["cenarios"]] and len(j["cenarios"]) == 3
    assert j["regras_duras"]["n_descartadas"] == 1 and j["regras_duras"]["nao_modelado"]
    tudo = api.post("/cenarios", json={**body, "regras": {"proibidas": [c for c in CULT if c != "milho"]}}).json()
    assert tudo["regras_duras"]["todas_descartadas"] and len(tudo["cenarios"]) == 1


@pytest.mark.parametrize("regras", [{"proibidas": ["banana_xx"]}, {"extra": 1}, {"max_seguidas_cultura": 0}, {"max_seguidas_cultura": 99},
                                    {"proibidas": "milho"}, {"proibidas": ["sorgo"], "obrigatorias": ["sorgo"]}, {"aceita_pousio": "talvez"}])
def test_api_regras_invalidas_422(regras):
    body = {"ponto_id": "quixada_ce", "cultura_atual": "milho", "prioridade": "sem", "n_sorteios": 500, "regras": regras}
    assert api.post("/cenarios", json=body).status_code == 422
    assert api.post("/rotacao", json={"ponto_id": "quixada_ce", "cultura_atual": "milho", "n_sorteios": 100, "regras": regras}).status_code == 422


def test_api_rotacao_com_regras_e_base_nunca_some():
    body = {"ponto_id": "quixada_ce", "cultura_atual": "milho", "n_sorteios": 300, "regras": {"max_seguidas_cultura": 1, "aceita_pousio": True}}
    r = api.post("/rotacao", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["estrategias"][0]["papel"] == "atual" and j["detalhes"]["regras_duras"]["base_viola"]
    assert any("Pousio não é modelado" in x for x in j["lacunas"])
    tudo = api.post("/rotacao", json={**body, "regras": {"proibidas": [c for c in CULT if c != "milho"]}}).json()
    assert tudo["estrategias"] == [] and tudo["detalhes"]["regras_duras"]["n_descartadas"] > 0


def test_api_chat_com_perfil_e_rejeita_identificador(monkeypatch):
    monkeypatch.setenv("SULCO_LLM_MODO", "template")
    perfil = {"regras": {"proibidas": ["gergelim"]}, "informativos": {"area_ha": 4, "declive": "forte"}, "textura": "arenoso"}
    r = api.post("/chat", json={"pergunta": "Por que o Sulco sugeriu esses caminhos?", "ponto_id": "quixada_ce", "cultura_atual": "milho", "perfil": perfil})
    assert r.status_code == 200
    for ruim in ({"municipio": "quixada_ce"}, {"ponto_id": "quixada_ce"}, {"nome": "Quixadá"}, {"lat": -4.9}, {"cultura_atual": "milho"},
                 {"regras": {"proibidas": ["xx"]}}, {"informativos": {"area_ha": -1}}, {"informativos": {"cidade": "x"}}):
        assert api.post("/chat", json={"pergunta": "oi", "ponto_id": "quixada_ce", "cultura_atual": "milho", "perfil": ruim}).status_code == 422, ruim


# ------------------------------------------------------------------------------------------ chat: anonimização
def test_perfil_no_prompt_sem_nenhum_identificador(tmp_path):
    from src.llm import chat as CH
    from src.llm.cache import Cache
    from src.llm.provedores import Provedor

    class Falso(Provedor):
        nome, modelo = "falso", "f1"

        def __init__(self):
            self.prompts, self.ultimo_uso = [], {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}

        def gerar(self, sistema, usuario, max_tokens=900):
            self.prompts.append(usuario)
            return "texto qualquer [F1]"

    privado = {"ponto_id": "quixada_ce", "nome": "Quixadá", "ibge": 2311405, "lat": -4.97, "lon": -39.02, "celula_power": "p1"}
    folha = {"fatos": [{"id": "F1", "tema": "caminhos", "rotulo": "caminho 1", "texto": "Caminho 1: repetir milho.", "origem": "x", "prio": 1,
                        "lacuna": False, "valor": None, "texto_simples": "Há três caminhos: repetir milho ou uma das duas alternativas."}],
             "privado": privado, "tem_cultura": True, "prioridade": "sem"}
    p = _perfil_cheio()
    pc = P.para_chat(p)
    assert not ({"municipio", "cultura_atual", "schema"} & set(pc))
    folha2 = P.folha_com_perfil(folha, pc, M.culturas_disponiveis())
    assert len(folha["fatos"]) == 1 and len(folha2["fatos"]) == 2                    # a folha original não muda
    prov = Falso()
    CH.responder_chat("Por que o Sulco sugeriu esses caminhos?", folha=folha2, modo="online", provedor=prov, cache=Cache(tmp_path))
    enviado = prov.prompts[0]
    assert "3,5 hectares" in enviado and "Gergelim" in enviado and "declive suave" in enviado          # o perfil foi
    for ident in ("quixada", "Quixadá", "2311405", "-4.97", "39.02", "lat", "lon", "municipio", "ponto_id", "perfil_sulco"):
        assert ident.lower() not in enviado.lower(), ident
    ctx = P.contexto_com_perfil({"caminhos": [{}]}, pc)
    assert "municipio" not in json.dumps(ctx["perfil_agricultor"]) and "quixada" not in json.dumps(ctx)


# ------------------------------------------------------------------------------------------ ligação com a conversa
def test_ligacao_conversa_tolerante_e_estado_para_perfil(monkeypatch):
    assert LC.ligar_conversa("oi") is None or LC.disponivel()
    r = P.estado_conversa_para_perfil({"culturas_citadas": ["milho", "banana_xx", "milho", "sorgo"], "foco": "agua"}, CULT)
    assert r == {"culturas": ["milho", "sorgo"], "prioridade": "agua"}
    assert P.estado_conversa_para_perfil({"foco": "lucro", "culturas_citadas": "milho"}, CULT) == {"culturas": []}
    assert P.estado_conversa_para_perfil(None, CULT) == {"culturas": []}
    import sys
    import types
    fake = types.ModuleType("src.llm.conversa")
    fake.responder = lambda fala, estado=None, perfil=None: {"texto": "ok", "chips": ["a", 3, "b"], "estado": {"culturas_citadas": ["milho"], "foco": None}}
    monkeypatch.setitem(sys.modules, "src.llm.conversa", fake)
    assert LC.disponivel()
    assert LC.ligar_conversa("oi", None, None) == {"texto": "ok", "chips": ["a", "b"], "estado": {"culturas_citadas": ["milho"], "foco": None}}
    fake.responder = lambda *a, **k: 1 / 0
    assert LC.ligar_conversa("oi") is None
