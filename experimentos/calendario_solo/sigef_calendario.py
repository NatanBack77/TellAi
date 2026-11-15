"""Resumo do SIGEF (campos de produção de sementes, CE): plantios por cultura x mês, nº de municípios e de cultivares. NÃO é calendário comercial."""
from pathlib import Path
import pandas as pd
RAIZ = Path(__file__).resolve().parents[2]
d = pd.read_csv(RAIZ / "data/externos/sigef_campos_sementes_ce.csv", dtype=str)
MAP = {"Zea mays": "milho", "Vigna unguiculata": "feijao_caupi", "Phaseolus vulgaris": "feijao_comum", "Sorghum bicolor (L.) Moench": "sorgo", "Gossypium hirsutum": "algodao",
       "Arachis hypogaea": "amendoim", "Ricinus communis": "mamona", "Sesamum indicum": "gergelim", "Helianthus": "girassol", "Manihot": "mandioca",
       "Pennisetum": "milheto", "Cajanus": "guandu", "Opuntia": "palma_forrageira", "Crotalaria": "crotalaria_juncea", "Canavalia": "feijao_de_porco", "Mucuna": "mucuna"}
def cid(e):
    for k, v in MAP.items():
        if e.startswith(k): return v
    return None
d["cultura"] = d.Especie.map(cid); d["mes"] = pd.to_datetime(d["Data do Plantio"], format="%d/%m/%Y", errors="coerce").dt.month
d["area"] = d.Area.str.replace(",", ".").astype(float)
x = d[d.cultura.notna()]
t = x.pivot_table(index="cultura", columns="mes", values="area", aggfunc="count", fill_value=0)
t["campos"] = t.sum(axis=1); t["municipios"] = x.groupby("cultura").Municipio.nunique(); t["cultivares"] = x.groupby("cultura").Cultivar.nunique()
t["area_ha_total"] = x.groupby("cultura").area.sum().round(0)
sem = [c for c in ["milho","feijao_caupi","feijao_comum","sorgo","algodao","amendoim","mamona","gergelim","girassol","mandioca","milheto","guandu","palma_forrageira","crotalaria_juncea","feijao_de_porco","mucuna"] if c not in t.index]
t.to_csv(RAIZ / "experimentos/calendario_solo/saida/sigef_ce_cultura_mes.csv")
print(t.to_string()); print("sem registro:", sem, "| linhas CE:", len(d), "| municípios:", d.Municipio.nunique(), "| safras:", d.Safra.min(), d.Safra.max())
