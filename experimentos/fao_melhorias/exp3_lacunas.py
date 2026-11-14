"""Experimento 3: quantas das 34 lacunas de tabela_culturas.csv o staging FAO fecha, e o que o staging diz sobre valores já presentes.
Uso: python -m experimentos.fao_melhorias.exp3_lacunas
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from experimentos.fao_melhorias import comum as C
from src.culturas import fao_staging as fs

ATRIB = {"demanda_hidrica_mm_ciclo": ("demanda_hidrica_mm_ciclo_min", "demanda_hidrica_mm_ciclo_max"),
         "n_fixado_kg_ha": ("n_fixado_kg_ha_min", "n_fixado_kg_ha_max"),
         "palha_ms_kg_ha": ("palha_ms_kg_ha",), "n_acumulado_parte_aerea_kg_ha": ("n_acumulado_parte_aerea_kg_ha",)}


def main():
    t = pd.read_csv(C.RAIZ / "data/culturas/tabela_culturas.csv")
    lin = fs.carregar()
    lac = t[t.status == "lacuna"]
    res = []
    for r in lac.itertuples():
        cobertos = [a for a in ATRIB[r.atributo] if fs.valores(lin, r.cultura_id, a)]
        res.append((r.atributo, r.cultura_id, bool(cobertos)))
    d = pd.DataFrame(res, columns=["atributo", "cultura", "fechada_por_FAO"])
    print("lacunas:", len(d), "| fechadas (qualquer qualidade):", int(d.fechada_por_FAO.sum()))
    print(d.groupby("atributo").fechada_por_FAO.agg(["sum", "count"]))
    print(d[d.fechada_por_FAO].to_string())
    print(d[~d.fechada_por_FAO].groupby("atributo").cultura.apply(list).to_string())
    # comparação com valores já presentes (qualidade do dado)
    print("\n--- valores ja presentes x FAO")
    ok = t[t.status != "lacuna"]
    for atr, (a,) in [("palha_ms_kg_ha", ("palha_ms_kg_ha",)), ("n_acumulado_parte_aerea_kg_ha", ("n_acumulado_parte_aerea_kg_ha",))]:
        for cid in ("guandu", "feijao_de_porco", "mucuna"):
            v = ok[(ok.atributo == atr) & (ok.cultura_id == cid)].valor
            print(atr, cid, "tabela:", v.tolist(), "FAO ICM12:", fs.valores(lin, cid, a))
    for cid in ("amendoim",):
        v = ok[(ok.atributo == "n_fixado_kg_ha") & (ok.cultura_id == cid)].valor.tolist()
        print("n_fixado", cid, "tabela:", v, "FAO Tab8:", fs.valores(lin, cid, "n_fixado_kg_ha_min"), fs.valores(lin, cid, "n_fixado_kg_ha_max"))
    for cid in ("milho", "sorgo", "milheto", "algodao", "amendoim", "girassol", "feijao_comum"):
        v = ok[(ok.atributo == "demanda_hidrica_mm_ciclo") & (ok.cultura_id == cid)].valor.tolist()
        print("demanda_hidrica", cid, "tabela(Brouwer, limite inferior):", v, "FAO-24 Tab.20:", fs.valores(lin, cid, "demanda_hidrica_mm_ciclo_min"), fs.valores(lin, cid, "demanda_hidrica_mm_ciclo_max"))
    # ciclo: EcoCrop (min, max, ponto medio) x FAO-56 Tabela 11
    print("\n--- ciclo EcoCrop x FAO-56 (dias)")
    ls = C.linhas_estagios()
    for cid, rows in sorted(ls.items()):
        mn = float(ok[(ok.atributo == "ciclo_min_dias") & (ok.cultura_id == cid)].valor.iloc[0])
        mx = float(ok[(ok.atributo == "ciclo_max_dias") & (ok.cultura_id == cid)].valor.iloc[0])
        somas = [r["soma"] for r in rows]
        print(f"{cid:14s} EcoCrop {mn:.0f}-{mx:.0f} (medio {(mn + mx) / 2:.0f}) | FAO {min(somas)}-{max(somas)} ({len(somas)} linhas) | FAO dentro do intervalo EcoCrop: {all(mn <= s <= mx for s in somas)} | medio EcoCrop / FAO mediana = {(mn + mx) / 2 / np.median(somas):.2f}")


if __name__ == "__main__":
    main()
