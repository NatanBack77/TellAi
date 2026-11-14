"""Vista do mapa (AP1/AP2): zoom opcional da órbita ao município e fundo liso para quando não há internet. Sem Streamlit.

A animação é só visual: não altera nenhum dado nem nenhuma pontuação. Desligada por padrão (e nos testes).
"""
from __future__ import annotations

import os

import pandas as pd
import pydeck as pdk

ZOOM_REGIAO = 5.6          # visão dos 195 pontos (Nordeste), a mesma de antes
ZOOM_ORBITA = 3.4          # Brasil inteiro
ZOOM_MUNICIPIO = 9.0       # ~ dezenas de km em volta do ponto: o satélite não enxerga o talhão, então não se aproxima mais que isto
DURACAO_MS = 2500
CAIXA_FUNDO = [[-52.0, 1.0], [-52.0, -18.0], [-32.0, -18.0], [-32.0, 1.0]]   # cobre os 195 pontos; só cor de fundo, sem dado


def abertura_padrao() -> bool:
    """Padrão da caixa 'aproximar': desligado; `SULCO_ABERTURA_ZOOM=1` liga (uso em demonstração). Testes não definem a variável."""
    return os.environ.get("SULCO_ABERTURA_ZOOM") == "1"


def parametros_vista(pts: pd.DataFrame, atual: str, aproximar: bool) -> dict:
    """Parâmetros do ViewState. Sem `aproximar`: visão da região (como sempre foi). Com: centro no município escolhido, zoom
    mais próximo e `transitionDuration` (o deck.gl anima da vista anterior até esta)."""
    if aproximar and atual in set(pts["ponto_id"]):
        r = pts.set_index("ponto_id").loc[atual]
        return {"latitude": float(r["lat"]), "longitude": float(r["lon"]), "zoom": ZOOM_MUNICIPIO, "transitionDuration": DURACAO_MS}
    return {"latitude": float(pts["lat"].mean()), "longitude": float(pts["lon"].mean()), "zoom": ZOOM_REGIAO}


def vista(pts: pd.DataFrame, atual: str, aproximar: bool) -> pdk.ViewState:
    return pdk.ViewState(**parametros_vista(pts, atual, aproximar))


def camada_fundo_liso() -> pdk.Layer:
    """Retângulo cinza claro atrás dos pontos: dá contraste quando o fundo do mapa (baixado da internet) não carrega."""
    return pdk.Layer("PolygonLayer", data=[{"poligono": CAIXA_FUNDO}], id="fundo_liso", get_polygon="poligono",
                     get_fill_color=[235, 235, 228, 255], stroked=False, pickable=False)
