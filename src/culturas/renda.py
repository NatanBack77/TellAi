"""Receita BRUTA por hectare a partir do IBGE/PAM (SIDRA tabela 1612, `data/processed/pam_ce.parquet`). Funções puras, sem Streamlit.

receita_bruta_r_ha = valor_producao_mil_reais * 1000 / area_colhida_ha, por município, cultura e ano; depois média simples dos anos
2021-2023 que tenham os dois dados (mínimo `MIN_ANOS`). Valores CORRENTES de cada ano, SEM correção de inflação (declarado).
NÃO É LUCRO: sem custo, preço futuro nem mercado. NÃO é previsão. Cultura sem produto no PAM (palma e perenes: tabela 1612 só cobre lavouras
temporárias, lacuna C8) ou sem dado no município = lacuna visível (None), nunca estimativa.
"feijão-caupi" e "feijão comum" usam o MESMO produto 'Feijão (em grão)' do PAM (não se separam): o valor é de feijão em geral.
"""
from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ

from .rotacao import PAM_PRODUTO

ANOS = (2021, 2022, 2023)
MIN_ANOS = 2
AVISO = ("Receita BRUTA por hectare (valor da produção do IBGE/PAM dividido pela área colhida), média de 2021-2023, valores correntes sem "
         "correção de inflação. NÃO é lucro: sem custo, preço futuro nem mercado. Não prevê renda. A avaliar com técnico local.")
NOTAS_CULTURA = {"feijao_caupi": "PAM não separa feijão-caupi de feijão comum: valor de 'Feijão (em grão)'.",
                 "feijao_comum": "PAM não separa feijão-caupi de feijão comum: valor de 'Feijão (em grão)'."}


@functools.lru_cache(maxsize=2)
def _pam(caminho: str) -> pd.DataFrame:
    d = pd.read_parquet(caminho)
    d = d[d["variavel"].isin(["valor_producao_mil_reais", "area_colhida_ha"]) & d["ano"].isin(ANOS)]
    return d.pivot_table(index=["ibge", "produto", "ano"], columns="variavel", values="valor", aggfunc="sum", dropna=False).reset_index()


def receita_bruta_por_ano(valor_mil_reais, area_ha) -> np.ndarray:
    """R$/ha; NaN se valor ou área faltam ou área <= 0 (nunca divide por zero nem preenche)."""
    v, a = np.asarray(valor_mil_reais, float), np.asarray(area_ha, float)
    ok = np.isfinite(v) & np.isfinite(a) & (a > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ok, v * 1000.0 / np.where(ok, a, 1.0), np.nan)


def media_receita(valores, min_anos: int = MIN_ANOS) -> float | None:
    x = np.asarray([v for v in valores if v is not None and np.isfinite(v)], float)
    return float(x.mean()) if len(x) >= min_anos else None


def renda_municipio(ibge: int | None, caminho: str | None = None) -> dict[str, dict]:
    """{cultura_id: {'receita_bruta_r_ha': float|None, 'anos_usados': [...], 'produto_pam': str|None, 'motivo_lacuna': str|None, 'nota': str|None}}
    para TODAS as culturas mapeadas em PAM_PRODUTO; as sem produto no PAM (não listadas) são adicionadas por `renda_com_lacunas`."""
    arq = str(RAIZ / "data/processed/pam_ce.parquet") if caminho is None else str(caminho)
    out: dict[str, dict] = {}
    base = None
    if ibge is not None and pd.io.common.file_exists(arq):
        base = _pam(arq)
        base = base[base["ibge"] == int(ibge)]
    for cid, prod in PAM_PRODUTO.items():
        r = {"receita_bruta_r_ha": None, "anos_usados": [], "produto_pam": prod, "motivo_lacuna": None, "nota": NOTAS_CULTURA.get(cid)}
        if base is None:
            r["motivo_lacuna"] = "município sem código IBGE ou arquivo PAM ausente"
        else:
            b = base[base["produto"] == prod].sort_values("ano")
            rec = receita_bruta_por_ano(b.get("valor_producao_mil_reais", pd.Series(dtype=float)), b.get("area_colhida_ha", pd.Series(dtype=float)))
            anos = [int(a) for a, x in zip(b["ano"], rec) if np.isfinite(x)]
            val = media_receita(rec[np.isfinite(rec)])
            r["receita_bruta_r_ha"], r["anos_usados"] = val, (anos if val is not None else [])
            if val is None:
                r["motivo_lacuna"] = f"menos de {MIN_ANOS} anos (de {ANOS[0]}-{ANOS[-1]}) com valor e área no município (PAM)"
        out[cid] = r
    return out


def renda_com_lacunas(ibge: int | None, ids_tabela: list[str], caminho: str | None = None) -> dict[str, dict]:
    """Inclui as culturas da tabela SEM produto no PAM como lacuna explícita (palma, perenes, milheto etc.: C8)."""
    r = renda_municipio(ibge, caminho)
    for cid in ids_tabela:
        if cid not in r:
            r[cid] = {"receita_bruta_r_ha": None, "anos_usados": [], "produto_pam": None, "nota": None,
                      "motivo_lacuna": "sem produto correspondente na tabela 1612 do PAM (só lavouras temporárias listadas); lacuna C8"}
    return r


def mapa_renda(r: dict[str, dict]) -> dict[str, float | None]:
    """Forma esperada por `rotacao.gerar_rotacoes(renda_por_cultura=...)`."""
    return {cid: v["receita_bruta_r_ha"] for cid, v in r.items()}
