"""MILP repetido com pesos, ano de clima e lacunas sorteados: com que frequência cada sequência é a ótima? Uso: python incerteza.py"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2]); sys.path.insert(0, RAIZ)
import time
import numpy as np
import pandas as pd
from src.culturas import ciclo
from src.culturas.motor import avaliar_local
from src.culturas.parametros import Parametros
from src.culturas.rotacao_milp import otimizar_com_incerteza
from src.culturas.tabela_culturas import carregar

tab = carregar()
clima_df = pd.read_parquet(Path(RAIZ) / "data/processed/clima_diario.parquet")
P = Parametros(n_sorteios=1000, usar_zarc=True)
nome = lambda s: " > ".join(tab[c]["cultura_pt"] for c in s)
for pid, atual in [("quixada_ce", "milho"), ("crateus_ce", "feijao_caupi"), ("limoeiro_do_norte_ce", "milho"), ("ipaumirim_ce", "mandioca")]:
    av = avaliar_local(tab, ciclo.ClimaPonto.de_dataframe(clima_df, pid), P)
    cult = [c for c in tab if av["culturas"][c]["res"] is not None and (av["culturas"][c]["estado"] == "viavel" or c == atual)]
    adeq = {c: np.asarray(av["culturas"][c]["res"]["adeq_por_ano"], float) for c in cult}
    fam = {c: (tab[c]["atributos"].get("familia_botanica") or {}).get("valor") for c in cult}
    pal = {c: (tab[c]["atributos"].get("palha_ms_kg_ha") or {}).get("valor") for c in cult}
    for T in (3, 5):
        t = time.perf_counter()
        r = otimizar_com_incerteza(cult, atual, adeq, fam, pal, T=T, n=300, regras={"sem_repetir_seguida": True, "min_leguminosas": 1})
        print(f"{pid} T={T} ({time.perf_counter()-t:.0f}s) {r['n_sequencias_distintas']} sequências distintas ótimas em {r['n_resolvidos']} sorteios")
        for x in r["top"][:3]:
            print(f"    {x['p_otima']:.0%}  {nome(x['sequencia'])}")
