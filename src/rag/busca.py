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


# ---------------------------------------------------------------- embeddings
_modelo = None


def _carregar_modelo():
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer  # import tardio: opcional
        _modelo = SentenceTransformer(MODELO_EMB, device="cpu")
    return _modelo


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
    def __init__(self, dir_indice: Path = DIR_INDICE, usar_embeddings: bool = True):
        self.dir = Path(dir_indice)
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

    def _cos(self, pergunta: str) -> np.ndarray | None:
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
        bm = self.bm25.scores(q)
        cos = self._cos(pergunta)
        rank_bm = {i: r for r, i in enumerate(np.argsort(-bm)[:50]) if bm[i] > 0}
        rank_cos = {} if cos is None else {i: r for r, i in enumerate(np.argsort(-cos)[:50])}
        cand = set(rank_bm) | set(rank_cos)
        pont = {}
        for i in cand:
            cobertura = len(qset & self.sets[i]) / len(qset)
            passa = cobertura >= lim_cobertura or (cos is not None and cos[i] >= lim_cos)
            if not passa:
                continue
            s = 0.0
            if i in rank_bm:
                s += 1 / (RRF_K + rank_bm[i])
            if i in rank_cos:
                s += 1 / (RRF_K + rank_cos[i])
            pont[i] = s
        if not pont:
            return _sem_evidencia()
        top = sorted(pont, key=lambda i: -pont[i])[:k]
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
