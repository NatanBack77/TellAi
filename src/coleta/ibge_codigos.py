"""Adiciona o código IBGE (geocódigo de 7 dígitos) a data/processed/pontos.csv.

Fontes (API pública do IBGE, sem chave):
- nomes e códigos: https://servicodados.ibge.gov.br/api/v1/localidades/estados/<UF>/municipios
- polígonos (conferência por coordenadas): https://servicodados.ibge.gov.br/api/v3/malhas/estados/<UF>?intrarregiao=municipio

Regra: o código só é aceito quando o NOME do ponto (ponto_id sem o sufixo da UF) casa com um município da UF
E o ponto (lat, lon) cai dentro do polígono desse mesmo município. Qualquer outra situação deixa `ibge` vazio e
escreve o motivo em `ibge_status` no relatório impresso (o CSV só ganha a coluna `ibge`).
Uso: python -m src.coleta.ibge_codigos [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PONTOS = RAIZ / "data" / "processed" / "pontos.csv"
UF_COD = {"ce": 23, "pe": 26, "pb": 25, "rn": 24, "pi": 22, "ba": 29}
URL_MUN = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
URL_MALHA = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}?intrarregiao=municipio"
             "&qualidade=minima&formato=application/vnd.geo+json")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _get(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        import gzip
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _anel_contem(x: float, y: float, anel: list) -> bool:
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i][0], anel[i][1]
        xj, yj = anel[j][0], anel[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def poligono_contem(x: float, y: float, geom: dict) -> bool:
    polis = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    for rings in polis:
        if _anel_contem(x, y, rings[0]) and not any(_anel_contem(x, y, h) for h in rings[1:]):
            return True
    return False


def mapear(df: pd.DataFrame) -> pd.DataFrame:
    """Devolve df com colunas `ibge` (str de 7 dígitos ou vazio) e `motivo`."""
    cache_mun, cache_malha = {}, {}
    ibge, motivo = [], []
    for _, r in df.iterrows():
        uf = r["ponto_id"].rsplit("_", 1)[-1]
        nome = r["ponto_id"].rsplit("_", 1)[0]
        if uf not in UF_COD:
            ibge.append("")
            motivo.append(f"UF '{uf}' fora da tabela de UFs")
            continue
        cod_uf = UF_COD[uf]
        if cod_uf not in cache_mun:
            cache_mun[cod_uf] = _get(URL_MUN.format(uf=cod_uf))
            cache_malha[cod_uf] = {f["properties"]["codarea"]: f["geometry"]
                                   for f in _get(URL_MALHA.format(uf=cod_uf))["features"]}
        achados = [m for m in cache_mun[cod_uf] if slug(m["nome"]) == nome]
        if len(achados) != 1:
            ibge.append("")
            motivo.append(f"nome '{nome}' casou com {len(achados)} municípios de {uf.upper()}")
            continue
        cod = str(achados[0]["id"])
        geom = cache_malha[cod_uf].get(cod)
        if geom is None:
            ibge.append("")
            motivo.append(f"sem polígono para {cod}")
        elif not poligono_contem(float(r["lon"]), float(r["lat"]), geom):
            ibge.append("")
            motivo.append(f"nome casa com {cod} ({achados[0]['nome']}) mas a coordenada cai fora do polígono")
        else:
            ibge.append(cod)
            motivo.append("ok: nome e coordenada conferem")
    out = df.copy()
    out["ibge"] = ibge
    out["motivo"] = motivo
    return out


def main(dry: bool = False) -> int:
    df = pd.read_csv(PONTOS, dtype={"ibge": str}).drop(columns=["ibge"], errors="ignore")
    res = mapear(df)
    falhas = res[res["ibge"] == ""]
    print(f"{len(res)} pontos; {len(res) - len(falhas)} com código; {len(falhas)} sem")
    for _, r in falhas.iterrows():
        print(" SEM CÓDIGO:", r["ponto_id"], "-", r["motivo"])
    if not dry:
        res.drop(columns=["motivo"]).to_csv(PONTOS, index=False)
        print("gravado", PONTOS)
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
