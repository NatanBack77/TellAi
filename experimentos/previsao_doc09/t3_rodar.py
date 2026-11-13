import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from t3_features import *
from wf_linhas import ANOS_PERMITIDOS
from src.modelos.walkforward import walk_forward, resumir
from src.modelos.entrada import carregar_config, carregar_entradas
cfg = carregar_config(); D = Path(__file__).parent
pl = "placebo" in sys.argv
ids = [str(x) for x in pd.read_csv(D / "t3_pontos_subconjunto.csv").ponto_id]
ids = [i for i in ids[:30] if len(list(CACHE.glob(f"{i}__*.json"))) == 14]
print("pontos com cobertura completa:", len(ids))
ent = carregar_entradas(cfg); ent["umidade_solo"] = None
for k in ("clima", "ndvi"): ent[k] = ent[k][ent[k].ponto_id.astype(str).isin(ids)].copy()
vs = variantes(ids, cfg)
SEL = list(range(2010, 2022)); assert set(SEL) <= ANOS_PERMITIDOS
res = walk_forward(ent, cfg, vs, SEL, placebo=pl)
res.to_pickle(D / f"t3_res{'_placebo' if pl else ''}.pkl")
N = int(sys.argv[sys.argv.index("--N") + 1]) if "--N" in sys.argv else 11
t = resumir(res, SEL, [], n_variantes=N, base="pers_lags4_c")
pd.set_option("display.width", 250, "display.max_columns", 30)
print("N (Bonferroni) =", N, "placebo =", pl)
print(t[["variante", "modelo", "skill_media", "skill_ic_inf_corrigido", "frac_anos_positivos", "dif_vs_base_media", "dif_vs_base_ic_inf"]].round(4).to_string(index=False))
print(res[res.modelo == "ridge"].pivot(index="ano_teste", columns="variante", values="skill").round(4).to_string())
print("n teste/ano:", res[(res.modelo == "ridge") & (res.variante == "pers_lags4_c")].set_index("ano_teste")["n"].to_dict())
