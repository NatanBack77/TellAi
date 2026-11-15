"""Extração DETERMINÍSTICA de intenção da mensagem do agricultor (sem LLM, sem rede, sem custo; testável).

Tira da frase: culturas (com sinônimos, flexões e erros comuns de grafia), ordem/quantidade de safras, foco (água, solo, renda, nitrogênio,
palha, pragas, forragem), tipo de pedido, restrições ('não quero mandioca'), município (só para achar o ponto, nunca vai à IA) e a resposta
sim/não a uma confirmação. Culturas FORA da tabela (melancia, abóbora...) nunca viram id: voltam em `fora_da_lista` para o diálogo dizer, com
franqueza, que ainda não há dado delas.

`confianca` = 'baixa' quando há termo ambíguo ('feijão' sozinho pode ser caupi ou comum), grafia corrigida por aproximação ou conflito
(a mesma cultura pedida e proibida): o gerente de diálogo CONFIRMA antes de calcular. O texto nunca é fonte de fato: só de entidades.
"""
from __future__ import annotations

import difflib
import re

from .verificador import sem_acento

# ------------------------------------------------------------------------------------------------ culturas (ids = tabela_culturas.csv)
SINONIMOS: dict[str, list[str]] = {
    "milho": ["milho", "milho verde", "milho cateto", "milho crioulo"],
    "feijao_caupi": ["feijao de corda", "feijao caupi", "caupi", "feijao macassar", "macassar", "feijao fradinho", "fradinho", "feijao verde",
                     "feijao manteiguinha", "manteiguinha", "feijao-de-corda"],
    "feijao_comum": ["feijao comum", "feijao carioca", "carioca", "feijao preto", "feijao rajado", "feijao mulatinho"],
    "sorgo": ["sorgo", "sorgo forrageiro", "sorgo granifero"],
    "milheto": ["milheto"],
    "mandioca": ["mandioca", "macaxeira", "aipim", "maniva", "mandioca brava", "mandioca mansa"],
    "algodao": ["algodao", "algodao herbaceo", "algodao colorido", "algodao em caroco"],
    "amendoim": ["amendoim"],
    "girassol": ["girassol"],
    "mamona": ["mamona", "carrapateira", "mamoneira"],
    "gergelim": ["gergelim", "sesamo"],
    "guandu": ["guandu", "feijao guandu", "andu", "feijao andu", "feijao-guandu"],
    "palma_forrageira": ["palma forrageira", "palma", "palma miuda", "palma gigante", "palma orelha de elefante", "palma doce"],
    "crotalaria_juncea": ["crotalaria juncea", "crotalaria", "crotalaria-juncea"],
    "feijao_de_porco": ["feijao de porco", "feijao-de-porco", "feijao porco", "canavalia"],
    "mucuna": ["mucuna", "mucuna preta", "mucuna cinza", "mucuna anã", "mucuna ana"],
}
# termo ambíguo: vale para uma cultura mais provável, mas pede confirmação
AMBIGUOS: dict[str, dict] = {
    "feijao": {"id": "feijao_caupi", "alternativas": ["feijao_caupi", "feijao_comum"]},
    "feijoes": {"id": "feijao_caupi", "alternativas": ["feijao_caupi", "feijao_comum"]},
}
# fora da lista do Sulco: nunca vira cultura; o diálogo diz que não há dado
FORA_DA_LISTA = {
    "melancia": "melancia", "abobora": "abóbora", "jerimum": "jerimum", "tomate": "tomate", "cebola": "cebola", "batata": "batata",
    "batata doce": "batata-doce", "arroz": "arroz", "trigo": "trigo", "cana": "cana", "cana de acucar": "cana-de-açúcar", "banana": "banana",
    "coco": "coco", "caju": "caju", "manga": "manga", "uva": "uva", "cafe": "café", "soja": "soja", "capim": "capim", "pimentao": "pimentão",
    "quiabo": "quiabo", "maxixe": "maxixe", "coentro": "coentro", "alface": "alface", "repolho": "repolho", "cenoura": "cenoura",
    "pepino": "pepino", "melao": "melão", "mamao": "mamão", "laranja": "laranja", "limao": "limão", "abacaxi": "abacaxi", "cacau": "cacau",
    "abacate": "abacate", "goiaba": "goiaba", "acerola": "acerola", "ervilha": "ervilha", "lentilha": "lentilha", "grao de bico": "grão-de-bico",
    "fava": "fava", "leucena": "leucena", "gliricidia": "gliricídia", "aveia": "aveia", "cevada": "cevada", "inhame": "inhame", "pimenta": "pimenta",
    "beterraba": "beterraba", "couve": "couve", "chuchu": "chuchu", "braquiaria": "braquiária", "capim elefante": "capim-elefante", "sisal": "sisal",
    "umbu": "umbu", "mangaba": "mangaba", "jaca": "jaca", "graviola": "graviola", "pinha": "pinha", "amora": "amora", "morango": "morango",
}

NOME_FORA = FORA_DA_LISTA


def _norm(s: str) -> str:
    t = sem_acento(str(s).lower())
    t = re.sub(r"[-_/]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _padrao_termo(t: str) -> str:
    """Termo com flexão simples (plural 's'/'es') e espaço ou hífen entre palavras."""
    p = re.escape(_norm(t)).replace(r"\ ", r"[\s-]+")
    return rf"(?<![a-z0-9]){p}(?:s|es)?(?![a-z0-9])"


_TERMOS: list[tuple[str, str, str]] = []        # (regex, tipo, chave) tipo: 'cultura' | 'ambiguo' | 'fora'
for _cid, _ts in SINONIMOS.items():
    for _t in _ts:
        _TERMOS.append((_padrao_termo(_t), "cultura", _cid))
for _t, _v in AMBIGUOS.items():
    _TERMOS.append((_padrao_termo(_t), "ambiguo", _t))
for _t in FORA_DA_LISTA:
    _TERMOS.append((_padrao_termo(_t), "fora", _t))
_TERMOS.sort(key=lambda x: -len(x[0]))          # termos longos primeiro: 'feijao de porco' antes de 'feijao'
_TERMOS = [(re.compile(r), tp, ch) for r, tp, ch in _TERMOS]

# vocabulário de uma palavra para erro de grafia (aproximação)
_VOCAB: dict[str, tuple[str, str]] = {}
for _cid, _ts in SINONIMOS.items():
    for _t in _ts:
        _n = _norm(_t)
        if " " not in _n and len(_n) >= 5:
            _VOCAB[_n] = ("cultura", _cid)
for _t in AMBIGUOS:
    if len(_t) >= 5:
        _VOCAB[_t] = ("ambiguo", _t)
for _t in FORA_DA_LISTA:
    if " " not in _t and len(_t) >= 5:
        _VOCAB[_t] = ("fora", _t)
# palavras comuns que NÃO podem virar cultura por aproximação
_NAO_FUZZY = set("agora entao ainda depois antes planta plantar plantas plantio plantei plantou ciclo ciclos rotacao safra safras quero queria melhor outra outro agua terra solo "
                 "depois primeiro seguido antes aqui local gastar gasto renda forte cultura culturas palha mesmo tempo tenho fazer cobertura "
                 "milha mulher manga cafe carro vamos todas todos pouca pouco muita muito pasto gado".split())


# ------------------------------------------------------------------------------------------------ foco, tipo, restrição
FOCOS = ("agua", "solo", "renda", "nitrogenio", "palhada", "pragas", "forragem")
ROTULO_FOCO = {"agua": "economizar água", "solo": "proteger o solo", "renda": "pensar na renda", "nitrogenio": "adubar a terra com planta (nitrogênio)",
               "palhada": "cobrir o solo com palha", "pragas": "reduzir pragas e doenças", "forragem": "ter comida para os animais (forragem)"}
_FOCO_RE = {
    "agua": r"\bagua\b|gastar menos agua|economiz\w+ agua|poupar agua|pouca agua|falta d agua|seca\b|estiagem|veranico|aguent\w+ (a )?seca|resistente a seca|"
            r"pouca chuva|chove pouco|irrigacao cara|menos irrigacao|consumo de agua",
    "solo": r"\bsolo\b|\bterra\b|erosao|enxurrada|conservar|proteger o solo|cuidar da terra|terra fraca|terra cansada|materia organica|solo descoberto|"
            r"solo nu|compactacao|fertilidade",
    "renda": r"\brenda\b|renda extra|vender|\bvenda\b|mercado|\bdinheiro\b|\bganhar\b|\bganho\b|sustento|\bcomercio\b",
    "nitrogenio": r"nitrogenio|adubacao verde|adubo verde|adubar|\badubo\b|fixa\w* nitrogenio|fixacao|\buree?ia\b|\bna terra\b.{0,12}nutri",
    "palhada": r"palhada|\bpalha\b|cobertura morta|cobertura do solo|plantio direto|cobrir o solo",
    "pragas": r"\bpraga|doenca|lagarta|pulgao|quebrar (o )?ciclo|nematoide|fungo|mosca branca",
    "forragem": r"forragem|forrageira|racao|\bpasto\b|\bgado\b|silagem|\bbode\b|\bcabra\b|ovelha|animais|capim|alimento (para|pro|dos) animais|comida (pro|para o|dos) (gado|animais)",
}
_FOCO = {k: re.compile(v) for k, v in _FOCO_RE.items()}

_NEGA_CUE = re.compile(r"\b(nao (quero|vou|posso|gosto d\w+|tenho|plant\w+|pretendo|da|dao|uso|trabalho com)|sem|evit\w+|menos|exceto|tirando|"
                       r"fora|nunca|dispenso|alem d\w+ nao|nao)\b")
_QUEBRA = re.compile(r"[,.;:!?]|\bmas\b|(?<!nao )\bquero\b|\bpreciso\b|\bgostaria\b")

_TIPOS = [
    ("previsao", r"^(?!.*\b(costuma\w*|sofr\w+)\b).*(previs\w+|\bndvi\b|como vai (ficar|estar)|proxim\w+ (semana|quinzena|dia)|nas proximas|verdor|vegetacao|satelite|vai ficar)"),   # "quando a vegetação costuma sofrer" é do passado (épocas de estresse), não previsão
    ("explicar", r"por ?que\b|explic\w+|como funciona|o que (e|sao|significa)\b|\bsignifica\b|quer dizer|de onde (vem|vêm)|\bcaminhos?\b|\blacuna|"
                 r"como (voces |o sulco |o app )?(calcula|decide|funciona)|para que serve|limite"),
    ("viabilidade", r"da(o)? (certo )?(aqui|no meu|na minha)|da pra plantar|serve(m)? (aqui|pra mim|para mim)|viavel|viabilidade|"
                    r"so ver se|ver se (dao|da|serve)|aguenta(m)?\b|posso plantar|vai bem aqui|da bem"),
    ("avaliar", r"\bciclo\b|rotacao|sequencia|\bdepois\b|primeiro|em seguida|seguid[oa]|montar|montei|combin\w+|junt[oa]s?|\bordem\b|"
                r"melhor (ordem|solucao|jeito|forma|combinacao|sequencia)|se eu (plantar|montar|fizer|colocar)|alternar|consorci"),
    ("sugerir", r"o que (da|posso|devo|vale|planto|plantar|tem pra|tem para|se da|combina)|que (planta|cultura|culturas|plantas) (da|posso|combina|serve)|"
                r"sugir\w*|sugest\w+|indic\w+|recomend\w+|me (ajud\w+|diga|fale|mostre|conte)|qual (cultura|planta|rotacao|plantio)|opcoes|"
                r"alternativas|que tal|\bideia\b|nao sei o que|o que (voce|vc|ce) (acha|indica|sugere)|plantar aqui|plantar na minha|quero (plantar|saber|ajuda)|"
                r"o que (fazer|plantar)"),
]
_TIPOS = [(t, re.compile(r)) for t, r in _TIPOS]
_MELHOR = re.compile(r"melhor|ideal|mais indicad|mais adequad|o que (voce|vc|ce)? ?(indica|sugere|acha)|qual (seria|e|vale|seria a)\b")
_ORDEM_CUE = re.compile(r"\bprimeiro\b|\bprimeira\b|\bdepois\b|em seguida|\bseguid[oa]s?\b|\bantes\b|por fim|por ultimo|no final|na ordem|\bapos\b|\bsegunda safra|"
                        r"\bde pois\b|→|->|>")
_DEPOIS_DE = re.compile(r"\b(depois d[eoa]s?|apos|logo apos|vindo depois d[eoa]s?|seguind[oa] (o|a|de))\b")
_ANTES_DE = re.compile(r"\bantes d[eoa]s?\b")
_NUM = {"um": 1, "uma": 1, "1": 1, "dois": 2, "duas": 2, "2": 2, "tres": 3, "3": 3, "quatro": 4, "4": 4}
_N_SAFRAS = re.compile(r"\b(um|uma|dois|duas|tres|quatro|[1-4])\s+(safras?|culturas?|plantios?|colheitas?)\b|\bciclo de (um|uma|dois|duas|tres|quatro|[1-4])\b")
_SIM = re.compile(r"^(sim|isso( mesmo| ai)?|certo|esta certo|ta certo|correto|exato|exatamente|pode ser|pode|ok|uhum|aham|claro|positivo|"
                  r"isso ai|e isso( mesmo)?|e sim|sim,? (esta|ta|isso))\b")
_NAO = re.compile(r"^(nao|errado|negativo|esta errado|nao esta|nao e isso|ta errado|nao,)\b")
_IRRIGADO = re.compile(r"irrigad\w+|irrigacao|\bpoco\b|\bacude\b|tenho agua|gotejament\w+|aspersao|pivo")
_SEQUEIRO = re.compile(r"sequeiro|sem irrigacao|so (na|com a) chuva|so de chuva|depende da chuva")
_ADICIONAR = re.compile(r"\b(tambem|e mais|mais uma|alem d\w+|acrescent\w+|adicion\w+|coloca\w*|junta\w*|inclu\w+|e (se )?(eu )?(botar|colocar|incluir))\b")
_ESCOLHA_ORDEM = {"ver_ordem": re.compile(r"melhor ordem|ver a ordem|qual (a )?ordem|em que ordem|ver a melhor"),
                  "so_viabilidade": re.compile(r"so ver se (dao|da|serve)|ver se dao|so (ver )?se (dao|da)"),
                  "ja_tenho": re.compile(r"ja tenho (uma )?ordem|tenho a ordem|minha ordem")}


def _cultura_ou_ambiguo(tp: str, ch: str):
    if tp == "cultura":
        return ch, False
    return AMBIGUOS[ch]["id"], True


def achar_mencoes(n: str) -> list[dict]:
    """Culturas (e ambíguas/fora da lista) citadas em `n` (texto já normalizado), em ordem de aparição, sem sobreposição."""
    ocupado: list[tuple[int, int]] = []
    achados: list[dict] = []

    def livre(a, b):
        return all(b <= x or a >= y for x, y in ocupado)
    for rg, tp, ch in _TERMOS:
        for m in rg.finditer(n):
            if livre(m.start(), m.end()):
                ocupado.append((m.start(), m.end()))
                achados.append({"pos": m.start(), "fim": m.end(), "tipo": tp, "chave": ch, "termo": m.group(), "aprox": False})
    # erro de grafia: palavra solta parecida com termo conhecido (mesma letra inicial, semelhança >= 0,8)
    for m in re.finditer(r"[a-z]{5,}", n):
        if not livre(m.start(), m.end()) or m.group() in _NAO_FUZZY:
            continue
        w = m.group()
        cands = [v for v in _VOCAB if v[0] == w[0] and abs(len(v) - len(w)) <= 2]
        par = difflib.get_close_matches(w, cands, n=1, cutoff=0.8)
        if par:
            tp, ch = _VOCAB[par[0]]
            ocupado.append((m.start(), m.end()))
            achados.append({"pos": m.start(), "fim": m.end(), "tipo": tp, "chave": ch, "termo": w, "aprox": True})
    return sorted(achados, key=lambda a: a["pos"])


def _negada(n: str, pos: int) -> bool:
    """A cultura que começa em `pos` está sob uma negação ('não quero mandioca', 'sem mandioca')? Olha só o trecho depois da última quebra."""
    antes = n[:pos]
    cortes = list(_QUEBRA.finditer(antes))
    trecho = antes[cortes[-1].end():] if cortes else antes
    palavras = trecho.split()[-6:]
    return bool(_NEGA_CUE.search(" ".join(palavras)))


def _ordenar(n: str, ments: list[dict]) -> list[dict]:
    """Ordem das safras: a ordem de aparição, trocando os pares ligados por 'depois de/após' ('feijão depois do milho' = milho, feijão)."""
    seq: list[dict] = []
    for i, m in enumerate(ments):
        if i > 0:
            entre = n[ments[i - 1]["fim"]:m["pos"]]
            if _DEPOIS_DE.search(entre) and ments[i - 1] in seq:
                seq.insert(seq.index(ments[i - 1]), m)
                continue
        seq.append(m)
    return seq


def extrair(mensagem: str, municipios: list[tuple[str, str]] | None = None, pendente: str | None = None) -> dict:
    """Entidades e intenção da mensagem. `municipios` = [(ponto_id, nome_sem_acento)] (padrão: pontos do projeto). Nunca levanta."""
    n = _norm(mensagem if isinstance(mensagem, str) else "")
    ments = achar_mencoes(n)
    culturas, proibidas, fora, ambiguos, aprox, vistos = [], [], [], [], [], set()
    pos_cult: list[dict] = []
    for m in ments:
        if m["tipo"] == "fora":
            nome = NOME_FORA[m["chave"]]
            if nome not in fora:
                fora.append(nome)
            continue
        cid, amb = _cultura_ou_ambiguo(m["tipo"], m["chave"])
        if _negada(n, m["pos"]):
            if cid not in proibidas:
                proibidas.append(cid)
            continue
        if cid in vistos:
            continue
        vistos.add(cid)
        pos_cult.append({**m, "cid": cid})
        if amb:
            ambiguos.append({"termo": m["termo"], "escolhido": cid, "alternativas": AMBIGUOS[m["chave"]]["alternativas"]})
        if m["aprox"]:
            aprox.append({"termo": m["termo"], "id": cid})
    ordenado = _ordenar(n, pos_cult)
    culturas = [m["cid"] for m in ordenado][:8]
    ordem_dita = bool(len(culturas) >= 2 and (_ORDEM_CUE.search(n)))
    ns = _N_SAFRAS.search(n)
    n_safras = _NUM.get(ns.group(1) or ns.group(3)) if ns else None
    focos = [(m.start(), k) for k, r in _FOCO.items() for m in [r.search(n)] if m]
    focos = [k for _, k in sorted(focos)]
    if "renda" in focos and re.search(r"quero (ganhar|lucrar)|ganhar", n) and len(focos) > 1:
        pass
    foco = focos[0] if focos else None
    tipo = None
    for t, r in _TIPOS:
        if r.search(n):
            tipo = t
            break
    escolha = next((k for k, r in _ESCOLHA_ORDEM.items() if r.search(n)), None)
    if escolha == "so_viabilidade":
        tipo = "viabilidade"
    elif escolha == "ver_ordem":
        tipo = "avaliar"
    tipo_cru = tipo or "duvida_geral"          # 'duvida_geral' = a frase não traz pedido claro (ex.: só 'milho, feijão e sorgo')
    if tipo is None:
        tipo = "sugerir" if (foco and not culturas) else "avaliar" if len(culturas) >= 2 else "duvida_geral"
    if tipo == "viabilidade" and not culturas and foco:
        tipo = "sugerir"
    if culturas and tipo in ("sugerir", "duvida_geral"):
        tipo = "avaliar"                      # citou cultura: o pedido é olhar o que ele citou (uma só = viabilidade e o que ela deixa na terra)
    pal = n.split()
    curta = len(pal) <= 4
    afirmacao = "sim" if (_SIM.search(n) and (curta or n.startswith(("sim", "isso", "certo", "correto")))) else None
    if _NAO.search(n) and (curta or re.match(r"^(nao e isso|nao esta|esta errado|errado|ta errado|nao,)", n)):
        afirmacao = "nao"
    if afirmacao == "nao" and pendente != "confirmar" and not curta:
        afirmacao = None
    motivos = []
    if ambiguos:
        motivos.append("termo ambíguo: " + ", ".join(a["termo"] for a in ambiguos))
    if aprox:
        motivos.append("grafia corrigida: " + ", ".join(f"{a['termo']}" for a in aprox))
    conflito = sorted(set(culturas) & set(proibidas))
    if conflito:
        motivos.append("cultura pedida e proibida ao mesmo tempo")
    manejo = "irrigado" if _IRRIGADO.search(n) and not _SEQUEIRO.search(n) else "sequeiro" if _SEQUEIRO.search(n) else None
    return {"texto_norm": n, "culturas": culturas, "ordem_dita": ordem_dita, "n_safras": n_safras, "foco": foco, "focos": focos, "tipo": tipo, "tipo_cru": tipo_cru,
            "proibidas": proibidas, "fora_da_lista": fora, "ambiguos": ambiguos, "aproximadas": aprox, "afirmacao": afirmacao, "manejo": manejo,
            "adicionar": bool(_ADICIONAR.search(n)), "pede_melhor": bool(_MELHOR.search(n)), "escolha_ordem": escolha,
            "ponto_id": achar_municipio(n, municipios), "confianca": "baixa" if motivos else "alta", "motivos_baixa": motivos}


# ------------------------------------------------------------------------------------------------ município (só para achar o ponto)
_COMUNS = {"barro", "jardim", "granja", "cruz", "aurora", "graca", "cedro", "marco", "choro", "milha", "baixio", "jati", "oros", "palhano", "umari"}
_CUE_MUN = re.compile(r"(?:\b(?:em|de|do|da|no|na|moro|sou|municipio|cidade|aqui|fica|perto)\s+)$")


def achar_municipio(n: str, municipios: list[tuple[str, str]] | None = None) -> str | None:
    """ponto_id se UM município do projeto aparece na mensagem (nome palavra inteira); nomes que também são palavras comuns só com 'em/de...'."""
    if municipios is None:
        from .seguranca import municipios_do_projeto
        municipios = municipios_do_projeto()
    n = _norm(n)
    achados = set()
    for pid, nome in municipios:
        nm = _norm(nome)
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(nm) + r"(?![a-z0-9])", n):
            if nm in _COMUNS and not (_CUE_MUN.search(n[:m.start()]) or len(n.split()) <= 3):
                continue
            achados.add(pid)
    return next(iter(achados)) if len(achados) == 1 else None


# ================================================================================================ PLANTIOS (calendário)
# 'plantei milho em fevereiro', 'semeei feijão no começo de março', 'botei sorgo faz dois meses', 'ontem plantei sorgo'.
# Saída = ENTIDADES (cultura + 'quando' no formato de `culturas.calendario_plantio`), nunca fato. Data relativa vira data concreta com a `hoje`
# injetada; mês sem ano fica sem ano (o cálculo escolhe o mais recente que já começou). Texto fora do padrão não é adivinhado: vira pergunta.
import calendar as _cal
from datetime import date as _date, timedelta as _td

_MESES_N = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_MES_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(_MESES_N) + r")(?![a-z0-9])")
_VERBO_PLANTIO = re.compile(r"(?<![a-z0-9])(plant(ei|amos|ou|aram|ado|ada|ados|adas)|semei(ei|amos|ou)|sement(ei|amos)|botei|botamos|coloquei|colocamos|pus|pusemos|"
                            r"joguei|jogamos|fiz o plantio|fizemos o plantio|plantio (feito|foi)|ja plantei)(?![a-z0-9])")
_NEGA_VERBO = re.compile(r"(?<![a-z])(nao|nunca|jamais|ainda nao)\s+(?:\w+\s+)?(plantei|plantamos|semeei|semeamos|botei|botamos|coloquei|colocamos|joguei)")
_VERBOS_FUZZY = ["plantei", "plantamos", "semeei", "semeamos", "plantado", "plantada"]
_PARTE_ANTES = re.compile(r"(?:no |nos |do |de |ali |la )?(comeco|inicio|principio|primeiros dias|primeira semana|meio|meados|metade|segunda semana|terceira semana|"
                          r"fim|final|finalzinho|ultimos dias|ultima semana|quarta semana)(?: do mes| de| do| da)?(?: mes)?(?: de| do)?\s*$")
_PARTE_DEPOIS = re.compile(r"^[\s,]*(?:no |nos |la no |la pelo |pelo |ali no |mais ou menos no |mais pro )?(comeco|inicio|principio|meio|meados|fim|final|finalzinho)(?![a-z])")
_PARTE_MAP = {"comeco": "comeco", "inicio": "comeco", "principio": "comeco", "primeiros dias": "comeco", "primeira semana": "comeco", "meio": "meio",
              "meados": "meio", "metade": "meio", "segunda semana": "meio", "terceira semana": "meio", "fim": "fim", "final": "fim", "finalzinho": "fim",
              "ultimos dias": "fim", "ultima semana": "fim", "quarta semana": "fim"}
_NUM_EXT = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
            "doze": 12, "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40, "sessenta": 60, "noventa": 90, "cem": 100}
_N_RE = r"(\d{1,3}|" + "|".join(_NUM_EXT) + r")"
_REL = re.compile(r"(?<![a-z0-9])(?:faz|fazem|ha|tem|ja faz|faz mais ou menos|faz uns|faz umas|ha uns|ha umas|faz cerca de)\s+(?:uns |umas |cerca de |quase |mais de )?" + _N_RE +
                  r"\s+(dia|dias|semana|semanas|mes|meses|ano|anos)(?![a-z])")
_ESTACAO = re.compile(r"(?<![a-z0-9])(no inverno|na quadra chuvosa|na quadra|no tempo das aguas|no tempo de chuva|na epoca das chuvas|na epoca de chuva|"
                      r"nas primeiras chuvas|com as primeiras chuvas|no periodo chuvoso)(?![a-z])")
_DATA_BARRA = re.compile(r"(?<![0-9/])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![0-9/])")
_DIA_MES = re.compile(r"(?<![0-9])(?:dia\s+)?(\d{1,2})\s+de\s+(" + "|".join(_MESES_N) + r")(?:\s+de\s+(\d{4}))?(?![a-z0-9])")
_ANO = re.compile(r"^\s*(?:de|do|em)?\s*(20\d\d)(?![0-9])")
_CICLO_DIAS = re.compile(r"(?:ciclo(?: dela| da semente| dela e| de)?\s*(?:de|em|e de|e)?\s*(?:uns |umas |cerca de |mais ou menos )?(\d{2,3})\s*dias|"
                         r"(?:leva|demora|dura|fica|colhe com|colho com|colhe em|colho em|colhe de|de)\s+(?:uns |umas |cerca de |mais ou menos |ate )?(\d{2,3})\s*dias|"
                         r"(\d{2,3})\s*dias\s+de\s+ciclo|semente de (\d{2,3})\s*dias|(\d{2,3})\s*dias(?: ate| pra| para| pro) (?:a )?(?:colheita|colher))")
_SO_NUMERO = re.compile(r"^\s*(?:uns |umas |cerca de |mais ou menos |ate |de |em )?(\d{2,3})(?:\s*dias?)?\s*[.!]?\s*$")
_N_MESES_CICLO = re.compile(r"^\s*(?:uns |umas |cerca de |mais ou menos )?" + _N_RE + r"\s+mes(?:es)?\s*[.!]?\s*$")
_NAO_SEI = re.compile(r"^(nao sei|nao lembro|nao me lembro|sei nao|nao tenho certeza|esqueci|nao faco ideia|nao conheco|nao sabe|nao|nada|nenhum|sem ideia|nao lembro nao|"
                      r"nao sei nao|nao sei dizer)\b")


_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_MES_ABREV_RE = re.compile(r"(?<![a-z0-9])(?:em|de|no|desde|ate|ja em)\s+(" + "|".join(_ABREV) + r")\.?(?![a-z0-9])")


def _norm_barra(s: str) -> str:
    """Como `_norm`, mas mantém a barra de datas ('10/02')."""
    t = sem_acento(str(s).lower())
    t = re.sub(r"[-_]", " ", t)
    return re.sub(r"[ \t\r\n]+", " ", t).strip()


def _n_pal(w: str) -> int | None:
    w = w.strip()
    if w.isdigit():
        return int(w)
    return _NUM_EXT.get(w)


def _mes_aprox(w: str) -> int | None:
    """Número do mês (1 a 12) de uma palavra (com erro de grafia: 'fervereiro', 'feveriro', 'setenbro')."""
    if w in _MESES_N:
        return _MESES_N.index(w) + 1
    if len(w) >= 5 and w not in _NAO_FUZZY:
        par = difflib.get_close_matches(w, [m for m in _MESES_N if m[0] == w[0]], n=1, cutoff=0.8)
        if par:
            return _MESES_N.index(par[0]) + 1
    return None


def _data_valida(a: int, m: int, d: int) -> _date | None:
    try:
        return _date(a, m, d)
    except ValueError:
        return None


def _quando_relativo(n: str, hoje: _date) -> list[dict]:
    out = []
    for m in re.finditer(r"(?<![a-z0-9])(anteontem|ontem|hoje|agora ha pouco)(?![a-z])", n):
        d = hoje - _td(days={"anteontem": 2, "ontem": 1}.get(m.group(1), 0))
        out.append({"pos": m.start(), "fim": m.end(), "spec": {"data": d.isoformat()}, "tipo": "relativo"})
    for m in re.finditer(r"(?<![a-z0-9])(?:na )?semana passada(?![a-z])", n):
        seg = hoje - _td(days=hoje.weekday())                       # segunda-feira desta semana
        a = seg - _td(days=7)
        out.append({"pos": m.start(), "fim": m.end(), "spec": {"de": a.isoformat(), "ate": (a + _td(days=6)).isoformat(), "precisao": "semana"}, "tipo": "relativo"})
    for m in re.finditer(r"(?<![a-z0-9])(?:no )?mes passado(?![a-z])", n):
        a = _date(hoje.year, hoje.month, 1) - _td(days=1)
        out.append({"pos": m.start(), "fim": m.end(), "spec": {"mes": a.month, "ano": a.year, "parte": None}, "tipo": "relativo"})
    for m in _REL.finditer(n):
        k = _n_pal(m.group(1))
        un = m.group(2)
        if not k:
            continue
        if un.startswith("dia"):
            d = hoje - _td(days=k)
            spec = {"data": d.isoformat()} if k <= 3 else {"de": (d - _td(days=2)).isoformat(), "ate": (d + _td(days=2)).isoformat(), "precisao": "relativo"}
        elif un.startswith("semana"):
            d = hoje - _td(days=7 * k)
            spec = {"de": (d - _td(days=3)).isoformat(), "ate": (d + _td(days=3)).isoformat(), "precisao": "relativo"}
        elif un.startswith("mes"):
            mm = hoje.month - 1 - k
            a, m_ = hoje.year + mm // 12, mm % 12 + 1
            d = _date(a, m_, min(hoje.day, _cal.monthrange(a, m_)[1]))
            spec = {"de": (d - _td(days=7)).isoformat(), "ate": (d + _td(days=7)).isoformat(), "precisao": "relativo"}
        else:
            d = _data_valida(hoje.year - k, hoje.month, min(hoje.day, 28))
            if d is None:
                continue
            spec = {"de": (d - _td(days=15)).isoformat(), "ate": (d + _td(days=15)).isoformat(), "precisao": "relativo"}
        out.append({"pos": m.start(), "fim": m.end(), "spec": spec, "tipo": "relativo"})
    return out


def achar_quandos(n: str, hoje: _date) -> list[dict]:
    """Expressões de TEMPO do texto normalizado `n`, em ordem, sem sobreposição: [{pos, fim, spec, tipo}]. `spec` = formato de `calendario_plantio`."""
    achados: list[dict] = list(_quando_relativo(n, hoje))

    def livre(a, b):
        return all(b <= x["pos"] or a >= x["fim"] for x in achados)
    for m in _ESTACAO.finditer(n):
        if livre(m.start(), m.end()):
            a = hoje.year if _date(hoje.year, 2, 1) <= hoje else hoje.year - 1
            achados.append({"pos": m.start(), "fim": m.end(), "tipo": "estacao",
                            "spec": {"de": _date(a, 2, 1).isoformat(), "ate": _date(a, 5, 31).isoformat(), "precisao": "estacao"}})
    for m in _DIA_MES.finditer(n):
        if livre(m.start(), m.end()):
            mes, dia = _MESES_N.index(m.group(2)) + 1, int(m.group(1))
            ano = int(m.group(3)) if m.group(3) else (hoje.year if _data_valida(hoje.year, mes, dia) and _data_valida(hoje.year, mes, dia) <= hoje else hoje.year - 1)
            d = _data_valida(ano, mes, dia)
            if d:
                achados.append({"pos": m.start(), "fim": m.end(), "tipo": "data", "spec": {"data": d.isoformat()}})
    for m in _DATA_BARRA.finditer(n):
        if livre(m.start(), m.end()):
            dia, mes = int(m.group(1)), int(m.group(2))
            if m.group(3):
                a = int(m.group(3))
                a += 2000 if a < 100 else 0
            else:
                d0 = _data_valida(hoje.year, mes, dia)
                a = hoje.year if d0 and d0 <= hoje else hoje.year - 1
            d = _data_valida(a, mes, dia)
            if d:
                achados.append({"pos": m.start(), "fim": m.end(), "tipo": "data", "spec": {"data": d.isoformat()}})
    for m in _MES_RE.finditer(n):
        if not livre(m.start(), m.end()):
            continue
        mes = _MESES_N.index(m.group(1)) + 1
        achados.append(_spec_mes(n, m.start(), m.end(), mes, hoje))
    for m in _MES_ABREV_RE.finditer(n):
        if livre(m.start(1), m.end(1)):
            achados.append(_spec_mes(n, m.start(1), m.end(1), _ABREV.index(m.group(1)) + 1, hoje))
    for m in re.finditer(r"[a-z]{5,}", n):          # mês com erro de grafia
        w = m.group()
        if not livre(m.start(), m.end()) or w in _MESES_N or w in _NAO_FUZZY or m.start() in {a["pos"] for a in achados}:
            continue
        mes = _mes_aprox(w)
        if mes:
            a = _spec_mes(n, m.start(), m.end(), mes, hoje)
            a["aprox"] = True
            achados.append(a)
    return sorted(achados, key=lambda a: a["pos"])


def _spec_mes(n: str, pos: int, fim: int, mes: int, hoje: _date) -> dict:
    """Mês + parte ('começo de', 'no meio de', 'fim de') + ano ('de 2025', 'ano passado'): o que está junto do nome do mês."""
    antes = n[max(0, pos - 32):pos]
    parte = None
    pa = _PARTE_ANTES.search(antes)
    ini = pos
    if pa:
        parte, ini = _PARTE_MAP.get(pa.group(1)), pos - (len(antes) - pa.start())
    else:
        pd_ = _PARTE_DEPOIS.search(n[fim:fim + 24])
        if pd_:
            parte = _PARTE_MAP.get(pd_.group(1))
            fim = fim + pd_.end()
    ano = None
    ma = _ANO.search(n[fim:fim + 12])
    if ma:
        ano = int(ma.group(1))
        fim += ma.end()
    elif re.match(r"\s*(?:de\s+)?(?:do )?ano passado", n[fim:fim + 22]):
        ano = hoje.year - 1
        fim += re.match(r"\s*(?:de\s+)?(?:do )?ano passado", n[fim:fim + 22]).end()
    elif re.match(r"\s*(?:de\s+)?(?:deste|desse|este|esse) ano", n[fim:fim + 22]):
        ano = hoje.year
        fim += re.match(r"\s*(?:de\s+)?(?:deste|desse|este|esse) ano", n[fim:fim + 22]).end()
    return {"pos": ini, "fim": fim, "tipo": "mes", "spec": {"mes": mes, "ano": ano, "parte": parte}}


def tem_verbo_plantio(n: str) -> bool:
    if _VERBO_PLANTIO.search(n):
        return True
    for w in re.findall(r"[a-z]{6,}", n):
        if w in _NAO_FUZZY:
            continue
        if difflib.get_close_matches(w, _VERBOS_FUZZY, n=1, cutoff=0.8):
            return True
    return False


def ler_ciclo_dias(texto: str, pendente: bool = False) -> tuple[int | None, bool]:
    """(dias, nao_sabe): 'uns 90 dias', 'ciclo de 120 dias', '3 meses' (resposta à pergunta; 1 mês = 30 dias, declarado), 'não sei'.
    Fora de 30 a 800 dias = ignorado (volta a perguntar). `pendente`: aceita só o número."""
    n = _norm(texto)
    m = _CICLO_DIAS.search(n)
    if m:
        v = int(next(g for g in m.groups() if g))
        return (v, False) if 30 <= v <= 800 else (None, False)
    if pendente:
        if _NAO_SEI.search(n):
            return None, True
        m = _SO_NUMERO.match(n)
        if m and 30 <= int(m.group(1)) <= 800:
            return int(m.group(1)), False
        m = _N_MESES_CICLO.match(n)
        if m and _n_pal(m.group(1)):
            v = _n_pal(m.group(1)) * 30
            return (v, False) if 30 <= v <= 800 else (None, False)
    return None, False


def ler_mes(texto: str, hoje: _date) -> dict | None:
    """Resposta a 'Em que mês você plantou?': {'mes','ano','parte'} ou None. Aceita 'fevereiro', 'em março de 2025', 'no começo de maio'."""
    n = _norm_barra(texto)
    for a in achar_quandos(n, hoje):
        if a["tipo"] == "mes":
            return dict(a["spec"])
    return None


def ler_parte(texto: str) -> tuple[str | None, bool]:
    """(parte, nao_sabe): 'no começo' -> comeco, 'meio' -> meio, 'fim' -> fim, 'não lembro' -> (None, True)."""
    n = _norm(texto)
    if _NAO_SEI.search(n) or re.search(r"nao lembro|nao sei|esqueci|o mes todo|todo o mes|varios dias", n):
        return None, True
    m = re.search(r"(?<![a-z])(comeco|inicio|principio|primeiros dias|primeira semana|meio|meados|metade|segunda semana|terceira semana|fim|final|finalzinho|ultimos dias|ultima semana|quarta semana)(?![a-z])", n)
    return (_PARTE_MAP[m.group(1)], False) if m else (None, False)


def extrair_plantios(mensagem: str, hoje: _date | None = None, pendente: str | None = None) -> dict:
    """Plantios ditos na mensagem. `eh_plantio` = há verbo de plantio (ou 'plantado') e ao menos uma cultura. Cada plantio: {cultura (id|None), ambiguo (alternativas),
    fora (nome fora da lista), quando (formato do calendário | None), aprox}. Várias culturas na frase: o tempo vale para a cultura que vem antes dele; um tempo
    no começo da frase vale para todas. Nunca levanta."""
    hoje = hoje or _date.today()
    n_raw = _norm_barra(mensagem if isinstance(mensagem, str) else "")
    n = n_raw.replace("/", " ")                       # mesmo tamanho: as posições valem nos dois
    verbo = tem_verbo_plantio(n) and not _NEGA_VERBO.search(n)
    ments = [m for m in achar_mencoes(n) if not _negada(n, m["pos"])]
    quandos = achar_quandos(n_raw, hoje)
    ciclo, _ = ler_ciclo_dias(n)
    # o tempo e a duração do ciclo não podem ser confundidos: '60 dias' em 'faz 60 dias' já foi lido como tempo
    rel_spans = [(q["pos"], q["fim"]) for q in quandos if q["tipo"] == "relativo"]
    if ciclo and any(a <= (_CICLO_DIAS.search(n).start() if _CICLO_DIAS.search(n) else -1) < b for a, b in rel_spans):
        ciclo = None
    plantios: list[dict] = []
    fora: list[str] = []
    ordem = sorted(ments, key=lambda m: m["pos"])
    for i, m in enumerate(ordem):
        if m["tipo"] == "fora":
            nome = NOME_FORA[m["chave"]]
            if nome not in fora:
                fora.append(nome)
            plantios.append({"cultura": None, "ambiguo": None, "fora": nome, "quando": None, "aprox": False, "pos": m["pos"]})
            continue
        cid, amb = _cultura_ou_ambiguo(m["tipo"], m["chave"])
        plantios.append({"cultura": cid, "ambiguo": AMBIGUOS[m["chave"]]["alternativas"] if amb else None, "fora": None, "quando": None, "aprox": bool(m["aprox"]),
                         "pos": m["pos"], "fim": m["fim"]})
    # atribui tempos: o primeiro tempo depois de cada cultura (e antes da próxima); o que veio antes de todas vale para as que ficaram sem tempo
    for i, p in enumerate(plantios):
        limite = plantios[i + 1]["pos"] if i + 1 < len(plantios) else len(n) + 1
        for q in quandos:
            if p["pos"] <= q["pos"] < limite:
                p["quando"], p["aprox"] = q["spec"], p["aprox"] or bool(q.get("aprox"))
                break
    if plantios:
        antes = [q for q in quandos if q["pos"] < plantios[0]["pos"]]
        if antes:
            for p in plantios:
                if p["quando"] is None:
                    p["quando"] = antes[0]["spec"]
        # um tempo só no fim da frase vale para todas as culturas citadas ('plantei milho e feijão em março')
        if len(quandos) == 1 and len(plantios) > 1:
            for p in plantios:
                if p["quando"] is None:
                    p["quando"] = quandos[0]["spec"]
    if verbo and not plantios and quandos:           # 'plantei em fevereiro' (sem dizer a cultura): o diálogo pergunta qual
        plantios.append({"cultura": None, "ambiguo": None, "fora": None, "quando": quandos[0]["spec"], "aprox": False})
    for p in plantios:
        p.pop("pos", None), p.pop("fim", None)
    cults = [p for p in plantios if p["cultura"] or p["ambiguo"]]
    amb = [p for p in plantios if p["ambiguo"]]
    sim = bool(_SIM.search(n)) and len(n.split()) <= 4
    nao = bool(_NAO.search(n)) and len(n.split()) <= 4
    return {"texto_norm": n, "verbo": verbo, "eh_plantio": bool(verbo and (cults or fora or plantios)), "plantios": plantios, "ciclo_dias": ciclo, "fora_da_lista": fora,
            "ambiguos": bool(amb), "afirmacao": "sim" if sim else "nao" if nao else None, "tem_quando": bool(quandos),
            "ponto_id": achar_municipio(n)}
