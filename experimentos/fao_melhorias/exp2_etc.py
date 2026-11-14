"""Experimento 2: ETc = Kc x ETo (Kc e estágios da FAO-56; ETo Hargreaves de balanco_hidrico.py) e critério 'atendimento hídrico'.

Para cada município e cada cultura com Kc FAO (11 de 16): ETc no ciclo, chuva no ciclo, razão chuva/ETc, no início de plantio
que o motor escolhe (com o ciclo FAO). Depois testa se um critério novo `atendimento_hidrico = min(1, chuva/ETc)` SEPARA as
alternativas (menos empate técnico), no universo das 11 culturas com Kc. Não altera o motor.
Limites: Kc de clima sub-úmido não ajustado ao semiárido; estágios de outras regiões; Kc único por cultura; ETo de Hargreaves
(só Tmax/Tmin); sem solo/armazenamento (chuva sobre ETc, não balanço); chuva de célula de ~50 km.
Uso: python -m experimentos.fao_melhorias.exp2_etc
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from experimentos.fao_melhorias import comum as C
from src.culturas import ciclo, fao_staging as fs, incerteza
from src.culturas.balanco_hidrico import eto_diaria
from src.culturas.motor import CRITERIOS, PESOS, _criterios_ranking, _notas_estaticas, avaliar_local
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar

ATUAIS = ["milho", "feijao_caupi"]


def kc_fao(lin) -> dict[str, dict]:
    """{cid: {kc_ini, kc_mid, kc_end}}; faixas 'min-max' viram o PONTO MÉDIO (decisão declarada). Mandioca: ano 1."""
    out = {}
    for cid in {l["cultura_id"] for l in lin}:
        d = {}
        for nome in ("kc_ini", "kc_mid", "kc_end"):
            if cid == "mandioca":
                v = [l["valor"] for l in lin if l["cultura_id"] == cid and l["atributo"] == nome and "year 1" in l["pagina_tabela"]]
                if v:
                    d[nome] = v[0]
                continue
            v = fs.valores(lin, cid, nome)
            lo, hi = fs.valores(lin, cid, nome + "_min"), fs.valores(lin, cid, nome + "_max")
            if v:
                d[nome] = float(np.mean(v))
            elif lo and hi:
                d[nome] = (lo[0] + hi[0]) / 2
        if len(d) == 3:
            out[cid] = d
    return out


def curva_kc(row: dict, kc: dict) -> np.ndarray:
    """Kc diário (FAO-56 cap. 6): constante na inicial, linear no desenvolvimento, constante no meio, linear na final."""
    a, b, c, d = row["ini"], row["dev"], row["mid"], row["late"]
    k = np.concatenate([np.full(a, kc["kc_ini"]), np.linspace(kc["kc_ini"], kc["kc_mid"], b + 1)[1:], np.full(c, kc["kc_mid"]),
                        np.linspace(kc["kc_mid"], kc["kc_end"], d + 1)[1:]])
    return k


def eto_alinhado(clima_df: pd.DataFrame, pid: str, lat: float) -> np.ndarray:
    d = clima_df[(clima_df.ponto_id == pid) & clima_df.data.dt.year.between(2001, 2024)]
    e = eto_diaria(d[["data", "chuva_mm", "tmax_c", "tmin_c"]], lat).set_index("data")["eto_mm"]
    return e.reindex(pd.date_range("2001-01-01", "2024-12-31", freq="D")).to_numpy(float)


def janelas(x: np.ndarray, ini: np.ndarray, dur: int, w: np.ndarray | None = None):
    """Soma (ponderada por w, comprimento dur) de x na janela [ini, ini+dur); NaN se sair da série ou houver NaN."""
    out = np.full(len(ini), np.nan)
    for i, s in enumerate(ini):
        seg = x[s:s + dur]
        if len(seg) == dur and not np.isnan(seg).any():
            out[i] = float((seg * (w if w is not None else 1.0)).sum())
    return out


def montar_T(tab, av, ids, atual, extra: dict | None):
    est = _notas_estaticas(tab, atual, ids)
    n_a = av["anos"][2]
    crit = list(CRITERIOS) + (["atendimento_hidrico"] if extra else [])
    T = np.full((len(ids), len(crit), n_a), np.nan)
    for i, c in enumerate(ids):
        r = av["culturas"][c]["res"]
        T[i, crit.index("temperatura")] = r["nt_por_ano"]
        T[i, crit.index("chuva")] = r["nr_por_ano"]
        for k in ("familia_diferente", "n_na_biomassa", "palha"):
            if est[c][k] is not None:
                T[i, crit.index(k)] = est[c][k]
        if extra:
            T[i, crit.index("atendimento_hidrico")] = extra[c]
    return T, crit


def rodar():
    lin = fs.carregar()
    kcs = kc_fao(lin)
    rows_fao = C.ciclos_fao("mediana")
    cult11 = sorted(set(kcs) & set(rows_fao))
    tab = carregar()
    tab11 = {c: tab[c] for c in cult11}
    ov = tuple((c, rows_fao[c]["soma"]) for c in cult11)
    muni = C.escolher_municipios(15)
    pontos = pd.read_csv(C.PROC / "pontos.csv").set_index("ponto_id")
    clima = C.carregar_clima()
    sazonal, sep, smaa = [], [], []
    for m in muni:
        pid = m["ponto_id"]
        eto = eto_alinhado(clima, pid, float(pontos.loc[pid, "lat"]))
        serie = ciclo.ClimaPonto.de_dataframe(clima, pid, 2001, 2024)
        p = Parametros(ciclo_override=ov)
        av = avaliar_local(tab11, serie, p)
        ok = av["ok"]
        ini_all = ciclo.indices_inicio(serie, p.passo_inicio_dias)       # [ano, início]
        razao = {}
        for c in cult11:
            res = av["culturas"][c]["res"]
            if res is None:
                continue
            row, kc = rows_fao[c], kcs[c]
            w = curva_kc(row, kc)
            dur = row["soma"]
            assert len(w) == dur, (c, len(w), dur)
            k = res["k"]
            ini = ini_all[ok, k]
            etc = janelas(eto, ini, dur, w)
            ch = janelas(serie.chuva, ini, dur)
            r = ch / etc
            razao[c] = np.minimum(1.0, r)
            sazonal.append({"ponto_id": pid, "chuva_anual_mm": round(m["chuva_anual"]), "cultura": c, "dur": dur, "k": k,
                            "etc_mm_media": np.nanmean(etc), "chuva_ciclo_mm_media": np.nanmean(ch), "razao_mediana": np.nanmedian(r),
                            "razao_p10": np.nanpercentile(r, 10), "razao_p90": np.nanpercentile(r, 90),
                            "atend_media": np.nanmean(razao[c]), "nota_chuva_motor_media": float(np.mean(res["nr_por_ano"])),
                            "etc_demanda_tabela_mm": (tab[c]["atributos"].get("demanda_hidrica_mm_ciclo") or {}).get("valor")})
        # separação por intervalos (p10-p90 entre anos), como o empate técnico do motor, mas sobre a razão e sobre a nota de chuva
        cs = [c for c in cult11 if c in razao]
        def pares_sep(getter):
            lo = {c: np.nanpercentile(getter(c), 10) for c in cs}
            hi = {c: np.nanpercentile(getter(c), 90) for c in cs}
            tot = sep_ = 0
            for a in range(len(cs)):
                for b in range(a + 1, len(cs)):
                    tot += 1
                    if lo[cs[a]] > hi[cs[b]] or lo[cs[b]] > hi[cs[a]]:
                        sep_ += 1
            return sep_ / tot
        sep.append({"ponto_id": pid, "pares_separados_atendimento": pares_sep(lambda c: razao[c]),
                    "pares_separados_nota_chuva": pares_sep(lambda c: av["culturas"][c]["res"]["nr_por_ano"]),
                    "pares_separados_nota_temp": pares_sep(lambda c: av["culturas"][c]["res"]["nt_por_ano"])})
        # SMAA no universo das 11 culturas, com e sem o critério novo
        for atual in ATUAIS:
            for rotulo, extra in (("sem", None), ("com", razao)):
                if av["culturas"][atual]["res"] is None:
                    continue
                cand = [c for c in cult11 if c != atual and av["culturas"][c]["estado"] == "viavel" and c in razao]
                ids = [atual] + cand
                T, crit = montar_T(tab11, av, ids, atual, extra)
                pr = [crit[k] for k in _criterios_ranking(T)]
                # `_criterios_ranking` só enxerga os 5 + novo se todas têm; N/palha têm lacunas => ficam fora
                sim = incerteza.simular(T, crit, pr, np.array([c != atual for c in ids]), p)
                rk = sim["principal"]["ranking"]
                emp = sim["principal"]["empates"]
                ptop = np.array(rk["p_topo"])
                smaa.append({"ponto_id": pid, "atual": atual, "criterio_agua": rotulo, "criterios_principais": ",".join(pr),
                             "n_cand": len(cand), "p_top3_sd": ptop.std(), "p_top3_max": ptop.max(),
                             "frac_com_empate": float(np.mean([len(e) > 0 for e in emp])),
                             "n_empatadas_media": float(np.mean([len(e) for e in emp])),
                             "top3": ",".join(cand[j] for j in np.argsort(-ptop)[:3])})
    S, P, Q = pd.DataFrame(sazonal), pd.DataFrame(sep), pd.DataFrame(smaa)
    S.to_csv(C.SAIDA / "exp2_etc_sazonal.csv", index=False)
    P.to_csv(C.SAIDA / "exp2_separacao_pares.csv", index=False)
    Q.to_csv(C.SAIDA / "exp2_smaa_com_sem_agua.csv", index=False)
    return S, P, Q


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    S, P, Q = rodar()
    pd.set_option("display.width", 250)
    print(S.groupby("cultura")[["dur", "etc_mm_media", "chuva_ciclo_mm_media", "razao_mediana", "atend_media", "nota_chuva_motor_media"]].agg(["mean"]).round(2).to_string())
    print(S.groupby("cultura")[["etc_mm_media", "etc_demanda_tabela_mm"]].agg(["min", "max"]).round(0).to_string())
    print(P.drop(columns="ponto_id").mean().round(3))
    g = Q.groupby(["atual", "criterio_agua"])[["p_top3_sd", "p_top3_max", "frac_com_empate", "n_empatadas_media", "n_cand"]].mean().round(3)
    print(g.to_string())
    print(Q.groupby(["atual", "criterio_agua"]).criterios_principais.agg(lambda s: s.value_counts().to_dict()).to_string())
    a = Q[Q.criterio_agua == "sem"].set_index(["ponto_id", "atual"]).top3
    b = Q[Q.criterio_agua == "com"].set_index(["ponto_id", "atual"]).top3
    print("top3 igual (conjunto):", sum(set(a[i].split(",")) == set(b[i].split(",")) for i in a.index), "de", len(a))
