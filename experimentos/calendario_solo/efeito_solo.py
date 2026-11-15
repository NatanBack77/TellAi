"""Efeito do critério de solo (solo_modo='ecocrop') em ~15 municípios (motor completo, antes/depois) e nota de solo nos 183 pontos do CE.
Saída: experimentos/calendario_solo/saida/efeito_solo_*.csv e efeito_solo.json. Rodar com .venv/bin/python (1 processo)."""
import json, sys, itertools
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(RAIZ))
import numpy as np, pandas as pd
from src.app import mvp as M
from src.culturas.parametros import Parametros
from src.culturas.motor import avaliar_local
from src.culturas import solo_ecocrop as SE
SAIDA = RAIZ / "experimentos/calendario_solo/saida"; SAIDA.mkdir(exist_ok=True)
MUN = ["fortaleza", "aracati", "itapipoca", "camocim", "quixada", "taua", "quixeramobim", "crateus", "crato", "barbalha", "tiangua", "ibiapina",
       "limoeiro_do_norte", "russas", "ico"]
tab = M.carregar_tabela(); cult = list(tab)
lin, viav = [], {}
for m in MUN:
    pid = m + "_ce"; cl = M.clima_ponto(pid); s = SE.solo_do_ponto(pid)
    r = {}
    for modo in ("sem", "ecocrop"):
        av = avaliar_local(tab, cl, Parametros(usar_zarc=True, solo_modo=modo, n_sorteios=100))
        r[modo] = av["culturas"]
    for c in cult:
        a, b = r["sem"][c], r["ecocrop"][c]
        so = (b["av"] or {}).get("solo") or {}
        lin.append({"ponto_id": pid, "cultura": c, "estado_sem": a["estado"], "estado_ecocrop": b["estado"],
                    "adeq_sem": a["res"]["adeq_media"] if a["res"] else None, "adeq_ecocrop": b["res"]["adeq_media"] if b["res"] else None,
                    "nota_solo": so.get("nota"), "nota_ph": (so.get("ph") or {}).get("nota"), "nota_textura": (so.get("textura") or {}).get("nota"),
                    "ph_local": (so.get("ph") or {}).get("valor_local"), "textura_local": (so.get("textura") or {}).get("classe_local"),
                    "inicio_sem": a["res"]["inicio"] if a["res"] else None, "inicio_ecocrop": b["res"]["inicio"] if b["res"] else None})
    for modo in ("sem", "ecocrop"):
        viav[(pid, modo)] = frozenset(c for c in cult if r[modo][c]["estado"] == "viavel")
    print(pid, len(viav[(pid, "sem")]), len(viav[(pid, "ecocrop")]), flush=True)
d = pd.DataFrame(lin); d.to_csv(SAIDA / "efeito_solo_15municipios.csv", index=False)
def jac(a, b): return 1 - len(a & b) / len(a | b) if a | b else 0.0
res = {}
for modo in ("sem", "ecocrop"):
    ns = [len(viav[(m + "_ce", modo)]) for m in MUN]
    dist = [jac(viav[(a + "_ce", modo)], viav[(b + "_ce", modo)]) for a, b in itertools.combinations(MUN, 2)]
    adq = d.pivot(index="ponto_id", columns="cultura", values="adeq_sem" if modo == "sem" else "adeq_ecocrop")
    res[modo] = {"n_viaveis_media": float(np.mean(ns)), "n_viaveis_dp": float(np.std(ns)), "n_viaveis_min_max": [min(ns), max(ns)],
                 "n_conjuntos_viaveis_distintos": len({viav[(m + "_ce", modo)] for m in MUN}), "dist_jaccard_media_pares": float(np.mean(dist)),
                 "dp_adeq_entre_municipios_media_por_cultura": float(adq.std(ddof=0).mean())}
res["culturas_que_perdem_viabilidade"] = d[(d.estado_sem == "viavel") & (d.estado_ecocrop != "viavel")][["ponto_id", "cultura", "nota_solo", "ph_local", "textura_local"]].to_dict("records")
res["n_pares_cultura_municipio_piores"] = int(((d.adeq_ecocrop < d.adeq_sem - 1e-9)).sum()); res["n_pares_total"] = int(len(d))
res["n_pares_mudou_inicio"] = int((d.inicio_sem != d.inicio_ecocrop).sum())
# nota de solo em todos os pontos do CE (escalar, sem clima)
p = pd.read_csv(RAIZ / "data/processed/pontos.csv"); ce = p[p.ponto_id.str.endswith("_ce")].ponto_id.tolist()
ln = []
for pid in ce:
    s = SE.solo_do_ponto(pid)
    for c in cult:
        n = SE.nota_solo(c, s)
        ln.append({"ponto_id": pid, "cultura": c, "nota_solo": n.get("nota"), "ph": s["ph_agua"] if s else None, "textura": s["textura"] if s else None,
                   "fracao_pixels_validos": s["fracao_pixels_validos"] if s else None})
dn = pd.DataFrame(ln); dn.to_csv(SAIDA / "nota_solo_184pontos.csv", index=False)
sem = dn.ponto_id[dn.nota_solo.isna()].nunique()
res["ce_todos"] = {"pontos": len(ce), "pontos_sem_nota_solo": int(dn[dn.nota_solo.isna()].ponto_id.nunique()), "pontos_pixels_validos_lt_50pct": int(dn[dn.fracao_pixels_validos < 0.5].ponto_id.nunique()),
                   "ph_min_med_max": [float(dn.ph.min()), float(dn.ph.median()), float(dn.ph.max())],
                   "textura_contagem": dn.drop_duplicates("ponto_id").textura.value_counts().to_dict(),
                   "culturas_nota0_em_n_pontos": dn[dn.nota_solo == 0].groupby("cultura").ponto_id.nunique().to_dict(),
                   "culturas_nota_lt1_em_n_pontos": dn[dn.nota_solo < 1].groupby("cultura").ponto_id.nunique().to_dict()}
json.dump(res, open(SAIDA / "efeito_solo.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)[:4000])
