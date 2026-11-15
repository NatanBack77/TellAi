"""Frases em português simples para o agricultor: datas de verdade no lugar de "decêndio" e "quinzena", e "X em cada 10 anos" no lugar de porcentagem."""
from __future__ import annotations

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


def quantos_anos(fracao: float) -> str:
    """0,91 -> 'Costuma dar certo aqui (9 em cada 10 anos)'."""
    n = round(fracao * 10)
    if n >= 9:
        return f"Costuma dar certo aqui ({n} em cada 10 anos)"
    if n >= 7:
        return f"Dá certo na maior parte dos anos ({n} em cada 10)"
    return f"Falha em alguns anos (deu certo em {n} de cada 10)"
