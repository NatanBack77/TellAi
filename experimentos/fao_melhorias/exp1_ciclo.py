"""Experimento 1: ciclo do EcoCrop (ponto médio, atual) x ciclo da FAO-56 Tabela 11 (soma dos 4 estágios; onde há).

Roda o motor de produção (sem alterá-lo) com Parametros(ciclo_override=...) em 15 municípios do CE, cultura atual milho e
feijao_caupi. Variantes FAO: mediana / min / max das linhas da Tabela 11. Culturas sem FAO (guandu, palma, crotalária,
feijão-de-porco, mucuna) mantêm o ciclo EcoCrop em todas as variantes.
Uso: python -m experimentos.fao_melhorias.exp1_ciclo
"""
from __future__ import annotations

import json
import warnings
from itertools import combinations

import numpy as np
import pandas as pd

from experimentos.fao_melhorias import comum as C
from src.culturas.ciclo import ClimaPonto
from src.culturas.motor import avaliar_local, gerar_cenarios
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar

ATUAIS = ["milho", "feijao_caupi"]


def variantes():
    v = {"ecocrop_medio": ()}
    for regra in ("mediana", "min", "max"):
        v[f"fao_{regra}"] = tuple((cid, r["soma"]) for cid, r in sorted(C.ciclos_fao(regra).items()))
    return v


# variantes que também trocam o modo da chuva (separa o efeito do ciclo do efeito da definição da faixa de chuva)
EXTRA = {"ecocrop_medio_chuva_anual": ("ecocrop_medio", "anual"), "fao_mediana_chuva_anual": ("fao_mediana", "anual")}


def rodar():
    tab = carregar()
    clima = C.carregar_clima()
    muni = C.escolher_municipios(15)
    var = variantes()
    linhas = []
    for m in muni:
        pid = m["ponto_id"]
        serie = ClimaPonto.de_dataframe(clima, pid, 2001, 2024)
        todas = dict(var)
        for nome_x, (b, ch) in EXTRA.items():
            todas[nome_x] = (var[b], ch)
        for nome, ov in todas.items():
            p = (Parametros(ciclo_override=ov[0], chuva_modo=ov[1]) if nome in EXTRA else Parametros(ciclo_override=ov))
            av = avaliar_local(tab, serie, p)
            viaveis = sorted(c for c, d in av["culturas"].items() if d["estado"] == "viavel")
            adeq = {c: d["res"]["adeq_media"] for c, d in av["culturas"].items() if d["res"]}
            ini = {c: d["res"]["k"] for c, d in av["culturas"].items() if d["res"]}
            for atual in ATUAIS:
                cen = gerar_cenarios({"local": pid}, atual, tab, clima=serie, params=p)
                alt = [c["rotacao"][1] for c in cen[1:]]
                fx = [c["faixa_incerteza"] for c in cen[1:]]
                linhas.append({
                    "ponto_id": pid, "chuva_anual_mm": round(m["chuva_anual"]), "variante": nome, "atual": atual,
                    "n_viaveis": len(viaveis), "viaveis": ",".join(viaveis),
                    "k_atual": ini.get(atual), "adeq_atual": adeq.get(atual), "dur_atual": av["culturas"][atual]["av"]["dur"],
                    "alternativas": ",".join(alt),
                    "p_top3": np.mean([f["p_top3"] for f in fx]) if fx else np.nan,
                    "empate": np.mean([f["empate_tecnico"] for f in fx]) if fx else np.nan,
                    "n_empatadas": np.mean([len(f["empate_tecnico_com"]) for f in fx]) if fx else np.nan,
                    "score_atual": cen[0]["score"],
                    "adeq_por_cultura": json.dumps({c: round(v, 4) for c, v in adeq.items()}),
                    "k_por_cultura": json.dumps(ini)})
    df = pd.DataFrame(linhas)
    df.to_csv(C.SAIDA / "exp1_ciclo_linhas.csv", index=False)
    return df


def circ(a, b):
    """Distância em DIAS entre dois inícios da grade (k*10 dias desde 1º/jan; ano de 365 dias, circular)."""
    d = abs(a - b) * 10
    return min(d, 365 - d)


def resumo(df):
    out = {}
    base = df[df.variante == "ecocrop_medio"].set_index(["ponto_id", "atual"])
    for v in [x for x in df.variante.unique()]:
        d = df[df.variante == v].set_index(["ponto_id", "atual"])
        for atual in ATUAIS:
            b, x = base.xs(atual, level=1), d.xs(atual, level=1)
            r = {"adeq_atual_media": x.adeq_atual.mean(), "adeq_atual_sd_entre_municipios": x.adeq_atual.std(ddof=0),
                 "n_inicios_distintos": int(x.k_atual.nunique()), "n_viaveis_media": x.n_viaveis.mean(),
                 "n_viaveis_min": int(x.n_viaveis.min()), "n_viaveis_max": int(x.n_viaveis.max()),
                 "p_top3_media": x.p_top3.mean(), "taxa_empate": x.empate.mean(), "n_empatadas_media": x.n_empatadas.mean(),
                 "score_atual_media": x.score_atual.mean(),
                 "conjuntos_alternativas_distintos": int(x.alternativas.apply(lambda s: tuple(sorted(s.split(",")))).nunique())}
            if v != "ecocrop_medio":
                r["delta_inicio_dias_medio"] = float(np.mean([circ(int(a), int(c)) for a, c in zip(b.k_atual, x.k_atual)]))
                r["mudou_inicio"] = int(sum(int(a) != int(c) for a, c in zip(b.k_atual, x.k_atual)))
                r["delta_adeq_atual_medio"] = float((x.adeq_atual - b.adeq_atual).mean())
                r["mudou_viaveis"] = int(sum(a != c for a, c in zip(b.viaveis, x.viaveis)))
                r["mudou_alternativas_set"] = int(sum(set(a.split(",")) != set(c.split(",")) for a, c in zip(b.alternativas, x.alternativas)))
                r["alt_iguais_ordem"] = int(sum(a == c for a, c in zip(b.alternativas, x.alternativas)))
            out[f"{v}|{atual}"] = r
    # frequência das alternativas por variante
    freq = {}
    for (v, atual), g in df.groupby(["variante", "atual"]):
        s = pd.Series([a for x in g.alternativas for a in x.split(",")]).value_counts()
        freq[f"{v}|{atual}"] = s.to_dict()
    return out, freq


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    df = rodar()
    res, freq = resumo(df)
    (C.SAIDA / "exp1_resumo.json").write_text(json.dumps({"resumo": res, "freq_alternativas": freq}, indent=1, ensure_ascii=False))
    pd.set_option("display.width", 250)
    print(pd.DataFrame(res).T.round(3).to_string())
    for k, v in freq.items():
        print(k, v)
