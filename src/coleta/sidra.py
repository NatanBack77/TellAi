"""Produção agrícola municipal (PAM/IBGE, SIDRA tabela 1612, lavouras temporárias) do Ceará -> data/processed/pam_ce.parquet.

API pública do IBGE (sem login). Variáveis: 216 área colhida (ha), 214 quantidade produzida, 112 rendimento médio, 215 valor da produção (mil reais correntes; receita bruta, não lucro). Anos 2015-2023.
Valores não numéricos do IBGE (traço, reticências, X) viram NaN; nunca são preenchidos. Uso: saber quais culturas são relevantes no
município e dar contexto de produtividade (não é preço nem mercado).
"""
from __future__ import annotations

import json
import time
import urllib.request

import pandas as pd

from src.modelos.entrada import RAIZ

URL = "https://apisidra.ibge.gov.br/values/t/1612/n6/in%20n3%2023/v/{v}/p/{ano}/c81/all"
VARS = {"216": "area_colhida_ha", "214": "quantidade_produzida", "112": "rendimento_medio", "215": "valor_producao_mil_reais"}


def _get(url, tentativas=4):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except Exception:
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"SIDRA falhou: {url}")


def coletar(anos=range(2015, 2024)):
    linhas = []
    for ano in anos:
        for v, nome in VARS.items():
            for x in _get(URL.format(v=v, ano=ano))[1:]:
                linhas.append({"ibge": int(x["D1C"]), "municipio": x["D1N"], "ano": int(x["D3C"]), "produto": x["D4N"],
                               "variavel": nome, "valor": pd.to_numeric(x["V"], errors="coerce"), "unidade": x["MN"]})
        print("ano", ano, len(linhas), flush=True)
    d = pd.DataFrame(linhas)
    d.to_parquet(RAIZ / "data/processed/pam_ce.parquet", index=False)
    return {"linhas": len(d), "municipios": int(d["ibge"].nunique()), "produtos": int(d["produto"].nunique())}


if __name__ == "__main__":
    print(coletar())
