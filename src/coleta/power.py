"""Coleta NASA POWER (diário, por ponto) -> data/processed/clima_diario.parquet.

Roda OFFLINE-first: cada ponto é guardado em data/raw/power/<ponto_id>.json e só é baixado se faltar.
O app e os modelos nunca chamam a API. Valor de preenchimento (-999) vira NaN, nunca é preenchido.
Latitude/longitude ficam em pontos.csv (descritivo); não entram nas features.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ, DadosInvalidos, carregar_config

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FILL = -999.0


def celula_power(lat: float, lon: float, cfg: dict) -> str:
    """Identificador aproximado da célula da grade (0,5° x 0,625°) do ponto."""
    c = cfg["coleta"]["power"]
    return f"{round(lat / c['grade_lat'])}_{round(lon / c['grade_lon'])}"


def baixar_ponto(lat: float, lon: float, cfg: dict, tentativas: int = 4) -> dict:
    c = cfg["coleta"]["power"]
    q = urllib.parse.urlencode({"parameters": ",".join(c["parametros"].values()), "community": c["comunidade"],
                                "longitude": lon, "latitude": lat, "start": c["inicio"], "end": c["fim"],
                                "format": "JSON"})
    erro = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(f"{URL}?{q}", timeout=120) as r:
                return json.load(r)
        except Exception as e:  # rede/HTTP: tenta de novo com espera crescente
            erro = e
            time.sleep(2 ** i)
    raise DadosInvalidos(f"Falha ao baixar POWER ({lat}, {lon}): {erro}")


def para_dataframe(bruto: dict, ponto_id: str, celula: str, cfg: dict) -> pd.DataFrame:
    par = bruto["properties"]["parameter"]
    cols = cfg["coleta"]["power"]["parametros"]
    faltam = [p for p in cols.values() if p not in par]
    if faltam:
        raise DadosInvalidos(f"Resposta POWER sem parâmetros {faltam} ({ponto_id}).")
    datas = pd.to_datetime(list(par[next(iter(cols.values()))].keys()), format="%Y%m%d")
    df = pd.DataFrame({"data": datas})
    for nome, p in cols.items():
        v = np.array(list(par[p].values()), dtype=float)
        v[v == FILL] = np.nan
        df[nome] = v
    df.insert(0, "celula_power", celula)
    df.insert(0, "ponto_id", ponto_id)
    return df


def gravar_pontos(pontos: list[dict], celulas: dict, destino) -> pd.DataFrame:
    """Grava pontos.csv PRESERVANDO colunas que o coletor não produz (ex.: `ibge`, D5): lê o arquivo existente
    e junta por ponto_id as colunas extras. Ponto novo fica com a coluna vazia (lacuna), nunca com valor inventado."""
    novo = pd.DataFrame(pontos).assign(celula_power=lambda d: d["ponto_id"].map(celulas))
    if destino.exists():
        antigo = pd.read_csv(destino, dtype={"ibge": "Int64"} if "ibge" in pd.read_csv(destino, nrows=0).columns else None)
        extras = [c for c in antigo.columns if c not in novo.columns]
        if extras:
            novo = novo.merge(antigo[["ponto_id", *extras]].drop_duplicates("ponto_id"), on="ponto_id", how="left")
    novo.to_csv(destino, index=False)
    return novo


def coletar(cfg: dict | None = None, forcar: bool = False) -> dict:
    cfg = cfg or carregar_config()
    c = cfg["coleta"]
    bruta = RAIZ / c["power"]["pasta_bruta"]
    bruta.mkdir(parents=True, exist_ok=True)
    pontos = c["pontos"]
    celulas = {p["ponto_id"]: celula_power(p["lat"], p["lon"], cfg) for p in pontos}
    repetidas = sorted({x for x in celulas.values() if list(celulas.values()).count(x) > 1})
    avisos = [f"Pontos na mesma célula POWER aproximada ({x}): contam como UMA amostra efetiva." for x in repetidas]
    partes = []
    for p in pontos:
        arq = bruta / f"{p['ponto_id']}.json"
        if forcar or not arq.exists():
            arq.write_text(json.dumps(baixar_ponto(p["lat"], p["lon"], cfg)), encoding="utf-8")
            print("baixado", p["ponto_id"])
        partes.append(para_dataframe(json.loads(arq.read_text(encoding="utf-8")), p["ponto_id"],
                                     celulas[p["ponto_id"]], cfg))
    df = pd.concat(partes, ignore_index=True)
    saida = RAIZ / cfg["caminhos"]["clima"]
    saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(saida, index=False)
    gravar_pontos(pontos, celulas, saida.parent / "pontos.csv")
    resumo = {"arquivo": str(saida), "linhas": int(len(df)), "pontos": len(pontos),
              "celulas": len(set(celulas.values())),
              "ausentes_por_coluna": {k: int(df[k].isna().sum()) for k in c["power"]["parametros"]}, "avisos": avisos}
    return resumo


if __name__ == "__main__":
    import sys

    print(json.dumps(coletar(forcar="--forcar" in sys.argv), ensure_ascii=False, indent=2))
