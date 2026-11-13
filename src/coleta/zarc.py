"""Coleta do ZARC (Tábua de Risco, MAPA, licença CC BY) só do Ceará -> data/processed/zarc_ce.parquet.

Dataset: https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f (CKAN; exige User-Agent de navegador).
Baixa em streaming (sem guardar o CSV bruto: são centenas de MB), filtra `UF == CE` linha a linha e registra sha256 e data
em data/processed/zarc_manifesto.json. Formato do CSV (conferido em 2026-11-13): separador `;`, UTF-8 com BOM, colunas
Nome_cultura, SafraIni, SafraFin, Cod_Cultura, Cod_Ciclo, Cod_Solo, geocodigo (IBGE 7 dígitos), UF, municipio, Cod_Clima,
Cod_Outros_Manejos (1 sequeiro, 2 irrigado, 3 irrigado c/ controle de geada), Cod_NM, Portaria, dec1..dec36.
`decN` = 0 (sem indicação de plantio no decêndio) ou 20 / 30 / 40 (nível de risco máximo em que o plantio é indicado).
O dicionário oficial NÃO descreve o significado de 0/20/30/40; esta leitura vem da observação das linhas e das portarias
do ZARC e deve ser conferida (docs/13_ZARC.md).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import urllib.request
from datetime import date

import pandas as pd

from src.modelos.entrada import RAIZ, DadosInvalidos

BASE = "https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f/resource"
RECURSOS = {
    "safra_2024_2025": "95588752-a068-415b-ab2f-55043eb7f9ac/download/dados-abertos-tabua-de-risco-safra-2024-2025.csv",
    "safra_2025_2026": "f9d597f9-0fee-47eb-9344-8642274ca9da/download/dados-abertos-tabua-de-risco-safra-2025-2026.csv",
    "safra_2026_2027": "139e5a60-1f43-4cc8-aeab-a35dbbf816c0/download/dados-abertos-tabua-de-risco-safra-2026-2027.csv",
    "perene_olericola_sem_safra": "dae65d31-683f-4ac4-ab90-3abd0c1583ba/download/dados-abertos-tabua-de-risco-safra-perene-olericola-sem-safra.csv",
}
UA = {"User-Agent": "Mozilla/5.0"}
DEC = [f"dec{i}" for i in range(1, 37)]


def _baixar_ce(url: str, uf: str = "CE", tentativas: int = 4) -> tuple[list[dict], str, int]:
    erro = None
    for i in range(tentativas):
        try:
            h, n, linhas = hashlib.sha256(), 0, []
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                class Tee(io.RawIOBase):
                    def readable(self):
                        return True

                    def readinto(self, b):
                        dados = r.read(len(b))
                        h.update(dados)
                        b[:len(dados)] = dados
                        return len(dados)
                txt = io.TextIOWrapper(io.BufferedReader(Tee(), 1 << 20), encoding="utf-8-sig", newline="")
                for lin in csv.DictReader(txt, delimiter=";"):
                    n += 1
                    if lin["UF"] == uf:
                        linhas.append(lin)
            return linhas, h.hexdigest(), n
        except Exception as e:
            erro = e
            time.sleep(2 ** i)
    raise DadosInvalidos(f"Falha ao baixar ZARC: {erro}")


def coletar(uf: str = "CE") -> dict:
    partes, manifesto = [], {"data_coleta": str(date.today()), "uf": uf, "licenca": "CC BY", "recursos": {}}
    for nome, rel in RECURSOS.items():
        linhas, sha, total = _baixar_ce(f"{BASE}/{rel}", uf)
        df = pd.DataFrame(linhas)
        if not df.empty:
            df["recurso"] = nome
            partes.append(df)
        manifesto["recursos"][nome] = {"url": f"{BASE}/{rel}", "sha256": sha, "linhas_total": total, "linhas_uf": len(df)}
        print(nome, "linhas totais", total, f"{uf}:", len(df), flush=True)
    if not partes:
        raise DadosInvalidos("Nenhuma linha do ZARC para a UF pedida.")
    d = pd.concat(partes, ignore_index=True)
    for c in DEC + ["SafraIni", "SafraFin", "Cod_Ciclo", "Cod_Solo", "Cod_Outros_Manejos", "geocodigo"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    saida = RAIZ / "data/processed/zarc_ce.parquet"
    d.to_parquet(saida, index=False)
    (RAIZ / "data/processed/zarc_manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    manifesto["linhas_ce"] = int(len(d))
    return manifesto


if __name__ == "__main__":
    m = coletar()
    print(json.dumps({k: v for k, v in m.items() if k != "recursos"}, ensure_ascii=False))
