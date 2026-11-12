"""Acervo local -> trechos indexaveis (extracao fiel, sem resumo, sem texto de memoria).

Regras:
- O texto indexado e exatamente o texto extraido do PDF por `pdftotext` (poppler),
  pagina a pagina, com UMA normalizacao documentada: sequencias de espacos/quebras
  de linha viram um unico espaco (`normalizar_ws`).
- Cada trecho e uma substring contigua da pagina normalizada; `pagina` e 1-based
  (numero fisico da pagina no PDF, nao o numero impresso).
- O manifesto (docs_rag/manifesto.json) guarda URL, data de download e sha256;
  `construir_indice` recusa arquivo cujo sha256 difere do manifesto.

Uso:  python -m src.rag.rag_docs          (reconstroi indice/)
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_DOCS = RAIZ / "docs_rag"
DIR_INDICE = RAIZ / "indice"
MANIFESTO = DIR_DOCS / "manifesto.json"
MODELO_EMB = "intfloat/multilingual-e5-small"

ALVO_CHARS = 600      # tamanho-alvo de um trecho
MAX_CHARS = 1000      # limite duro
MIN_CHARS = 120       # trechos menores sao descartados
MIN_FRACAO_LETRAS = 0.65  # descarta tabelas numericas / lixo


def normalizar_ws(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def extrair_paginas(pdf: Path) -> list[str]:
    """Texto normalizado de cada pagina (indice 0 = pagina 1)."""
    saida = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")
    paginas = saida.split("\f")
    if paginas and paginas[-1].strip() == "":
        paginas = paginas[:-1]
    return [normalizar_ws(p) for p in paginas]


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


_FIM_SENT = re.compile(r"(?<=[.!?;:])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9\"“(])")


def _fracao_letras(t: str) -> float:
    return sum(c.isalpha() for c in t) / max(1, len(t))


def cortar_pagina(texto: str) -> list[tuple[int, int]]:
    """Spans (ini, fim) de `texto` em janelas de ~ALVO_CHARS, em fronteira de frase,
    com sobreposicao de uma frase. Spans sao indices da string original."""
    if not texto:
        return []
    cortes = [0] + [m.end() for m in _FIM_SENT.finditer(texto)] + [len(texto)]
    # frases = (cortes[i], cortes[i+1])
    sents = [(cortes[i], cortes[i + 1]) for i in range(len(cortes) - 1) if cortes[i + 1] > cortes[i]]
    # quebra frases gigantes em pedacos de MAX_CHARS em espaco
    sp: list[tuple[int, int]] = []
    for a, b in sents:
        while b - a > MAX_CHARS:
            k = texto.rfind(" ", a, a + MAX_CHARS)
            k = k if k > a else a + MAX_CHARS
            sp.append((a, k))
            a = k + 1 if texto[k:k + 1] == " " else k
        sp.append((a, b))
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(sp):
        ini = sp[i][0]
        j = i
        while j < len(sp) and sp[j][1] - ini < ALVO_CHARS:
            j += 1
        j = min(j, len(sp) - 1)
        if sp[j][1] - ini > MAX_CHARS and j > i:
            j -= 1
        spans.append((ini, sp[j][1]))
        if j >= len(sp) - 1:
            break
        i = j if j > i else j + 1  # sobreposicao de 1 frase
    return spans


@dataclass
class Trecho:
    id: int
    arquivo: str
    pagina: int
    texto: str


def trechos_do_pdf(pdf: Path) -> list[Trecho]:
    out: list[Trecho] = []
    for p, texto in enumerate(extrair_paginas(pdf), start=1):
        for a, b in cortar_pagina(texto):
            t = texto[a:b].strip()
            if len(t) < MIN_CHARS or _fracao_letras(t) < MIN_FRACAO_LETRAS:
                continue
            out.append(Trecho(-1, pdf.name, p, t))
    return out


def carregar_manifesto() -> dict:
    return json.loads(MANIFESTO.read_text(encoding="utf-8"))


def construir_indice(com_embeddings: bool = True, dir_docs: Path = DIR_DOCS,
                     dir_indice: Path = DIR_INDICE) -> dict:
    """Le o manifesto, valida sha256, extrai trechos e grava indice/."""
    man = json.loads((dir_docs / "manifesto.json").read_text(encoding="utf-8"))
    todos: list[Trecho] = []
    docs_ok, erros = [], []
    for d in man["documentos"]:
        pdf = dir_docs / d["arquivo"]
        if not pdf.exists():
            erros.append(f"{d['arquivo']}: arquivo ausente")
            continue
        sha = sha256_arquivo(pdf)
        if sha != d["sha256"]:
            erros.append(f"{d['arquivo']}: sha256 difere do manifesto ({sha})")
            continue
        ts = trechos_do_pdf(pdf)
        todos.extend(ts)
        docs_ok.append({"arquivo": d["arquivo"], "titulo": d["titulo"], "tipo": d.get("tipo"),
                        "url": d["url"], "data_download": d["data_download"], "trechos": len(ts)})
    for i, t in enumerate(todos, start=1):
        t.id = i
    dir_indice.mkdir(exist_ok=True)
    with open(dir_indice / "trechos.jsonl", "w", encoding="utf-8") as f:
        for t in todos:
            f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")
    meta = {"documentos": docs_ok, "erros": erros, "n_trechos": len(todos),
            "normalizacao": "pdftotext por pagina; espacos/quebras -> 1 espaco",
            "embeddings": None}
    if com_embeddings:
        try:
            from .busca import calcular_embeddings
            meta["embeddings"] = calcular_embeddings([t.texto for t in todos], dir_indice)
        except Exception as e:  # modelo ausente/nao instalavel: segue so com BM25
            meta["embeddings"] = None
            meta["embeddings_erro"] = f"{type(e).__name__}: {e}"
            arq = dir_indice / "embeddings.npy"
            if arq.exists():
                arq.unlink()
    (dir_indice / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    m = construir_indice()
    print(json.dumps({k: m[k] for k in ("n_trechos", "erros", "embeddings")}, ensure_ascii=False, indent=2))
