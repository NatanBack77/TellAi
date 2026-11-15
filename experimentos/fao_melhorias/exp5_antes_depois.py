"""Experimento 5: ANTES x DEPOIS da decisão (A) chuva anual + (B) ciclo FAO-56, com o motor de PRODUÇÃO e seus parâmetros.

ANTES  = Parametros(chuva_modo="ciclo", ciclo_fonte="ecocrop")   (padrão até 2026-11-13)
DEPOIS = Parametros()                                            (chuva_modo="anual", ciclo_fonte="fao"; padrão novo)
Variantes de decomposição: so_chuva_anual (ecocrop + anual), so_ciclo_fao (fao + chuva do ciclo).
15 municípios do CE escolhidos por quantis da chuva anual (comum.escolher_municipios), cultura atual milho e feijao_caupi.
Uso: python -m experimentos.fao_melhorias.exp5_antes_depois
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from experimentos.fao_melhorias import comum as C
from src.culturas.ciclo import ClimaPonto
from src.culturas.motor import avaliar_local, gerar_cenarios
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar

ATUAIS = ["milho", "feijao_caupi"]
VARIANTES = {"antes": Parametros(chuva_modo="ciclo", ciclo_fonte="ecocrop"), "depois": Parametros(),
             "so_chuva_anual": Parametros(chuva_modo="anual", ciclo_fonte="ecocrop"),
             "so_ciclo_fao": Parametros(chuva_modo="ciclo", ciclo_fonte="fao")}


def circ(a, b, passo=10):
    d = abs(int(a) - int(b)) * passo
    return min(d, 365 - d)


def rodar():
    tab, clima = carregar(), C.carregar_clima()
    linhas = []
    for m in C.escolher_municipios(15):
        pid = m["ponto_id"]
        serie = ClimaPonto.de_dataframe(clima, pid, 2001, 2024)
        for nome, p in VARIANTES.items():
            av = avaliar_local(tab, serie, p)
            viaveis = sorted(c for c, d in av["culturas"].items() if d["estado"] == "viavel")
            for atual in ATUAIS:
                cen = gerar_cenarios({"local": pid}, atual, tab, clima=serie, params=p)
                fx = [c["faixa_incerteza"] for c in cen[1:]]
                ca = av["culturas"][atual]
                linhas.append({
                    "ponto_id": pid, "chuva_anual_mm": round(m["chuva_anual"]), "variante": nome, "atual": atual,
                    "estado_atual": ca["estado"], "k_atual": ca["res"]["k"] if ca["res"] else None,
                    "inicio_atual": ca["res"]["inicio"] if ca["res"] else None,
                    "dur_atual": ca["av"]["dur"], "adeq_atual": ca["res"]["adeq_media"] if ca["res"] else np.nan,
                    "p_anos_viaveis_atual": ca["res"]["p_ano_viavel"] if ca["res"] else np.nan,
                    "n_plato": len(ca["res"]["plato"]) if ca["res"] else np.nan,
                    "frac_inicios_perto_do_melhor": float((ca["res"]["media_por_inicio"] >= ca["res"]["media_por_inicio"].max() - 0.05).mean()) if ca["res"] else np.nan,
                    "n_viaveis": len(viaveis), "viaveis": ",".join(viaveis), "anos": av["anos"][2],
                    "alternativas": ",".join(c["rotacao"][1] for c in cen[1:]),
                    "p_top3": np.mean([f["p_top3"] for f in fx]) if fx else np.nan,
                    "empate": np.mean([f["empate_tecnico"] for f in fx]) if fx else np.nan,
                    "n_empatadas": np.mean([len(f["empate_tecnico_com"]) for f in fx]) if fx else np.nan})
    df = pd.DataFrame(linhas)
    df.to_csv(C.SAIDA / "exp5_antes_depois_linhas.csv", index=False)
    return df


def resumo(df):
    out = {}
    base = df[df.variante == "antes"]
    for v in df.variante.unique():
        for atual in ATUAIS:
            b = base[base.atual == atual].set_index("ponto_id")
            x = df[(df.variante == v) & (df.atual == atual)].set_index("ponto_id")
            r = {"adeq_atual_media": x.adeq_atual.mean(), "adeq_sd_entre_municipios": x.adeq_atual.std(ddof=0),
                 "inicios_distintos": int(x.k_atual.nunique()), "dur_atual": int(x.dur_atual.iloc[0]),
                 "atual_viavel": int((x.estado_atual == "viavel").sum()),
                 "p_anos_viaveis_atual_media": x.p_anos_viaveis_atual.mean(),
                 "n_viaveis_media": x.n_viaveis.mean(), "n_viaveis_min": int(x.n_viaveis.min()), "n_viaveis_max": int(x.n_viaveis.max()),
                 "p_top3_media": x.p_top3.mean(), "taxa_empate": x.empate.mean(), "n_empatadas_media": x.n_empatadas.mean(),
                 "conjuntos_alt_distintos": int(x.alternativas.apply(lambda s: tuple(sorted(s.split(",")))).nunique()),
                 "anos_usados": int(x.anos.iloc[0]),
                 "n_plato_medio": x.n_plato.mean(), "frac_inicios_a_0.05_do_melhor": x.frac_inicios_perto_do_melhor.mean()}
            if v != "antes":
                r["mudou_inicio"] = int((b.k_atual != x.k_atual).sum())
                r["desloc_inicio_dias_medio"] = float(np.mean([circ(a, c) for a, c in zip(b.k_atual, x.k_atual)]))
                r["mudou_viaveis"] = int((b.viaveis != x.viaveis).sum())
                r["mudou_alternativas"] = int(sum(set(a.split(",")) != set(c.split(",")) for a, c in zip(b.alternativas, x.alternativas)))
            out[f"{v}|{atual}"] = r
    freq = {f"{v}|{a}": pd.Series([z for s in g.alternativas for z in s.split(",")]).value_counts().to_dict()
            for (v, a), g in df.groupby(["variante", "atual"])}
    return out, freq


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    df = rodar()
    res, freq = resumo(df)
    (C.SAIDA / "exp5_resumo.json").write_text(json.dumps({"resumo": res, "freq_alternativas": freq}, indent=1, ensure_ascii=False, default=float))
    pd.set_option("display.width", 250)
    print(pd.DataFrame(res).T.round(3).to_string())
    for k, v in freq.items():
        print(k, v)
