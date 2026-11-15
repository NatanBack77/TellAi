"""Carga e validação do dado curado do plano de plantio (`data/plano/plano_plantio.csv`), gerado por `src.plano.construir`.

Cada linha = um atributo de uma cultura numa etapa, com a fonte (nome, página, trecho literal). Lacuna e "não se aplica" são linhas explícitas.
A validação falha ALTO: dado sem fonte, termo proibido (produto/defensivo) no valor, cultura desconhecida ou status inválido derrubam a carga.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.plano.etapas import ETAPAS_CURADAS, PROIBIDOS, STATUS

RAIZ = Path(__file__).resolve().parents[2]
ARQ_DADOS = RAIZ / "data" / "plano" / "plano_plantio.csv"
ARQ_CULTURAS = RAIZ / "data" / "culturas" / "tabela_culturas.csv"
COLUNAS = ["cultura_id", "etapa", "atributo", "valor", "unidade", "status", "fonte", "url", "pagina", "trecho", "contexto", "requer_tecnico",
           "motivo_interno", "data_consulta"]
_PROIB = re.compile("|".join(PROIBIDOS), re.I)


@dataclass(frozen=True)
class Linha:
    cultura_id: str
    etapa: int
    atributo: str
    valor: str
    unidade: str
    status: str
    fonte: str
    url: str
    pagina: int | None
    trecho: str
    contexto: str
    requer_tecnico: bool
    motivo_interno: str
    data_consulta: str


def termo_proibido(texto: str) -> str | None:
    m = _PROIB.search(texto or "")
    return m.group(0) if m else None


@lru_cache(maxsize=1)
def culturas_da_tabela() -> frozenset[str]:
    with open(ARQ_CULTURAS, encoding="utf-8", newline="") as f:
        return frozenset(r["cultura_id"] for r in csv.DictReader(f))


def validar(linhas: list[dict]) -> list[str]:
    """Lista de problemas (vazia = ok). Não altera nada."""
    erros: list[str] = []
    vistos: set[tuple] = set()
    cultu = culturas_da_tabela()
    for i, r in enumerate(linhas, 2):
        onde = f"linha {i} ({r.get('cultura_id')}|{r.get('etapa')}|{r.get('atributo')})"
        try:
            etapa = int(r["etapa"])
        except (KeyError, ValueError):
            erros.append(f"{onde}: etapa inválida"); continue
        if etapa not in ETAPAS_CURADAS:
            erros.append(f"{onde}: etapa {etapa} não é de dado curado")
        if r["cultura_id"] not in cultu:
            erros.append(f"{onde}: cultura fora da tabela de culturas")
        if r["status"] not in STATUS:
            erros.append(f"{onde}: status inválido '{r['status']}'")
        if r["status"] == "verificado":
            if not r["valor"].strip():
                erros.append(f"{onde}: verificado sem valor")
            if not r["fonte"].strip() or not r["trecho"].strip():
                erros.append(f"{onde}: verificado sem fonte ou sem trecho")
            if not str(r["pagina"]).strip().isdigit():
                erros.append(f"{onde}: verificado sem página numérica")
            t = termo_proibido(r["valor"])
            if t:
                erros.append(f"{onde}: termo proibido no valor ('{t}')")
        elif r["valor"].strip():
            erros.append(f"{onde}: {r['status']} não pode ter valor")
        elif r["trecho"].strip() or r["fonte"].strip():
            erros.append(f"{onde}: {r['status']} não pode ter fonte nem trecho (sem trecho conferido não há fonte)")
        t = termo_proibido(r["contexto"])
        if t:
            erros.append(f"{onde}: termo proibido no contexto público ('{t}')")
        if r["requer_tecnico"] not in ("0", "1"):
            erros.append(f"{onde}: requer_tecnico deve ser 0 ou 1")
        k = (r["cultura_id"], etapa, r["atributo"], r["valor"], r["pagina"])
        if k in vistos:
            erros.append(f"{onde}: linha duplicada")
        vistos.add(k)
    return erros


def _linha(r: dict) -> Linha:
    return Linha(r["cultura_id"], int(r["etapa"]), r["atributo"], r["valor"], r["unidade"], r["status"], r["fonte"], r["url"],
                 int(r["pagina"]) if str(r["pagina"]).strip().isdigit() else None, r["trecho"], r["contexto"], r["requer_tecnico"] == "1",
                 r["motivo_interno"], r["data_consulta"])


@lru_cache(maxsize=1)
def carregar(arquivo: str | None = None) -> dict[tuple[str, int], list[Linha]]:
    """{(cultura_id, etapa): [Linha, ...]}. Levanta ValueError se o arquivo não existe ou não passa na validação."""
    arq = Path(arquivo) if arquivo else ARQ_DADOS
    if not arq.is_file():
        raise ValueError(f"dado do plano não encontrado: {arq.name} (rode: python -m src.plano.construir)")
    with open(arq, encoding="utf-8", newline="") as f:
        leitor = csv.DictReader(f)
        if leitor.fieldnames != COLUNAS:
            raise ValueError(f"colunas inesperadas em {arq.name}: {leitor.fieldnames}")
        linhas = list(leitor)
    erros = validar(linhas)
    if erros:
        raise ValueError("dado do plano inválido:\n  " + "\n  ".join(erros[:20]) + (f"\n  ... e mais {len(erros) - 20}" if len(erros) > 20 else ""))
    out: dict[tuple[str, int], list[Linha]] = {}
    for r in linhas:
        ln = _linha(r)
        out.setdefault((ln.cultura_id, ln.etapa), []).append(ln)
    return out
