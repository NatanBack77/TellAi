"""Teste de ponta a ponta: motor (ciclo + SMAA) com e sem ZARC em municípios escolhidos. Uso: python e2e.py"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2]); sys.path.insert(0, RAIZ)
import dataclasses, json
from src.app import mvp
CASOS = [("quixada_ce", "milho"), ("crateus_ce", "feijao_caupi"), ("limoeiro_do_norte_ce", "milho"), ("ipaumirim_ce", "mandioca")]
orig = mvp.parametros
out = []
for pid, atual in CASOS:
    linha = {"ponto": pid, "atual": atual}
    for nome, zarc in (("sem_zarc", False), ("com_zarc", True)):
        mvp.parametros = lambda pr, n=1000, z=zarc: dataclasses.replace(orig(pr, n), usar_zarc=z)
        r = mvp.calcular(pid, atual, "sem", n_sorteios=1000, com_evidencias=False)
        est = []
        for c in r["cenarios"]:
            j = c.get("janela") or {}
            est.append({"cultura": c["rotacao"][1], "atual": c["atual"], "score": round(c["score"], 1) if c.get("score") is not None else None,
                        "faixa": c.get("faixa_incerteza"), "melhor_inicio": j.get("melhor_inicio") or j.get("inicio"),
                        "lacunas": len(c["lacunas"]), "empate": c.get("empate_tecnico")})
        linha[nome] = {"estrategias": est, "segundos": round(r["segundos"], 1)}
    out.append(linha)
    for nome in ("sem_zarc", "com_zarc"):
        print(f"{pid} [{nome}]:", [(e["cultura"], e["score"], e["melhor_inicio"]) for e in linha[nome]["estrategias"]])
json.dump(out, open(Path(__file__).parent / "e2e.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
