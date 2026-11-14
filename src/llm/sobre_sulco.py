"""Fonte 'sobre o Sulco' do chat: o glossário, a página 'Limites dos dados', as prioridades, o fluxo do cálculo e as seções do app.

Todo texto vem do CÓDIGO ou de ARQUIVO (nada digitado aqui de memória): `mvp.glossario_atual()` (com os trechos do acervo que o próprio
glossário cita), `mvp.limites_linhas()` (números lidos de arquivo), `mvp.PRIORIDADES`, o docstring de `mvp` (fluxo) e os títulos/
docstrings das páginas e seções lidos de `src/app/app.py` por `ast`. Cada documento sai no mesmo formato dos trechos do acervo
({n, arquivo, pagina, texto}) com `arquivo` = 'sobre o Sulco: ...', e entra no chat junto com o RAG, em índice léxico próprio.

Portão (anti-alucinação, como o do RAG): um termo do glossário só vale se TODAS as suas palavras de conteúdo estão na pergunta;
os documentos gerais (limites, fluxo, seções) só entram se a pergunta é sobre o próprio Sulco. Pergunta agronômica não os aciona.
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

from .fatos import simples_limite_global
from .verificador import sem_acento

ROTULO = "sobre o Sulco"
RAIZ = Path(__file__).resolve().parents[2]
ARQ_APP = RAIZ / "src/app/app.py"
MAX_DOCS = 3
STOP = set("a o as os um uma uns umas de do da dos das em no na nos nas por para com sem e ou que qual quais como quando onde "
           "e ao aos se sua seu suas seus isso essa esse esta este neste nesta app".split())
# pergunta SOBRE o próprio Sulco (controle de roteamento; não é conteúdo)
INTENCAO_FUNCIONA = re.compile(r"como (e )?(que )?(o sulco |o app |a ferramenta |ele |ela )?(funciona|calcula|calculam|decide|chega|faz as contas)|"
                               r"o que (e|faz) (o |a )?(sulco|app|aplicativo|ferramenta)\b|para que serve|"
                               r"\b(o sulco|este app|esse app|o aplicativo|a ferramenta) (calcula|funciona|decide|faz|escolhe|usa)")
INTENCAO_LIMITES = re.compile(r"limite|nao (sabe|consegue|enxerga|ve)\b|o que (voce|ele|o sulco) (nao )?(sabe|consegue|faz)|de onde (vem|vêm|veem)"
                              r"|fonte dos dados|confiavel|confianca|quantos (locais|municipios|pontos)|resolucao|celula|enxerga")


def _norm(s: str) -> str:
    return sem_acento(s.lower())


def _stems(s: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9]+", _norm(s)) if w not in STOP and len(w) >= 2}


def _chaves_termo(termo: str) -> list[frozenset[str]]:
    """Conjuntos de radicais, cada um suficiente para acionar o termo: o nome sem qualificativo e, se houver, a sigla entre parênteses."""
    principal = re.sub(r"\(.*?\)", " ", termo)
    chaves = [frozenset(_stems(principal))]
    m = re.search(r"\(([A-Z]{3,})\)", termo)
    if m:
        chaves.append(frozenset(_stems(m.group(1))))
    return [c for c in chaves if c]


# ---------------------------------------------------------------------------------------------- leitura do app.py (títulos e docstrings)
def _texto_literal(no: ast.AST) -> str | None:
    """Texto de uma constante ou f-string; cada {campo} vira 'seu local' (nenhum nome é lido)."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return no.value
    if isinstance(no, ast.JoinedStr):
        return "".join(p.value if isinstance(p, ast.Constant) else "seu local" for p in no.values)
    return None


def secoes_do_app(caminho: Path = ARQ_APP) -> dict:
    """{'paginas': [...], 'secoes': [{'funcao', 'titulos': [...], 'doc': str|None}]} lido do código de `app.py` (nada digitado aqui)."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    paginas, secoes = [], []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.func.attr == "radio" and len(no.args) >= 2 \
                and isinstance(no.args[1], ast.List) and "Meu local" in [getattr(e, "value", None) for e in no.args[1].elts]:
            paginas = [e.value for e in no.args[1].elts if isinstance(e, ast.Constant)]
    for no in arvore.body:
        if not (isinstance(no, ast.FunctionDef) and no.name.startswith(("painel_", "pagina_"))):
            continue
        titulos = []
        for c in ast.walk(no):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.args:
                t = _texto_literal(c.args[0])
                if t and (c.func.attr in ("header", "subheader") or (c.func.attr == "markdown" and t.startswith("####"))):
                    titulos.append(t.lstrip("# ").strip())
        doc = ast.get_docstring(no)
        if titulos or doc:
            secoes.append({"funcao": no.name, "titulos": titulos, "doc": doc.splitlines()[0] if doc else None})
    return {"paginas": paginas, "secoes": secoes}


# ---------------------------------------------------------------------------------------------- texto simples (para o agricultor)
# Palavras do Sulco que o agricultor pode perguntar. Definições em linguagem simples escritas aqui (explicam o vocabulário do app; não há
# número nem dado do local). A pergunta só aciona o termo se todas as palavras dele estiverem nela (portão do glossário).
GLOSSARIO_EXTRA = [      # palavras que o agricultor pode ouvir/ler e que NÃO estão no glossário do app
    ("Skill", "É o quanto o modelo acerta mais do que usar só a média dos anos anteriores."),
    ("Composto de 16 dias", "É a foto do satélite que junta as melhores imagens de umas duas semanas."),
]
# glossário do app (termo -> frase simples); a chave é o início do termo, sem acento e minúsculo
GLOSSARIO_SIMPLES = {
    "ndvi": "É o verde das plantas visto do satélite. Quanto mais verde, mais folha na área; não é colheita nem qualidade do solo.",
    "solo nu": "É a época em que a terra fica descoberta, com pouco verde, comparando com o resto do ano no mesmo local.",
    "anomalia": "É o quanto o verde das plantas visto do satélite está mais forte ou mais fraco do que o normal para aquela época do ano.",
    "umidade do solo": "É a água que está na terra. O satélite mede numa área grande, então não mostra a sua roça.",
    "evapotranspiracao": "É a água que o calor e as plantas tiram da terra. Aqui é só uma conta de referência, não é o que a sua planta gasta.",
    "veranico": "É um período seco no meio da época de chuva, com vários dias seguidos sem chover.",
    "empate tecnico": "Empate técnico quer dizer que, com os dados que temos, não dá para dizer qual é melhor.",
    "faixa de incerteza": "É a margem de variação: o resultado pode ser um pouco maior ou um pouco menor, e não dá para ter certeza.",
    "fixadoras de nitrogenio": "São plantas da família do feijão que pegam o nitrogênio do ar e deixam na terra. Por isso o Sulco dá ponto a elas na rotação.",
    "adubacao verde": "É plantar uma cobertura, como crotalária ou guandu, e deixar sobre a terra para cobrir o solo e dar matéria orgânica.",
    "raizes profundas": "São raízes que descem fundo e buscam água que as raízes rasas não alcançam. O Sulco não mede isso: usa o que a tabela diz de cada cultura.",
    "balanco hidrico": "É a conta da água: o que entra (chuva) menos o que sai (calor e uso pela planta). O Sulco só mostra a chuva menos a água que o calor tira, por quinzena; não é a conta completa do solo.",
    "risco de erosao": "É a chance de a chuva levar a terra embora. Cresce com terreno inclinado, solo descoberto e chuva forte. No mapa é só uma indicação, não mede quanta terra se perde.",
}
SIMPLES_FUNCIONA = [
    ("como o Sulco calcula", "O Sulco olha o seu local, compara três caminhos de rotação e mostra por que cada um foi sugerido e o que ainda falta saber."),
    ("prioridades", "Você escolhe o que pesa mais: economizar água, proteger o solo ou renda extra. Isso muda a ordem dos caminhos."),
    ("aviso do app", "O Sulco ajuda a conversar com o técnico; ele não escolhe a rotação por você nem promete ganho."),
]


def _simples_termo(termo: str) -> str | None:
    n = _norm(termo)
    return next((v for k, v in GLOSSARIO_SIMPLES.items() if n.startswith(k)), None)


# ---------------------------------------------------------------------------------------------- documentos
def _doc(grupo: str, rotulo: str, texto: str, chaves=None, simples: str | None = None) -> dict:
    return {"grupo": grupo, "arquivo": f"{ROTULO}: {rotulo}", "pagina": None, "texto": texto, "chaves": chaves or [],
            "stems": _stems(texto), "texto_simples": simples}


@lru_cache(maxsize=1)
def documentos() -> tuple[dict, ...]:
    from src.app import mvp as M
    docs: list[dict] = []
    for termo, texto, trecho in M.glossario_atual():
        t = f"{termo}: {texto}"
        if trecho:
            t += f" (Do acervo, {trecho['arquivo']}, p. {trecho['pagina']}: \"{trecho['trecho']}\")"
        docs.append(_doc("termo", "glossário", t, _chaves_termo(termo), _simples_termo(termo)))
    for termo, frase in GLOSSARIO_EXTRA:
        docs.append(_doc("termo", "glossário", f"{termo}: {frase}", _chaves_termo(termo), frase))
    lim = M.limites_linhas()
    for t in lim["visao_geral"] + lim["previsao"] + lim["motor"]:
        docs.append(_doc("limites", "limites dos dados", t, simples=simples_limite_global(t)))
    fluxo = re.search(r"Fluxo:.*?(?:\n\n|\Z)", M.__doc__ or "", flags=re.S)
    if fluxo:
        docs.append(_doc("funciona", "como o Sulco calcula (código)", " ".join(fluxo.group(0).split()), simples=SIMPLES_FUNCIONA[0][1]))
    for k, p in M.PRIORIDADES.items():
        docs.append(_doc("funciona", "prioridades", f"Prioridade '{p['rotulo']}': {p['regra']}", simples=SIMPLES_FUNCIONA[1][1]))
    docs.append(_doc("funciona", "aviso do app", M.AVISO, simples=SIMPLES_FUNCIONA[2][1]))
    try:
        s = secoes_do_app()
        if s["paginas"]:
            docs.append(_doc("funciona", "páginas do app", "O app tem as páginas: " + "; ".join(s["paginas"]) + "."))
        for sec in s["secoes"]:
            partes = list(dict.fromkeys(sec["titulos"]))
            if sec["doc"]:
                partes.append(sec["doc"])
            if partes:
                docs.append(_doc("secoes", "seções do app", f"Seção do app ({sec['funcao']}): " + " | ".join(partes)))
    except (OSError, SyntaxError):
        pass
    return tuple(docs)


def limpar_cache() -> None:
    documentos.cache_clear()


def buscar(pergunta: str, k: int = MAX_DOCS) -> dict:
    """Mesmo formato de `src.rag.busca.buscar`. Sem portão aprovado => sem_evidencia (e o chat segue para o RAG)."""
    n = _norm(pergunta)
    q = _stems(pergunta)
    docs = documentos()
    achados: list[dict] = []
    for d in docs:                                   # 1) termos do glossário: todas as palavras do nome na pergunta
        if d["grupo"] == "termo" and any(c <= q for c in d["chaves"]):
            achados.append(d)
    funciona, limites = bool(INTENCAO_FUNCIONA.search(n)), bool(INTENCAO_LIMITES.search(n))
    if funciona and not achados:                     # 2) pergunta sobre o próprio Sulco: fluxo, prioridades, páginas e seções
        achados += [d for d in docs if d["grupo"] in ("funciona", "secoes")
                    and (d["arquivo"].endswith(("código)", "páginas do app")) or len(d["stems"] & q) >= 2)][:k]
    if limites:                                      # 3) limites: os mais parecidos com a pergunta (>= 2 radicais em comum)
        pont = sorted(((len(d["stems"] & q), i, d) for i, d in enumerate(docs) if d["grupo"] == "limites"), key=lambda x: (-x[0], x[1]))
        melhores = [d for s, _, d in pont if s >= 2][:k]
        achados += melhores or [d for d in docs if d["grupo"] == "limites"][:k]   # sem parecido: o começo da página
    vistos, trechos = set(), []
    for d in achados:
        if d["texto"] in vistos:
            continue
        vistos.add(d["texto"])
        trechos.append({"n": len(trechos) + 1, "arquivo": d["arquivo"], "pagina": None, "texto": d["texto"], "texto_simples": d.get("texto_simples")})
        if len(trechos) >= k:
            break
    return {"sem_evidencia": not trechos, "mensagem": "" if trechos else "sem evidência", "trechos": trechos}


def e_sobre_o_sulco(arquivo: str) -> bool:
    return str(arquivo).startswith(ROTULO)
