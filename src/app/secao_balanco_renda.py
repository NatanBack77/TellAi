"""Dados prontos para a tela das seções A2 (balanço hídrico), A3 (renda) e A8 (forragem). SEM Streamlit; o app só desenha o que vem daqui.

Como ligar (quem edita app.py/mvp.py): `secao_balanco_hidrico(ponto_id)`, `secao_renda(ibge, ids_tabela)`, `secao_forragem()`; cada uma devolve
{'titulo', 'aviso', 'lacunas', ...}. Para a prioridade 'renda': `rotacao.gerar_rotacoes(..., renda_por_cultura=secao_renda(ibge, ids)['renda_por_cultura'])`.
"""
from __future__ import annotations

import functools

import pandas as pd

from src.culturas import balanco_hidrico as bh
from src.culturas import forragem, renda
from src.modelos.entrada import RAIZ

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def rotulo_quinzena(q: int) -> str:
    return f"{MESES[(q - 1) // 2]} {'1ª' if q % 2 == 1 else '2ª'} quinz."


@functools.lru_cache(maxsize=1)
def _pontos() -> pd.DataFrame:
    return pd.read_csv(RAIZ / "data/processed/pontos.csv").set_index("ponto_id")


def secao_balanco_hidrico(ponto_id: str, clima: pd.DataFrame | None = None) -> dict:
    lac = [bh.LACUNA_KC, "Penman-Monteith não calculado: faltam vento e umidade (" + "; ".join(bh.PENMAN_PARAMETROS_A_CONFIRMAR) + ")."]
    base = {"titulo": "Chuva menos evapotranspiração de referência (ETo), por quinzena", "aviso": bh.AVISO_ETO, "fonte": bh.FONTE,
            "ponto_id": ponto_id, "lacunas": lac, "quinzenas": []}
    pts = _pontos()
    if ponto_id not in pts.index:
        return {**base, "lacunas": lac + [f"ponto '{ponto_id}' sem latitude em pontos.csv"]}
    if clima is None:
        clima = pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet")
    c = clima[clima["ponto_id"] == ponto_id]
    if c.empty:
        return {**base, "lacunas": lac + ["ponto sem clima diário"]}
    lat = float(pts.loc[ponto_id, "lat"])
    cl = bh.climatologia_quinzenal(c, lat)
    base["quinzenas"] = [{"quinzena": int(r.quinzena), "rotulo": rotulo_quinzena(int(r.quinzena)),
                          "chuva_mm": None if pd.isna(r.chuva_mm) else round(float(r.chuva_mm), 1),
                          "eto_mm": None if pd.isna(r.eto_mm) else round(float(r.eto_mm), 1),
                          "saldo_mm": None if pd.isna(r.saldo_mm) else round(float(r.saldo_mm), 1),
                          "saldo_p10": None if pd.isna(r.saldo_p10) else round(float(r.saldo_p10), 1),
                          "saldo_p90": None if pd.isna(r.saldo_p90) else round(float(r.saldo_p90), 1), "n_anos": int(r.n_anos)}
                         for r in cl.itertuples()]
    base["latitude"] = lat
    base["definicao_quinzena"] = "dias 1-15 e 16-fim de cada mês (definição do projeto); p10-p90 entre os anos"
    base["conferencia_radiacao_power"] = bh.conferencia_radiacao(c, lat)
    return base


def secao_renda(ibge: int | None, ids_tabela: list[str], caminho: str | None = None) -> dict:
    r = renda.renda_com_lacunas(ibge, ids_tabela, caminho)
    itens = [{"cultura": cid, "receita_bruta_r_ha": None if v["receita_bruta_r_ha"] is None else round(v["receita_bruta_r_ha"], 0),
              "anos_usados": v["anos_usados"], "produto_pam": v["produto_pam"], "lacuna": v["receita_bruta_r_ha"] is None,
              "motivo_lacuna": v["motivo_lacuna"], "nota": v["nota"]} for cid, v in r.items() if cid in ids_tabela]
    return {"titulo": "Receita bruta por hectare (IBGE/PAM, média 2021-2023, valores correntes)", "aviso": renda.AVISO, "itens": itens,
            "renda_por_cultura": renda.mapa_renda({k: v for k, v in r.items() if k in ids_tabela}),
            "lacunas": [f"{i['cultura']}: {i['motivo_lacuna']}" for i in itens if i["lacuna"]]}


def secao_forragem() -> dict:
    return {"titulo": "Valor forrageiro (palma, sorgo, milheto)", "aviso": forragem.AVISO, "itens": forragem.lacunas_forragem(),
            "lacunas": [f"{x['cultura']}: valor forrageiro sem número lido" for x in forragem.lacunas_forragem()]}
