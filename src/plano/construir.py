"""Constrói `data/plano/plano_plantio.csv` a partir da curadoria em `data/plano_staging/claude/` (etapas 1, 4 a 10).

    python -m src.plano.construir          # grava o CSV e o manifesto (falha se a validação não passar)
    python -m src.plano.construir --testar # só valida, não grava

O que faz além de juntar os arquivos:
  - separa do `contexto` a nota "REVISÃO TÉCNICA: ..." (vira `requer_tecnico=1` + `motivo_interno`, que NÃO vai para a API);
  - marca `requer_tecnico=1` quando o trecho cita produto/fumigação (a API não mostra esse trecho);
  - valida tudo (src/plano/dados.py): dado sem fonte, termo proibido no valor/contexto ou cultura desconhecida param a construção.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from src.plano import dados
from src.plano.etapas import ETAPAS_CURADAS

RAIZ = dados.RAIZ
STAGING = RAIZ / "data" / "plano_staging" / "claude"
SAIDA = dados.ARQ_DADOS
MANIFESTO = SAIDA.with_name("manifesto.json")
_REV = re.compile(r"REVISÃO TÉCNICA:.*?(?=; (?:Embrapa|semiárido do Nordeste)|$)", re.S)


def _transforma(r: dict) -> dict:
    ctx = r.get("contexto", "")
    m = _REV.search(ctx)
    motivo, requer = "", 0
    if m:
        motivo = m.group(0).replace("REVISÃO TÉCNICA:", "").strip()
        ctx = (ctx[:m.start()] + ctx[m.end():])
        requer = 1
    ctx = re.sub(r"(;\s*)+", "; ", ctx).strip("; ").strip()
    if dados.termo_proibido(r.get("trecho", "")):
        requer = 1
        motivo = (motivo + "; " if motivo else "") + "o trecho da fonte cita produto ou fumigação (a API não mostra o trecho)"
    return {"cultura_id": r["cultura_id"], "etapa": int(r["etapa"]), "atributo": r["atributo"], "valor": r["valor"], "unidade": r["unidade"],
            "status": r["status"], "fonte": r["fonte"], "url": r["url"], "pagina": r["pagina"], "trecho": r["trecho"], "contexto": ctx,
            "requer_tecnico": str(requer), "motivo_interno": motivo, "data_consulta": r["data_consulta"]}


def construir() -> list[dict]:
    linhas: list[dict] = []
    for etapa in sorted(ETAPAS_CURADAS):
        arq = STAGING / f"etapa_{etapa:02d}.csv"
        if not arq.is_file():
            raise SystemExit(f"falta {arq}")
        with open(arq, encoding="utf-8", newline="") as f:
            linhas += [_transforma(r) for r in csv.DictReader(f)]
    ordem = {c: i for i, c in enumerate(sorted({r["cultura_id"] for r in linhas}))}
    linhas.sort(key=lambda r: (r["etapa"], ordem[r["cultura_id"]], r["atributo"], r["valor"]))
    for r in linhas:
        r["etapa"] = str(r["etapa"])
    return linhas


def main(argv: list[str]) -> int:
    linhas = construir()
    erros = dados.validar(linhas)
    if erros:
        print("VALIDAÇÃO FALHOU:")
        print("\n".join("  " + e for e in erros[:30]))
        return 1
    por = Counter((int(r["etapa"]), r["status"]) for r in linhas)
    print(f"{len(linhas)} linhas válidas")
    if "--testar" in argv:
        return 0
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=dados.COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    resumo = {"linhas": len(linhas), "por_etapa_e_status": {f"{e}:{s}": n for (e, s), n in sorted(por.items())},
              "culturas": sorted({r["cultura_id"] for r in linhas}), "requer_tecnico": sum(r["requer_tecnico"] == "1" for r in linhas),
              "origem": "data/plano_staging/claude (curadoria com fonte; trecho conferido literalmente na página citada)"}
    MANIFESTO.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print("gravado:", SAIDA.relative_to(RAIZ), "e", MANIFESTO.name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
