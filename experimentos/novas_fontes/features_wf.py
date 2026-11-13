"""Terreno (SRTM) e índices climáticos (Niño 3.4, Atlântico tropical) como features, pelo protocolo walk-forward (docs/05_EXPERIMENTOS.md).

Uso:
  python features_wf.py selecao [placebo]  -> 2010-2021
  python features_wf.py confirma           -> UMA vez, 2022-2024, só as variantes que passarem na seleção (argv[2], separadas por vírgula)
Referência = `persistencia` (modelo de produção). N de comparações para o Bonferroni = 3 variantes x 2 modelos + 2 de referência = 8.

Índices (NOAA PSL, mensais): Niño 3.4 (anomalia), TNA e TSA (Atlântico tropical Norte e Sul). Para o composto que começa em t (mês m), usa a
média dos 3 meses ANTERIORES a m (m-3..m-1), já conhecidos. Dipolo = TNA - TSA. Literatura: Atlântico tropical e ENSO modulam a chuva do Ceará
(ver docs/05_EXPERIMENTOS.md, seção de pesquisa). Terreno: altitude, declive médio e p90 em ~1 km (estático por ponto).
"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import numpy as np
import pandas as pd
from src.modelos.entrada import carregar_config, carregar_entradas
from src.modelos.walkforward import VARIANTES, Variante, extra_persistencia, resumir, walk_forward

OUT = Path(__file__).resolve().parent
cfg = carregar_config()
IDX = Path(RAIZ) / "data/raw/indices"


def ler_indice(nome: str) -> pd.Series:
    """Série mensal (índice = primeiro dia do mês); -99.99 e afins viram NaN."""
    linhas = [l.split() for l in (IDX / f"{nome}.txt").read_text(encoding="utf-8").splitlines()]
    dados = {}
    for p in linhas:
        if len(p) == 13 and p[0].isdigit():
            for m, v in enumerate(map(float, p[1:]), start=1):
                dados[pd.Timestamp(int(p[0]), m, 1)] = np.nan if v <= -90 else v
    return pd.Series(dados).sort_index()


def media_3m_anteriores(s: pd.Series, datas: pd.Series) -> np.ndarray:
    """Média dos 3 meses ANTERIORES ao mês de cada data (vetorizado)."""
    s = s.reindex(pd.date_range(s.index.min(), s.index.max() + pd.DateOffset(months=12), freq="MS"))
    m3 = pd.concat([s.shift(k) for k in (1, 2, 3)], axis=1).mean(axis=1, skipna=False)
    return datas.dt.to_period("M").dt.to_timestamp().map(m3).to_numpy(float)


def extra_terreno(d):
    t = pd.read_parquet(Path(RAIZ) / "data/processed/terreno.parquet").set_index("ponto_id")
    cols = ["elev_m", "declive_medio_1km_pct", "declive_p90_1km_pct"]
    for c in cols:
        d[c] = d["ponto_id"].map(t[c])
    return d, cols


def extra_indices(d):
    nino, tna, tsa = (ler_indice(n) for n in ("nino34", "tna", "tsa"))
    d["nino34_m3"] = media_3m_anteriores(nino, d["data"])
    d["tna_m3"] = media_3m_anteriores(tna, d["data"])
    d["tsa_m3"] = media_3m_anteriores(tsa, d["data"])
    d["dipolo_m3"] = d["tna_m3"] - d["tsa_m3"]
    return d, ["nino34_m3", "tna_m3", "tsa_m3", "dipolo_m3"]


def combinar(*fs):
    def f(d):
        d, c = extra_persistencia(d)
        for g in fs:
            d, n = g(d)
            c += n
        return d, c
    return f


VS = {"persistencia": VARIANTES["persistencia"],
      "pers_terreno": Variante("pers_terreno", "+ terreno", extra=combinar(extra_terreno)),
      "pers_indices": Variante("pers_indices", "+ Niño3.4/TNA/TSA/dipolo", extra=combinar(extra_indices)),
      "pers_terreno_indices": Variante("pers_terreno_indices", "+ ambos", extra=combinar(extra_terreno, extra_indices))}
COLS = ["variante", "modelo", "skill_media", "skill_ic_inf_corrigido", "frac_anos_positivos", "dif_vs_base_media", "dif_vs_base_ic_inf", "skill_confirmacao"]

if __name__ == "__main__":
    modo = sys.argv[1]
    ent = carregar_entradas(cfg)
    ent["umidade_solo"] = None
    pd.set_option("display.width", 220, "display.max_columns", 30)
    if modo == "selecao":
        placebo = "placebo" in sys.argv
        anos = list(range(2010, 2022))
        res = walk_forward(ent, cfg, list(VS.values()), anos, placebo=placebo)
        res.to_csv(OUT / f"selecao{'_placebo' if placebo else ''}_linhas.csv", index=False)
        t = resumir(res, anos, [], n_variantes=8, base="persistencia")
        t.to_csv(OUT / f"selecao{'_placebo' if placebo else ''}_resumo.csv", index=False)
        print("PLACEBO" if placebo else "SELECAO 2010-2021 (base = persistencia)")
        print(t[COLS].round(4).to_string(index=False))
    else:
        fin = ["persistencia"] + [v for v in sys.argv[2].split(",") if v != "persistencia"]
        res = walk_forward(ent, cfg, [VS[v] for v in fin], [2022, 2023, 2024])
        res.to_csv(OUT / "confirmacao_linhas.csv", index=False)
        t = res[res.modelo != "ingenua"].groupby(["variante", "modelo"])["skill"].mean().unstack()
        print("CONFIRMAÇÃO 2022-2024 (skill)"); print(t.round(4).to_string())
