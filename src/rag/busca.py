"""Busca hibrida (BM25 proprio + embeddings multilingual-e5-small, se disponiveis).

Saida de `buscar`:
    {"sem_evidencia": bool,
     "mensagem": "sem evidência" | "",
     "trechos": [{"n", "arquivo", "pagina", "texto"}, ...]}
`texto` e substring verificavel da pagina `pagina` de `docs_rag/<arquivo>` (ver rag_docs).

Anti-alucinacao: um trecho so e devolvido se passar por um portao de relevancia:
  (a) cobertura lexical: >= LIM_COBERTURA dos termos de conteudo da pergunta
      (radicais) aparecem no trecho; OU
  (b) similaridade de cosseno e5 >= LIM_COS (apenas se houver embeddings).
Nada passa => "sem evidência". Sem LLM, sem LangChain.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
DIR_INDICE = RAIZ / "indice"
MODELO_EMB = "intfloat/multilingual-e5-small"

LIM_COBERTURA = 0.6   # fracao dos radicais da pergunta presentes no trecho
LIM_COS = 0.87        # cosseno minimo; e5 comprime scores em ~0.76-0.92. Calibrado em poucas perguntas (negativas atingem max 0.862): margem pequena
K_PADRAO = 5
PESO_EXP = 0.5        # peso do voto da consulta expandida (sinonimos/EN) na fusao RRF
PASSA_EXP = False
N_RERANK = 30
W_FUSAO = 1.0
MODELO_CROSS = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
RRF_K = 60
MSG_SEM_EVIDENCIA = "sem evidência"

_STOP = set("""
a o as os um uma uns umas de do da dos das em no na nos nas por para pra com sem sob sobre entre ate ao aos
e ou mas que se como qual quais quando onde quem quanto quanta quantos quantas porque pois ja mais menos muito
muita muitos muitas pouco pouca eu tu ele ela nos eles elas meu minha seu sua isso isto esse essa esses essas
este esta estes estas aquele aquela ser sao era foi eh esta estao ter tem tenho temos ha havia pode podem posso
deve devo devem fazer faz fazem usar uso usa vale pena melhor bom boa qual preciso precisa posso devo
the of and or to in on for with is are be by as at from that this these those it its an
""".split())


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def radical(tok: str) -> str:
    """Radical grosseiro (plural + prefixo de 6 letras). Determinista, sem dicionario."""
    for suf in ("coes", "oes", "ais", "eis", "res", "ns", "es", "s"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            tok = tok[: -len(suf)]
            break
    return tok[:6]


def tokenizar(texto: str, manter_stop: bool = False) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", _sem_acento(texto.lower()))
    return [radical(t) for t in toks if (manter_stop or (t not in _STOP and len(t) >= 3))]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.dl = np.array([len(d) for d in docs], dtype=float)
        self.avg = self.dl.mean() if len(docs) else 0.0
        df: Counter = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, consulta: list[str]) -> np.ndarray:
        s = np.zeros(len(self.tf))
        for t in set(consulta):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, c in enumerate(self.tf):
                f = c.get(t)
                if f:
                    s[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avg))
        return s


# ------------------------------------------------- vocabulario (sinonimos PT e termos EN)
# Regras (regex sobre a pergunta sem acento, minuscula) -> termos extras anexados a consulta.
# Sao sinonimos/traducoes de vocabulario agronomico geral; NAO contem fatos nem respostas.
# Servem para: (a) "falta de agua" x "deficit hidrico"; (b) pergunta PT x documento EN (FAO).
SINONIMOS: list[tuple[str, str]] = [
    (r"falta d.? ?agua|escassez (hidrica|de agua)|seca\b|estiagem|sem agua|pouca agua",
     "déficit hídrico deficiência hídrica estresse hídrico water stress drought"),
    (r"deficit hidric|deficiencia hidric|estresse hidric",
     "falta de água seca water stress drought"),
    (r"rotacao de cultura|rotacao",
     "rotação de culturas sucessão de culturas crop rotation"),
    (r"palha|restos? de cultura|residuo|cobertura morta",
     "palhada cobertura morta resíduos vegetais mulch crop residues"),
    (r"cobertura (do solo|vegetal)|planta.{0,3} de cobertura",
     "cobertura do solo plantas de cobertura cover crops soil cover mulch"),
    (r"adub[oa].{0,3} verde|adubacao verde",
     "adubação verde adubos verdes plantas de cobertura leguminosas green manure cover crops"),
    (r"leguminos",
     "leguminosas fixação biológica de nitrogênio legumes nitrogen fixation"),
    (r"nitrogenio",
     "nitrogênio nitrogen fixação biológica"),
    (r"praga|doenca",
     "pragas doenças pests diseases"),
    (r"seguro rural|risco climatico|zoneamento",
     "zoneamento agrícola de risco climático ZARC"),
    (r"plantio direto|semeadura direta|sistema de plantio",
     "sistema plantio direto SPD no-till zero tillage direct seeding"),
    (r"agricultura de conservacao",
     "conservation agriculture CA"),
    (r"principio|pilar",
     "princípios pilares principles"),
    (r"erosao", "erosão erosion"),
    (r"chuva|vento", "chuva vento rain wind"),
    (r"consorci", "consórcio consorciado intercropping"),
    (r"semiarid", "Semi-Árido semiárido Caatinga Nordeste"),
    (r"eventos? climatic|mudanca.{0,3} clim", "climate change extreme climatic events"),
    (r"subsolador|escarificador", "ripper subsoiler"),
]
_SIN_RE = [(re.compile(r), extra) for r, extra in SINONIMOS]


def expandir_consulta(pergunta: str) -> str:
    """Termos extras (sinonimos/EN) a anexar a consulta; string vazia se nenhuma regra casar."""
    base = _sem_acento(pergunta.lower())
    extras = [e for r, e in _SIN_RE if r.search(base)]
    return " ".join(extras)


# ---------------------------------------------------------------- embeddings
_modelo = None


def _carregar_modelo():
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer  # import tardio: opcional
        _modelo = SentenceTransformer(MODELO_EMB, device="cpu")
    return _modelo


_cross = None


def _carregar_cross():
    global _cross
    if _cross is None:
        from sentence_transformers import CrossEncoder  # import tardio: opcional
        _cross = CrossEncoder(MODELO_CROSS, device="cpu")
    return _cross


def calcular_embeddings(textos: list[str], dir_indice: Path = DIR_INDICE) -> dict:
    """Embeddings 'passage: ' normalizados -> indice/embeddings.npy. Retorna metadados."""
    m = _carregar_modelo()
    emb = m.encode(["passage: " + t for t in textos], normalize_embeddings=True,
                   batch_size=32, show_progress_bar=False)
    np.save(dir_indice / "embeddings.npy", emb.astype(np.float32))
    try:
        from huggingface_hub import model_info
        rev = model_info(MODELO_EMB).sha
    except Exception:
        rev = None
    return {"modelo": MODELO_EMB, "dim": int(emb.shape[1]), "prefixo_passagem": "passage: ",
            "prefixo_consulta": "query: ", "revisao_hf": rev}


# -------------------------------------------------------------------- indice
class Indice:
    def __init__(self, dir_indice: Path = DIR_INDICE, usar_embeddings: bool = True, expandir: bool = False,
                 rerank: bool = True):
        self.dir = Path(dir_indice)
        self.expandir = expandir
        self.rerank = rerank
        self.trechos = [json.loads(l) for l in (self.dir / "trechos.jsonl").read_text(encoding="utf-8").splitlines() if l]
        self.tok = [tokenizar(t["texto"]) for t in self.trechos]
        self.sets = [set(t) for t in self.tok]
        self.bm25 = BM25(self.tok)
        self.emb = None
        arq = self.dir / "embeddings.npy"
        if usar_embeddings and arq.exists():
            e = np.load(arq)
            if e.shape[0] == len(self.trechos):
                self.emb = e
        self.modo = "hibrido" if self.emb is not None else "bm25"

    def _reordenar(self, pergunta: str, cand: list[int]) -> list[int]:
        """Reranking por cross-encoder multilingue sobre os candidatos da fusao (ordem estavel em empate)."""
        try:
            ce = _carregar_cross()
            sc = ce.predict([(pergunta, self.trechos[i]["texto"]) for i in cand], show_progress_bar=False)
        except Exception:
            return cand  # modelo indisponivel: mantem a ordem da fusao
        fus = {i: 1.0 / (r + 1) for r, i in enumerate(cand)}
        # combina o score do cross-encoder (z-score) com a posicao da fusao (peso pequeno)
        z = (sc - sc.mean()) / (sc.std() + 1e-9)
        return sorted(cand, key=lambda i: -(z[cand.index(i)] + W_FUSAO * fus[i]))

    def _cos(self, pergunta: str) -> np.ndarray | None:  # `pergunta` ja pode vir expandida
        if self.emb is None:
            return None
        try:
            q = _carregar_modelo().encode(["query: " + pergunta], normalize_embeddings=True)[0]
        except Exception:
            return None
        return self.emb @ q

    def buscar(self, pergunta: str, k: int = K_PADRAO, lim_cobertura: float = LIM_COBERTURA,
               lim_cos: float = LIM_COS) -> dict:
        q = tokenizar(pergunta)
        if not q:
            return _sem_evidencia()
        qset = set(q)
        extra = expandir_consulta(pergunta) if self.expandir else ""
        bm = self.bm25.scores(q)
        cos = self._cos(pergunta)
        # listas ordenadas: (pontuacoes, peso). A consulta expandida entra como voto extra (peso menor)
        listas = [(bm, 1.0), (cos, 1.0)]
        extoks = set(tokenizar(extra)) if extra else set()
        if extra:
            listas.append((self.bm25.scores(q + sorted(extoks)), PESO_EXP))
            ce = self._cos(pergunta + " " + extra)
            listas.append((ce, PESO_EXP))
        ranks = []
        for sc, w in listas:
            if sc is None:
                ranks.append(({}, w))
            else:
                ranks.append(({i: r for r, i in enumerate(np.argsort(-sc)[:50]) if sc[i] > 0}, w))
        cand = set().union(*[set(r) for r, _ in ranks])
        pont = {}
        for i in cand:
            cobertura = len(qset & self.sets[i]) / len(qset)
            passa = cobertura >= lim_cobertura or (cos is not None and cos[i] >= lim_cos)
            if not passa and extoks and PASSA_EXP:
                cob_exp = len((qset | extoks) & self.sets[i]) / len(qset | extoks)
                passa = cob_exp >= lim_cobertura
            if not passa:
                continue
            pont[i] = sum(w / (RRF_K + r[i]) for r, w in ranks if i in r)
        if not pont:
            return _sem_evidencia()
        ordem = sorted(pont, key=lambda i: -pont[i])
        if self.rerank:
            ordem = self._reordenar(pergunta, ordem[:N_RERANK]) + ordem[N_RERANK:]
        top = ordem[:k]
        return {"sem_evidencia": False, "mensagem": "", "modo": self.modo,
                "trechos": [{"n": n, "arquivo": self.trechos[i]["arquivo"],
                             "pagina": self.trechos[i]["pagina"], "texto": self.trechos[i]["texto"]}
                            for n, i in enumerate(top, start=1)]}


def _sem_evidencia() -> dict:
    return {"sem_evidencia": True, "mensagem": MSG_SEM_EVIDENCIA, "trechos": []}


_cache: dict[str, Indice] = {}


def buscar(pergunta: str, k: int = K_PADRAO, dir_indice: Path = DIR_INDICE, **kw) -> dict:
    chave = str(dir_indice)
    if chave not in _cache:
        _cache[chave] = Indice(dir_indice)
    return _cache[chave].buscar(pergunta, k=k, **kw)
