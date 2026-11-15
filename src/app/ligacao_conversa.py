"""Ponto de ligação com a conversa consultiva (`src/llm/conversa.py`, escrita por outro agente). Aqui NÃO há lógica de conversa.

Contrato combinado (o módulo da conversa decide o resto; tudo é opcional e tolerante a ausência):
  estado da conversa   dict {'culturas_citadas': [ids da tabela], 'foco': 'agua'|'solo'|'renda'|None}
  chips                lista de textos curtos de resposta rápida (botões); o clique vira a próxima fala do usuário
  `conversa.responder(fala, estado=..., perfil=...)` -> dict {'texto': str, 'chips': [str], 'estado': {...}}  (se existir)

`ligar_conversa` devolve None se o módulo ainda não existe ou não tem `responder`; a página então não mostra a seção. Nunca levanta.
`perfil` já vem sem identificador (`perfil.para_chat`). O estado pode ser aplicado ao perfil com `perfil.estado_conversa_para_perfil`.
"""
from __future__ import annotations

import importlib

CHIPS_INICIAIS = ["Quero economizar água", "Quero proteger o solo", "Quero uma renda extra", "Ainda não sei o que plantar"]
ESTADO_VAZIO = {"culturas_citadas": [], "foco": None}


def disponivel() -> bool:
    try:
        return callable(getattr(importlib.import_module("src.llm.conversa"), "responder", None))
    except Exception:  # noqa: BLE001 - módulo ausente ou com defeito: a seção some
        return False


def ligar_conversa(fala: str, estado: dict | None = None, perfil: dict | None = None) -> dict | None:
    """Envia a fala do usuário à conversa consultiva. None = conversa indisponível (ou falhou)."""
    try:
        mod = importlib.import_module("src.llm.conversa")
        fn = getattr(mod, "responder", None)
        if not callable(fn):
            return None
        r = fn(fala, estado=dict(estado or ESTADO_VAZIO), perfil=perfil)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(r, dict) or not isinstance(r.get("texto"), str):
        return None
    chips = [c for c in (r.get("chips") or []) if isinstance(c, str)][:6]
    est = r.get("estado") if isinstance(r.get("estado"), dict) else dict(estado or ESTADO_VAZIO)
    return {"texto": r["texto"], "chips": chips, "estado": est}
