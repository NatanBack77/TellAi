"""Entradas do agricultor como FILTROS sobre as alternativas (A6). Sem Streamlit; testável.

Regra: o filtro só diz "atende", "não atende" ou "LACUNA" com base em dado de arquivo. Não altera a nota nem o ranking do motor
e não inventa efeito (por exemplo, o ganho de produtividade da irrigação). O que não tem dado vira lacuna declarada.

- manejo: sequeiro usa o ZARC sequeiro (Cod_Outros_Manejos = 1, como o motor); irrigado consulta o ZARC irrigado
  (Cod_Outros_Manejos = 2 em data/processed/zarc_ce.parquet; o código 3 não existe nos dados do Ceará). Só indica se o ZARC TRAZ a cultura
  irrigada no município; ausência no ZARC não quer dizer que irrigar seja proibido, e sim que não há zoneamento para consultar.
- água disponível: água de irrigação que o agricultor diz poder aplicar por ciclo (mm). Comparada com a demanda de água do ciclo da tabela de
  culturas (limite inferior da faixa FAO, quando existe) e a chuva média no ciclo calculada pelo motor.
- equipamento: a tabela de culturas não traz exigência de máquina/mão de obra: sempre LACUNA (a resposta vai para a ficha do técnico).
- preferência de mercado: o app não tem preço nem demanda. Único dado real: área colhida da cultura no município (IBGE/PAM), usada como
  PROXY de "cultura que já tem escoamento/conhecimento local". Não é preço nem garantia de venda.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass

import pandas as pd

from src.culturas import zarc as Z
from src.culturas.rotacao import PAM_PRODUTO, contexto_pam
from src.modelos.entrada import RAIZ

MANEJOS = {"sequeiro": "Sequeiro (só a chuva)", "irrigado": "Irrigado"}
EQUIPAMENTOS = ["não informar", "só trabalho manual ou tração animal", "trator e implementos"]
MERCADOS = ["sem preferência", "só culturas já colhidas no meu município (IBGE)"]
RISCO_ZARC = 30
COD_IRRIGADO = 2
# nome ZARC irrigado (normalizado) por cultura da nossa tabela. Só correspondência clara; o resto = sem ZARC irrigado.
MAPA_IRRIGADO = {"feijao_comum": ("feijao",)}


@dataclass(frozen=True)
class Filtros:
    manejo: str = "sequeiro"
    agua_irrigacao_mm: float = 0.0
    equipamento: str = EQUIPAMENTOS[0]
    mercado: str = MERCADOS[0]

    def ativos(self) -> bool:
        return self.manejo == "irrigado" or self.equipamento != EQUIPAMENTOS[0] or self.mercado != MERCADOS[0] or self.agua_irrigacao_mm > 0


def _item(filtro: str, status: str, texto: str) -> dict:
    return {"filtro": filtro, "status": status, "texto": texto}          # status: atende | nao_atende | lacuna


@functools.lru_cache(maxsize=1)
def _irrigado() -> pd.DataFrame | None:
    arq = RAIZ / "data/processed/zarc_ce.parquet"
    if not arq.exists():
        return None
    d = pd.read_parquet(arq, columns=["geocodigo", "Nome_cultura", "Cod_Outros_Manejos", *Z.DEC])
    d = d[d["Cod_Outros_Manejos"] == COD_IRRIGADO].copy()
    d["_n"] = d["Nome_cultura"].map({n: Z._norm(n) for n in d["Nome_cultura"].unique()})
    return d


def zarc_irrigado(geocodigo: int | None, cultura_id: str, risco: int = RISCO_ZARC) -> dict:
    """{'tem': True/False/None, 'n_decendios', 'motivo'}. None = não há como consultar (lacuna)."""
    if geocodigo is None:
        return {"tem": None, "motivo": "ponto sem código IBGE: ZARC não consultado"}
    nomes = MAPA_IRRIGADO.get(cultura_id)
    if not nomes:
        return {"tem": None, "motivo": f"o ZARC irrigado do Ceará não traz '{cultura_id}' (ou não há correspondência clara de nome)"}
    d = _irrigado()
    if d is None:
        return {"tem": None, "motivo": "arquivo do ZARC ausente"}
    x = d[(d["geocodigo"] == int(geocodigo)) & d["_n"].isin(nomes)]
    if x.empty:
        return {"tem": None, "motivo": f"o ZARC irrigado não traz '{cultura_id}' para este município"}
    v = x[Z.DEC].astype(float)
    ok = ((v > 0) & (v <= risco)).any(axis=0)
    return {"tem": bool(ok.any()), "n_decendios": int(ok.sum()), "motivo": None}


def _checar_manejo(f: Filtros, geocodigo: int | None, cid: str) -> dict:
    if f.manejo == "irrigado":
        z = zarc_irrigado(geocodigo, cid)
        if z["tem"] is None:
            return _item("Manejo irrigado", "lacuna", f"LACUNA: {z['motivo']}. Não quer dizer que irrigar seja proibido: confirme com o técnico.")
        if z["tem"]:
            return _item("Manejo irrigado", "atende", f"o ZARC irrigado indica plantio em {z['n_decendios']} dos 36 decêndios do ano (risco até {RISCO_ZARC}%).")
        return _item("Manejo irrigado", "nao_atende", f"o ZARC irrigado traz a cultura neste município, mas sem decêndio com risco até {RISCO_ZARC}%.")
    j = Z.janela(geocodigo, cid, RISCO_ZARC)
    if j["permitido"] is None:
        return _item("Manejo sequeiro", "lacuna", f"LACUNA: {j['motivo']}.")
    n = int(j["n_decendios"])
    if n:
        return _item("Manejo sequeiro", "atende", f"o ZARC sequeiro indica plantio em {n} dos 36 decêndios do ano (risco até {RISCO_ZARC}%).")
    return _item("Manejo sequeiro", "nao_atende", f"o ZARC sequeiro traz a cultura neste município, mas sem decêndio com risco até {RISCO_ZARC}%.")


def _checar_agua(f: Filtros, chuva_ciclo_mm: float | None, demanda_mm: float | None) -> dict:
    irrig = float(f.agua_irrigacao_mm) if f.manejo == "irrigado" else 0.0
    if demanda_mm is None:
        return _item("Água disponível", "lacuna", "LACUNA: a tabela de culturas não tem a demanda de água do ciclo desta cultura.")
    if chuva_ciclo_mm is None:
        return _item("Água disponível", "lacuna", "LACUNA: chuva do ciclo não calculada para esta cultura neste local.")
    falta = demanda_mm - chuva_ciclo_mm - irrig
    base = (f"demanda do ciclo {demanda_mm:.0f} mm (limite inferior da faixa FAO, referência global), chuva média no ciclo "
            f"{chuva_ciclo_mm:.0f} mm, irrigação informada {irrig:.0f} mm")
    if falta <= 0:
        return _item("Água disponível", "atende", base + ": a soma cobre a demanda de referência.")
    return _item("Água disponível", "nao_atende", base + f": faltam cerca de {falta:.0f} mm para a demanda de referência.")


def _checar_equipamento(f: Filtros) -> dict | None:
    if f.equipamento == EQUIPAMENTOS[0]:
        return None
    return _item("Equipamento", "lacuna", f"LACUNA: a tabela de culturas não traz exigência de máquina ou mão de obra; não dá para filtrar. "
                 f"Sua resposta ('{f.equipamento}') vai para a ficha do técnico.")


def _checar_mercado(f: Filtros, cid: str, ibge: int | None) -> dict | None:
    if f.mercado == MERCADOS[0]:
        return None
    if cid not in PAM_PRODUTO:
        return _item("Mercado", "lacuna", "LACUNA: esta cultura não tem correspondência no IBGE (PAM); sem dado de preço ou de demanda.")
    ctx = contexto_pam_cache(ibge)
    if not ctx:
        return _item("Mercado", "lacuna", "LACUNA: sem dado do IBGE (PAM) para este município.")
    if cid in ctx:
        return _item("Mercado", "atende", f"o IBGE registra {ctx[cid]['area_colhida_ha']:.0f} ha colhidos no município em {ctx[cid]['ano']} "
                     "(proxy de escoamento local; não é preço nem garantia de venda).")
    ano = next(iter(ctx.values()))["ano"]
    return _item("Mercado", "nao_atende", f"o IBGE não registra colheita desta cultura no município em {ano} (proxy de escoamento local; "
                 "não quer dizer que não haja mercado).")


@functools.lru_cache(maxsize=256)
def contexto_pam_cache(ibge: int | None) -> dict:
    return contexto_pam(ibge)


def geocodigo(ponto_id: str) -> int | None:
    return Z.geocodigo_do_ponto(ponto_id)


def avaliar(f: Filtros, ponto_id: str, cultura_id: str, chuva_ciclo_mm: float | None = None, demanda_mm: float | None = None,
            com_agua: bool = True) -> dict:
    """Resultado dos filtros para UMA cultura: {'itens': [...], 'passa': bool, 'tem_lacuna': bool}. `passa` = nenhum filtro ativo NÃO atende."""
    g = geocodigo(ponto_id)
    itens = [_checar_manejo(f, g, cultura_id)]
    if com_agua:
        itens.append(_checar_agua(f, chuva_ciclo_mm, demanda_mm))
    for x in (_checar_equipamento(f), _checar_mercado(f, cultura_id, g)):
        if x:
            itens.append(x)
    return {"itens": itens, "passa": not any(i["status"] == "nao_atende" for i in itens),
            "tem_lacuna": any(i["status"] == "lacuna" for i in itens)}


def resumo(res: dict) -> str:
    if not res["passa"]:
        return "NÃO passa: " + "; ".join(i["filtro"] for i in res["itens"] if i["status"] == "nao_atende")
    return "passa, com lacuna(s)" if res["tem_lacuna"] else "passa"
