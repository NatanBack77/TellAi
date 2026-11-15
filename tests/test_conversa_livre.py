"""Conversa LIVRE (src/llm/conhecimento.py + gancho em conversa.py): bateria de 90+ perguntas de agricultor (com erro de grafia), 30 inesperadas e 10 de fora
do assunto. SEM rede e SEM chave: provedor FALSO; busca do acervo (RAG) injetada (nunca carrega o modelo). Dados reais de Quixadá."""
import re
from datetime import date

import pytest

from perguntas_livres import FORA_DO_ASSUNTO, INESPERADAS, PERGUNTAS, PONTO
from src.llm import chat as CH
from src.llm import conhecimento as CK
from src.llm import conversa as C
from src.llm import dialogo as D
from src.llm import fatos as FT
from src.llm.cache import Cache
from src.llm.provedores import Provedor
from src.llm.verificador import contar_palavras, limpar_citacoes, sem_acento

SEM_RAG = lambda p: {"sem_evidencia": True, "trechos": []}  # noqa: E731
HOJE = date(2026, 11, 14)


class Prov(Provedor):
    nome, modelo = "falso", "f1"

    def __init__(self, saida):
        self.saida, self.prompts, self.chamadas = saida, [], 0
        self.ultimo_uso = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    def gerar(self, sistema, usuario, max_tokens=900):
        self.chamadas += 1
        self.prompts.append((sistema, usuario))
        return self.saida(usuario) if callable(self.saida) else self.saida


@pytest.fixture(scope="module")
def sels():
    return {q: CK.selecionar_fatos(q, PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE) for q, *_ in PERGUNTAS}


def _numeros(t: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", t))


def _corpo(sel: dict) -> str:
    return limpar_citacoes(CK.texto_padrao_livre(sel))


# ---------------------------------------------------------------------------------------------- métricas da bateria
def test_bateria_tem_80_ou_mais_perguntas():
    assert len(PERGUNTAS) >= 80 and len(INESPERADAS) >= 30


def test_tema_detectado_e_fatos_em_quase_todas(sels):
    falhas = []
    for q, tem, cult, lac in PERGUNTAS:
        s = sels[q]
        if not (set(s["temas"]) & tem) or not set(cult) <= set(s["culturas"]) or not s["fatos"]:
            falhas.append((q, s["temas"], s["culturas"]))
        if not lac and all(f["lacuna"] for f in s["fatos"]):
            falhas.append((q, "só lacuna onde há dado", [f["texto_simples"][:40] for f in s["fatos"]]))
    assert len(falhas) <= 0.03 * len(PERGUNTAS), falhas


def test_lacuna_honesta_onde_nao_ha_dado(sels):
    for q, tem, cult, lac in PERGUNTAS:
        if not lac:
            continue
        s = sels[q]
        t = sem_acento(_corpo(s).lower())
        assert any(f["lacuna"] and f["prio"] == 0 for f in s["fatos"]), q
        assert re.search(r"ainda nao temos|nao prev|nao calcula|nao tem dado", t), (q, t)
        assert not re.search(r"\bvai render\b|garanto|com certeza|\bplante\b|recomendo", t), q


def test_fatos_tem_origem_texto_simples_e_marca_de_lacuna(sels):
    for q, s in sels.items():
        for f in s["fatos"]:
            assert f["origem"] and f["texto_simples"] and isinstance(f["lacuna"], bool) and re.fullmatch(r"F\d+", f["id"]), (q, f)


def test_nenhum_numero_vem_de_fora_dos_fatos(sels):
    for q, s in sels.items():
        fora = _numeros(_corpo(s)) - _numeros(" ".join(f["texto_simples"] for f in s["fatos"]))
        assert not fora, (q, fora)


def test_resposta_padrao_curta_para_voz_e_simples(sels):
    for q, s in sels.items():
        t = _corpo(s)
        assert contar_palavras(t) <= 62, (q, contar_palavras(t), t)
        assert not re.search(r"\b(NDVI|anomalia|composto|percentil|RMSE|conformal|MODIS|POWER)\b", t), (q, t)


def test_nada_e_prometido_nem_prescrito(sels):
    for q, s in sels.items():
        t = sem_acento(_corpo(s).lower())
        assert not re.search(r"\bgaranto\b|\bprometo\b|vai render|rende mais|\bplante\b|\bdeve plantar\b|recomendo|vale a pena plantar", t), (q, t)


def test_prompt_cabe_em_2800_tokens(sels):
    nomes = C._nomes()
    mx = 0
    for q, s in sels.items():
        p = C.montar_prompt(q, D.estado_inicial(), None, "livre", s["fatos"], D.PERGUNTA_FOCO, nomes)
        mx = max(mx, FT.tokens_aprox(C.SISTEMA_CONVERSA) + FT.tokens_aprox(p))
    assert mx <= 2800, mx


# ---------------------------------------------------------------------------------------------- ficha: assuntos NÃO previstos
def test_inesperadas_achem_fatos_uteis_e_fora_do_assunto_nao():
    ok = []
    for q, kw in INESPERADAS:
        s = CK.selecionar_fatos(q, PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE)
        txt = sem_acento(" ".join(f["texto_simples"] for f in s["fatos"]).lower())
        if any(k in txt for k in kw) and s["fatos"][0]["tema"] != "nada":
            ok.append(q)
    assert len(ok) >= 0.85 * len(INESPERADAS), [q for q, _ in INESPERADAS if q not in ok]
    for q in FORA_DO_ASSUNTO:
        s = CK.selecionar_fatos(q, PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE)
        assert all(f["lacuna"] for f in s["fatos"]) and "não achei" in CK.texto_padrao_livre(s), (q, [f["texto_simples"][:50] for f in s["fatos"]])


def test_pergunta_combinada_junta_fatos_de_varios_temas():
    s = CK.selecionar_fatos("dá para plantar milho agora e vai chover?", PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE)
    ts = {f["tema"] for f in s["fatos"]}
    assert len(ts) >= 2 and s["culturas"] == ["milho"], (ts, s["temas"])


# ---------------------------------------------------------------------------------------------- casos reais do teste por voz
def test_chuva_da_epoca_atual_e_nao_solo_nu():
    s = CK.selecionar_fatos("costuma chover muito nessa época do ano", PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE)
    t = _corpo(s)
    assert s["temas"][0] == "chuva_atual" and "Em novembro" in t and "solo" not in t.lower() and "descoberta" not in t


def test_janeiro_nao_vira_cultura_nem_couve():
    for q in ("chove muito em janeiro", "quando chove mais aqui", "kuando chove mais aki"):
        s = CK.selecionar_fatos(q, PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE)
        assert s["culturas"] == [] and "couve" not in _corpo(s).lower() and "janeiro" not in [f["texto_simples"] for f in s["fatos"]][:0], q


def test_o_que_planta_nessa_epoca_usa_o_mes_de_hoje_e_o_zarc():
    s = CK.selecionar_fatos("o que dá para plantar nessa época do ano", PONTO, {}, buscar_fn=SEM_RAG, hoje=date(2026, 3, 5))
    t = _corpo(s)
    assert s["temas"] == ["plantar_agora"] and "Em março" in t and "zoneamento" in t


# ---------------------------------------------------------------------------------------------- fluxo: qualquer estado, retoma a pergunta aberta
@pytest.mark.parametrize("pend,msg,retoma", [
    ("foco", "quanto custa a semente?", "o que pesa mais"),
    ("ordem", "quando começa a chover aqui?", "em que ordem"),
    ("culturas", "o milho aguenta seca?", "quais culturas"),
    ("refazer", "quantos dias o feijão demora?", "quais culturas"),
    ("municipio", "o que é veranico?", "município"),
    ("ordem_texto", "meu solo é fraco, e agora?", "a ordem que você pensou"),
    ("confirmar", "vou ganhar dinheiro com isso?", "se entendi certo"),
])
def test_pergunta_livre_no_meio_de_pergunta_aberta_mantem_o_estado_e_retoma(pend, msg, retoma):
    est = D.normalizar_estado({**D.estado_inicial(), "pendente": pend, "culturas": ["milho", "feijao_caupi"] if pend in ("confirmar", "ordem") else []})
    r = C.conversar(msg, est, PONTO if pend != "municipio" else None, None, buscar_fn=SEM_RAG, modo="template", hoje=HOJE)
    assert r["estado"]["pendente"] == pend and retoma in r["resposta"], r["resposta"]
    assert r["resposta"].strip().lower() not in ("sem evidência", "sem evidencia")
    assert r["resposta"].count("?") <= 1 and r["acao"] in ("responder", "perguntar")


def test_pergunta_livre_no_meio_do_calendario_retoma_a_pergunta_do_calendario():
    r1 = C.conversar("plantei milho", None, PONTO, None, modo="template", hoje=HOJE)
    assert r1["estado"]["pendente"] and r1["estado"]["pendente"].startswith("plantio_")
    r2 = C.conversar("quanto custa a semente?", r1["estado"], PONTO, None, buscar_fn=SEM_RAG, modo="template", hoje=HOJE)
    assert r2["estado"]["pendente"] == r1["estado"]["pendente"] and "Voltando" in r2["resposta"] and "semente" in r2["resposta"].lower()


def test_sem_municipio_e_pergunta_so_local_pede_o_municipio():
    r = C.conversar("quando começa a chover aqui?", None, None, None, buscar_fn=SEM_RAG, modo="template", hoje=HOJE)
    assert r["acao"] == "perguntar" and r["pede"] == "municipio" and r["estado"]["pendente"] == "municipio"


def test_pergunta_direta_nao_exige_foco_nem_cultura_antes():
    r = C.conversar("quantos dias o milho demora?", None, PONTO, None, buscar_fn=SEM_RAG, modo="template", hoje=HOJE)
    assert r["acao"] == "responder" and "140 dias" in r["resposta"] and r["estado"]["pendente"] is None
    r2 = C.conversar("e ele aguenta seca?", r["estado"], PONTO, None, buscar_fn=SEM_RAG, modo="template", hoje=HOJE)
    assert "milho" in r2["resposta"].lower() and r2["estado"]["ult_cultura"] == ["milho"] and r2["estado"]["culturas"] == []


def test_pedidos_guiados_continuam_no_fluxo_guiado():
    r = C.conversar("o que dá para plantar aqui?", None, PONTO, None, buscar_fn=SEM_RAG, modo="template")
    assert r["pede"] == "foco"
    r = C.conversar("quero economizar água", None, PONTO, None, buscar_fn=SEM_RAG, modo="template")
    assert r["acao"] == "responder" and "gastar menos água" in r["resposta"]


# ---------------------------------------------------------------------------------------------- LLM: só reescreve, verificador vale
def _llm(texto, msg, tmp_path, est=None):
    p = Prov(texto)
    r = C.conversar(msg, est, PONTO, None, provedor=p, modo="online", cache=Cache(tmp_path), buscar_fn=SEM_RAG, hoje=HOJE)
    return r, p


def test_llm_reescreve_os_fatos_e_so_eles(tmp_path):
    def bom(u):
        (i, t), *_ = re.findall(r"^\[(F\d+)\] (.*)$", u, flags=re.M)
        return f"{re.split(r'(?<=[.!?])[ ]', t)[0].rstrip('.')} [{i}]."
    r, p = _llm(bom, "quantos dias o milho demora?", tmp_path)
    assert r["origem"] == "llm" and r["verificacao"]["ok"] is True and "?" not in r["resposta"].split("\n")[0]
    assert "<<<FATOS_DO_LOCAL>>>" in p.prompts[0][1] and "quixada" not in p.prompts[0][1].lower()


def test_llm_com_numero_inventado_ou_promessa_cai_no_texto_padrao(tmp_path):
    r, _ = _llm("O milho leva 90 dias para colher [F1].", "quantos dias o milho demora?", tmp_path)
    assert r["origem"] == "template" and "140 dias" in r["resposta"] and r["verificacao"]["ok"] is False
    r, _ = _llm("Garanto que o milho vai render muito [F1].", "o milho da certo aqui?", tmp_path)
    assert r["origem"] == "template"


def test_llm_sem_evidencia_cai_no_texto_padrao_nunca_em_so_sem_evidencia(tmp_path):
    r, _ = _llm("sem evidência", "quantos dias o milho demora?", tmp_path)
    assert r["origem"] == "template" and r["resposta"].strip().lower() != "sem evidência" and "dias" in r["resposta"]


# ---------------------------------------------------------------------------------------------- acervo (RAG) vira frase simples
def test_rag_cru_vira_frase_simples_sem_autor_nem_citacao():
    cru = {"n": 1, "arquivo": "embrapa_milho.pdf", "pagina": 9, "texto":
           "SILVA, José Barbosa Duarte Júnior et al. (2009) CULTURA DO MILHO. Tabela 4. A lagarta-do-cartucho é a principal praga do milho e ataca as folhas novas. "
           "Brasília: Embrapa, 2009. 267 O controle da lagarta no milho começa com o monitoramento semanal da lavoura."}
    r = CH.responder_chat("Como controlar a lagarta no milho?", modo="template", buscar_fn=lambda p: {"trechos": [cru], "sem_evidencia": False})
    t = r["resposta"]
    assert "Barbosa" not in t and "et al" not in t and "Tabela" not in t and "- " not in t and "lagarta" in t and contar_palavras(t) <= 60, t
    s = CK.selecionar_fatos("como controlar a lagarta no milho", PONTO, {}, buscar_fn=lambda p: {"trechos": [cru], "sem_evidencia": False}, hoje=HOJE)
    assert any(f["tema"] == "acervo" and "Barbosa" not in f["texto_simples"] for f in s["fatos"])


def test_rag_sem_trecho_limpo_diz_que_nao_achou():
    cru = {"n": 1, "arquivo": "embrapa_x.pdf", "pagina": 1, "texto": "SILVA, José Barbosa Duarte Júnior; SOUSA, Maria Lima Santos. Tabela 3. Resumo."}
    r = CH.responder_chat("Como controlar a lagarta no milho?", modo="template", buscar_fn=lambda p: {"trechos": [cru], "sem_evidencia": False})
    assert "Barbosa" not in r["resposta"] and "Não achei" in r["resposta"]


def test_pergunta_sem_base_nunca_devolve_so_sem_evidencia():
    r = C.conversar("como fabrico queijo de coalho?", None, PONTO, None, buscar_fn=SEM_RAG, modo="template")
    assert r["resposta"].strip().lower() != "sem evidência" and len(r["resposta"]) > 40 and "o que dá" not in r["resposta"][:5]


# ---------------------------------------------------------------------------------------------- número só se o usuário trouxer ou pedir número
def test_flag_numeros_permitidos():
    sim = ["quantos mm chove em março", "quantos dias o milho demora", "quanto chove aqui por ano", "em 2024 choveu bem?", "qual a temperatura boa pro girassol",
           "são 90 dias?", "quanto custa a semente", "me dá o número de hectares", "choveu 30 mm ontem"]
    nao = ["quando começa a chover aqui", "o milho aguenta seca", "meu solo é fraco, e agora", "o que é rotação", "o verde vai melhorar", "posso plantar milho com feijão junto"]
    assert all(CK.numeros_permitidos(q) for q in sim) and not any(CK.numeros_permitidos(q) for q in nao)


def test_sem_pedido_de_numero_a_resposta_nao_tem_digito_nem_numeral():
    n_sem = 0
    for q, tem, cult, lac in PERGUNTAS:
        nums = CK.numeros_permitidos(q)
        s = CK.selecionar_fatos(q, PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE, numeros=nums)
        t = CK.texto_padrao_livre(s)
        if not nums:
            n_sem += 1
            assert not CK.tem_numero(t), (q, t)
            assert s["fatos"] and s["fatos"][0]["tema"] != "nada", q
    assert n_sem >= 40


def test_quantos_mm_chove_em_marco_traz_numero_dos_fatos():
    q = "quantos mm chove em março"
    assert CK.numeros_permitidos(q)
    s = CK.selecionar_fatos(q, PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE, numeros=True)
    t = CK.texto_padrao_livre(s)
    assert re.search(r"março[^.]*\d+ mm", t) and _numeros(limpar_citacoes(t)) <= _numeros(" ".join(f["texto_simples"] for f in s["fatos"]))
    s2 = CK.selecionar_fatos("chove muito em março", PONTO, {}, buscar_fn=SEM_RAG, hoje=HOJE, numeros=False)
    assert re.search(r"março[^.]*(chuvosos|chove pouco|quase não chove)", CK.texto_padrao_livre(s2)) and not CK.tem_numero(CK.texto_padrao_livre(s2))


def test_prompt_e_verificador_com_flag_falsa(tmp_path):
    p = Prov(lambda u: "Em novembro a chuva é pouca [F1].")
    r = C.conversar("costuma chover muito nessa época do ano", None, PONTO, None, provedor=p, modo="online", cache=Cache(tmp_path), buscar_fn=SEM_RAG, hoje=HOJE)
    assert "NÃO cite número" in p.prompts[0][1] and not re.search(r"\d", re.sub(r"\[F\d+\]", "", p.prompts[0][1].split("<<<FATOS_DO_LOCAL>>>")[1].split("<<<FIM_FATOS>>>")[0]))
    assert r["estado"]["numeros_permitidos"] is False
    r2, _ = _llm("Em novembro chove 10 mm [F1].", "costuma chover muito nessa época do ano", tmp_path / "b")
    assert r2["origem"] == "template" and any("número" in m for m in r2["verificacao"]["motivos"]) and not CK.tem_numero(r2["resposta"])
    r3, _ = _llm("Em novembro chove 10 mm [F1].", "quantos mm chove em novembro", tmp_path / "c")
    assert r3["estado"]["numeros_permitidos"] is True


def test_numeros_permitidos_vale_so_no_turno():
    r1 = C.conversar("quantos dias o milho demora?", None, PONTO, None, buscar_fn=SEM_RAG, modo="template", hoje=HOJE)
    assert r1["estado"]["numeros_permitidos"] is True and re.search(r"\d", r1["resposta"])
    r2 = C.conversar("e ele aguenta seca?", r1["estado"], PONTO, None, buscar_fn=SEM_RAG, modo="template", hoje=HOJE)
    assert r2["estado"]["numeros_permitidos"] is False and not CK.tem_numero(r2["resposta"].split("\n")[0])
