import sys, json, glob, pickle
from pathlib import Path
RAIZ = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, RAIZ)
import pandas as pd, numpy as np
from src.modelos.entrada import carregar_config, carregar_entradas
from src.modelos.features import features_diarias_ponto
from src.modelos.walkforward import Variante, walk_forward, resumir, extra_persistencia
AQUI = Path(__file__).parent
D13 = AQUI.parent / "dados13"
cfg = carregar_config()
cfg["caminhos"].update(clima=str(D13/"clima_diario.parquet"), ndvi=str(D13/"ndvi_16d.parquet"))
cfg["caminhos"]["umidade_solo"] = str(D13/"umidade_solo.parquet")  # inexistente => None
ent = carregar_entradas(cfg)
# --- CHIRPS diario
rows = []
for f in glob.glob(str(AQUI/"cache"/"*.json")):
    pid = Path(f).stem.rsplit("_", 1)[0]
    for r in json.load(open(f)):
        rows.append((pid, pd.Timestamp(year=r["year"], month=r["month"], day=r["day"]), r["raw_value"]))
ch = pd.DataFrame(rows, columns=["ponto_id", "data", "chuva_mm"])
ch.loc[ch.chuva_mm < 0, "chuva_mm"] = np.nan   # fill value (-9999) => ausente
print("CHIRPS linhas", len(ch), "NaN", ch.chuva_mm.isna().sum())
cl = ent["clima"]
cmp_ = cl[["ponto_id","data","chuva_mm"]].merge(ch, on=["ponto_id","data"], suffixes=("_p","_c"))
print("corr diaria POWER x CHIRPS:", cmp_[["chuva_mm_p","chuva_mm_c"]].corr().iloc[0,1],
      "| total anual medio P/C:", cmp_.chuva_mm_p.sum()/cmp_.chuva_mm_c.sum())
# features CHIRPS (mesma logica do repo, prefixo ch_)
fs = []
for pid, g in cl.groupby("ponto_id"):
    c = ch[ch.ponto_id == pid]
    gg = g[["ponto_id","celula_power","data","tmax_c"]].drop(columns="tmax_c").merge(c[["data","chuva_mm"]], on="data", how="left")
    gg["tmax_c"] = g["tmax_c"].values if len(gg)==len(g) else np.nan
    f = features_diarias_ponto(gg, None, cfg)[[f"chuva_ac_{w}d" for w in cfg["preditivo"]["janelas_chuva_dias"]] + ["dias_secos_consecutivos"]]
    f.columns = ["ch_" + x for x in f.columns]
    f["ponto_id"] = pid; f.index.name = "data"
    fs.append(f.reset_index())
CH = pd.concat(fs)
COLS_CH = [c for c in CH.columns if c.startswith("ch_")]
def extra_chirps(d):
    d = d.merge(CH, on=["ponto_id","data"], how="left")
    return d, COLS_CH
def extra_pers_chirps(d):
    d, n1 = extra_chirps(d)
    d, n2 = extra_persistencia(d)
    return d, n1 + n2
base_chuva = tuple(["chuva_ac_30d","chuva_ac_60d","chuva_ac_90d","dias_secos_consecutivos"])
V = [
 Variante("base", "POWER"),
 Variante("base_chirps", "CHIRPS no lugar", extra=extra_chirps, remover=base_chuva),
 Variante("base_power_chirps", "POWER+CHIRPS", extra=extra_chirps),
 Variante("persistencia", "pers + POWER", extra=extra_persistencia),
 Variante("pers_chirps", "pers + CHIRPS no lugar", extra=extra_pers_chirps, remover=base_chuva),
 Variante("pers_power_chirps", "pers + POWER + CHIRPS", extra=extra_pers_chirps),
]
N = len(V); anos = list(range(2010, 2022))
assert max(anos) < 2022
out = {}
for plac in (False, True):
    res = walk_forward(ent, cfg, V, anos, placebo=plac)
    res.to_pickle(AQUI / f"res_{'placebo' if plac else 'real'}.pkl")
    pd.set_option("display.width", 250, "display.max_columns", 30)
    cols = ["variante","modelo","anos_selecao","skill_media","skill_ic_inf_corrigido","frac_anos_positivos","dif_vs_base_media","dif_vs_base_ic_inf"]
    tp = resumir(res, range(2010, 2022), [], n_variantes=N, base="persistencia")[cols]
    tb = resumir(res, range(2010, 2022), [], n_variantes=N, base="base")[cols]
    print("\n==== placebo" if plac else "\n==== REAL", "(dif vs persistencia)"); print(tp.round(4).sort_values(["variante","modelo"]).to_string(index=False))
    print("==== (dif vs base)"); print(tb.round(4).sort_values(["variante","modelo"]).to_string(index=False))
    print("n teste por ano:", res[res.modelo=="ridge"].groupby("ano_teste").n.first().tolist())
