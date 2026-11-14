"""L4: avalia as 20 perguntas estilo agricultor (tests/l4_perguntas.py) contra o indice real.

    python -m src.llm.avaliar_l4                      # provedor stub (valida o encanamento; NAO mede LLM)
    python -m src.llm.avaliar_l4 --provedor deepseek  # COM chave: mede tambem latencia e custo
    python -m src.llm.avaliar_l4 --indice hibrido     # embeddings + reranker (usa ~RAM; padrao: bm25)
Metricas:
  recuperacao@5     : trecho esperado (arquivo+pagina+frase) esta entre os trechos devolvidos (so positivas)
  citacao_correta   : a resposta tem >=1 [n] e TODO [n] aponta para um trecho com arquivo+pagina esperados
  sem_evidencia_ok  : (negativas) origem == sem_evidencia
  json_valido       : o dict devolvido pelo servico serializa em JSON e tem as chaves do contrato
  latencia/custo    : so com provedor real (tempo por chamada; tokens do campo `usage` da API; custo pela tabela
                      de precos lida em 2026-11-12, docs/14_LLM.md secao 2, faixa fora-do-pico..pico, cache miss)
Sem chave com --provedor deepseek: avisa e sai sem chamar nada.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

from . import servico
from .integracao import tem_chave
from .provedores import Stub, obter

CHAVES = {"texto", "origem", "motivos", "provedor", "em_cache"}
PRECO_M = {"entrada_min": 0.15, "entrada_max": 0.30, "saida_min": 0.60, "saida_max": 1.20}  # US$/1M tokens (doc 14)


def _indice(modo: str):
    from src.rag.busca import Indice
    if modo == "hibrido":
        return Indice(usar_embeddings=True, rerank=True)
    return Indice(usar_embeddings=False, rerank=False)


def avaliar(provedor, indice, perguntas=None, k: int = 5) -> dict:
    if perguntas is None:
        from tests.l4_perguntas import L4
        perguntas = L4
    linhas = []
    for q, arq, pag, frase in perguntas:
        busca = lambda p: indice.buscar(p, k=k)  # noqa: E731
        t0 = time.perf_counter()
        r = servico.responder(q, provedor=provedor, buscar_fn=busca)
        dt = time.perf_counter() - t0
        trechos = r.get("trechos") or []
        L = {"pergunta": q, "origem": r["origem"], "latencia_s": round(dt, 3)}
        try:
            L["json_valido"] = CHAVES <= set(json.loads(json.dumps(r, ensure_ascii=False)))
        except (TypeError, ValueError):
            L["json_valido"] = False
        if arq is None:
            L["tipo"] = "negativa"
            L["sem_evidencia_ok"] = r["origem"] == "sem_evidencia"
        else:
            L["tipo"] = "positiva"
            bruto = busca(q)
            L["recuperacao"] = any(t["arquivo"] == arq and t["pagina"] == pag and frase in t["texto"]
                                   for t in bruto["trechos"])
            ns = {int(n) for n in re.findall(r"\[(\d+)\]", r["texto"])}
            por_n = {t["n"]: t for t in trechos}
            L["citacao_correta"] = (r["origem"] == "llm" and bool(ns)
                                    and all(n in por_n and por_n[n]["arquivo"] == arq and por_n[n]["pagina"] == pag
                                            for n in ns))
            L["verificador_rejeitou"] = r["origem"] == "template" and bool(r["motivos"]) and r["motivos"] != [""]
        u = getattr(provedor, "ultimo_uso", None)
        if u:
            L["tokens"] = u
        linhas.append(L)
    pos = [l for l in linhas if l["tipo"] == "positiva"]
    neg = [l for l in linhas if l["tipo"] == "negativa"]
    res = {
        "provedor": provedor.nome, "n_positivas": len(pos), "n_negativas": len(neg),
        "recuperacao_top5": sum(l["recuperacao"] for l in pos) / max(1, len(pos)),
        "citacao_correta": sum(l["citacao_correta"] for l in pos) / max(1, len(pos)),
        "sem_evidencia_ok": sum(l["sem_evidencia_ok"] for l in neg) / max(1, len(neg)),
        "json_valido": sum(l["json_valido"] for l in linhas) / len(linhas),
        "latencia_media_s": round(sum(l["latencia_s"] for l in linhas) / len(linhas), 3),
        "linhas": linhas,
    }
    toks = [l["tokens"] for l in linhas if l.get("tokens")]
    if toks:
        ent = sum(t["prompt_tokens"] or 0 for t in toks)
        sai = sum(t["completion_tokens"] or 0 for t in toks)
        res["custo_usd_faixa"] = [round((ent * PRECO_M["entrada_min"] + sai * PRECO_M["saida_min"]) / 1e6, 5),
                                  round((ent * PRECO_M["entrada_max"] + sai * PRECO_M["saida_max"]) / 1e6, 5)]
        res["tokens_total"] = {"entrada": ent, "saida": sai}
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provedor", default="stub")
    ap.add_argument("--indice", default="bm25", choices=["bm25", "hibrido"])
    a = ap.parse_args(argv)
    prov = obter(a.provedor)
    if not isinstance(prov, Stub) and not tem_chave(prov):
        print("DEEPSEEK_API_KEY não configurada: avaliação com LLM real não executada (nenhuma chamada feita).")
        return 0
    res = avaliar(prov, _indice(a.indice))
    resumo = {k: v for k, v in res.items() if k != "linhas"}
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    for l in res["linhas"]:
        print(f"- [{l['tipo'][:3]}] {l['origem']:<13} rec={l.get('recuperacao')} cit={l.get('citacao_correta')} "
              f"se={l.get('sem_evidencia_ok')} | {l['pergunta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
