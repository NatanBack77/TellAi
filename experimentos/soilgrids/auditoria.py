"""Parte 1: auditoria do solo (SoilGrids) sem ajustar nada. Só leitura de data/processed/solo.parquet, pontos.csv, terreno.parquet."""
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from src.culturas.risco_solo import classe_textura
pd.set_option("display.width", 220, "display.max_columns", 40)
s = pd.read_parquet(RAIZ / "data/processed/solo.parquet").set_index("ponto_id")
p = pd.read_csv(RAIZ / "data/processed/pontos.csv").set_index("ponto_id")
D = ["0-5cm", "5-15cm", "15-30cm"]; W = np.array([5, 10, 15]) / 30
out = []
def L(*a):
    t = " ".join(str(x) for x in a); print(t); out.append(t)
L("N pontos", len(s), "| NaN em qualquer coluna:", int(s.isna().any(axis=1).sum()))
L("pixel central valido:", int(s.pixel_central_valido.sum()), "| invalido:", int((~s.pixel_central_valido).sum()))
inv = s[~s.pixel_central_valido]
L("fracao de pixels validos nos 14 invalidos:\n", inv.fracao_pixels_validos.round(2).to_string())
L("pontos com fracao<0,5:", list(s.index[s.fracao_pixels_validos < 0.5]))
# soma textura
for d in D:
    t = s[f"sand_{d}"] + s[f"silt_{d}"] + s[f"clay_{d}"]
    L(f"soma areia+silte+argila {d}: min {t.min():.2f} max {t.max():.2f} (mediana de cada propriedade na janela => soma pode desviar de 100)")
# faixas
for c in [c for c in s.columns if c.split('_')[0] in ('sand','silt','clay','soc','phh2o')]:
    L(f"{c}: min {s[c].min():.1f} p50 {s[c].median():.1f} max {s[c].max():.1f}")
# outliers soc
z = s["soc_0-5cm"]; q1, q3 = z.quantile([.25, .75]); lim = q3 + 3 * (q3 - q1)
L("soc 0-5cm acima de Q3+3IQR (%.1f):" % lim, {k: round(v, 1) for k, v in z[z > lim].items()})
# media simples vs ponderada por espessura
def media(pre, w=None):
    M = np.column_stack([s[f"{pre}_{d}"] for d in D]); return M.mean(1) if w is None else M @ w
for pre in ("clay", "sand", "soc"):
    dif = media(pre) - media(pre, W)
    L(f"{pre} 0-30: media simples - ponderada (5/10/15 cm): media {dif.mean():+.2f} min {dif.min():+.2f} max {dif.max():+.2f}")
# classes
arg, are = media("clay"), media("sand")
app = np.where(arg < 15, "arenoso", np.where(arg > 35, "argiloso", "medio"))
sib = [classe_textura(a, b) for a, b in zip(arg, are)]
tab = pd.crosstab(pd.Series(app, index=s.index, name="app"), pd.Series(sib, index=s.index, name="SiBCS"))
L("rotulo do app (argila<15/15-35/>35) x SiBCS (risco_solo.classe_textura), media simples 0-30 cm:\n" + tab.to_string())
argw, arew = media("clay", W), media("sand", W)
sibw = [classe_textura(a, b) for a, b in zip(argw, arew)]
L("classe SiBCS com media ponderada: mudam de classe", int(sum(a != b for a, b in zip(sib, sibw))), "pontos")
L("argila 0-30 (media simples): min %.1f p50 %.1f max %.1f; pontos com argila<15: %d; >35: %d" % (arg.min(), np.median(arg), arg.max(), (arg<15).sum(), (arg>35).sum()))
L("areia 0-30: min %.1f max %.1f; arenosa SiBCS (areia-argila>70): %d" % (are.min(), are.max(), sum(x == 'arenosa' for x in sib)))
# vizinhos
xy = np.radians(p.loc[s.index, ["lat", "lon"]].to_numpy()); xyz = np.column_stack([np.cos(xy[:,0])*np.cos(xy[:,1]), np.cos(xy[:,0])*np.sin(xy[:,1]), np.sin(xy[:,0])])
tr = cKDTree(xyz); dd, ii = tr.query(xyz, k=2)
km = dd[:, 1] * 6371
nb = pd.DataFrame({"ponto": s.index, "vizinho": s.index[ii[:, 1]], "km": km, "argila": arg, "argila_viz": arg[ii[:,1]], "areia": are, "areia_viz": are[ii[:,1]], "soc": media("soc"), "soc_viz": media("soc")[ii[:,1]]})
nb["d_argila"] = (nb.argila - nb.argila_viz).abs(); nb["d_soc"] = (nb.soc - nb.soc_viz).abs()
perto = nb[nb.km < 10]
L("pares de vizinhos mais proximos <10 km:", len(perto), "| distancia mediana (todos) %.1f km" % nb.km.median())
L("  |d argila| mediana %.2f p90 %.2f max %.2f ; |d soc| mediana %.2f max %.2f" % (perto.d_argila.median(), perto.d_argila.quantile(.9), perto.d_argila.max(), perto.d_soc.median(), perto.d_soc.max()))
L("5 pares <10 km com maior diferenca de argila:\n" + perto.sort_values("d_argila", ascending=False).head(5).round(1).to_string(index=False))
nb.to_csv("auditoria_vizinhos.csv", index=False)
# correlacao soc com tipo de pixel
L("soc medio 0-5: pixel central valido %.1f vs invalido %.1f" % (s[s.pixel_central_valido]["soc_0-5cm"].mean(), inv["soc_0-5cm"].mean()))
L("argila 0-30: valido %.1f vs invalido %.1f" % (arg[s.pixel_central_valido.values].mean(), arg[~s.pixel_central_valido.values].mean()))
# variacao entre pontos / celulas
cel = pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet", columns=["ponto_id", "celula_power"]).drop_duplicates().set_index("ponto_id")["celula_power"]
g = pd.DataFrame({"cel": cel.reindex(s.index), "arg": arg, "soc": media("soc")})
tot = g.arg.var(); dentro = g.groupby("cel").arg.transform(lambda x: x - x.mean()).var()
L("argila 0-30: variancia total %.1f, dentro de celula %.1f (fracao %.0f%% da variancia esta DENTRO da celula de clima)" % (tot, dentro, 100*dentro/tot))
# extremos de pH
L("pH 0-5 min/max:", s['phh2o_0-5cm'].min(), s['phh2o_0-5cm'].max())
(Path("auditoria.txt")).write_text("\n".join(out), encoding="utf-8")
