"""Rota POST /conversa (conversa consultiva com o agricultor). Módulo PRONTO PARA INCLUIR: o dono de `src/api/main.py` só precisa de

    from src.api.rota_conversa import router as rota_conversa
    app.include_router(rota_conversa)

(logo depois da rota /chat). Nada aqui importa `main` no topo (evita importação circular): o que precisa dele é lido dentro da função.
O servidor NÃO guarda a conversa: o cliente devolve o `estado` recebido na rodada anterior (JSON com entidades, sem texto das mensagens).
O limite de taxa do `main` vale para esta rota também (middleware global). Ver docs/21_resultados_fases/CONVERSA_CONSULTIVA.md.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["conversa"])


class ConversaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mensagem: str = Field(min_length=1, max_length=2000, description="O que o agricultor escreveu (ou o `texto` de um chip). Acima de ~400 letras, a resposta é um pedido para escrever mais curto.")
    estado: dict[str, Any] | None = Field(None, description="O `estado` devolvido na rodada anterior (None = conversa nova). Só entidades: culturas, foco, regras, ponto, `plantios` (lista validada por schema: cultura, quando, ciclo_dias, manejo) e o rascunho do plantio em andamento; nunca o texto das mensagens.")
    ponto_id: str | None = Field(None, description="Local escolhido no app. Fica no servidor: nunca vai à API externa de IA.")
    cultura_atual: str | None = Field(None, description="Cultura que ele planta hoje (opcional). Com ela e um foco, a resposta inclui os caminhos de 3 safras.")
    perfil: dict[str, Any] | None = Field(None, description="Perfil do app (mesmo formato de `PerfilChatIn` do /chat; sem município nem cultura_atual). Aceita `plantios` (schema estrito de `calendario_plantio.validar_plantios`): vale para perguntas de acompanhamento ('como choveu?') mesmo sem estado.")


class ConversaChip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rotulo: str = Field(description="Texto do botão.")
    texto: str = Field(description="Mensagem enviada como `mensagem` quando o botão é tocado.")


class ConversaFonte(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    tema: str
    rotulo: str
    texto_simples: str
    origem: str = Field(description="Função/arquivo de onde o fato veio (para conferir).")
    lacuna: bool


class ConversaVerificacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool | None = Field(description="true = texto da IA aprovado; false = rejeitado (veja `motivos`; o texto padrão foi mostrado); null = não houve texto de IA.")
    motivos: list[str]


class ConversaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resposta: str = Field(description="Texto LIMPO para exibir (sem [F#]); a última linha pode ser a pergunta que o assistente faz.")
    resposta_com_citacoes: str = Field(description="Mesmo texto com os marcadores [F#], para conferência.")
    estado: dict[str, Any] = Field(description="Guardar e devolver na próxima rodada.")
    acao: Literal["responder", "perguntar", "confirmar", "recusar"]
    chips: list[ConversaChip] = Field(description="Respostas rápidas (botões). Vazio = campo de texto livre.")
    pergunta: str | None = Field(description="A pergunta que o assistente fez (também é a última linha de `resposta`).")
    pede: Literal["municipio", "foco", "ordem", "culturas", "confirmacao", "mensagem"] | None
    origem: Literal["llm", "template", "sem_evidencia", "recusa"]
    entendido: str | None = Field(description="Frase 'Entendi: ...' com o que foi extraído (para mostrar ao agricultor).")
    verificacao: ConversaVerificacao
    fontes: list[ConversaFonte] = Field(description="Fatos [F#] que serviram de fonte.")
    fatos: list[dict[str, Any]] = Field(description="Fatos com texto técnico, texto simples, origem e lacuna (conferência).")
    trechos: list[dict[str, Any]]
    citados_fatos: list[str]
    uso: dict | None
    motivo: str
    em_cache: bool
    provedor: str
    modelo: str
    assistente: str = Field(description="Rótulo fixo para a tela: deixa claro que é um assistente automático, não uma pessoa nem um técnico.")
    calendario: dict[str, Any] | None = Field(None, description="Só nas respostas do calendário de plantio: {plantio, indice, tema, status, ver_no_calendario}. O `estado.plantios` guarda a lista (schema estrito).")


@router.post("/conversa", response_model=ConversaOut)
def conversa(req: ConversaIn):
    """Uma rodada da conversa consultiva. O assistente entende (sem IA), pergunta uma coisa por vez, confirma quando não tem certeza e responde com os
    fatos calculados pelo código; a IA, se ligada, só reescreve esses fatos e o verificador confere. Sem chave ou texto reprovado: texto padrão."""
    from src.api import main as A
    from src.app import perfil as PF
    from src.llm import conversa as C
    if req.ponto_id is not None:
        A.exigir_ponto(req.ponto_id)
    if req.cultura_atual is not None and req.cultura_atual not in A.tabela():
        raise HTTPException(422, f"cultura '{req.cultura_atual}' não está na tabela de culturas")
    perfil: dict = {}
    if req.perfil is not None:
        try:
            perfil = PF.para_chat(PF.validar(req.perfil, A.tabela(), como_chat=True))
        except PF.PerfilErro as e:
            raise HTTPException(422, "perfil inválido: " + "; ".join(e.erros))
    if req.cultura_atual:
        perfil["cultura_atual"] = req.cultura_atual
    estado = req.estado
    if isinstance(estado, dict) and "plantios" in estado:          # estado com plantios fora do schema = 422 (os demais campos do estado são só descartados)
        from src.culturas import calendario_plantio as CP
        try:
            CP.validar_plantios(estado["plantios"], A.tabela())
        except ValueError as e:
            raise HTTPException(422, "plantios do estado inválidos: " + str(e))
    return C.conversar(req.mensagem, estado, req.ponto_id, perfil)
