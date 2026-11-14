"""Utilitários comuns dos experimentos FAO (leitura do staging, escolha de municípios, séries). Somente leitura do motor."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from src.culturas import fao_staging as fs
from src.culturas.ciclo import ClimaPonto

RAIZ = Path(__file__).resolve().parents[2]
PROC = RAIZ / "data/processed"
SAIDA = Path(__file__).parent / "saida"
SAIDA.mkdir(exist_ok=True)
EST = ("estagio_ini_dias", "estagio_dev_dias", "estagio_mid_dias", "estagio_late_dias")


def linhas_estagios() -> dict[str, list[dict]]:
    """{cultura: [{tag, ini, dev, mid, late, soma, total_impresso}]} da Tabela 11 (uma entrada por linha da FAO)."""
    g = defaultdict(dict)
    for l in fs.carregar():
        if l["atributo"] in EST + ("ciclo_dias_total",):
            g[(l["cultura_id"], l["pagina_tabela"])][l["atributo"]] = l["valor"]
    out = defaultdict(list)
    for (cid, tag), d in g.items():
        st = [int(d[k]) for k in EST]
        out[cid].append({"tag": tag, "ini": st[0], "dev": st[1], "mid": st[2], "late": st[3], "soma": sum(st),
                         "total_impresso": int(d["ciclo_dias_total"])})
    for cid in out:
        out[cid].sort(key=lambda r: (r["soma"], r["tag"]))
    return dict(out)


def escolher_linha(linhas: list[dict], regra: str) -> dict:
    """regra: 'min', 'max' ou 'mediana' (linha cuja soma e a mediana inferior; empate pela ordem do rótulo)."""
    if regra == "min":
        return linhas[0]
    if regra == "max":
        return linhas[-1]
    return linhas[(len(linhas) - 1) // 2]


def ciclos_fao(regra: str) -> dict[str, dict]:
    ls = linhas_estagios()
    out = {}
    for cid, rows in ls.items():
        if cid == "mandioca":      # ano 2 (360 d) é cultivo de 2 anos: só o ano 1 entra (decisão declarada)
            rows = [r for r in rows if "year 1" in r["tag"]]
        out[cid] = escolher_linha(rows, regra)
    return out


def escolher_municipios(n: int = 15) -> list[dict]:
    """n pontos do CE, uma célula POWER cada, espaçados por quantis da chuva anual média (critério climático, não de resultado)."""
    pontos = pd.read_csv(PROC / "pontos.csv")
    ce = pontos[pontos.ponto_id.str.endswith("_ce")]
    clima = pd.read_parquet(PROC / "clima_diario.parquet", columns=["ponto_id", "data", "chuva_mm"])
    clima = clima[clima.ponto_id.isin(ce.ponto_id)]
    anual = clima.groupby("ponto_id").chuva_mm.sum() / 24.0
    ce = ce.assign(chuva_anual=ce.ponto_id.map(anual)).sort_values(["chuva_anual", "ponto_id"])
    ce = ce.drop_duplicates("celula_power")
    idx = np.unique(np.round(np.linspace(0, len(ce) - 1, n)).astype(int))
    return ce.iloc[idx].to_dict("records")


def carregar_clima():
    return pd.read_parquet(PROC / "clima_diario.parquet")
