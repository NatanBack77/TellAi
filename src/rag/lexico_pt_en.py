"""Lexico controlado PT -> EN para perguntas sobre documentos em ingles (FAO). SEM LLM, sem rede.

Cada entrada e vocabulario agronomico geral (palavra PT sem acento, minuscula -> termos EN). Nao contem fatos nem
respostas. Montado a partir do vocabulario das perguntas de DEV (nao do conjunto TESTE). A traducao e usada so como
consulta extra (BM25 e embeddings) e como portao lexical adicional para trechos em ingles; nunca vira texto de resposta.
"""
from __future__ import annotations

import re
import unicodedata

LEXICO = {
    "rotacao": "rotation", "sucessao": "rotation sequence", "cultura": "crop", "culturas": "crops",
    "lavoura": "crop field", "plantar": "plant", "plantio": "planting seeding", "semeadura": "seeding sowing",
    "direto": "direct no-till", "solo": "soil", "solos": "soils", "agua": "water", "chuva": "rain rainfall",
    "palha": "residues mulch", "palhada": "residues mulch", "restos": "residues", "residuos": "residues",
    "cobertura": "cover covering", "adubo": "fertilizer", "adubos": "fertilizers", "adubacao": "fertilization",
    "verde": "green", "verdes": "green", "leguminosa": "legume", "leguminosas": "legumes",
    "nitrogenio": "nitrogen", "fixam": "fixing fix", "fixa": "fixing fix", "fixacao": "fixation",
    "praga": "pests", "pragas": "pests", "doenca": "diseases", "doencas": "diseases",
    "erosao": "erosion", "revolvimento": "tillage disturbance", "preparo": "tillage preparation",
    "minimo": "minimum", "principios": "principles", "principio": "principle", "pilares": "principles",
    "agricultura": "agriculture", "conservacao": "conservation", "produtividade": "yield productivity",
    "rendimento": "yield", "semente": "seed", "sementes": "seeds", "milho": "maize corn", "feijao": "beans",
    "trigo": "wheat", "arroz": "rice", "sorgo": "sorghum", "mandioca": "cassava", "soja": "soybean",
    "vulnerabilidade": "vulnerability", "eventos": "events", "clima": "climate", "climaticos": "climatic climate",
    "climatica": "climatic", "extremos": "extreme", "extremas": "extreme", "seca": "drought", "umidade": "moisture",
    "organica": "organic", "organico": "organic", "carbono": "carbon", "controle": "control controlling",
    "controlar": "control", "daninhas": "weeds", "ervas": "weeds", "herbicida": "herbicide",
    "maquinas": "machinery equipment", "implemento": "implement", "agricultor": "farmer", "agricultores": "farmers",
    "beneficios": "benefits", "vantagens": "advantages", "vantagem": "advantage", "reduz": "reduces reduce",
    "reduzir": "reduce", "aumenta": "increases increase", "diferentes": "different", "camada": "layer",
    "compactacao": "compaction", "infiltracao": "infiltration", "escoamento": "runoff", "temperatura": "temperature",
    "vento": "wind", "proteger": "protect protects", "protege": "protects protect", "impacto": "impact",
    "estacao": "season", "estacoes": "seasons", "anos": "years", "campo": "field", "mesmo": "same",
    "subsolador": "ripper subsoiler", "consorcio": "intercropping", "consorciar": "intercropping",
    "microrganismos": "microorganisms", "biologica": "biological", "fertilidade": "fertility", "nutrientes": "nutrients",
    "decomposicao": "decomposition", "cobrir": "cover", "mulch": "mulch", "tres": "three", "definicao": "definition",
    "semiarido": "semi-arid", "irrigacao": "irrigation", "irrigado": "irrigated", "custo": "cost", "custos": "costs",
    "trabalho": "labour labor", "tempo": "time", "pequenos": "smallholder small", "pequeno": "smallholder small",
    "pequena": "smallholder small", "familiar": "family smallholder",
}
_STOP = set("quais qual como para que por de do da dos das em no na nos nas um uma ao aos as os e ou se com sem sobre "
            "ser sao uso usa usar fazer faz pode podem deve devo vale pena melhor onde quando porque pra eu meu minha "
            "seu sua muito mais menos ate entre isso esse essa".split())


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return s


def traduzir(pergunta: str) -> tuple[str, float]:
    """(consulta em ingles, fracao das palavras de conteudo da pergunta que tiveram traducao). '' se nada."""
    toks = [t for t in re.findall(r"[a-z0-9]+", _norm(pergunta)) if t not in _STOP and len(t) >= 3]
    if not toks:
        return "", 0.0
    out, hit = [], 0
    for t in toks:
        e = LEXICO.get(t) or (LEXICO.get(t[:-1]) if t.endswith("s") else None) or (LEXICO.get(t[:-2]) if t.endswith("es") else None)
        if e:
            out.append(e)
            hit += 1
    return " ".join(out), hit / len(toks)
