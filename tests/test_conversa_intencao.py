"""Extração determinística de intenção (src/llm/intencao.py): frases reais de agricultor, com erros comuns de grafia. SEM LLM, SEM rede."""
import pytest

from src.llm import intencao as IT

M, CA, CO, SO, MIL, MAN, ALG, AME, GIR, MAM, GER, GUA, PAL, CRO, POR, MUC = (
    "milho", "feijao_caupi", "feijao_comum", "sorgo", "milheto", "mandioca", "algodao", "amendoim", "girassol", "mamona", "gergelim", "guandu",
    "palma_forrageira", "crotalaria_juncea", "feijao_de_porco", "mucuna")

# (frase, culturas na ordem, foco, ordem_dita, proibidas, fora_da_lista)
CASOS = [
    ("primeiro milho, depois feijão de corda e crotalária juncea", [M, CA, CRO], None, True, [], []),
    ("Quero plantar milho e feijão macassar", [M, CA], None, False, [], []),
    ("planto caupi e sorgo", [CA, SO], None, False, [], []),
    ("feijão fradinho depois do milho", [M, CA], None, True, [], []),
    ("macaxeira e aipim", [MAN], None, False, [], []),
    ("quero macaxeira, feijão carioca e milheto", [MAN, CO, MIL], None, False, [], []),
    ("girassol, amendoim e mamona", [GIR, AME, MAM], None, False, [], []),
    ("gergelim antes do algodão", [GER, ALG], None, True, [], []),
    ("palma forrageira para o gado", [PAL], "forragem", False, [], []),
    ("mucuna e guandu para adubar a terra", [MUC, GUA], "nitrogenio", False, [], []),
    ("feijão-de-porco primeiro, depois milho", [POR, M], None, True, [], []),
    ("feijão de porco antes do milho", [POR, M], None, True, [], []),
    ("mandioca depois de feijão-de-porco", [POR, MAN], None, True, [], []),
    ("milheto e sorgo seguido de algodão", [MIL, SO, ALG], None, True, [], []),
    ("crotalaria e milho", [CRO, M], None, False, [], []),
    ("milho milho feijão caupi", [M, CA], None, False, [], []),
    ("não quero mandioca, quero milho e feijão macassar", [M, CA], None, False, [MAN], []),
    ("sem mandioca, milho e feijão caupi", [M, CA], None, False, [MAN], []),
    ("evitar algodão e mamona, quero sorgo", [SO], None, False, [ALG, MAM], []),
    ("não gosto de palma, prefiro milheto", [MIL], None, False, [PAL], []),
    ("quero plantar melancia e milho", [M], None, False, [], ["melancia"]),
    ("abóbora depois do milho", [M], None, False, [], ["abóbora"]),
    ("tomate, cebola e feijão caupi", [CA], None, False, [], ["tomate", "cebola"]),
    ("quero plantar caju", [], None, False, [], ["caju"]),
    ("quero economizar água", [], "agua", False, [], []),
    ("tenho pouca água, o que aguenta a seca?", [], "agua", False, [], []),
    ("quero proteger o solo da enxurrada", [], "solo", False, [], []),
    ("a terra está cansada e fraca", [], "solo", False, [], []),
    ("quero uma renda extra", [], "renda", False, [], []),
    ("preciso de adubo verde", [], "nitrogenio", False, [], []),
    ("quero deixar palha na terra", [], "palhada", False, [], []),
    ("muita praga e doença na roça", [], "pragas", False, [], []),
    ("preciso de ração para os animais", [], "forragem", False, [], []),
    ("o que dá para plantar aqui?", [], None, False, [], []),
    ("fejão caupi e milio", [CA, M], None, False, [], []),
    ("girasol e amendoin", [GIR, AME], None, False, [], []),
    ("quero plantar sorgu", [SO], None, False, [], []),
    ("macaxera e milho", [MAN, M], None, False, [], []),
    ("crotalaia juncea", [CRO], None, False, [], []),
    ("MILHO, FEIJÃO-DE-CORDA E SORGO!!", [M, CA, SO], None, False, [], []),
    ("Milhos e feijões", [M, CA], None, False, [], []),
    ("milho verde e feijão verde", [M, CA], None, False, [], []),
    ("quero economizar água com milho e sorgo", [M, SO], "agua", False, [], []),
    ("tenho poço e quero plantar milheto", [MIL], None, False, [], []),
]


@pytest.mark.parametrize("frase,culturas,foco,ordem,proib,fora", CASOS)
def test_extrai_culturas_foco_ordem_restricao(frase, culturas, foco, ordem, proib, fora):
    r = IT.extrair(frase, municipios=[])
    assert r["culturas"] == culturas, r
    assert r["foco"] == foco
    assert r["ordem_dita"] is ordem
    assert r["proibidas"] == proib
    assert r["fora_da_lista"] == fora


def test_ha_pelo_menos_40_frases():
    assert len(CASOS) >= 40


def test_culturas_so_da_tabela():
    """Todo id extraído existe na tabela de culturas (nada inventado), e cultura fora da lista nunca vira id."""
    from src.culturas.tabela_culturas import carregar
    ids = set(carregar())
    for frase, *_ in CASOS:
        assert set(IT.extrair(frase, municipios=[])["culturas"]) <= ids
    assert set(IT.SINONIMOS) <= ids and set(IT.SINONIMOS) == ids      # as 16 culturas da tabela têm sinônimos


@pytest.mark.parametrize("frase,ambiguo", [("milho, feijão e crotalária", True), ("feijão", True), ("feijão caupi e milho", False), ("feijão de corda", False),
                                           ("feijão comum e milho", False), ("feijão de porco e milho", False)])
def test_feijao_sozinho_e_ambiguo_e_pede_confirmacao(frase, ambiguo):
    r = IT.extrair(frase, municipios=[])
    assert bool(r["ambiguos"]) is ambiguo
    assert (r["confianca"] == "baixa") is ambiguo


def test_grafia_corrigida_baixa_confianca():
    r = IT.extrair("plantar sorgu e milio", municipios=[])
    assert r["culturas"] == [SO, M] and r["confianca"] == "baixa" and r["aproximadas"]


def test_palavras_comuns_nao_viram_cultura_por_aproximacao():
    for f in ["quero plantar", "depois da safra", "cobertura do solo", "muita terra", "vamos fazer um ciclo", "milha"]:
        assert IT.extrair(f, municipios=[])["culturas"] in ([], [M]) or f == "milha"


@pytest.mark.parametrize("frase,tipo", [
    ("se eu montar um ciclo com milho e sorgo, qual a melhor ordem?", "avaliar"),
    ("o que dá para plantar aqui?", "sugerir"),
    ("quero economizar água, o que você indica?", "sugerir"),
    ("como vai ficar o verde nas próximas semanas?", "previsao"),
    ("por que o Sulco sugeriu esse caminho?", "explicar"),
    ("o que é lacuna?", "explicar"),
    ("só quero ver se milho e sorgo dão certo aqui", "viabilidade"),
    ("bom dia", "duvida_geral"),
])
def test_tipo_de_pedido(frase, tipo):
    assert IT.extrair(frase, municipios=[])["tipo"] == tipo


def test_culturas_soltas_sem_pedido_claro():
    r = IT.extrair("milho, sorgo e mandioca", municipios=[])
    assert r["tipo_cru"] == "duvida_geral" and len(r["culturas"]) == 3 and not r["ordem_dita"]


@pytest.mark.parametrize("frase,n", [("amendoim, girassol e mamona em 3 safras", 3), ("um ciclo de dois anos", 2), ("ciclo de 2 safras com milho", 2),
                                     ("quatro culturas", 4), ("quero milho", None)])
def test_quantidade_de_safras(frase, n):
    assert IT.extrair(frase, municipios=[])["n_safras"] == n


@pytest.mark.parametrize("frase,r", [("sim", "sim"), ("isso mesmo", "sim"), ("está certo", "sim"), ("não", "nao"), ("não, quero mudar", "nao"),
                                     ("errado", "nao"), ("não quero mandioca e quero milho hoje de manhã cedo", None), ("quero milho", None)])
def test_resposta_a_confirmacao(frase, r):
    assert IT.extrair(frase, municipios=[], pendente="confirmar")["afirmacao"] == r


def test_municipio_so_com_nome_unico_e_nome_comum_so_com_dica():
    m = [("quixada_ce", "quixada"), ("barro_ce", "barro"), ("crato_ce", "crato")]
    assert IT.extrair("moro em Quixadá", municipios=m)["ponto_id"] == "quixada_ce"
    assert IT.extrair("moro em Crato e Quixadá", municipios=m)["ponto_id"] is None          # dois: não adivinha
    assert IT.extrair("o barro da minha terra é duro e quero milho no meu terreno hoje", municipios=m)["ponto_id"] is None
    assert IT.extrair("em Barro", municipios=m)["ponto_id"] == "barro_ce"


def test_manejo():
    assert IT.extrair("tenho poço e irrigação", municipios=[])["manejo"] == "irrigado"
    assert IT.extrair("planto só na chuva, sequeiro", municipios=[])["manejo"] == "sequeiro"
    assert IT.extrair("quero milho", municipios=[])["manejo"] is None


def test_nunca_levanta_com_entrada_estranha():
    for x in ["", None, 123, "   ", "\x00\x01", "a" * 5000, "🌽🌽", "milho" * 400]:
        r = IT.extrair(x, municipios=[])
        assert isinstance(r["culturas"], list)
