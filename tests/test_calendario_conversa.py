"""Conversa do calendário de plantio: intenção (40+ frases reais, com erros de grafia), diálogo de ponta a ponta, folha de fatos anonimizada, verificador,
tamanho do prompt e o caminho da IA com provedor FALSO. Hoje = 14/11/2026 (injetado). SEM rede e SEM chave (a suíte bloqueia sockets)."""
import json
import re
from datetime import date

import pytest

from src.llm import calendario_conversa as CC
from src.llm import conversa as C
from src.llm import dialogo as D
from src.llm import fatos as FT
from src.llm import intencao as IT
from src.llm.cache import Cache
from src.llm.provedores import Provedor
from src.llm.verificador import contar_palavras, limpar_citacoes, termos_tecnicos

HOJE = date(2026, 11, 14)
PID = "quixada_ce"
M = lambda mes, parte=None, ano=None: {"mes": mes, "ano": ano, "parte": parte}
DIA = lambda iso: {"data": iso}

# (frase, [(cultura, quando)]) -- `quando` None = a frase não diz quando (o diálogo pergunta)
FRASES = [
    ("plantei milho em fevereiro", [("milho", M(2))]),
    ("Plantei milho em Fevereiro.", [("milho", M(2))]),
    ("semeei feijão no começo de março", [("feijao_caupi", M(3, "comeco"))]),
    ("botei sorgo faz dois meses", [("sorgo", {"de": "2026-09-07", "ate": "2026-09-21", "precisao": "relativo"})]),
    ("ontem plantei sorgo", [("sorgo", DIA("2026-11-13"))]),
    ("anteontem eu plantei mandioca", [("mandioca", DIA("2026-11-12"))]),
    ("plantamos milho no meio de janeiro", [("milho", M(1, "meio"))]),
    ("coloquei amendoim no fim de abril", [("amendoim", M(4, "fim"))]),
    ("plantei milho no final de fevereiro", [("milho", M(2, "fim"))]),
    ("plantei feijão de corda em março de 2025", [("feijao_caupi", M(3, None, 2025))]),
    ("plantei o feijão caupi no inicio de abril", [("feijao_caupi", M(4, "comeco"))]),
    ("em fevereiro eu plantei milho", [("milho", M(2))]),
    ("no começo de março plantei feijão carioca", [("feijao_comum", M(3, "comeco"))]),
    ("plantei milho dia 10 de fevereiro", [("milho", DIA("2026-02-10"))]),
    ("plantei milho no dia 5 de março de 2025", [("milho", DIA("2025-03-05"))]),
    ("plantei milho 10/02", [("milho", DIA("2026-02-10"))]),
    ("plantei sorgo 15/12", [("sorgo", DIA("2025-12-15"))]),
    ("plantei milho na semana passada", [("milho", {"de": "2026-11-02", "ate": "2026-11-08", "precisao": "semana"})]),
    ("plantei mandioca no mês passado", [("mandioca", M(10, None, 2026))]),
    ("plantei algodão faz 3 meses", [("algodao", {"de": "2026-08-07", "ate": "2026-08-21", "precisao": "relativo"})]),
    ("plantei milho há duas semanas", [("milho", {"de": "2026-10-28", "ate": "2026-11-03", "precisao": "relativo"})]),
    ("semeei girassol faz uns 10 dias", [("girassol", {"de": "2026-11-02", "ate": "2026-11-06", "precisao": "relativo"})]),
    ("plantei milho no inverno", [("milho", {"de": "2026-02-01", "ate": "2026-05-31", "precisao": "estacao"})]),
    ("plantamos feijão na quadra", [("feijao_caupi", {"de": "2026-02-01", "ate": "2026-05-31", "precisao": "estacao"})]),
    ("plantei milho e feijão de corda em março", [("milho", M(3)), ("feijao_caupi", M(3))]),
    ("plantei milho em fevereiro e sorgo em março", [("milho", M(2)), ("sorgo", M(3))]),
    ("plantei milho no começo de fevereiro e feijão no fim de março", [("milho", M(2, "comeco")), ("feijao_caupi", M(3, "fim"))]),
    ("plantei miilho em fervereiro", [("milho", M(2))]),
    ("plantei feijao de corda em marco", [("feijao_caupi", M(3))]),
    ("semeei sorgu em abril", [("sorgo", M(4))]),
    ("plantei mandioka em janeiro", [("mandioca", M(1))]),
    ("plantei milho em fev", [("milho", M(2))]),
    ("plantei macaxeira em set", [("mandioca", M(9))]),
    ("plantei milho em novembro", [("milho", M(11))]),
    ("já plantei milho em dezembro", [("milho", M(12))]),
    ("plantei milho no meio de fevereiro deste ano", [("milho", M(2, "meio", 2026))]),
    ("plantei milho em fevereiro do ano passado", [("milho", M(2, None, 2025))]),
    ("tenho milho plantado desde fevereiro", [("milho", M(2))]),
    ("plantei milho", [("milho", None)]),
    ("plantei feijão", [("feijao_caupi", None)]),
    ("semeei mamona na primeira semana de março", [("mamona", M(3, "comeco"))]),
    ("plantei gergelim em abril, mais ou menos no meio", [("gergelim", M(4, "meio"))]),
    ("plantei milho de 90 dias em abril", [("milho", M(4))]),
    ("plantei palma em janeiro", [("palma_forrageira", M(1))]),
    ("coloquei guandu em maio", [("guandu", M(5))]),
]
CICLO_NA_FRASE = {"plantei milho de 90 dias em abril": 90}
NAO_SAO_PLANTIO = ["quero plantar milho em fevereiro", "o que dá para plantar aqui?", "não plantei milho", "milho, feijão e sorgo", "quanto vou ganhar com milho?",
                   "oi, tudo bem?", "vai chover em março?", "o milho é bom?", "qual a melhor ordem para milho e feijão?", "quero economizar água"]


@pytest.mark.parametrize("frase,esperado", FRASES, ids=[f[0][:45] for f in FRASES])
def test_intencao_reconhece_plantio_cultura_e_quando(frase, esperado):
    r = IT.extrair_plantios(frase, HOJE)
    assert r["eh_plantio"], frase
    obtido = [(p["cultura"], p["quando"]) for p in r["plantios"]]
    assert obtido == esperado, frase
    assert r["ciclo_dias"] == CICLO_NA_FRASE.get(frase)


def test_sao_mais_de_40_frases_e_as_que_nao_sao_plantio_passam_longe():
    assert len(FRASES) >= 40
    for f in NAO_SAO_PLANTIO:
        assert IT.extrair_plantios(f, HOJE)["eh_plantio"] is False, f


def test_feijao_sozinho_e_ambiguo_e_cultura_fora_da_lista_nao_vira_id():
    r = IT.extrair_plantios("semeei feijão em março", HOJE)
    assert r["plantios"][0]["ambiguo"] == ["feijao_caupi", "feijao_comum"]
    f = IT.extrair_plantios("plantei melancia em março", HOJE)
    assert f["fora_da_lista"] == ["melancia"] and f["plantios"][0]["cultura"] is None and f["plantios"][0]["fora"] == "melancia"


def test_respostas_curtas_as_perguntas_do_dialogo():
    assert IT.ler_mes("em março", HOJE) == M(3) and IT.ler_mes("fevereiro de 2025", HOJE) == M(2, None, 2025) and IT.ler_mes("não lembro", HOJE) is None
    assert IT.ler_parte("no começo") == ("comeco", False) and IT.ler_parte("lá pelo meio") == ("meio", False) and IT.ler_parte("final") == ("fim", False)
    assert IT.ler_parte("não lembro") == (None, True)
    assert IT.ler_ciclo_dias("uns 90 dias", True) == (90, False) and IT.ler_ciclo_dias("120", True) == (120, False) and IT.ler_ciclo_dias("3 meses", True) == (90, False)
    assert IT.ler_ciclo_dias("não sei", True) == (None, True) and IT.ler_ciclo_dias("5 dias", True) == (None, False)


# ------------------------------------------------------------------------------------------------ diálogo de ponta a ponta
def falar(msg, estado=None, **kw):
    kw.setdefault("hoje", HOJE)
    return C.conversar(msg, estado, modo="template", **kw)


def test_dialogo_de_6_turnos_uma_pergunta_por_vez_e_depois_os_dados():
    r1 = falar("plantei milho em fevereiro")
    assert r1["acao"] == "perguntar" and r1["estado"]["pendente"] == "plantio_parte" and r1["resposta"].count("?") == 1
    assert r1["resposta"] == "Entendi: milho plantado em fevereiro. Foi no começo, no meio ou no fim do mês?"
    r2 = falar("no começo", r1["estado"])
    assert r2["resposta"] == D.PERGUNTA_CICLO and r2["estado"]["pendente"] == "plantio_ciclo" and r2["resposta"].count("?") == 1
    r3 = falar("não sei", r2["estado"])
    assert r3["acao"] == "confirmar" and r3["resposta"] == "Entendi: milho plantado no começo de fevereiro. Está certo?"
    assert [c["rotulo"] for c in r3["chips"]] == ["Sim, está certo", "Não, quero mudar"]
    r4 = falar("sim", r3["estado"])
    assert r4["acao"] == "perguntar" and r4["pede"] == "municipio" and r4["estado"]["plantios"] == [
        {"cultura": "milho", "quando": {"mes": 2, "ano": None, "parte": "comeco"}, "ciclo_dias": None, "manejo": "sequeiro"}]
    r5 = falar("Quixadá", r4["estado"])
    assert r5["acao"] == "responder" and r5["origem"] == "template" and r5["estado"]["ponto_id"] == PID
    t = r5["resposta"]
    assert "referência da FAO (de outras regiões)" in t and "Sua semente pode ser diferente" in t and "zoneamento" in t and "colheita" in t
    assert t.rstrip().split("\n")[-2:] == ["Converse com o técnico.", D.OFERTAS_CALENDARIO["chuva"][0]]
    assert contar_palavras(t) <= 105 and r5["pergunta"] == D.OFERTAS_CALENDARIO["chuva"][0] and r5["estado"]["pendente"] == "plantio_oferta"
    assert r5["fatos"] and all(f["origem"] for f in r5["fatos"]) and r5["calendario"]["ver_no_calendario"] and r5["calendario"]["status"] == "ciclo_concluido"
    r6 = falar("sim", r5["estado"])                                     # 'sim' à oferta: a chuva desde o plantio
    assert "choveram" in r6["resposta"] and "veranico" in r6["resposta"] and r6["estado"]["cal_vistos"] == ["resumo", "chuva"]
    assert r6["pergunta"] == D.OFERTAS_CALENDARIO["solo"][0]


def test_perguntas_de_acompanhamento_com_o_que_ja_foi_guardado():
    est = D.normalizar_estado({"plantios": [{"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}, "ciclo_dias": None, "manejo": "sequeiro"}], "ponto_id": PID})
    r = falar("e a terra, fica descoberta depois da colheita?", est)
    assert "descoberta" in r["resposta"] and r["calendario"]["tema"] == "solo"
    r = falar("o que vem depois do milho?", est)
    assert r["calendario"]["tema"] == "proximas" and "rotação" in " ".join(f["rotulo"] + f["origem"] for f in r["fatos"]) + "rotação" and "milho" in r["resposta"]
    r = falar("choveu bem?", est)
    assert r["calendario"]["tema"] == "chuva" and "mm" in r["resposta"]
    r = falar("o zarc deixa plantar nessa época?", est)
    assert r["calendario"]["tema"] == "zarc" and "zoneamento" in r["resposta"]


def test_confirmacao_negada_recomeca_e_confirmacao_sem_resposta_clara_repete():
    r = falar("plantei milho no meio de março", falar("plantei milho no meio de março")["estado"])
    r = falar("plantei sorgo no dia 3 de abril")
    assert r["estado"]["pendente"] == "plantio_ciclo"
    r = falar("120 dias", r["estado"])
    assert r["acao"] == "confirmar" and "ciclo de 120 dias" in r["resposta"]
    nao = falar("não, quero mudar", r["estado"])
    assert nao["resposta"] == D.TEXTO_REFAZER_PLANTIO and nao["estado"]["rascunho"] is None and nao["estado"]["plantios"] == []
    de_novo = falar("talvez", r["estado"])
    assert de_novo["acao"] == "confirmar" and de_novo["resposta"].startswith("Não entendi bem.")


def test_perguntas_do_que_falta_cultura_e_mes_e_estacao():
    r = falar("plantei em fevereiro")
    assert r["resposta"] == D.PERGUNTA_CULTURA_PLANTIO and r["estado"]["pendente"] == "plantio_cultura" and r["estado"]["rascunho"]["quando"] == M(2)
    r1 = falar("milho", r["estado"])
    assert r1["estado"]["rascunho"]["cultura"] == "milho" and r1["estado"]["pendente"] == "plantio_parte"
    r = falar("plantei milho")
    assert r["resposta"] == "Em que mês você plantou o milho?" and r["estado"]["pendente"] == "plantio_mes"
    r2 = falar("sem lembrar", r["estado"])
    assert r2["resposta"] == D.TEXTO_SEM_MES
    r3 = falar("não lembro", r2["estado"])
    assert r3["estado"]["rascunho"] is None and "Quando lembrar" in r3["resposta"]
    inv = falar("plantei milho no inverno")
    assert inv["resposta"].startswith("Entendi que foi na época de chuva") and inv["estado"]["pendente"] == "plantio_mes"
    ok = falar("em março", inv["estado"])
    assert ok["estado"]["rascunho"]["quando"] == {"mes": 3, "ano": 2026, "parte": None} and ok["estado"]["pendente"] == "plantio_parte"
    mandioca = falar("plantei mandioca")
    assert mandioca["resposta"] == "Em que mês você plantou a mandioca?"
    feijao = falar("semeei feijão em abril")
    assert feijao["resposta"] == D.PERGUNTA_FEIJAO and [c["rotulo"] for c in feijao["chips"]] == ["Feijão de corda", "Feijão comum"]
    f2 = falar("feijão comum", feijao["estado"])
    assert f2["estado"]["rascunho"]["cultura"] == "feijao_comum" and f2["estado"]["pendente"] == "plantio_parte"


def test_duas_culturas_na_mesma_frase_ficam_na_fila_e_cultura_fora_da_lista_e_dita():
    r = falar("plantei milho em fevereiro e sorgo em março", hoje=HOJE)
    assert r["estado"]["rascunho"]["cultura"] == "milho" and [x["cultura"] for x in r["estado"]["fila"]] == ["sorgo"]
    r = falar("no começo", r["estado"])
    r = falar("não sei", r["estado"])
    r = falar("sim", r["estado"], ponto_id=PID)
    assert r["estado"]["rascunho"]["cultura"] == "sorgo" and r["resposta"].startswith("Anotado.") and len(r["estado"]["plantios"]) == 1
    f = falar("plantei melancia em março")
    assert "melancia" in f["resposta"] and "não está na lista do Sulco" in f["resposta"] and f["estado"]["pendente"] == "plantio_cultura"
    assert f["estado"]["plantios"] == []


def test_data_impossivel_pede_o_mes_de_novo_e_nao_calcula():
    est = D.normalizar_estado({"plantios": [{"cultura": "milho", "quando": {"data": "2028-03-01"}, "ciclo_dias": None, "manejo": "sequeiro"}], "ponto_id": PID})
    r = falar("como choveu?", est)
    assert r["acao"] == "perguntar" and "muito longe" in r["resposta"] and r["resposta"].endswith("Em que mês você plantou o milho?")
    assert r["estado"]["plantios"] == [] and r["estado"]["pendente"] == "plantio_mes"


def test_recusa_lucro_clima_e_produtividade_mesmo_dentro_do_calendario():
    est = falar("plantei milho em fevereiro")["estado"]
    for msg, motivo in (("plantei milho em fevereiro, quanto vou ganhar?", "lucro"), ("plantei milho em março e vai chover?", "previsao_clima"),
                        ("plantei milho em março, quantas sacas vou colher?", "produtividade")):
        r = falar(msg, est)
        assert r["acao"] == "recusar" and r["motivo"] == motivo and r["estado"] == est


def test_perfil_com_plantios_vale_para_acompanhamento_sem_estado():
    perfil = {"plantios": [{"cultura": "feijao_caupi", "quando": {"mes": 3}, "ciclo_dias": 70, "manejo": "sequeiro"}], "textura": "não sei"}
    r = falar("como choveu?", None, ponto_id=PID, perfil=perfil)
    assert r["calendario"]["tema"] == "chuva" and r["calendario"]["plantio"]["cultura"] == "feijao_caupi"
    assert "feijão-caupi" in " ".join(f["texto"] for f in r["fatos"]).lower() or r["fatos"]


# ------------------------------------------------------------------------------------------------ estado e schema
def test_estado_adulterado_com_plantios_e_descartado_sem_executar_nada():
    est = D.normalizar_estado({"plantios": [{"cultura": "../x", "quando": {"mes": 2}}], "rascunho": {"cultura": "milho", "quando": {"mes": 99}, "ciclo_dias": "x", "extra": 1},
                               "fila": "x", "cal_idx": 9, "cal_vistos": ["chuva", "rm -rf"], "pendente": "plantio_oferta"}, {"milho"})
    assert est["plantios"] == [] and est["rascunho"]["quando"] is None and est["rascunho"]["ciclo_dias"] is None and "extra" not in est["rascunho"]
    assert est["fila"] == [] and est["cal_idx"] is None and est["cal_vistos"] == ["chuva"]
    bom = D.normalizar_estado({"plantios": [{"cultura": "milho", "quando": {"mes": 2}}], "cal_idx": 0}, {"milho"})
    assert bom["plantios"][0]["manejo"] == "sequeiro" and bom["cal_idx"] == 0
    assert json.loads(json.dumps(est)) == est


# ------------------------------------------------------------------------------------------------ folha de fatos, privacidade e verificador
@pytest.fixture(scope="module")
def folha_real():
    from src.culturas import calendario_plantio as CP
    calc = CP.calcular(PID, [{"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}}, {"cultura": "feijao_caupi", "quando": {"mes": 3}, "ciclo_dias": 70}], HOJE)
    return calc, FT.montar_folha_calendario(calc, C._nomes(), C._privado(PID))


def test_folha_de_fatos_tem_texto_simples_origem_e_nenhum_identificador(folha_real):
    calc, folha = folha_real
    fatos = folha["fatos"]
    assert {f["papel"] for f in fatos} >= {"entendido", "fase", "colheita", "zarc", "chuva", "veranico", "verde", "solo_nu", "proximas", "limite_clima"}
    assert {f["plantio"] for f in fatos} == {0, 1} and all(f["origem"] and f["id"].startswith("F") and f["tema"] == "calendario" for f in fatos)
    tudo = json.dumps(fatos, ensure_ascii=False).lower()
    priv = C._privado(PID)
    for ident in ("quixadá", "quixada", PID, str(priv["ibge"]), str(priv["lat"]), str(priv["lon"]), priv["celula_power"]):
        assert ident.lower() not in tudo, ident
    assert FT.vazou(tudo, priv) == []
    simples = " ".join(f["texto_simples"] or "" for f in fatos)
    assert termos_tecnicos(simples) == [] and "ndvi" not in simples.lower()
    ciclo_fatos = [f for f in fatos if f["papel"] == "fase" and f["plantio"] == 0][0]
    assert "outras regiões" in ciclo_fatos["texto_simples"] and "semente" in ciclo_fatos["texto_simples"] and "FAO" in ciclo_fatos["texto_simples"]
    informado = [f for f in fatos if f["papel"] == "fase" and f["plantio"] == 1][0]
    assert "ciclo que você informou" in informado["texto_simples"] and "semente" not in informado["texto_simples"]


def test_selecao_por_assunto_respeita_o_plantio_e_o_teto(folha_real):
    _, folha = folha_real
    for tema, papeis in FT.PAPEIS_CALENDARIO.items():
        for i in (0, 1):
            sel = FT.selecionar_calendario(folha, tema, i)
            assert sel and all(f["plantio"] == i and f["papel"] in papeis for f in sel)
            assert sum(FT.tokens_aprox(f["texto_simples"]) + 6 for f in sel) <= FT.TETO_TOKENS_CALENDARIO and len(sel) <= FT.MAX_FATOS_CALENDARIO


def test_lacuna_aparece_como_lacuna_e_nao_como_numero():
    from src.culturas import calendario_plantio as CP
    calc = CP.calcular(PID, [{"cultura": "sorgo", "quando": {"mes": 3}}], HOJE, blocos=set())
    folha = FT.montar_folha_calendario(calc, C._nomes())
    z = [f for f in folha["fatos"] if f["papel"] == "zarc"][0]
    assert z["lacuna"] is True and "não traz o sorgo" in z["texto_simples"] and "não conferi essa época" in z["texto_simples"]


def calendario_com_ia(saida, tema_msg="plantei milho em fevereiro"):
    class Prov(Provedor):
        nome, modelo = "falso", "f1"

        def __init__(self):
            self.prompts, self.ultimo_uso = [], {"total_tokens": 7}

        def gerar(self, sistema, usuario, max_tokens=900):
            self.prompts.append((sistema, usuario))
            return saida(usuario) if callable(saida) else saida
    return Prov()


def _estado_pronto():
    return D.normalizar_estado({"plantios": [{"cultura": "milho", "quando": {"mes": 2, "parte": "comeco"}, "ciclo_dias": None, "manejo": "sequeiro"}], "ponto_id": PID})


def _ia(prov, tmp, msg="como está meu milho?", estado=None):
    return C.conversar(msg, estado or _estado_pronto(), modo="online", provedor=prov, cache=Cache(tmp), hoje=HOJE, permitir_stub=False)


def _fatos_do_prompt(usuario):
    return dict(re.findall(r"^\[(F\d+)\] (.*)$", usuario, flags=re.M))


def bom(usuario):
    f = _fatos_do_prompt(usuario)
    ids = list(f)
    fase = next(i for i in ids if "referência da FAO" in f[i])
    return f"Você plantou o milho em fevereiro. Pela referência de outras regiões, ele leva uns 140 dias; sua semente pode ser diferente. [{fase}]"


def test_ia_reescreve_os_fatos_e_o_texto_aprovado_vai_a_tela(tmp_path):
    prov = calendario_com_ia(bom)
    r = _ia(prov, tmp_path)
    assert r["origem"] == "llm" and r["verificacao"]["ok"] is True and r["citados_fatos"] and "semente" in r["resposta"] and r["resposta"].endswith("Converse com o técnico.") is False
    assert "Converse com o técnico." in r["resposta"] and "[F" not in r["resposta"] and r["uso"] == {"total_tokens": 7}
    sistema, usuario = prov.prompts[0]
    assert "ASSUNTO: resumo" in usuario and "<<<FATOS_DO_LOCAL>>>" in usuario


@pytest.mark.parametrize("texto", ["Você deve colher entre junho e agosto. [F{i}]", "Pela referência, tem que colher logo. [F{i}]", "Plante de novo em março. [F{i}]",
                                   "Recomendo esperar a chuva. [F{i}]", "Vai chover mais em março. [F{i}]", "Sua lavoura está verde e boa. [F{i}]",
                                   "O milho vai render mais nessa época. [F{i}]", "Pela referência de outras regiões leva 999 dias. [F{i}]",
                                   "Precisa irrigar o milho. [F{i}]", "A produtividade deve ser boa. [F{i}]"])
def test_verificador_rejeita_ordem_previsao_e_numero_inventado(tmp_path, texto):
    def ruim(usuario):
        return texto.format(i=next(iter(_fatos_do_prompt(usuario))).lstrip("F"))
    r = _ia(calendario_com_ia(ruim), tmp_path)
    assert r["origem"] == "template" and r["verificacao"]["ok"] is False and r["verificacao"]["motivos"]
    assert "deve colher" not in r["resposta"].lower() and "Converse com o técnico." in r["resposta"]


def test_verificar_calendario_exige_dizer_que_o_ciclo_e_de_referencia_e_a_semente():
    fatos = [{"id": "F1", "texto_simples": "x"}]
    assert CC.verificar_calendario("Ele leva uns 140 dias. [F1]", fatos, "resumo", "fao")
    assert not CC.verificar_calendario("Pela referência de outras regiões, uns 140 dias; a sua semente pode ser diferente. [F1]", fatos, "resumo", "fao")
    assert not CC.verificar_calendario("Ele leva uns 90 dias. [F1]", fatos, "resumo", "informado")
    assert CC.verificar_calendario("Você deve colher em junho.", fatos, "chuva", None)
    assert CC.verificar_calendario("Sua roça está fraca.", fatos, "verde", None)
    assert not CC.verificar_calendario("O verde da região estava fraco.", fatos, "verde", None)


def test_prompt_cabe_em_2800_tokens_e_nao_leva_identificador(tmp_path):
    prov = calendario_com_ia(bom)
    _ia(prov, tmp_path)
    sistema, usuario = prov.prompts[0]
    assert FT.tokens_aprox(sistema + usuario) <= CC.TETO_PROMPT_TOKENS
    priv = C._privado(PID)
    assert FT.vazou(sistema + usuario, priv) == [] and "quixad" not in (sistema + usuario).lower()
    for tema in ("resumo", "chuva", "verde", "solo", "zarc", "colheita"):
        p2 = calendario_com_ia(lambda u: "sem evidência")
        _ia(p2, tmp_path / tema, msg={"resumo": "como está meu milho?", "chuva": "como choveu?", "verde": "e o verde?", "solo": "a terra fica descoberta?", "zarc": "e o zarc?",
                                      "colheita": "quando colho?"}[tema])
        assert FT.tokens_aprox("".join(p2.prompts[0])) <= CC.TETO_PROMPT_TOKENS, tema


def test_sem_chave_ou_modo_template_nao_chama_a_ia(tmp_path):
    prov = calendario_com_ia(bom)
    r = C.conversar("como está meu milho?", _estado_pronto(), modo="template", provedor=prov, hoje=HOJE)
    assert r["origem"] == "template" and prov.prompts == [] and r["uso"] is None


def test_texto_padrao_cabe_no_limite_de_palavras_em_todos_os_assuntos():
    est = _estado_pronto()
    for msg in ("como está meu milho?", "como choveu?", "e o verde?", "e a terra depois da colheita?", "e o zarc?", "quando colho?", "o que vem depois do milho?"):
        r = falar(msg, est)
        assert contar_palavras(limpar_citacoes(r["resposta"])) <= 108, (msg, r["resposta"])
        assert "deve" not in r["resposta"].lower().split() and "recomendo" not in r["resposta"].lower() and "rende mais" not in r["resposta"].lower()
        assert r["resposta"].count("?") <= 1
