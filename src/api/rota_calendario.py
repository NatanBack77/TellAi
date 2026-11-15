"""Rota POST /calendario: o calendário de plantio (`culturas/calendario_plantio.calcular`) para uma lista de plantios. Módulo PRONTO PARA INCLUIR: o dono de
`src/api/main.py` só precisa de DUAS linhas (junto com a de /conversa):

    from src.api.rota_calendario import router as rota_calendario
    app.include_router(rota_calendario)

(e, se quiser limite de taxa próprio, acrescentar "/calendario" a `limite_taxa.PESADAS`: o primeiro cálculo carrega o motor e leva alguns segundos).
Nada aqui importa `main` no topo (evita importação circular). Sem IA, sem rede, sem identificador na saída: o servidor não guarda nada.
Resposta = o cálculo (cada bloco com `disponivel`/`motivo`, lacuna visível) + `fatos` (as mesmas frases simples e origens que o chat reescreve).
O `hoje` é sempre o do servidor (não é campo de entrada).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["calendario"])


class QuandoIn(BaseModel):
    """Uma de 3 formas: {data} | {mes, ano?, parte?} | {de, ate, precisao?}. Mês sem ano = o mais recente que já começou."""
    model_config = ConfigDict(extra="forbid")
    data: str | None = Field(None, description="Data exata AAAA-MM-DD.")
    mes: int | None = Field(None, ge=1, le=12)
    ano: int | None = Field(None, ge=2000, le=2100, description="Sem ano: o mês mais recente que já começou.")
    parte: Literal["comeco", "meio", "fim"] | None = Field(None, description="comeco = dias 1-10, meio = 11-20, fim = 21 em diante.")
    de: str | None = Field(None, description="Início da faixa (AAAA-MM-DD).")
    ate: str | None = Field(None, description="Fim da faixa (AAAA-MM-DD).")
    precisao: Literal["semana", "relativo", "quinzena", "faixa", "estacao"] | None = None

    def para_dict(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class PlantioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cultura: str = Field(description="Id da tabela de culturas (ex.: milho, feijao_caupi, sorgo).")
    quando: QuandoIn | str = Field(description="Objeto (ver QuandoIn) ou data AAAA-MM-DD.")
    ciclo_dias: int | None = Field(None, ge=30, le=800, description="Ciclo da semente do agricultor, em dias (sobrepõe o ciclo da FAO/EcoCrop).")
    manejo: Literal["sequeiro", "irrigado"] = "sequeiro"


class CalendarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str = Field(description="Local (pontos.csv).")
    plantios: list[PlantioIn] = Field(min_length=1, max_length=12)
    textura: Literal["não sei", "arenoso", "médio", "argiloso"] = "não sei"
    proibidas: list[str] = Field(default_factory=list, max_length=16, description="Culturas que ele não quer (saem da lista do que vem depois).")
    proximas: bool = Field(True, description="False pula a consulta da rotação (a mais lenta na primeira chamada).")


class CalendarioOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: str
    hoje: str
    plantios: list[dict[str, Any]] = Field(description="Um por plantio, na ordem: status (em_andamento|ciclo_concluido|planejamento|esclarecimento), quando, ciclo, fase, colheita, zarc, chuva, veranico, verde, solo_nu, proximas, lacunas.")
    limites: list[str]
    fatos: list[dict[str, Any]] = Field(description="Fatos [F#] (texto técnico, texto simples, origem, lacuna) de cada plantio (campo `plantio` = índice).")


def _hoje() -> date:
    return date.today()


@router.post("/calendario", response_model=CalendarioOut)
def calendario(req: CalendarioIn):
    """O que os dados mostram sobre cada plantio: fase, colheita esperada (referência de outras regiões), janela do ZARC, chuva desde o plantio contra os
    anos anteriores, período seco, verde da região, época de solo nu e o que a matriz de rotação mostra para depois. Nada é ordem nem previsão."""
    from src.api import main as A
    from src.culturas import calendario_plantio as CP
    from src.llm import conversa as CV
    from src.llm import fatos as FT
    A.exigir_ponto(req.ponto_id)
    tab = A.tabela()
    for c in req.proibidas:
        if c not in tab:
            raise HTTPException(422, f"cultura '{c}' não está na tabela de culturas")
    pls = [{"cultura": p.cultura, "quando": p.quando.para_dict() if isinstance(p.quando, QuandoIn) else p.quando, "ciclo_dias": p.ciclo_dias, "manejo": p.manejo}
           for p in req.plantios]
    solo = {"arenoso": "arenoso", "médio": "medio", "argiloso": "argiloso"}.get(req.textura, "qualquer")
    try:
        calc = CP.calcular(req.ponto_id, pls, _hoje(), blocos=None if req.proximas else set(), proibidas=tuple(req.proibidas), solo=solo)
    except ValueError as e:
        raise HTTPException(422, str(e))
    folha = FT.montar_folha_calendario(calc, CV._nomes())
    return {**calc, "fatos": [{k: f.get(k) for k in ("id", "plantio", "papel", "rotulo", "texto", "texto_simples", "origem", "lacuna")} for f in folha["fatos"]]}
