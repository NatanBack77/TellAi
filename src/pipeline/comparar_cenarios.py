"""Compara os cenários gravados entre locais: os municípios se diferenciam? (todo número vem dos JSON).

Uso: python -m src.pipeline.comparar_cenarios [pasta]   (padrão: data/processed/cenarios)
Mostra, por local: célula POWER, score/janela/chuva da cultura atual, alternativas escolhidas, faixa e P(top-3); e
conta quantos valores distintos há entre os locais (o clima é da célula POWER: locais da mesma célula são iguais).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.pipeline.gerar_cenarios import SAIDA


def resumo(pasta: Path = SAIDA) -> list[dict]:
    linhas = []
    for arq in sorted(Path(pasta).glob("*.json")):
        cens = json.loads(arq.read_text(encoding="utf-8"))
        atual = next(c for c in cens if c.get("atual"))
        j = atual.get("janela_plantio") or {}
        linhas.append({
            "local": arq.stem, "celula": (atual.get("local") or {}).get("celula_power"), "score_atual": atual.get("score"),
            "inicio_atual": j.get("melhor_inicio"), "chuva_ciclo_atual": j.get("chuva_ciclo_mm"),
            "adeq_atual": j.get("adequacao_media"),
            "alternativas": [c["rotacao"][1] for c in cens if not c.get("atual")],
            "scores_alt": [c.get("score") for c in cens if not c.get("atual")],
            "janelas_alt": [(c.get("janela_plantio") or {}).get("melhor_inicio") for c in cens if not c.get("atual")],
            "faixas_alt": [(c["faixa_incerteza"] or {}).get("min", None) for c in cens if not c.get("atual")],
            "p_top3_alt": [(c["faixa_incerteza"] or {}).get("p_top3") for c in cens if not c.get("atual")]})
    return linhas


def main(argv=None) -> None:
    pasta = Path((argv or sys.argv[1:] or [str(SAIDA)])[0])
    ls = resumo(pasta)
    for r in ls:
        print(f"{r['local']:24s} célula {r['celula']:>8s} atual: score {r['score_atual']} início {r['inicio_atual']} "
              f"chuva_ciclo {r['chuva_ciclo_atual']} adeq {r['adeq_atual']} | alt {r['alternativas']} scores "
              f"{r['scores_alt']} janelas {r['janelas_alt']} P(top3) {r['p_top3_alt']}")
    for campo in ("score_atual", "inicio_atual", "chuva_ciclo_atual", "adeq_atual"):
        v = [r[campo] for r in ls]
        print(f"{campo}: {len(set(v))} valores distintos em {len(v)} locais")
    print("alternativas escolhidas distintas:", len({tuple(r["alternativas"]) for r in ls}), "combinações;",
          "células POWER distintas:", len({r["celula"] for r in ls}))


if __name__ == "__main__":
    main()
