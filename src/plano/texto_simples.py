"""Frases em português simples para o agricultor: datas de verdade no lugar de "decêndio" e "quinzena", e "X em cada 10 anos" no lugar de porcentagem."""
from __future__ import annotations

import re

_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _faixas(indices: list[int]) -> list[tuple[int, int]]:
    faixas: list[tuple[int, int]] = []
    for i in sorted(set(indices)):
        if faixas and i == faixas[-1][1] + 1:
            faixas[-1] = (faixas[-1][0], i)
        else:
            faixas.append((i, i))
    return faixas


def datas_decendios(permitido) -> str:
    """36 decêndios (3 por mês, True = pode plantar) -> 'de 11 de janeiro até o fim de fevereiro' (várias faixas ligadas por ' e ')."""
    def comeco(d: int) -> str:
        dia = (1, 11, 21)[d % 3]
        return f"{dia}º de {_MESES[d // 3]}" if dia == 1 else f"{dia} de {_MESES[d // 3]}"

    def fim(d: int) -> str:
        return f"{(10, 20)[d % 3]} de {_MESES[d // 3]}" if d % 3 < 2 else f"o fim de {_MESES[d // 3]}"

    return " e ".join(f"de {comeco(a)} até {fim(b)}" for a, b in _faixas([i for i, ok in enumerate(permitido) if ok]))


def datas_quinzenas(quinzenas: list[int]) -> str:
    """Quinzenas numeradas de 1 a 24 -> 'de 16 de janeiro até 15 de maio'."""
    def comeco(q: int) -> str:
        return f"{'1º' if q % 2 == 1 else '16'} de {_MESES[(q - 1) // 2]}"

    def fim(q: int) -> str:
        return f"15 de {_MESES[(q - 1) // 2]}" if q % 2 == 1 else f"o fim de {_MESES[(q - 1) // 2]}"

    return " e ".join(f"de {comeco(a)} até {fim(b)}" for a, b in _faixas(quinzenas))


_TROCAS = [
    (re.compile(r"\s*\((?:nota|Nota) \d+\)"), ""),                                  # "(nota 6)": nota de rodapé da fonte, não ajuda o agricultor
    (re.compile(r"\bt/ha\b"), "toneladas por hectare"),
    (re.compile(r"\bkg ha-1\b|\bkg/ha\b"), "kg por hectare"),
    (re.compile(r"\bplantas/ha\b|\bpl/ha\b"), "plantas por hectare"),
    (re.compile(r"/ha\b"), " por hectare"),
    (re.compile(r"\bde P2O5\b"), "de fósforo (P2O5)"),
    (re.compile(r"\bde K2O\b"), "de potássio (K2O)"),
]


def simplificar(texto: str) -> str:
    """Só a FORMA: troca siglas por palavras ('kg/ha' -> 'kg por hectare') e tira nota de rodapé. Nunca muda número nem acrescenta informação."""
    for padrao, troca in _TROCAS:
        texto = padrao.sub(troca, texto)
    return re.sub(r"\s{2,}", " ", texto).strip()


def quantos_anos(fracao: float) -> str:
    """0,91 -> 'Costuma dar certo aqui (9 em cada 10 anos)'."""
    n = round(fracao * 10)
    if n >= 10:
        return "O clima daqui foi bom para essa planta em todos os últimos 24 anos"
    if n >= 9:
        return "O clima daqui foi bom para essa planta em quase todos os últimos 24 anos"
    if n >= 7:
        return "O clima daqui foi bom para essa planta na maior parte dos últimos 24 anos"
    return f"O clima daqui falhou para essa planta em vários dos últimos 24 anos (foi bom em só {n} de cada 10)"
