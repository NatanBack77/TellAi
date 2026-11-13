"""MILP x simulador SMAA (rotacao.py) em municípios reais, com ZARC ligado. Uso: python comparar.py
Pergunta: o ótimo do MILP coincide com o que o SMAA sugere? O MILP acrescenta algo (regras duras, horizonte longo, robustez ao clima)?
"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2]); sys.path.insert(0, RAIZ)
import dataclasses, time
import numpy as np
import pandas as pd
from src.culturas import ciclo
from src.culturas.motor import avaliar_local
from src.culturas.parametros import Parametros
from src.culturas.rotacao import gerar_rotacoes
from src.culturas.rotacao_milp import nota_sequencia, otimizar
from src.culturas.tabela_culturas import carregar

tab = carregar()
clima_df = pd.read_parquet(Path(RAIZ) / "data/processed/clima_diario.parquet")
pts = pd.read_csv(Path(RAIZ) / "data/processed/pontos.csv").set_index("ponto_id")
P = Parametros(n_sorteios=3000, usar_zarc=True)
CASOS = [("quixada_ce", "milho"), ("crateus_ce", "feijao_caupi"), ("limoeiro_do_norte_ce", "milho"), ("ipaumirim_ce", "mandioca")]
nome = lambda s: " > ".join(tab[c]["cultura_pt"] for c in s)
for pid, atual in CASOS:
    cl = ciclo.ClimaPonto.de_dataframe(clima_df, pid)
    av = avaliar_local(tab, cl, P)
    cult = [c for c in tab if av["culturas"][c]["res"] is not None and (av["culturas"][c]["estado"] == "viavel" or c == atual)]
    adeq = {c: np.asarray(av["culturas"][c]["res"]["adeq_por_ano"], float) for c in cult}
    fam = {c: (tab[c]["atributos"].get("familia_botanica") or {}).get("valor") for c in cult}
    pal = {c: (tab[c]["atributos"].get("palha_ms_kg_ha") or {}).get("valor") for c in cult}
    smaa = gerar_rotacoes({"local": pid}, atual, tab, cl, P, "sem", ibge=int(pts.loc[pid, "ibge"]))
    alts = [tuple(e["sequencia"]) for e in smaa["estrategias"][1:]]
    print(f"\n== {pid} (atual: {atual}); {len(cult)} culturas viáveis")
    print("  SMAA alternativas :", " | ".join(nome(a) for a in alts))
    for rotulo, kw in (("MILP esperado T=3", dict(T=3)),
                       ("MILP esperado + regras duras T=3", dict(T=3, regras={"sem_repetir_seguida": True, "min_leguminosas": 1})),
                       ("MILP ROBUSTO (CVaR 25%) T=3", dict(T=3, robusto_beta=0.25)),
                       ("MILP esperado + regras T=5", dict(T=5, regras={"sem_repetir_seguida": True, "min_leguminosas": 2}))):
        t = time.perf_counter(); r = otimizar(cult, atual, adeq, fam, pal, **kw)
        seq = tuple(r["sequencia"])
        pior = np.sort(np.mean([adeq[c] for c in seq], axis=0))[:max(1, int(np.ceil(0.25 * len(next(iter(adeq.values()))))))].mean()
        no_smaa = " (= alternativa do SMAA)" if seq in alts else ""
        print(f"  {rotulo:34s} {nome(seq)}{no_smaa}  [{time.perf_counter()-t:.2f}s; adequação nos 25% piores anos {pior:.2f}]")
