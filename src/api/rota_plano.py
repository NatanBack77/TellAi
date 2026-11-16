"""Rotas do plano de plantio de 10 etapas (docs/34_PLANO_DE_PLANTIO.md):

    POST /plano-plantio              {ponto_id, cultura}  -> as 10 etapas, cada item com valor, fonte (nome, página, trecho) e status
    GET  /plano-plantio/culturas                         -> culturas que têm plano e quantos itens há por etapa
    GET  /plano-plantio/etapas                           -> o contrato das etapas (número, nome, origem)

Incluir em `src/api/main.py` (junto das outras): `from src.api.rota_plano import router as _rota_plano` e `app.include_router(_rota_plano)`.
O limite de taxa "pesado" já cobre este caminho (prefixo "/plano"). Sem IA, sem rede, sem identificador na saída; o servidor não guarda nada.
Regras (aplicadas em `src/plano/montar.py`, não dependem do front): nenhum caminho de arquivo; trecho com produto/fumigação não sai; lacuna nunca tem valor.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["plano-plantio"])


class FonteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str
    pagina: int | None = None
    url: str | None = Field(None, description="Só endereços http(s); nunca caminho de arquivo.")


class ItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    atributo: str
    rotulo: str
    valor: str | None = Field(description="null quando o status é lacuna ou nao_se_aplica. Nunca preenchido pelo front.")
    unidade: str = ""
    status: Literal["verificado", "calculado", "lacuna", "nao_se_aplica"] = Field(
        description="verificado = trecho de publicação conferido na página; calculado = vem do motor do Sulco.")
    fonte: FonteOut | None = None
    trecho: str | None = Field(None, description="Trecho literal da fonte; pode vir vazio quando a fonte cita produto.")
    contexto: str = Field("", description="De onde vem (região da fonte, limites). Mostrar junto do valor.")
    requer_tecnico: bool = Field(False, description="true = mostrar 'converse com o técnico antes de aplicar' ao lado deste item.")
    referencia_da_fonte: bool = Field(False, description="true = é o que a fonte diz, NÃO é recomendação para o terreno do agricultor (adubação, doses).")
    experimento: bool = Field(False, description="true = valor de parcela de experimento, não recomendação de plantio.")
    destaque: bool = Field(False, description="true = faz parte da resposta objetiva da etapa (até 3 por etapa): mostrar primeiro; o resto vai em 'detalhes'.")


class EtapaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero: int
    slug: str
    titulo: str
    origem: Literal["dado_curado", "motor"]
    itens: list[ItemOut]
    lacunas: list[str] = Field(description="O que NÃO temos nesta etapa. Mostrar sempre; nunca esconder.")
    nao_se_aplica: bool = Field(description="true = a etapa não se aplica a esta cultura (ex.: adubo verde não tem grão colhido).")
    aviso_tecnico: bool = True


class PlanoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str = Field(description="Local (pontos.csv).")
    cultura: str | None = Field(None, description="Id da tabela de culturas (ex.: milho). Sem ela, o plano segue pela planta mais indicada para o local e o solo "
                                "(a etapa 2 lista as melhores opções).")
    solo: Literal["qualquer", "arenoso", "medio", "argiloso"] = Field("qualquer", description="Textura do solo que a pessoa informou; o zoneamento é calculado para ela.")


class PlanoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: str
    ponto_id: str
    cultura: str
    cultura_nome: str
    cultura_exemplo: bool = Field(description="true = o servidor escolheu a cultura (a mais indicada para o local e o solo) porque o pedido não trazia cultura.")
    etapas: list[EtapaOut] = Field(description="Sempre 10, na ordem do contrato.")
    cobertura_itens: dict[str, int] = Field(description="Itens com dado por etapa (número da etapa -> quantidade).")
    limites: list[str]
    aviso: str


class CulturaPlanoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cultura: str
    nome: str
    itens_por_etapa: dict[str, int]


class EtapaContratoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero: int
    slug: str
    titulo: str
    origem: Literal["dado_curado", "motor"]


def _dados():
    from src.plano import dados
    try:
        return dados.carregar()
    except ValueError as e:
        raise HTTPException(503, f"dado do plano indisponível: {str(e).splitlines()[0]}")


@router.post("/plano-plantio", response_model=PlanoOut)
def plano_plantio(req: PlanoIn):
    """O plano de plantio em 10 etapas para um local e uma cultura. Compara e mostra o que as fontes dizem; não decide nem promete."""
    from src.api import main as A
    from src.plano import montar, motor_etapas
    A.exigir_ponto(req.ponto_id)
    tab = A.tabela()
    exemplo = req.cultura is None
    cultura = req.cultura if req.cultura is not None else motor_etapas.cultura_exemplo(req.ponto_id, req.solo)
    if cultura is None:
        raise HTTPException(404, "nenhuma cultura com plano é viável para este local")
    if cultura not in tab:
        raise HTTPException(422, f"cultura '{cultura}' fora da tabela de culturas")
    ds = _dados()
    try:
        return montar.montar(req.ponto_id, cultura, nome_cultura=tab[cultura]["cultura_pt"],
                             fornecedores={2: lambda p, c: motor_etapas.recomendacao(p, c, req.solo), 3: motor_etapas.clima_epoca}, ds=ds, exemplo=exemplo)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/plano-plantio/culturas", response_model=list[CulturaPlanoOut])
def culturas_com_plano():
    """Culturas que têm plano e quantos itens com fonte há em cada etapa curada (as etapas 2 e 3 vêm do cálculo do local)."""
    from src.api import main as A
    from src.plano.etapas import ETAPAS_CURADAS
    ds = _dados()
    tab = A.tabela()
    out = []
    for cid in sorted({c for c, _ in ds}):
        por = {str(e): sum(1 for ln in ds.get((cid, e), []) if ln.status == "verificado") for e in sorted(ETAPAS_CURADAS)}
        out.append(CulturaPlanoOut(cultura=cid, nome=tab[cid]["cultura_pt"] if cid in tab else cid, itens_por_etapa=por))
    return out


@router.get("/plano-plantio/etapas", response_model=list[EtapaContratoOut])
def etapas_do_plano():
    from src.plano.etapas import ETAPAS
    return [EtapaContratoOut(numero=n, slug=s, titulo=t, origem="dado_curado" if o == "curado" else "motor") for n, s, t, o in ETAPAS]
