"""Avaliacao da base agronomica: python -m src.rag.avaliar_agronomia  (top-1/top-5, fonte correta, sem evidencia, vazamento de projeto)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .agronomia import RAIZ, bloco_proibido, buscar_agronomia

ARQ = RAIZ / "tests" / "dados" / "perguntas_agronomia.json"


def _acerto(t: dict, p: dict) -> bool:
    return t["fonte"] in p["fontes"] and re.search(p["kw"], t["texto"], re.I | re.S) is not None


def avaliar(k: int = 5, **kw) -> dict:
    d = json.loads(ARQ.read_text(encoding="utf-8"))
    r = {"n": len(d["dominio"]), "top1": 0, "top3": 0, "top5": 0, "sem_evidencia": [], "erros": [], "internas": {"n": 0, "top5": 0}}
    for p in d["dominio"]:
        res = buscar_agronomia(p["q"], k=k, **kw)
        ok = [_acerto(t, p) for t in res["trechos"]]
        r["top1"] += bool(ok[:1] and ok[0]); r["top3"] += any(ok[:3]); r["top5"] += any(ok)
        if p.get("interna"):
            r["internas"]["n"] += 1; r["internas"]["top5"] += any(ok)
        if res["sem_evidencia"]:
            r["sem_evidencia"].append(p["q"])
        if not any(ok):
            r["erros"].append((p["q"], [(t["fonte"], t["texto"][:70]) for t in res["trechos"][:2]]))
    fora = [buscar_agronomia(q, k=k, **kw)["sem_evidencia"] for q in d["fora_do_dominio"]]
    proj = [buscar_agronomia(q, k=k, **kw) for q in d["projeto"]]
    r["fora_sem_evidencia"] = f"{sum(fora)}/{len(fora)}"
    r["projeto_sem_evidencia"] = f"{sum(x['sem_evidencia'] for x in proj)}/{len(proj)}"
    r["projeto_trechos_devolvidos"] = [(q, [t["texto"][:60] for t in x["trechos"][:1]]) for q, x in zip(d["projeto"], proj) if x["trechos"]]
    r["projeto_com_termo_proibido"] = sum(bloco_proibido(t["texto"]) for x in proj for t in x["trechos"])
    return r


if __name__ == "__main__":
    out = avaliar()
    print(json.dumps(out, ensure_ascii=False, indent=1))
