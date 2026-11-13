"""Protecao contra injecao de instrucoes e saneamento de dados enviados a API externa."""
from __future__ import annotations

import re

from .verificador import sem_acento

INJECAO = [re.compile(p) for p in [
    r"ignor\w* .{0,30}(regra|instruc|anterior|acima|prompt|sistema)",
    r"(esquec|desconsider|desobedec|burl|sobrescrev)\w* .{0,40}(regra|instruc|prompt)",
    r"ignore .{0,30}(rules|instructions|prompt)", r"disregard .{0,30}(rules|instructions)",
    r"(system|developer) prompt|prompt do sistema|suas instrucoes|instrucoes do sistema",
    r"voce (agora )?(e|eh|sera) (um|uma|o|a) ", r"\bfinja\b|faca de conta|aja como|act as|pretend|jailbreak|modo desenvolvedor",
    r"\binvent\w*", r"(revel|mostr|mand)\w* .{0,25}(chave|senha|prompt|api.?key)",
]]
FORA_ESCOPO = [re.compile(p) for p in [
    r"vai chover|previs\w+ d[oe] (chuva|clima|tempo)|prev\w+ (a )?(chuva|clima)|chovera",
    r"quanto vou (ganhar|colher|lucrar|faturar)",
    r"qual (a )?(melhor )?(rotacao|cultura) (eu )?(devo|escolher|plantar)|o que (eu )?devo plantar|qual a melhor (rotacao|cultura)",
]]
MSG_INJECAO = ("Não posso atender: o pedido tenta mudar as regras da ferramenta. Eu só explico, com base nos "
               "documentos do acervo, e não invento números.")
MSG_ESCOPO = ("Essa pergunta pede previsão do clima ou a escolha de uma rotação, o que esta ferramenta não faz. "
              "Veja os cenários na tela e converse com um técnico local.")
CHAVES_SENSIVEIS = {"lat", "lon", "lng", "latitude", "longitude", "coordenadas", "geometria", "poligono", "geojson",
                    "agricultor", "nome_agricultor", "produtor", "cpf", "cnpj", "telefone", "email", "endereco",
                    "propriedade", "car", "usuario"}


def classificar_pergunta(p: str) -> str:
    n = sem_acento(p.lower())
    if any(r.search(n) for r in INJECAO):
        return "injecao"
    if any(r.search(n) for r in FORA_ESCOPO):
        return "fora_de_escopo"
    return "ok"


def trecho_suspeito(texto: str) -> bool:
    n = sem_acento(texto.lower())
    return any(r.search(n) for r in INJECAO)


def neutralizar(s: str) -> str:
    """Remove marcadores de delimitacao (<<<, >>>) para o texto nao fechar o bloco de dados."""
    return re.sub(r"[<>]{2,}", " ", s)


def sanear_json(x):
    """Remove campos sensiveis (coordenadas, identificacao) antes de qualquer envio a API externa."""
    if isinstance(x, dict):
        return {k: sanear_json(v) for k, v in x.items() if str(k).lower() not in CHAVES_SENSIVEIS}
    if isinstance(x, list):
        return [sanear_json(v) for v in x]
    return neutralizar(x) if isinstance(x, str) else x


def redigir_pergunta(p: str) -> str:
    p = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[e-mail removido]", p)
    p = re.sub(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", "[cpf removido]", p)
    p = re.sub(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}", "[telefone removido]", p)
    return neutralizar(p)[:500]
