"""Compara o motor de culturas SEM e COM ZARC em municípios do Ceará. Uso: python comparar.py"""
import sys
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[2]); sys.path.insert(0, RAIZ)
import dataclasses, json
import pandas as pd
from src.culturas import ciclo, motor, zarc
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar

pts = pd.read_csv(Path(RAIZ) / "data/processed/pontos.csv")
ce = pts[pts["ponto_id"].str.endswith("_ce") & pts["ibge"].notna()]
amostra = ce.iloc[:: max(1, len(ce) // 10)].head(10)["ponto_id"].tolist()
clima_df = pd.read_parquet(Path(RAIZ) / "data/processed/clima_diario.parquet")
tab = carregar()
base = Parametros(n_sorteios=2000)
res = []
for pid in amostra:
    cl = ciclo.ClimaPonto.de_dataframe(clima_df, pid)
    linha = {"ponto": pid}
    for nome, p in (("sem", base), ("com", dataclasses.replace(base, usar_zarc=True))):
        av = motor.avaliar_local(tab, cl, p)
        viaveis = sorted(c for c, v in av["culturas"].items() if v["estado"] == "viavel")
        janelas = {c: av["culturas"][c]["res"]["inicio"] for c in viaveis if av["culturas"][c]["res"]}
        linha[nome] = {"viaveis": viaveis, "janelas": janelas,
                       "zarc": {c: av["culturas"][c]["av"].get("zarc") for c in tab if av["culturas"][c]["av"].get("zarc")}}
    res.append(linha)
    s, c = linha["sem"], linha["com"]
    perdeu = sorted(set(s["viaveis"]) - set(c["viaveis"]))
    mudou = {k: (s["janelas"][k], c["janelas"][k]) for k in c["janelas"] if k in s["janelas"] and s["janelas"][k] != c["janelas"][k]}
    sem_zarc = sorted(k for k, v in c["zarc"].items() if v and not v["aplicado"])
    print(f"{pid}: viáveis {len(s['viaveis'])}->{len(c['viaveis'])}; deixam de ser viáveis: {perdeu}; janela muda: {mudou}; sem ZARC: {sem_zarc}")
json.dump(res, open(Path(__file__).parent / "comparacao.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
