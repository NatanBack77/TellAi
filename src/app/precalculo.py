"""Pré-cálculo do app (rodar uma vez, offline; o app só lê os arquivos gerados).

    python -m src.app.precalculo evidencias    # busca no acervo (RAG) por cultura e critério -> evidencias_rag.json
    python -m src.app.precalculo auditoria     # roda o motor nos 195 pontos -> auditoria_alternativas.json
    python -m src.app.precalculo tudo

Saída em data/processed/mvp/. Não escreve em data/processed/modelos/ nem em data/processed/cenarios/.
Só LÊ src/rag (busca) e src/pipeline (funções de evidência); não altera nenhum dos dois.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "data/processed/mvp"


def gerar_evidencias(saida: Path = SAIDA, busca=None) -> Path:
    from src.culturas.tabela_culturas import carregar
    from src.pipeline.gerar_cenarios import evidencias
    tab = carregar()
    out: dict = {"_meta": {"fonte": "src.rag.busca via src.pipeline.gerar_cenarios.evidencias (K=2 por critério; "
                                    "o trecho só é mantido se citar a cultura e um termo do critério)",
                           "acervo": "docs_rag/manifesto.json"}}
    t0 = time.time()
    for cid, c in tab.items():
        out[cid] = evidencias(cid, c["cultura_pt"], busca=busca)
        print(cid, {k: len(v["trechos"]) for k, v in out[cid].items()}, f"{time.time() - t0:.0f}s", flush=True)
    saida.mkdir(parents=True, exist_ok=True)
    arq = saida / "evidencias_rag.json"
    arq.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return arq


def auditar_alternativas(saida: Path = SAIDA, cultura_atual: str = "milho") -> Path:
    """Para cada ponto e cada prioridade: quais alternativas o motor escolhe e se há empate técnico."""
    from src.app import mvp
    pontos = mvp.carregar_pontos()
    linhas = []
    for pid in pontos["ponto_id"]:
        for prio in mvp.PRIORIDADES_AUDITORIA:
            r = mvp.calcular(pid, cultura_atual, prio)
            alts = [c for c in r["cenarios"] if not c.get("atual")]
            linhas.append({
                "ponto_id": pid, "prioridade": prio, "alternativas": [c["rotacao"][1] for c in alts],
                "empate_tecnico": [bool(mvp.bloco_ranking(c, prio).get("empate_tecnico")) for c in alts],
                "n_empatadas": [len(mvp.bloco_ranking(c, prio).get("empate_tecnico_com") or []) for c in alts],
                "p_top3": [mvp.bloco_ranking(c, prio).get("p_top3") for c in alts],
                "viabilidade_atual": r["cenarios"][0].get("viabilidade"),
            })
    df = pd.DataFrame(linhas)
    resumo: dict = {"cultura_atual": cultura_atual, "n_pontos": int(df["ponto_id"].nunique()), "por_prioridade": {}}
    for prio, g in df.groupby("prioridade"):
        n_alt = sum(len(x) for x in g["alternativas"])
        n_emp = sum(sum(x) for x in g["empate_tecnico"])
        escolhidas = Counter(a for x in g["alternativas"] for a in x)
        pt = [p for x in g["p_top3"] for p in x if p is not None]
        resumo["por_prioridade"][prio] = {
            "alternativas_mostradas": n_alt, "com_empate_tecnico": int(n_emp),
            "frac_com_empate_tecnico": round(n_emp / n_alt, 3) if n_alt else None,
            "mediana_n_empatadas": float(pd.Series([n for x in g["n_empatadas"] for n in x]).median()) if n_alt else None,
            "p_top3_min": min(pt) if pt else None, "p_top3_max": max(pt) if pt else None,
            "mais_escolhidas": escolhidas.most_common(5),
            "pontos_com_cultura_atual_inviavel": int((g["viabilidade_atual"] != "viavel").sum()),
        }
    saida.mkdir(parents=True, exist_ok=True)
    arq = saida / "auditoria_alternativas.json"
    arq.write_text(json.dumps({"resumo": resumo, "linhas": linhas}, ensure_ascii=False, indent=1), encoding="utf-8")
    return arq


def main(argv=None) -> None:
    a = (argv if argv is not None else sys.argv[1:]) or ["tudo"]
    if a[0] in ("evidencias", "tudo"):
        print(gerar_evidencias())
    if a[0] in ("auditoria", "tudo"):
        print(auditar_alternativas())


if __name__ == "__main__":
    main()
