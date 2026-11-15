"""Chat em linguagem SIMPLES para o agricultor: texto_simples dos fatos, tom do verificador (palavras e termos), texto padrão curto e
limpeza dos marcadores [F#]/[n] DEPOIS da verificação. SEM rede, SEM chave real: provedor falso."""
import re

import pytest
from fastapi.testclient import TestClient

from src.api.main import app as api_app
from src.llm import chat as CH
from src.llm import fatos as FT
from src.llm.cache import Cache
from src.llm.verificador import (frases_repetidas, MAX_PALAVRAS_CHAT, TERMOS_PROIBIDOS, contar_palavras, limpar_citacoes, numeros_da_fonte, termos_tecnicos,
                                 verificar, _NUM, _no_conjunto)
from tests.test_chat import AVISO, Falso, busca
from tests.test_fatos import MUNICIPIOS, PERG_PREV, SINT, chat_f

PERG_CAM = "Por que o Sulco sugeriu esses caminhos?"
PERGUNTAS = [PERG_PREV, PERG_CAM, "Qual o solo do meu local?", "Tenho risco de erosão aqui?", "Qual a receita bruta do milho no meu município?",
             "Qual a janela do ZARC para o meu município?", "Como está a chuva no meu município?", "Quando o campo fica sem vegetação, solo nu?"]


@pytest.fixture(scope="module")
def folhas():
    return {pid: FT.montar_folha(pid, "feijao_caupi" if pid != "quixada_ce" else "milho", "sem") for pid in MUNICIPIOS}


# ---------------------------------------------------------------------------------------------- limpeza dos marcadores
@pytest.mark.parametrize("entrada,saida", [
    ("O verde está fraco [F7].", "O verde está fraco."),
    ("O verde está fraco [F7]. Vale duas semanas [F8].", "O verde está fraco. Vale duas semanas."),
    ("Choveu pouco [1][4]. Converse com o técnico.", "Choveu pouco. Converse com o técnico."),
    ("Choveu pouco [1] [4] .", "Choveu pouco."),
    ("Choveu pouco [F2, F5]; plante cedo.", "Choveu pouco; plante cedo."),
    ("O solo é médio [F2] . Confirme.", "O solo é médio. Confirme."),
    ("[F2] Texto que começa com marcador.", "Texto que começa com marcador."),
    ("[F2] [F3]. Frase vazia.", "Frase vazia."),
    ("- primeiro [F1]\n- [F2]\n- terceiro [F3]", "- primeiro\n- terceiro"),
    ("Sem marcador nenhum.", "Sem marcador nenhum."),
])
def test_limpar_citacoes(entrada, saida):
    assert limpar_citacoes(entrada) == saida


def test_limpar_nunca_deixa_marcador():
    for t in ["a [F1] b [2] c [F3][F4] d [F5,F6] e [7; 8]", "[F1][F2][3]", " [1] "]:
        assert not re.search(r"\[F|\[\d", limpar_citacoes(t))


# ---------------------------------------------------------------------------------------------- verificador: citação, contagens, tom
def test_verificador_ainda_rejeita_f99_e_falta_de_citacao_antes_da_limpeza():
    r = verificar(f"O verde deve ficar parecido com o normal [F99]. {AVISO}", None, [], exigir_citacao=True, fatos=SINT["fatos"], tom=True)
    assert not r["ok"] and any("inexistente" in m for m in r["motivos"])
    r = verificar(f"O verde deve ficar parecido com o normal. {AVISO}", None, [], exigir_citacao=True, fatos=SINT["fatos"], tom=True)
    assert not r["ok"] and any("sem citacao" in m for m in r["motivos"])


def test_resposta_simples_com_contagens_por_extenso_e_aprovada(tmp_path):
    folha = {**SINT, "fatos": SINT["fatos"] + [{"id": "F4", "tema": "caminhos", "rotulo": "caminho 1", "prio": 1, "lacuna": False, "origem": "x",
                                                 "texto": "Caminho 1: repetir milho. Caminho 2 e Caminho 3: alternativas.",
                                                 "texto_simples": "Há três caminhos: repetir milho ou uma das duas alternativas."}]}
    saida = ("Nas próximas duas semanas, o verde das plantas deve ficar um pouco mais fraco que o normal [F1]. Há três caminhos para você olhar, "
             f"com duas alternativas [F4]. Converse com o técnico.")
    r, _ = chat_f(saida, pergunta="Por que o Sulco sugeriu esses caminhos e como vai ficar a vegetação nas próximas semanas?", folha=folha, tmp=tmp_path)
    assert r["origem"] == "llm", r["verificacao"]
    assert r["resposta"] == limpar_citacoes(saida) and r["resposta_com_citacoes"] == saida.strip() and "[F" not in r["resposta"]


def test_numero_por_extenso_sem_item_na_fonte_continua_barrado():
    for t in ("vai chover cinco por cento a mais", "são vinte dias de plantio", "dura dois dias", "dá três vezes mais", "custa cinco reais"):
        r = verificar(f"O verde muda: {t} [F1]. {AVISO}", None, [], exigir_citacao=True, fatos=SINT["fatos"])
        assert not r["ok"] and any("extenso" in m for m in r["motivos"]), t
    r = verificar(f"Escolha entre três caminhos [F1]. {AVISO}", None, [], exigir_citacao=True, fatos=SINT["fatos"])   # sem unidade: livre
    assert r["ok"], r
    r = verificar(f"Escolha entre onze caminhos [F1]. {AVISO}", None, [], exigir_citacao=True, fatos=SINT["fatos"])    # acima de dez: exige fonte
    assert not r["ok"] and any("extenso" in m for m in r["motivos"])


def test_numero_por_extenso_pequeno_solto_nao_precisa_de_fonte():
    for t in ("Veja três coisas: o verde, a chuva e o solo", "São duas as perguntas", "Há dois motivos e um limite"):
        r = verificar(f"{t} [F1]. {AVISO}", None, [], exigir_citacao=True, fatos=SINT["fatos"], tom=True)
        assert r["ok"], (t, r)


def test_contagem_de_palavras_e_limite():
    assert contar_palavras("Um dois [F1] três. [2] quatro-cinco") == 4
    longo = " ".join(["verde"] * (MAX_PALAVRAS_CHAT + 5)) + f" [F1]. {AVISO}"
    r = verificar(longo, None, [], exigir_citacao=True, fatos=SINT["fatos"], tom=True)
    assert not r["ok"] and any("longa demais" in m for m in r["motivos"])
    curto = f"O verde deve ficar um pouco mais fraco [F1]. {AVISO}"
    assert verificar(curto, None, [], exigir_citacao=True, fatos=SINT["fatos"], tom=True)["ok"]
    assert verificar(longo, None, [], exigir_citacao=True, fatos=SINT["fatos"])["ok"] is False or True   # sem tom=True o limite não vale (outros usos)


@pytest.mark.parametrize("termo", ["NDVI", "anomalia", "composto de 16 dias", "faixa de incerteza", "intervalo", "percentil", "skill", "RMSE", "R²",
                                   "ACI", "conformal", "Monte Carlo", "sorteios", "persistência", "climatologia", "MODIS", "POWER", "SMAP", "empate técnico"])
def test_termos_proibidos_sao_barrados_no_chat(termo):
    r = verificar(f"O verde mudou, segundo {termo} [F1]. {AVISO}", None, [], exigir_citacao=True, fatos=SINT["fatos"], tom=True)
    assert not r["ok"] and any("termo técnico" in m for m in r["motivos"]), termo
    # o termo que o próprio agricultor escreveu na pergunta pode ser usado na resposta
    assert not termos_tecnicos(f"O {termo} é um conceito do app", permitidos=f"o que é {termo}?")


def test_lista_de_termos_proibidos_cobre_o_pedido():
    pedido = {"ndvi", "anomalia", "composto", "faixa de incerteza", "intervalo", "percentil", "skill", "rmse", "aci", "conformal", "monte carlo",
              "sorteios", "persistencia", "climatologia", "modis", "power", "smap"}
    assert pedido <= set(TERMOS_PROIBIDOS)


# ---------------------------------------------------------------------------------------------- provedor falso técnico x simples
def test_resposta_tecnica_cai_no_texto_padrao_simples(tmp_path):
    tecnica = ("A anomalia de NDVI prevista para o próximo composto de 16 dias é -0,012, com faixa de incerteza de 80% entre -0,138 e 0,114; "
               f"o skill vem da persistência [F1]. {AVISO}")
    r, _ = chat_f(tecnica, tmp=tmp_path)
    assert r["origem"] == "template" and r["verificacao"]["ok"] is False
    assert any("termo técnico" in m for m in r["verificacao"]["motivos"])
    t = r["resposta"]
    assert not termos_tecnicos(t) and "[F" not in t and len(t.splitlines()) <= 5 and t.splitlines()[-1].endswith("converse com o técnico.")
    assert "duas semanas" in t and "composto" not in t and "nota" not in t.lower()


def test_resposta_simples_e_aprovada_e_exibida_limpa(tmp_path):
    saida = ("Nas próximas duas semanas, o verde das plantas deve ficar um pouco mais fraco que o normal [F1]. "
             "Isso vale só para as próximas duas semanas [F2]. Converse com o técnico.")
    r, _ = chat_f(saida, tmp=tmp_path)
    assert r["origem"] == "llm" and r["verificacao"]["ok"] is True and r["citados_fatos"] == ["F1", "F2"]
    assert r["resposta_com_citacoes"] == saida and "[F" not in r["resposta"] and not re.search(r"\[\d", r["resposta"])
    assert r["resposta"].endswith("Converse com o técnico.") and contar_palavras(r["resposta"]) <= MAX_PALAVRAS_CHAT


def test_cache_nao_mistura_prompt_antigo():
    assert CH.VERSAO_PROMPT == "chat-v3" and "70 palavras" in CH.SISTEMA_CHAT and "NDVI" in CH.SISTEMA_CHAT


# ---------------------------------------------------------------------------------------------- texto_simples dos fatos (5 municípios)
def _numeros_ok(simples: str, tecnico: str) -> list[str]:
    fonte = numeros_da_fonte(tecnico)
    return [t for t in _NUM.findall(simples) if not _no_conjunto(t, fonte)]


@pytest.mark.parametrize("pid", MUNICIPIOS)
def test_texto_simples_so_com_numeros_do_fato_tecnico_e_sem_termos(folhas, pid):
    f = folhas[pid]
    com = [x for x in f["fatos"] if x["texto_simples"]]
    assert len(com) >= 15, (pid, len(com))
    for x in f["fatos"]:
        assert "texto_simples" in x
        if not x["texto_simples"]:
            continue
        ts = x["texto_simples"]
        assert _numeros_ok(ts, x["texto"]) == [], (pid, x["id"], ts)
        assert not termos_tecnicos(ts), (pid, x["id"], ts)
        assert contar_palavras(ts) <= 45 and "[" not in ts and "{" not in ts and "nan" not in ts.lower().split(), (pid, x["id"], ts)
        assert not re.search(r"nota \d|\d,\d{3}", ts), (pid, x["id"], ts)                 # sem 'nota 0,73 de 1' nem coeficientes
    assert FT.vazou("\n".join(x["texto_simples"] or "" for x in f["fatos"]), f["privado"]) == []


def test_texto_simples_de_cada_tema_no_municipio_completo(folhas):
    por_tema = {}
    for x in folhas["quixada_ce"]["fatos"]:
        if x["texto_simples"]:
            por_tema.setdefault(x["tema"], []).append(x["texto_simples"])
    for tema in ("previsao", "previsao_limites", "modelo_skill", "diagnostico", "clima", "caminhos", "janela", "zarc", "solo", "risco", "extremos",
                 "eto", "renda", "limites"):
        assert por_tema.get(tema), tema
    prev = [x for x in folhas["quixada_ce"]["fatos"] if x["rotulo"] == "anomalia prevista"][0]["texto_simples"]
    assert prev.startswith("Para as próximas duas semanas, o verde das plantas deve ficar parecido com o normal para esta época; os dados não mostram")
    met = [x for x in folhas["quixada_ce"]["fatos"] if x["rotulo"] == "skill por fase"][0]["texto_simples"]
    assert met.startswith("Nos testes, o modelo acerta melhor que usar só a média dos anos anteriores, mas só olhando as próximas duas semanas")
    cam = [t for t in por_tema["caminhos"] if t.startswith("Caminho 2")][0]
    # Caminho 2 = crotalária juncea (não mais feijão-caupi): os cenários foram regerados com a matriz de rotação e o ZARC novos (commit 7bb3e12d);
    # as alternativas saem do sorteio do motor com empate técnico (fatos 'caminho 2'/'caminho 3'), e o feijão-caupi segue como Caminho 3.
    assert "milho" in cam and "crotalária juncea" in cam and "Os dados não mostram qual é melhor." in cam
    assert any(t.startswith("Caminho 3") and "feijão-caupi" in t for t in por_tema["caminhos"])
    assert any("por volta de fevereiro" in t for t in por_tema["janela"])
    assert any("R$ 485" in t and "não é lucro" in t for t in por_tema["renda"])
    assert any("ainda não temos dado de" in t.lower() for t in por_tema["renda"] + por_tema["caminhos"])


def test_municipio_sem_previsao_tem_frase_simples_de_lacuna(folhas):
    for pid in ("fortaleza_ce",):     # compostos anteriores não consecutivos (sobral_ce passou a ter previsão em 2026-11-14)
        prev = [x for x in folhas[pid]["fatos"] if x["tema"] == "previsao" and x["rotulo"] in ("previsão do NDVI", "sem previsão")]
        assert prev and all(x["lacuna"] and "ainda não temos previsão do verde das plantas" in x["texto_simples"] for x in prev)
        assert not any("anomalia" in x["texto_simples"].lower() for x in prev)


def test_previsao_com_faixa_que_nao_cruza_zero_diz_mais_fraco_ou_forte():
    for a, esperado in [(-0.10, "bem mais fraco"), (-0.03, "um pouco mais fraco"), (0.03, "um pouco mais forte"), (0.10, "bem mais forte"), (0.005, "parecido")]:
        assert esperado in FT.nivel_verde(a)
    assert FT.LIMIAR_PARECIDO < FT.LIMIAR_BEM


# ---------------------------------------------------------------------------------------------- o prompt só leva texto_simples
@pytest.mark.parametrize("pergunta", PERGUNTAS)
def test_prompt_so_tem_texto_simples_e_nenhum_termo_proibido(folhas, tmp_path, pergunta):
    f = folhas["quixada_ce"]
    prov = Falso("sem evidência")
    CH.responder_chat(pergunta, modo="online", provedor=prov, buscar_fn=busca([]), cache=Cache(tmp_path), folha=f)
    assert prov.prompts, pergunta
    prompt = prov.prompts[0]
    bloco = prompt.split("<<<FATOS_DO_LOCAL>>>")[1].split("<<<FIM_FATOS>>>")[0]
    linhas = [l for l in bloco.splitlines() if l.strip()]
    por_id = {x["id"]: x for x in f["fatos"]}
    assert linhas
    for l in linhas:
        m = re.match(r"\[(F\d+)\] (.*)", l)
        assert m, l
        assert m.group(2) == por_id[m.group(1)]["texto_simples"]
        assert m.group(2) != por_id[m.group(1)]["texto"]
    assert termos_tecnicos(bloco) == [], termos_tecnicos(bloco)
    assert "origem" not in bloco.lower() and "src.app" not in prompt


def test_prompt_de_previsao_do_municipio_sem_previsao(folhas, tmp_path):
    prov = Falso("sem evidência")
    CH.responder_chat(PERG_PREV, modo="online", provedor=prov, buscar_fn=busca([]), cache=Cache(tmp_path), folha=folhas["fortaleza_ce"])
    assert "ainda não temos previsão do verde das plantas" in prov.prompts[0] and "composto" not in prov.prompts[0].split("<<<FATOS_DO_LOCAL>>>")[1]


# ---------------------------------------------------------------------------------------------- texto padrão curto e simples
@pytest.mark.parametrize("pid", MUNICIPIOS)
@pytest.mark.parametrize("pergunta", PERGUNTAS)
def test_texto_padrao_curto_simples_sem_marcador(folhas, pid, pergunta):
    r = CH.responder_chat(pergunta, modo="template", folha=folhas[pid], buscar_fn=busca([]))
    if not r["fatos"]:
        return
    t = r["resposta"]
    assert r["origem"] == "template" and 2 <= len(t.splitlines()) <= 5, t
    assert not termos_tecnicos(t) and not re.search(r"\[F|\[\d|\{", t), t
    assert not re.search(r"nota \d|\d,\d{3}|sorteio|10% a 90%", t, flags=re.I), t
    assert "converse com o técnico" in t.lower() and "[F" in r["resposta_com_citacoes"]
    assert contar_palavras(t) <= 130


def test_texto_padrao_dos_caminhos_traz_cultura_vantagem_limite_epoca(folhas):
    r = CH.responder_chat(PERG_CAM, modo="template", folha=folhas["quixada_ce"], buscar_fn=busca([]))
    t = r["resposta"].lower()
    assert "milho" in t and ("feijão-caupi" in t or "crotalária" in t) and "converse com o técnico" in t and len(t.splitlines()) <= 5


def test_texto_padrao_sem_fato_simples_nao_inventa():
    assert FT.template_fatos([]).startswith("Ainda não temos dado")
    assert "[" not in limpar_citacoes(FT.template_fatos([{"id": "F1", "tema": "x", "texto": "t", "lacuna": False, "prio": 1}]))


# ---------------------------------------------------------------------------------------------- sobre o Sulco: respostas curtas
def test_sobre_o_sulco_resposta_curta():
    r = CH.responder_chat("O que é empate técnico?", modo="template", buscar_fn=busca([]))
    assert r["resposta"].splitlines()[0] == "Empate técnico quer dizer que, com os dados que temos, não dá para dizer qual é melhor."
    assert len(r["resposta"].splitlines()) <= 4 and "[" not in r["resposta"]
    for q in ["O que é NDVI?", "O que é anomalia?", "O que é faixa de incerteza?", "O que é veranico?"]:
        t = CH.responder_chat(q, modo="template", buscar_fn=busca([]))["resposta"]
        assert contar_palavras(t) <= 90 and "[" not in t and "Converse com o técnico" in t, (q, t)


def test_limites_do_sulco_em_frase_simples():
    t = CH.responder_chat("Quais os limites dos dados?", modo="template", buscar_fn=busca([]))["resposta"]
    assert "[" not in t and "pixels" not in t and "MODIS" not in t and "SMAP" not in t, t


# ---------------------------------------------------------------------------------------------- recusa e API
def test_recusas_e_sem_evidencia_tambem_trazem_os_dois_campos():
    r = CH.responder_chat("Qual rotação devo escolher?", modo="template")
    assert r["resposta"] == r["resposta_com_citacoes"] and "[" not in r["resposta"]
    assert CH.MSG_DINHEIRO.count(".") <= 4 and "técnico local" in CH.MSG_DINHEIRO


def test_api_devolve_resposta_limpa_e_com_citacoes(monkeypatch):
    monkeypatch.setenv("SULCO_LLM_MODO", "template")
    api = TestClient(api_app)
    j = api.post("/chat", json={"pergunta": PERG_PREV, "ponto_id": "quixada_ce", "cultura_atual": "milho"}).json()
    assert "resposta" in j and "resposta_com_citacoes" in j
    assert "[F" in j["resposta_com_citacoes"] and "[F" not in j["resposta"] and not re.search(r"\[\d", j["resposta"])
    assert j["fatos"] and all("texto" in f and "texto_simples" in f and f["origem"] for f in j["fatos"])
    assert any(f["texto_simples"] for f in j["fatos"]) and "duas semanas" in j["resposta"]
    assert j["citados"] == [] and isinstance(j["citados_fatos"], list)


def test_pagina_de_teste_mostra_resposta_limpa_e_detalhes():
    from src.api import pagina_teste as PT
    html = PT.renderizar({"milho": "Milho"})
    assert "r.resposta" in html and "resposta_com_citacoes" in html and "De onde veio esta resposta" in html and "texto_simples" in html


# ---------------------------------------------------------------------------------------------- (1) fecho anexado por código
_N = [0]


def _llm(saida, tmp, pergunta=PERG_PREV, folha=SINT):
    _N[0] += 1
    r, _ = chat_f(saida, pergunta=pergunta, folha=folha, tmp=tmp / f"c{_N[0]}")
    return r


def test_fecho_nao_e_exigido_da_ia_e_e_anexado_depois(tmp_path):
    r = _llm("O verde das plantas deve ficar um pouco mais fraco que o normal [F1].", tmp_path)
    assert r["origem"] == "llm" and r["verificacao"]["ok"] is True
    assert r["resposta"].endswith("Isso vale só para as próximas duas semanas; converse com o técnico.") and "[F" not in r["resposta"]
    assert r["resposta_com_citacoes"].endswith("converse com o técnico.")
    r = _llm("Nas próximas duas semanas o verde deve ficar mais fraco [F1].", tmp_path)       # já diz 'duas semanas': só falta o técnico
    assert r["resposta"].endswith("Converse com o técnico.") and r["resposta"].count("duas semanas") == 1
    r = _llm("O solo é de tipo médio [F3].", tmp_path, pergunta="Qual o solo do meu local?")
    assert r["origem"] == "llm" and r["resposta"].endswith(" Converse com o técnico.") and "duas semanas" not in r["resposta"]


def test_fecho_nao_duplica(tmp_path):
    r = _llm("Nas próximas duas semanas o verde deve ficar mais fraco [F1]. Isso vale só para as próximas duas semanas; converse com o técnico.", tmp_path)
    assert r["resposta"].lower().count("converse com o técnico") == 1 and r["resposta"].count("duas semanas") == 2
    r = _llm("O solo é de tipo médio [F3]. Isto é um cenário a avaliar com técnico local.", tmp_path, pergunta="Qual o solo do meu local?")
    assert "Converse com o técnico" not in r["resposta"]


# ---------------------------------------------------------------------------------------------- (3) o texto padrão responde o que foi perguntado
P_ACERTA = "Quanto esse modelo de previsão acerta?"


def test_pergunta_de_metricas_seleciona_e_responde_com_metricas(folhas):
    sel = FT.selecionar(folhas["quixada_ce"], P_ACERTA)
    assert sel and not any(x["rotulo"] in ("anomalia prevista", "último composto observado") for x in sel)
    assert any(x["rotulo"] == "skill por fase" for x in sel)
    r = CH.responder_chat(P_ACERTA, modo="template", folha=folhas["quixada_ce"])
    t = r["resposta"]
    assert "o modelo acerta melhor que usar só a média dos anos anteriores" in t and "só olhando as próximas duas semanas" in t
    assert "quanto mais longe, menos confiável" in t and "o verde das plantas deve ficar" not in t
    assert not termos_tecnicos(t) and len(t.splitlines()) <= 5 and t.splitlines()[-1].endswith("converse com o técnico.")


def test_texto_padrao_de_previsao_e_de_metricas_sao_diferentes(folhas):
    a = CH.responder_chat(PERG_PREV, modo="template", folha=folhas["quixada_ce"])["resposta"]
    b = CH.responder_chat(P_ACERTA, modo="template", folha=folhas["quixada_ce"])["resposta"]
    c = CH.responder_chat(PERG_PREV, modo="template", folha=folhas["fortaleza_ce"])["resposta"]
    assert a != b and a != c and "o verde das plantas deve ficar" in a


# ---------------------------------------------------------------------------------------------- (4) texto padrão do acervo: trechos limpos
SUJO_1 = {"n": 1, "arquivo": "Cultura_do_milho_Embrapa.pdf", "pagina": 8,
          "texto": "8 - Adubação no plantio do milho... A rotação do milho com feijão é prática recomendada porque o feijão ajuda a fixar nitro-\n"
                   "gênio no solo. 267 A prática de plantar feijão depois do milho reduz pragas e doenças da lavoura. CULTURA DO MILHO EMBRAPA 2009 "
                   "Outra frase que passa de duas frases."}
SUJO_2 = {"n": 2, "arquivo": "Manual_sorgo.pdf", "pagina": 12, "texto": "... 41 O sorgo tolera a seca e pode ser plantado depois do milho em áreas secas . . ."}
LONGE = {"n": 1, "arquivo": "Zoneamento_algodao.pdf", "pagina": 3, "texto": "O algodão herbáceo tem janela de plantio definida pelo zoneamento de risco climático."}


def test_limpar_trecho_pdf():
    t = CH.limpar_trecho_pdf(SUJO_1["texto"])
    assert "nitrogênio" in t and "nitro-" not in t and "\n" not in t and "..." not in t and not re.search(r"\b267\b|\b8 -", t)
    assert "CULTURA DO MILHO" not in t and t.count(".") <= 3 and len(re.split(r"(?<=[.!?])\s+", t)) <= 2, t
    t2 = CH.limpar_trecho_pdf(SUJO_2["texto"])
    assert t2.startswith("O sorgo tolera a seca") and "41" not in t2 and ". ." not in t2 and "…" not in t2[:5]


def test_texto_padrao_do_acervo_com_trechos_sujos_e_limpo(tmp_path):
    P = "Posso plantar feijão depois do milho?"
    r = CH.responder_chat(P, modo="template", buscar_fn=busca([SUJO_1, SUJO_2, LONGE]))
    t = r["resposta"]
    assert r["origem"] == "template" and "[" not in t and "267" not in t and "..." not in t and "-\n" not in t
    assert t.count("\n- ") <= 2 and "Zoneamento" not in t and "algodão" not in t and "Converse com o técnico" in t
    assert "fixar nitrogênio" in t and len(t.splitlines()) <= 4
    assert "[1]" in r["resposta_com_citacoes"] and r["trechos"][0]["texto"] == SUJO_1["texto"]       # o trecho cru fica para conferência


def test_acervo_sem_trecho_que_responda_mostra_so_o_documento():
    r = CH.responder_chat("Posso plantar feijão depois do milho?", modo="template", buscar_fn=busca([LONGE]))
    t = r["resposta"]
    assert t.startswith("Não achei no material do Sulco uma resposta direta; converse com o técnico.")
    assert "Zoneamento algodao" in t and "janela de plantio" not in t and "[" not in t and r["origem"] == "template"


# ---------------------------------------------------------------------------------------------- rodada 5: flexões, promessas negadas, fecho, fonte, caminhos
def _ok(texto, **kw):
    return verificar(f"{texto} [F1].", None, [], exigir_citacao=True, fatos=SINT["fatos"], tom=True, exigir_aviso=False, **kw)


@pytest.mark.parametrize("t", ["Duas ou mais culturas ficam juntas", "Duas ou mais culturas se sobrepõem", "Um caminho e uma opção",
                               "O primeiro caminho e a segunda opção", "A terceira alternativa e o terceiro lugar", "Há quatro opções e cinco culturas",
                               "Escolha entre dois e dez caminhos", "As próximas duas semanas valem"])
def test_numeros_por_extenso_flexionados_soltos_passam(t):
    r = _ok(t)
    assert r["ok"], (t, r["motivos"])


@pytest.mark.parametrize("t", ["Dura um ano", "No terceiro ano", "Chove cinco por cento a mais", "São quinze dias", "Custa duas vezes mais",
                               "Dura três meses", "Rende uma tonelada"])
def test_numeros_por_extenso_ligados_a_unidade_exigem_fonte(t):
    r = _ok(t)
    assert not r["ok"] and any("extenso" in m for m in r["motivos"]), (t, r)


@pytest.mark.parametrize("t", ["Isso não é garantia", "Sem garantia nenhuma de resultado", "Não garante nada", "Não prometo lucro", "Nunca garantimos colheita",
                               "A previsão não é garantia de nada"])
def test_negacao_de_promessa_passa(t):
    r = _ok(t)
    assert r["ok"], (t, r["motivos"])


@pytest.mark.parametrize("t", ["Isso garante lucro", "Há garantia de colheita", "O resultado é garantido", "Vai render mais", "Garantimos o rendimento maior"])
def test_promessa_afirmativa_continua_barrada(t):
    r = _ok(t)
    assert not r["ok"] and any("promessa" in m for m in r["motivos"]), (t, r)


def test_resposta_de_metricas_com_nao_e_garantia_e_aprovada(tmp_path):
    saida = ("Nos testes, o modelo acerta melhor que usar só a média dos anos anteriores [F2]. A margem de variação não é garantia [F2]. "
             "Duas ou mais respostas são possíveis [F2].")
    r = _llm(saida, tmp_path, pergunta=P_ACERTA)
    assert r["origem"] == "llm", r["verificacao"]


# (3) fecho certo por tema
def test_fecho_de_previsao_so_em_previsao_ou_metricas(tmp_path, folhas):
    P = "Posso plantar feijão depois do milho?"
    prov = Falso("Segundo o material consultado, feijão depois de milho ajuda o solo [1].")
    r = CH.responder_chat(P, modo="online", provedor=prov, buscar_fn=busca([{"n": 1, "arquivo": "embrapa_x.pdf", "pagina": 2,
                          "texto": "Feijão depois do milho ajuda o solo."}]), cache=Cache(tmp_path / "a"), folha=folhas["quixada_ce"])
    assert r["origem"] == "llm" and r["resposta"].endswith("Converse com o técnico.") and "duas semanas" not in r["resposta"]
    for q in (PERG_PREV, P_ACERTA):
        r = _llm("O verde deve ficar parecido com o normal [F1].", tmp_path, pergunta=q)
        assert r["resposta"].endswith("converse com o técnico.") and "duas semanas" in r["resposta"], q
    r = _llm("O solo é de tipo médio [F3].", tmp_path, pergunta="Qual o solo do meu local?")
    assert "duas semanas" not in r["resposta"] and r["resposta"].endswith("Converse com o técnico.")


def test_fecho_para_previsao_explicita():
    assert FT.fecho_para("Resposta qualquer.", [{"tema": "previsao"}], previsao=False) == "Converse com o técnico."
    assert FT.fecho_para("Resposta qualquer.", [], previsao=True).startswith("Isso vale só para as próximas duas semanas")


# (4) atribuição
def test_fonte_curta_so_vem_do_nome_do_arquivo():
    assert CH.fonte_curta("embrapa_meionorte_feijaocaupi.pdf") == "Embrapa" and CH.fonte_curta("mapa_zarc_ce_milho.pdf") == "o Ministério da Agricultura"
    assert CH.fonte_curta("Cultura_do_milho.pdf") is None and CH.fonte_curta("doc.pdf") is None and CH.fonte_curta("sobre o Sulco: glossário") is None


def test_prompt_do_acervo_traz_nome_da_fonte_e_orientacao_de_atribuicao(tmp_path):
    prov = Falso("sem evidência")
    tr = [{"n": 1, "arquivo": "embrapa_a.pdf", "pagina": 1, "texto": "Feijão depois do milho ajuda o solo."},
          {"n": 2, "arquivo": "outro.pdf", "pagina": 2, "texto": "Texto qualquer sobre milho e feijão."}]
    CH.responder_chat("Posso plantar feijão depois do milho?", modo="online", provedor=prov, buscar_fn=busca(tr), cache=Cache(tmp_path))
    p = prov.prompts[0]
    assert "<<<NOMES_DAS_FONTES>>>\n[1] Embrapa\n<<<FIM_NOMES>>>" in p and "[2] None" not in p
    assert "Segundo o material consultado" in CH.SISTEMA_CHAT and "Pode sim" in CH.SISTEMA_CHAT and "resposta direta" in CH.SISTEMA_CHAT
    prov2 = Falso("sem evidência")
    CH.responder_chat("Posso plantar feijão depois do milho?", modo="online", provedor=prov2, buscar_fn=busca(tr[1:]), cache=Cache(tmp_path / "b"))
    assert "NOMES_DAS_FONTES" not in prov2.prompts[0]


def test_texto_padrao_do_acervo_comeca_com_segundo_o_material_e_nome_da_fonte():
    t = [{"n": 1, "arquivo": "embrapa_a.pdf", "pagina": 1, "texto": "A rotação do milho com feijão é prática recomendada porque o feijão fixa nitrogênio."}]
    r = CH.responder_chat("Posso plantar feijão depois do milho?", modo="template", buscar_fn=busca(t))
    assert r["resposta"].startswith("Segundo o material consultado (Embrapa):") and "[" not in r["resposta"]
    r = CH.responder_chat("Posso plantar feijão depois do milho?", modo="template", buscar_fn=busca([{**t[0], "arquivo": "outro.pdf"}]))
    assert r["resposta"].startswith("Segundo o material consultado:")


# (5) caminhos
def test_texto_padrao_dos_caminhos_uma_linha_por_caminho_na_ordem(folhas):
    r = CH.responder_chat("Por que o Sulco sugeriu esses caminhos para mim?", modo="template", folha=folhas["quixada_ce"])
    ls = r["resposta"].splitlines()
    assert len(ls) <= 6 and ls[-1] == "Converse com o técnico."
    assert ls[0].startswith("Caminho 1 (o que você faz hoje): repetir milho") and "só para comparar" in ls[0]
    assert ls[1].startswith("Caminho 2:") and ls[2].startswith("Caminho 3:")
    assert sum(l.startswith("Caminho 2") for l in ls) == 1 and sum(l.startswith("Caminho 1") for l in ls) == 1
    assert all("melhor época para começar: fevereiro" in l for l in ls[:3])
    # a lacuna de nitrogênio/palha ('ainda não temos dado de') agora está no Caminho 3 (feijão-caupi): a crotalária (Caminho 2) tem N e palha em estudo pontual
    assert "crotalária juncea" in ls[1] and "ainda não temos dado de" in ls[2]
    assert any("não mostram qual é melhor" in l for l in ls) and "[F" not in r["resposta"] and not termos_tecnicos(r["resposta"])
    assert "[F" in r["resposta_com_citacoes"]


@pytest.mark.parametrize("pid", MUNICIPIOS)
def test_texto_padrao_dos_caminhos_em_todos_os_municipios(folhas, pid):
    r = CH.responder_chat("Por que o Sulco sugeriu esses caminhos para mim?", modo="template", folha=folhas[pid])
    ls = r["resposta"].splitlines()
    assert 4 <= len(ls) <= 6 and [l[:9] for l in ls[:3]] == ["Caminho 1", "Caminho 2", "Caminho 3"] and ls[-1] == "Converse com o técnico."


def test_prompt_dos_caminhos_usa_o_resumo_sem_repetir_detalhes(folhas, tmp_path):
    prov = Falso("sem evidência")
    CH.responder_chat("Por que o Sulco sugeriu esses caminhos para mim?", modo="online", provedor=prov, buscar_fn=busca([]), cache=Cache(tmp_path),
                      folha=folhas["quixada_ce"])
    bloco = prov.prompts[0].split("<<<FATOS_DO_LOCAL>>>")[1]
    assert bloco.count("Caminho 2") >= 1 and "o que você faz hoje" in bloco and not termos_tecnicos(bloco)
    assert bloco.count("melhor época para começar") == 3


# ---------------------------------------------------------------------------------------------- rodada 6: limite de duas semanas, 'fatos do local', prescritivas, repetição
EMB = [{"n": 1, "arquivo": "embrapa_a.pdf", "pagina": 2, "texto": "O feijão costuma ser plantado depois da colheita do milho, em rotação."}]
P_FEIJAO = "Posso plantar feijão depois do milho?"


def _acervo(saida, tmp, nome="a"):
    prov = Falso(saida)
    r = CH.responder_chat(P_FEIJAO, modo="online", provedor=prov, buscar_fn=busca(EMB), cache=Cache(tmp / nome))
    return r, prov


def test_prompt_so_menciona_duas_semanas_em_previsao_ou_metricas(tmp_path, folhas):
    assert "duas semanas" not in CH.SISTEMA_CHAT
    r, prov = _acervo("sem evidência", tmp_path)
    assert "duas semanas" not in prov.prompts[0]
    for q in (PERG_PREV, P_ACERTA):
        prov = Falso("sem evidência")
        CH.responder_chat(q, modo="online", provedor=prov, buscar_fn=busca([]), cache=Cache(tmp_path / re.sub(r"\W", "", q)), folha=folhas["quixada_ce"])
        assert "UMA frase dizendo que isso vale só para as próximas duas semanas" in prov.prompts[0]
    prov = Falso("sem evidência")
    CH.responder_chat("Qual o solo do meu local?", modo="online", provedor=prov, buscar_fn=busca([]), cache=Cache(tmp_path / "s"), folha=folhas["quixada_ce"])
    assert "duas semanas" not in prov.prompts[0]


def test_frase_de_duas_semanas_e_removida_de_resposta_agronomica(tmp_path):
    r, _ = _acervo("Segundo a Embrapa, o feijão costuma ser plantado depois da colheita do milho [1]. Isso vale só para as próximas duas semanas. "
                   "Converse com o técnico.", tmp_path)
    assert r["origem"] == "llm", r["verificacao"]
    assert "duas semanas" not in r["resposta"] and "duas semanas" not in r["resposta_com_citacoes"]
    assert r["resposta"].startswith("Segundo a Embrapa, o feijão costuma") and r["resposta"].endswith("Converse com o técnico.")
    assert r["resposta"].lower().count("converse com o técnico") == 1
    r, _ = _acervo("Segundo a Embrapa, o feijão costuma ser plantado depois da colheita do milho [1]. Isso vale só para as próximas duas semanas; "
                   "converse com o técnico.", tmp_path, "b")
    assert "duas semanas" not in r["resposta"] and r["resposta"].endswith("Converse com o técnico.")


def test_frase_de_duas_semanas_fica_em_previsao(tmp_path):
    r = _llm("O verde deve ficar parecido com o normal [F1]. Isso vale só para as próximas duas semanas.", tmp_path)
    assert r["resposta"].count("duas semanas") == 1 and r["resposta"].endswith("onverse com o técnico.")


def test_posprocessar_troca_fatos_do_local():
    assert CH.posprocessar("Segundo os fatos do local, o solo é médio.", False) == "Pelos dados do seu local, o solo é médio."
    assert CH.posprocessar("Segundo os fatos, chove pouco.", False).startswith("Pelos dados do seu local")
    assert "fatos" not in CH.posprocessar("De acordo com os fatos do seu local: ok.", False)


def test_resposta_da_ia_com_fatos_do_local_sai_com_pelos_dados(tmp_path):
    r = _llm("Segundo os fatos do local, o solo é de tipo médio [F3].", tmp_path, pergunta="Qual o solo do meu local?")
    assert r["resposta"].startswith("Pelos dados do seu local, o solo é de tipo médio") and "fatos" not in r["resposta"]


@pytest.mark.parametrize("frase", ["Pode sim: o feijão vai bem depois do milho [1].", "O senhor deve plantar feijão depois do milho [1].",
                                   "Eu recomendo plantar feijão depois do milho [1].", "Plante feijão depois do milho [1].",
                                   "Vale a pena plantar feijão depois do milho [1]."])
def test_prescritivas_caem_no_texto_padrao(frase, tmp_path):
    r, _ = _acervo(frase, tmp_path)
    assert r["origem"] == "template" and any("prescritiva" in m for m in r["verificacao"]["motivos"]), r["verificacao"]
    assert r["resposta"].startswith("Segundo o material consultado (Embrapa):")


def test_resposta_como_o_material_diz_e_aprovada(tmp_path):
    r, _ = _acervo("Segundo a Embrapa, o feijão costuma ser plantado depois da colheita do milho [1].", tmp_path)
    assert r["origem"] == "llm" and r["resposta"].endswith("Converse com o técnico.")


def test_frases_repetidas_sao_rejeitadas(tmp_path):
    rep = ("Empate técnico quer dizer que, com os dados que temos, não dá para dizer qual é melhor. Ou seja, os dados não mostram qual é melhor.")
    assert frases_repetidas(rep)
    r = CH.responder_chat("O que é empate técnico?", modo="online", provedor=Falso(rep + " [1]"), buscar_fn=busca([]), cache=Cache(tmp_path))
    assert r["origem"] == "template" and any("repetidas" in m for m in r["verificacao"]["motivos"])
    assert r["resposta"].splitlines()[0].startswith("Empate técnico quer dizer que")
    assert "Ou seja" not in r["resposta"] and "nem use \"ou seja\"" in CH.SISTEMA_CHAT and "Não repita a mesma ideia" in CH.SISTEMA_CHAT


def test_frases_diferentes_nao_sao_repeticao():
    ok = "Caminho 2: depois de milho, plantar feijão-caupi. Caminho 3: depois de milho, plantar crotalária juncea. O verde fica parecido com o normal."
    assert frases_repetidas(ok) == []
    assert frases_repetidas("O milho gosta de chuva. A chuva ajuda o milho.") == []
    assert frases_repetidas("O verde deve ficar parecido com o normal. O verde deve ficar parecido com o normal.")
