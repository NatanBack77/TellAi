"""Verificador deterministico da saida do LLM (sem LLM). Falhou => o servico descarta e usa o template."""
from __future__ import annotations

import json
import re
import unicodedata

AVISO = "a avaliar com tecnico local"
MAX_CHARS = 3000
PROMESSAS = [
    r"rende mais", r"render[aá] mais", r"vai render", r"rendimento (maior|garantido)", r"garant\w*", r"aumenta a renda",
    r"aumentar a renda", r"aumento de renda", r"lucr\w*", r"mais dinheiro", r"ganhar mais", r"retorno financeiro",
    r"aumenta a produtividade", r"aumentar a produtividade", r"dobra\w*", r"com certeza", r"certamente",
    r"sem risco", r"infal\w+", r"100 ?%", r"enriquec\w*", r"produz mais", r"colhe mais",
]
_PROM = [re.compile(unicodedata.normalize("NFD", p).encode("ascii", "ignore").decode()) for p in PROMESSAS]
PALAVRAS_NUM = ("dois duas tres quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis dezessete "
                "dezoito dezenove vinte trinta quarenta cinquenta sessenta setenta oitenta noventa cem cento mil milhao "
                "milhoes metade dobro triplo").split()
_CIT = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
_NUM = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)*")


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _variantes(tok: str) -> set[float]:
    """Interpretacoes numericas de um token com tolerancia pt-BR/en ('1.234,5', '0,35', '0.35', '1.234')."""
    out: set[float] = set()
    try:
        if "," in tok and "." in tok:
            dec = "," if tok.rfind(",") > tok.rfind(".") else "."
            mil = "." if dec == "," else ","
            out.add(float(tok.replace(mil, "").replace(dec, ".")))
        elif "," in tok or "." in tok:
            sep = "," if "," in tok else "."
            partes = tok.split(sep)
            if len(partes) > 2:
                out.add(float("".join(partes)))
            else:
                out.add(float(partes[0] + "." + partes[1]))
                if len(partes[1]) == 3 and len(partes[0]) <= 3:
                    out.add(float(partes[0] + partes[1]))
        else:
            out.add(float(tok))
    except ValueError:
        pass
    return out


def _decimais(tok: str) -> int:
    m = re.search(r"[.,](\d+)$", tok)
    return len(m.group(1)) if m and not (len(m.group(1)) == 3 and re.fullmatch(r"\d{1,3}[.,]\d{3}", tok)) else 0


def numeros_da_fonte(*fontes) -> set[float]:
    """Todos os numeros presentes em JSON/texto/trechos de origem."""
    vals: set[float] = set()

    def visita(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            vals.add(float(x))
            vals.update(_variantes(repr(x)))
        elif isinstance(x, str):
            for t in re.findall(r"\d+(?:[.,]\d+)*", x):
                vals.update(_variantes(t))
        elif isinstance(x, dict):
            for k, v in x.items():
                visita(str(k))
                visita(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                visita(v)

    for f in fontes:
        visita(f)
    return vals


def _no_conjunto(tok: str, fonte: set[float]) -> bool:
    d = _decimais(tok)
    for v in _variantes(tok):
        for s in fonte:
            if abs(s - v) <= 1e-9 * max(1.0, abs(s)):
                return True
            if d >= 1 and abs(s - v) <= 0.5 * 10 ** -d + 1e-9:
                return True
    return False


def citacoes(texto: str) -> list[int]:
    return [int(n) for g in _CIT.findall(texto) for n in re.split(r"[,;]", g)]


def verificar(texto, cenario_json=None, trechos=None, exigir_citacao: bool | None = None) -> dict:
    """Retorna {'ok': bool, 'motivos': [..]}. `trechos`: lista de {n, texto, ...} enviados ao modelo."""
    motivos: list[str] = []
    trechos = [t for t in (trechos or []) if isinstance(t, dict)]
    if not isinstance(texto, str) or not texto.strip():
        return {"ok": False, "motivos": ["saida vazia"]}
    if len(texto) > MAX_CHARS:
        motivos.append("saida longa demais")
    existentes = {t.get("n") for t in trechos}
    for n in sorted(set(citacoes(texto))):
        if n not in existentes:
            motivos.append(f"citacao [{n}] inexistente")
    if (exigir_citacao if exigir_citacao is not None else bool(trechos)) and not citacoes(texto):
        motivos.append("sem citacao [n]")
    sem_cit = _CIT.sub(" ", texto)
    fonte = numeros_da_fonte(cenario_json, [t.get("texto", "") for t in trechos])
    for tok in _NUM.findall(sem_cit):
        if not _no_conjunto(tok, fonte):
            motivos.append(f"numero '{tok}' fora da fonte")
    norm = sem_acento(texto.lower())
    for p in _PROM:
        m = p.search(norm)
        if m:
            motivos.append(f"promessa proibida: '{m.group()}'")
    fonte_txt = sem_acento(json.dumps(cenario_json, ensure_ascii=False).lower() + " " +
                           " ".join(str(t.get("texto", "")) for t in trechos).lower())
    for w in PALAVRAS_NUM:
        if re.search(rf"\b{w}\b", norm) and not re.search(rf"\b{w}\b", fonte_txt):
            motivos.append(f"numero por extenso '{w}' fora da fonte")
    if AVISO not in norm:
        motivos.append("falta o aviso 'a avaliar com técnico local'")
    return {"ok": not motivos, "motivos": motivos}
