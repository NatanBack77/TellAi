"""Pre-gera o cache de demo da camada LLM para os cenarios de data/processed/cenarios/.

    python -m src.llm.pregerar            # COM DEEPSEEK_API_KEY: chama o provedor e grava o cache
                                          # SEM chave: avisa e nao faz nada (nenhuma chamada de rede)
    python -m src.llm.pregerar --max 3    # limita o numero de cenarios
A chave nunca e impressa. O cache guarda a saida BRUTA do modelo; o verificador roda de novo na leitura.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import servico
from .cache import Cache, PASTA_PADRAO
from .integracao import obter_provedor_real, tem_chave

RAIZ = Path(__file__).resolve().parents[2]
PASTA_CENARIOS = RAIZ / "data" / "processed" / "cenarios"


def carregar(pasta: Path = PASTA_CENARIOS) -> list[dict]:
    out = []
    for p in sorted(Path(pasta).glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        itens = d if isinstance(d, list) else d.get("cenarios", [d]) if isinstance(d, dict) else []
        out += [c for c in itens if isinstance(c, dict)]
    return out


def pregerar(pasta: Path = PASTA_CENARIOS, provedor=None, cache: Cache | None = None, maximo: int | None = None) -> dict:
    prov = provedor or obter_provedor_real()
    if not tem_chave(prov):
        return {"feito": False, "motivo": "DEEPSEEK_API_KEY não configurada: nada foi gerado (nenhuma chamada feita).",
                "n": 0}
    cache = cache if cache is not None else Cache()
    cens = carregar(pasta)[:maximo]
    cont = {"llm": 0, "template": 0}
    rej = []
    for c in cens:
        r = servico.reescrever(c, provedor=prov, cache=cache, offline=False)
        cont[r["origem"]] = cont.get(r["origem"], 0) + 1
        if r["origem"] != "llm":
            rej.append(r["motivos"])
    return {"feito": True, "n": len(cens), "por_origem": cont, "rejeicoes": rej[:10], "cache": str(cache.pasta)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None)
    a = ap.parse_args(argv)
    r = pregerar(maximo=a.max)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
