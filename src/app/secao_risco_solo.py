"""Seções novas (A1 risco de erosão/escoamento e A4 calor/chuva extrema): devolvem dados prontos para a tela, sem Streamlit.

Para ligar no app: `d = secao_risco_solo(ponto_id)` e `e = secao_extremos(ponto_id)`; mostrar `d['classe']`, `d['entradas']`,
`d['limiares']`, `d['fontes']`, `d['lacunas']`, `d['avisos']` e, para A4, `e['tabela_por_ano']`, `e['tendencias']`.
"""
from __future__ import annotations

import pandas as pd

from src.culturas import extremos, risco_solo

FONTES_RISCO = [
    {"o_que": "classes de declive", "fonte": "Embrapa, Pereira & Lombardi Neto (2004), Documentos 43, Tabela 10, p. 22",
     "url": "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/14508/1/documentos43.pdf"},
    {"o_que": "classes de textura", "fonte": "SiBCS (Embrapa), Atributos do Solo",
     "url": "https://www.embrapa.br/en/solos/sibcs/atributos-do-solo?link=sibcs"},
    {"o_que": "chuva erosiva >= 10 mm", "fonte": "Embrapa Solos, Boletim P&D 286 (2023), citando Wischmeier & Smith (1978)",
     "url": "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1159615/1/CNPS-BPD-286-2023.pdf"},
]


def secao_risco_solo(ponto_id: str, tabela: pd.DataFrame | None = None) -> dict:
    """Pacote da tela para o risco de erosão/escoamento. `tabela` opcional (injeção para testes)."""
    tab = tabela if tabela is not None else risco_solo.tabela_pontos_cache()
    r = risco_solo.risco_do_ponto(ponto_id, tab)
    entradas = []
    for k, c in r["componentes"].items():
        entradas.append({"componente": k, "valor": c["valor"], "unidade": c.get("unidade"), "classe": c.get("classe"),
                         "nota": c["nota"], "nota_e_suposicao": c["nota_e_suposicao"], "corte": c.get("corte"),
                         "regra": c.get("regra"), "fonte_faixa": c["fonte_faixa"]})
    if r.get("declive_p90_pct") is not None:
        entradas.append({"componente": "declive_p90_1km (informativo, fora da nota)", "valor": r["declive_p90_pct"], "unidade": "%",
                         "classe": risco_solo.classe_declive(r["declive_p90_pct"]), "nota": None, "nota_e_suposicao": False})
    return {"disponivel": r["classe"] is not None, "ponto_id": ponto_id, "classe": r["classe"] or "sem dados suficientes",
            "soma_notas": r["soma_notas"], "soma_maxima": r["soma_maxima"], "entradas": entradas,
            "limiares": {"cortes_da_soma": r["cortes_da_soma"], "classes_declive_pct": risco_solo.CLASSES_DECLIVE[:-1],
                         "nota_declive": risco_solo.NOTA_DECLIVE, "nota_textura": risco_solo.NOTA_TEXTURA,
                         "dia_chuva_erosiva_mm": risco_solo.LIMIAR_DIA_EROSIVO_MM},
            "fontes": FONTES_RISCO, "lacunas": r["lacunas"], "avisos": [r["aviso"], r["tecnico"]]}


def secao_extremos(ponto_id: str, clima: pd.DataFrame | None = None) -> dict:
    """Pacote da tela para calor e chuva extrema por ano (tendência incluída). `clima` opcional (injeção para testes)."""
    c = clima if clima is not None else extremos.carregar_clima_ponto(ponto_id)
    out = extremos.resumo_extremos(c)
    out["ponto_id"] = ponto_id
    out["avisos"] = out["avisos"] + ["A avaliar com técnico local."]
    return out
