"""Ponte entre a camada LLM e o app/API (funcoes puras; sem Streamlit, sem rede por padrao).

Regra: o TEMPLATE (`src.app.logica.explicar`) e sempre o padrao. O LLM so reescreve quando
  (a) ha provedor real (nao stub) E chave configurada (modo "online"), ou
  (b) ha texto no cache de demo (modo "offline": le SO o cache; sem cache => template).
Tudo o que o LLM devolve passa pelo verificador (servico.reescrever); falhou => template.

Como o app deve chamar (resumo; detalhes em docs/21_resultados_fases/L_R.md):
    from src.llm import integracao as li
    r = li.explicar_cenario(cenario)                 # modo vem de SULCO_LLM_MODO (padrao: "template")
    st.write(r["texto"]); st.caption(li.rotulo_origem(r))
    r = li.responder_pergunta(pergunta)              # RAG + (template | llm | sem evidencia)
Modos: "template" (padrao), "offline" (cache de demo), "online" (chama o provedor; precisa de chave).
"""
from __future__ import annotations

import os

from . import servico
from .cache import Cache
from .provedores import DeepSeek, Provedor, Stub, ler_chave_env, obter

MODOS = ("template", "offline", "online")
ROTULOS = {
    "llm": "Texto reescrito por modelo de linguagem e verificado contra os dados e trechos (números e citações conferidos).",
    "template": "Texto gerado por regras (sem modelo de linguagem).",
    "sem_evidencia": "Sem evidência no acervo para esta pergunta.",
    "recusa": "Pedido fora do que a ferramenta faz.",
}


def modo_padrao() -> str:
    m = (os.environ.get("SULCO_LLM_MODO") or "template").strip().lower()
    return m if m in MODOS else "template"


def tem_chave(provedor: Provedor | None = None) -> bool:
    """True so se o provedor for real e tiver chave. Nunca devolve nem imprime a chave."""
    p = provedor or obter_provedor_real()
    if isinstance(p, Stub):
        return False
    if not hasattr(p, "_chave"):
        return True  # provedor sem conceito de chave (ex.: falso de teste, ou outro servico configurado)
    return bool(p._chave)


def obter_provedor_real() -> Provedor:
    """Provedor escolhido por SULCO_LLM; 'stub'/ausente => DeepSeek (para identificar o cache)."""
    nome = (os.environ.get("SULCO_LLM") or "deepseek").lower()
    return obter(nome) if nome != "stub" else DeepSeek()


def _template(cenario: dict, motivo: str) -> dict:
    return {"texto": servico.template_cenario(cenario), "origem": "template", "motivos": [motivo],
            "provedor": "nenhum", "em_cache": False}


def explicar_cenario(cenario: dict, modo: str | None = None, provedor: Provedor | None = None,
                     cache: Cache | None = None, permitir_stub: bool = False) -> dict:
    """{texto, origem: llm|template, motivos, provedor, em_cache}. Nunca levanta por falha do LLM/cache."""
    modo = (modo or modo_padrao()).lower()
    if modo not in MODOS:
        modo = "template"
    if modo == "template":
        return _template(cenario, "modo template (padrão)")
    prov = provedor or obter_provedor_real()
    if isinstance(prov, Stub) and not permitir_stub:
        return _template(cenario, "provedor stub não é usado na tela")
    cache = cache if cache is not None else Cache()
    try:
        if modo == "offline":
            return servico.reescrever(cenario, provedor=prov, cache=cache, offline=True)
        if not tem_chave(prov) and not isinstance(prov, Stub):
            return _template(cenario, "sem chave de API: usando template")
        return servico.reescrever(cenario, provedor=prov, cache=cache, offline=False)
    except Exception as e:  # defesa final: o app nunca quebra por causa do LLM
        return _template(cenario, f"falha na camada LLM ({type(e).__name__}): usando template")


def responder_pergunta(pergunta: str, modo: str | None = None, provedor: Provedor | None = None,
                       cache: Cache | None = None, buscar_fn=None, permitir_stub: bool = False) -> dict:
    """Pergunta ao acervo. Sem LLM disponivel: devolve os trechos (template). Sem trechos: 'sem evidência'."""
    modo = (modo or modo_padrao()).lower()
    prov = provedor or obter_provedor_real()
    usar_llm = modo in ("offline", "online") and (permitir_stub or not isinstance(prov, Stub))
    if modo == "online" and not (tem_chave(prov) or permitir_stub):
        usar_llm = False
    # sem LLM: provedor stub forcado e offline=True com cache vazio => template_resposta (nunca gera texto novo)
    try:
        if usar_llm:
            return servico.responder(pergunta, provedor=prov, buscar_fn=buscar_fn,
                                     cache=cache if cache is not None else Cache(), offline=(modo == "offline"))
        return servico.responder(pergunta, provedor=Stub(), buscar_fn=buscar_fn, cache=Cache(), offline=True)
    except Exception as e:
        return {"texto": servico.MSG_SEM_EVIDENCIA, "origem": "sem_evidencia",
                "motivos": [f"falha ({type(e).__name__})"], "provedor": "nenhum", "em_cache": False, "trechos": []}


def rotulo_origem(r: dict) -> str:
    return ROTULOS.get(r.get("origem"), "")
