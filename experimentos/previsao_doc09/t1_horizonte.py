"""TESTE 1 (doc 09): habilidade por horizonte (+1..+4 compostos) e estacao. So 2010-2021. Descritivo."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from wf_linhas import *
from src.modelos.walkforward import Variante, extra_persistencia
from src.modelos.entrada import carregar_config, carregar_entradas
OUT = Path(__file__).parent
cfg = carregar_config()
BASECOLS = None

def desloca(h, nlags):
    """Features como conhecidas na ORIGEM: h=1 e o padrao (previsao do composto que comeca agora);
    h>1 usa as features (clima e anomalias) do composto (h-1) passos antes, so se consecutivos. sin/cos mantem a estacao do ALVO."""
    def ex(d):
        d = d.sort_values(["ponto_id", "data"]).reset_index(drop=True)
        g = d.groupby("ponto_id")
        gap = g["data"].diff().dt.days
        # anomalias defasadas relativas ao alvo (lag k = k compostos antes do alvo)
        lagcols = []
        if nlags:
            for k in range(1, nlags + 1):
                ok = pd.Series(True, index=d.index)
                for j in range(k):
                    ok &= (gap.shift(j) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(j + 1))
                d[f"anom_lag{k}"] = g["anomalia_ndvi"].shift(k).where(ok)
                lagcols.append(f"anom_lag{k}")
        feat = [c for c in d.columns if c.startswith(("chuva_ac_", "tmax_media", "dias_secos"))] + lagcols
        s = h - 1
        if s > 0:
            ok = pd.Series(True, index=d.index)
            for j in range(s):
                ok &= (gap.shift(j) <= 17) & d["ponto_id"].eq(d["ponto_id"].shift(j + 1))
            for c in feat:
                d[c] = g[c].shift(s).where(ok)
        return d, lagcols
    return ex

def vs(h):
    return [Variante(f"base", "", extra=desloca(h, 0)),
            Variante(f"persistencia", "", extra=desloca(h, 2)),
            Variante(f"pers_lags4", "", extra=desloca(h, 4)),
            Variante(f"so_lags4", "controle sem clima", extra=desloca(h, 4), remover="*")]

if __name__ == "__main__":
    pl = "placebo" in sys.argv
    ent = carregar_entradas(cfg); ent["umidade_solo"] = None
    res = []
    hs = [int(x) for x in sys.argv[sys.argv.index('--h') + 1].split(',')] if '--h' in sys.argv else (1, 2, 3, 4)
    for h in hs:
        r = prever_linhas(ent, cfg, vs(h), list(range(2010, 2022)), placebo=pl)
        r["h"] = h; res.append(r); print("h", h, len(r), flush=True)
        pd.concat(res).to_pickle(OUT / f"t1_linhas{'_placebo' if pl else ''}_parcial.pkl")
    pd.concat(res).to_pickle(OUT / f"t1_linhas{'_placebo' if pl else ''}.pkl")
