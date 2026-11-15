"""Segunda base buscavel: CONHECIMENTO AGRONOMICO do dominio do Sulco (nao o projeto).

Entra por LISTA BRANCA: pesquisas de viabilidade/rotacao/FAO/ZARC/consorcio/calendario/solo, tabelas de dados com fonte,
dados minerados agregados por municipio (ZARC, PAM, solo, diagnostico) e dados externos (CONAB, SIGEF) com aviso.
Fica de fora: status, pendencias, arquitetura, API, app, LLM, voz, modelagem do NDVI, custos, testes, git, caminhos.
O indice dos PDFs (`indice/`) NAO e tocado; este vive em `indice_agronomia/` (gitignored) e o manifesto versionado em
`data/conhecimento_agronomia_manifesto.json`.

Regerar:  python -m src.rag.agronomia           (so reconstroi o que mudou; --forcar refaz tudo)
Buscar:   from src.rag.agronomia import buscar_agronomia
Alias:    buscar_projeto = buscar_agronomia (compatibilidade com o nome antigo; o modulo `projeto` reexporta).

Sem rede, sem LLM. Embeddings: multilingual-e5-small ja em cache (HF offline). Sem lat/lon em nenhum trecho.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HUB_OFFLINE", "1")          # nada novo e baixado
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from .busca import BM25, MODELO_EMB, _carregar_modelo, tokenizar  # noqa: E402  (reaproveita BM25, radical e o modelo e5)

RAIZ = Path(__file__).resolve().parents[2]
DIR_INDICE = RAIZ / "indice_agronomia"
MANIFESTO = RAIZ / "data" / "conhecimento_agronomia_manifesto.json"

PALAVRAS_ALVO_MIN, PALAVRAS_ALVO_MAX = 150, 250
LIM_COBERTURA = 0.5     # fracao dos radicais da pergunta no trecho (portao lexical)
LIM_COS = 0.86          # cosseno e5 minimo (portao semantico); ver avaliacao em CONHECIMENTO_AGRONOMICO.md
MSG_SEM_EVIDENCIA = "sem evidência"
RRF_K = 60

# ---------------------------------------------------------------- lista branca (documentos)
# caminho -> (rotulo para o modelo, tipo, confianca padrao)
DOCS_BRANCOS = {
    "docs/07_PESQUISA_VIABILIDADE.md": ("Pesquisa de viabilidade das culturas no semiárido", "pesquisa_interna", "media"),
    "docs/22_PESQUISA_ROTACAO.md": ("Pesquisa sobre rotação de culturas", "pesquisa_interna", "media"),
    "docs/25_PESQUISA_FAO.md": ("Pesquisa FAO: ciclo, Kc e água das culturas", "pesquisa_interna", "media"),
    "docs/13_ZARC.md": ("Zoneamento agrícola de risco climático (ZARC)", "pesquisa_interna", "media"),
    "docs/29_LER_CONSORCIO.md": ("Pesquisa sobre consórcio e LER", "pesquisa_interna", "media"),
    "docs/ler_trechos.md": ("Trechos de estudos publicados sobre consórcio (LER)", "estudo_publicado", "alta"),
    "docs/27_CALENDARIO_SOLO_SEMENTE_MERCADO.md": ("Calendário, solo, semente e mercado", "pesquisa_interna", "media"),
    "docs/27_EPOCA_DE_PLANTIO.md": ("Época de plantio", "pesquisa_interna", "media"),
    "docs/06_PESOS_E_CULTURAS.md": ("Culturas consideradas e seus parâmetros", "pesquisa_interna", "media"),
    "docs/21_resultados_fases/CALENDARIO_PLANTIO.md": ("Calendário de plantio", "pesquisa_interna", "media"),
    "docs/21_resultados_fases/CICLO_FAO_CHUVA_ANUAL.md": ("Ciclo FAO e chuva anual", "pesquisa_interna", "media"),
    "docs/21_resultados_fases/MATRIZ_ROTACAO.md": ("Matriz de rotação entre culturas", "pesquisa_interna", "media"),
    "docs/21_resultados_fases/SOILGRIDS.md": ("Solo estimado (SoilGrids)", "pesquisa_interna", "media"),
    "docs/21_resultados_fases/ROTACAO_REGRAS_PARETO.md": ("Regras de rotação entre culturas", "pesquisa_interna", "media"),
}
TABELAS = {
    "tabela_culturas": "data/culturas/tabela_culturas.csv",
    "fao_staging": "data/culturas/fao_staging.csv",
    "solo_staging": "data/culturas/solo_staging.csv",
    "ler_staging": "data/culturas/ler_staging.csv",
    "matriz_rotacao": "data/culturas/matriz_rotacao.csv",
}
EXTERNOS = {
    "conab_precos_uf": "data/externos/conab_precos_mensal_uf_ce.csv",
    "conab_precos_municipio": "data/externos/conab_precos_mensal_municipio_ce.csv",
    "conab_custos": "data/externos/conab_custos_producao_nordeste.csv",
    "sigef": "data/externos/sigef_campos_sementes_ce.csv",
    "manifesto_externos": "data/externos/manifesto_externos.json",
}
LACUNAS_DOC = "docs/31_LACUNAS_DE_DADOS.md"
MINERADOS = {
    "zarc": "data/processed/zarc_ce.parquet",
    "pam": "data/processed/pam_ce.parquet",
    "solo": "data/processed/solo.parquet",
    "diagnostico": "data/processed/diagnostico/diagnostico.json",
    "pontos": "data/processed/pontos.csv",
}

# ---------------------------------------------------------------- filtros de conteudo (o que NUNCA entra)
# Texto sobre o projeto/engenharia/infra/segredos. Bloco (paragrafo, linha de tabela, titulo) com qualquer um e descartado.
_PROIBIDAS = [
    r"docker\w*", r"deepseek", r"prompts?\b", r"agentes?\b", r"subagentes?", r"\bpin\b", r"\.env\b", r"pytest",
    r"commits?\b", r"endpoints?", r"\bapi\b", r"\bllm\b", r"\bchat\w*", r"\btokens?\b", r"\bgit\w*", r"streamlit",
    r"\bmvp\b", r"\bapp\b", r"\bsulco\b", r"\bmotor\b", r"pipeline", r"parquet", r"scripts?\b", r"\.py\b", r"\.md\b",
    r"\.json\b", r"\.csv\b", r"\bsrc/", r"\btests?/", r"\bdocs?/", r"\bdata/", r"deploy\w*", r"senhas?\b", r"api[_ ]?key",
    r"secret\w*", r"\bsk-[a-z0-9]{8,}", r"bearer\b", r"\bvoz\b", r"\bvozes\b", r"persona", r"rodada", r"subagent",
    r"\bfase \d", r"pendenc\w*", r"retomada", r"\bpitch\b", r"desafio nasa", r"hackathon", r"\bsha256\b", r"servidor",
    r"\bcommit", r"\btestes? (unit|automat)", r"\bcache\b", r"\bbackend\b", r"frontend", r"\bbug\b", r"refator\w*",
    r"verificador", r"\btela\b", r"r[eé]gua do desafio", r"assistente", r"regra de seguran\w+", r"proxy de pragas", r"\bcusto da (api|ia)\b", r"\bia\b generativa", r"\brag\b", r"claude", r"\bgpt\b", r"modelo (preditivo|de ndvi)",
    r"\bconformal", r"\bensemble", r"\bbaseline", r"overfit\w*", r"\bsintetic\w*", r"\bzoxide", r"\blatitude\b.*\blongitude\b",
]
_PROIB_RE = re.compile("|".join(_PROIBIDAS), re.I)
_SEGREDO_RE = re.compile(r"(sk-[A-Za-z0-9]{16,}|api[_-]?key\s*[:=]|secret\s*[:=]|password\s*[:=]|senha\s*[:=]|"
                         r"bearer\s+[A-Za-z0-9._-]{12,}|\bPIN\s*[:=]\s*\d|DEEPSEEK_\w+)", re.I)
_COORD_RE = re.compile(r"(?<![\d.])-?\d{1,2}[.,]\d{2,}\s*[,;/ ]\s*-?\d{1,2}[.,]\d{2,}(?![\d.])|\b(lat|lon|lng|latitude|longitude)\b\s*[:=]", re.I)


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def bloco_proibido(txt: str) -> bool:
    return bool(_PROIB_RE.search(_sem_acento(txt)) or _SEGREDO_RE.search(txt) or _COORD_RE.search(txt))


def varrer_proibidos(textos) -> list[str]:
    """Para teste: devolve os trechos que ainda contem termo proibido, segredo ou coordenada."""
    return [t for t in textos if bloco_proibido(t)]


# ---------------------------------------------------------------- utilidades
def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _limpar_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)          # links -> texto
    s = s.replace("**", "").replace("__", "").replace("`", "")
    s = re.sub(r"\*\*|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def _nw(s: str) -> int:
    return len(s.split())


_NIVEL_BAIXA = re.compile(r"n[aã]o verificad|hip[oó]tese|suposi[cç][aã]o|n[aã]o lido|n[aã]o consultad|estimativa grosseira|opini[aã]o", re.I)


def _confianca_texto(txt: str, padrao: str) -> str:
    return "baixa" if _NIVEL_BAIXA.search(txt) else padrao


# ---------------------------------------------------------------- culturas (rotulos e deteccao)
_CULT = {}  # id -> nome pt (preenchido sob demanda)


def _culturas() -> dict:
    if not _CULT:
        import csv
        with open(RAIZ / TABELAS["tabela_culturas"], encoding="utf-8") as f:
            for r in csv.DictReader(f):
                _CULT[r["cultura_id"]] = r["cultura_pt"]
    return _CULT


_ALIAS_EXTRA = {"feijao_caupi": ["caupi", "feijao de corda", "feijao-caupi"], "feijao_comum": ["feijao comum", "feijao carioca"],
                "palma_forrageira": ["palma"], "mamona": ["mamona", "carrapateira"], "milheto": ["milheto"], "sorgo": ["sorgo"]}


def _detectar_culturas(txt: str) -> list[str]:
    base = _sem_acento(txt.lower())
    achados = []
    for cid, nome in _culturas().items():
        nomes = {_sem_acento(nome.lower()), cid.replace("_", " ")} | set(_ALIAS_EXTRA.get(cid, []))
        if any(re.search(r"(?<![a-z])" + re.escape(n) + r"s?(?![a-z])", base) for n in nomes):
            achados.append(cid)
    return achados


def _nome_cultura(cid: str) -> str:
    return _culturas().get(cid, cid.replace("_", " ")).lower()


_ATR = {
    "temp_min_abs_c": "temperatura mínima absoluta (°C)", "temp_otima_min_c": "temperatura ótima mínima (°C)",
    "temp_otima_max_c": "temperatura ótima máxima (°C)", "temp_max_abs_c": "temperatura máxima absoluta (°C)",
    "chuva_min_abs_mm": "chuva mínima absoluta (mm)", "chuva_otima_min_mm": "chuva ótima mínima (mm)",
    "chuva_otima_max_mm": "chuva ótima máxima (mm)", "chuva_max_abs_mm": "chuva máxima absoluta (mm)",
    "ciclo_min_dias": "ciclo mínimo (dias)", "ciclo_max_dias": "ciclo máximo (dias)", "familia_botanica": "família botânica",
    "palha_ms_kg_ha": "palha, matéria seca (kg/ha)", "n_acumulado_parte_aerea_kg_ha": "nitrogênio acumulado na parte aérea (kg/ha)",
    "n_fixado_kg_ha": "nitrogênio fixado (kg/ha)", "demanda_hidrica_mm_ciclo": "demanda de água no ciclo (mm)",
    "estagio_ini_dias": "estágio inicial FAO (dias)", "estagio_dev_dias": "estágio de desenvolvimento FAO (dias)",
    "estagio_mid_dias": "estágio intermediário FAO (dias)", "estagio_late_dias": "estágio final FAO (dias)",
    "ciclo_dias_total": "ciclo total FAO (dias)", "kc_ini": "Kc inicial", "kc_mid": "Kc intermediário", "kc_end": "Kc final",
    "altura_max_m": "altura máxima (m)", "profundidade_raiz_m_min": "profundidade de raiz mínima (m)",
    "profundidade_raiz_m_max": "profundidade de raiz máxima (m)", "fracao_deplecao_p": "fração de depleção p",
    "ky_total": "Ky total (resposta da produtividade à falta de água)",
    "ph_otimo_min": "pH ótimo mínimo", "ph_otimo_max": "pH ótimo máximo", "ph_min_abs": "pH mínimo absoluto", "ph_max_abs": "pH máximo absoluto",
    "profundidade_otima": "profundidade do solo ótima", "profundidade_faixa": "profundidade do solo (faixa)",
    "textura_otima": "textura ótima", "textura_faixa": "textura (faixa)", "fertilidade_otima": "fertilidade ótima",
    "fertilidade_faixa": "fertilidade (faixa)", "salinidade_otima": "salinidade ótima", "salinidade_faixa": "salinidade (faixa)",
    "drenagem_otima": "drenagem ótima", "drenagem_faixa": "drenagem (faixa)", "toxicidade_otima": "toxicidade ótima",
    "toxicidade_faixa": "toxicidade (faixa)",
}


def _atr(a: str) -> str:
    return _ATR.get(a, a.replace("_", " "))


def _v(x) -> str:
    return "" if x is None or (isinstance(x, float) and x != x) or str(x).strip().lower() in ("nan", "none") else str(x).strip()


# ---------------------------------------------------------------- 1) documentos markdown -> trechos
def _blocos_md(texto: str):
    """Gera (caminho_de_titulos, tipo, linhas) com tipo 'p' (paragrafo/lista) ou 't' (tabela)."""
    pilha: list[tuple[int, str]] = []
    buf: list[str] = []
    modo = "p"
    for linha in texto.splitlines() + [""]:
        m = re.match(r"^(#{1,6})\s+(.*)$", linha)
        eh_tab = linha.lstrip().startswith("|")
        if m or not linha.strip() or (eh_tab and modo == "p" and buf) or (not eh_tab and modo == "t" and buf):
            if buf:
                yield [t for _, t in pilha], modo, buf
                buf = []
        if m:
            n = len(m.group(1))
            pilha = [x for x in pilha if x[0] < n] + [(n, _limpar_md(m.group(2)))]
            continue
        if not linha.strip():
            continue
        if linha.lstrip().startswith(">"):
            linha = linha.lstrip()[1:].strip()
        modo = "t" if eh_tab else "p"
        buf.append(linha)


def _empacotar(secao: list[str], blocos: list[tuple[str, list[str]]]) -> list[str]:
    """Junta blocos em trechos de ~150-250 palavras; titulo da secao no inicio; tabela grande repete o cabecalho."""
    secao = [x for x in secao if not bloco_proibido(x)]
    titulo = " > ".join(secao[-3:]) if secao else ""
    pecas: list[str] = []
    for modo, linhas in blocos:
        if modo == "t" and _nw(" ".join(linhas)) > PALAVRAS_ALVO_MAX:
            cab = linhas[:2] if len(linhas) > 2 and re.match(r"^\|[\s:|-]+\|?$", linhas[1].strip()) else []
            corpo = linhas[len(cab):]
            atual: list[str] = []
            for l in corpo:
                if atual and _nw(" ".join(cab + atual + [l])) > PALAVRAS_ALVO_MAX:
                    pecas.append("\n".join(cab + atual)); atual = []
                atual.append(l)
            if atual:
                pecas.append("\n".join(cab + atual))
        elif modo == "p" and _nw(" ".join(linhas)) > PALAVRAS_ALVO_MAX:
            atual = []
            for l in linhas:
                fr = re.split(r"(?<=[.!?;])\s+", l) if _nw(l) > PALAVRAS_ALVO_MAX else [l]
                for s in fr:
                    if atual and _nw(" ".join(atual + [s])) > PALAVRAS_ALVO_MAX:
                        pecas.append("\n".join(atual)); atual = []
                    atual.append(s)
            if atual:
                pecas.append("\n".join(atual))
        else:
            pecas.append("\n".join(linhas))
    out: list[str] = []
    atual = ""
    for p in pecas:
        if atual and (_nw(atual) >= PALAVRAS_ALVO_MIN or _nw(atual) + _nw(p) > PALAVRAS_ALVO_MAX):
            out.append(atual); atual = ""
        atual = (atual + "\n" + p) if atual else p
    if atual:
        if out and _nw(atual) < 40 and _nw(out[-1]) + _nw(atual) <= PALAVRAS_ALVO_MAX + 60:
            out[-1] += "\n" + atual
        else:
            out.append(atual)
    return [(titulo + "\n" + o) if titulo else o for o in out if _nw(o) >= 20]


def trechos_de_markdown(caminho: str, texto: str, rotulo: str, tipo: str, conf_padrao: str, data: str, contadores: dict) -> list[dict]:
    secoes: dict[tuple, list] = {}
    ordem: list[tuple] = []
    for titulos, modo, linhas in _blocos_md(texto):
        if titulos and bloco_proibido(titulos[-1]):          # titulo de secao sobre o projeto: secao inteira fora
            contadores["blocos_descartados"] = contadores.get("blocos_descartados", 0) + 1
            continue
        if modo == "p":
            lim = [_limpar_md(l) for l in linhas]
            bons = [l for l in lim if not bloco_proibido(l)]
        else:
            lim, bons = [], []
            for i, l in enumerate(linhas):
                if i < 2 and re.match(r"^\|[\s:|-]+\|?$", l.strip()) or i == 0:
                    bons.append(_limpar_md(l)); continue
                if not bloco_proibido(l):
                    bons.append(_limpar_md(l))
            lim = linhas
            if len(bons) <= 2:
                bons = []
        contadores["blocos_descartados"] = contadores.get("blocos_descartados", 0) + (len(lim) - len(bons))
        if not bons:
            continue
        k = tuple(titulos)
        if k not in secoes:
            secoes[k] = []; ordem.append(k)
        secoes[k].append((modo, bons))
    res = []
    for k in ordem:
        for i, t in enumerate(_empacotar(list(k), secoes[k]), 1):
            res.append({"texto": t, "tipo": tipo, "arquivo": rotulo, "secao": " > ".join(k[-3:]) or rotulo, "fonte": caminho,
                        "url": "", "data": data, "confianca": _confianca_texto(t, conf_padrao), "municipio": None,
                        "culturas": _detectar_culturas(t), "pode_citar_ao_agricultor": True,
                        "aviso": "Resumo de pesquisa interna; confira a fonte original antes de afirmar." if tipo == "pesquisa_interna" else ""})
    return res


# ---------------------------------------------------------------- 2) tabelas com fonte -> fatos por linha
def _higienizar(v):
    """Campo livre com termo de projeto/infra: tira parenteses ofensivos; se ainda ofender, esvazia o campo (o fato fica)."""
    if not isinstance(v, str) or not bloco_proibido(v):
        return v
    v2 = re.sub(r"\s*\([^()]*\)", lambda m: "" if bloco_proibido(m.group(0)) else m.group(0), v)
    return v2 if not bloco_proibido(v2) else ""


def _ler_csv(rel: str) -> list[dict]:
    import csv
    with open(RAIZ / rel, encoding="utf-8", newline="") as f:
        return [{k: (v if k.startswith("url") else _higienizar(v)) for k, v in r.items()} for r in csv.DictReader(f)]


def fatos_tabela_culturas(data: str) -> list[dict]:
    out = []
    for r in _ler_csv(TABELAS["tabela_culturas"]):
        nome, cid = r["cultura_pt"], r["cultura_id"]
        lac = r["status"] != "verificado"
        val = _v(r["valor"])
        if lac or not val:
            t = f"{nome} ({r['nome_cientifico']}): {_atr(r['atributo'])}: LACUNA (sem valor verificado na fonte). {_v(r['contexto'])}"
        else:
            t = f"{nome} ({r['nome_cientifico']}): {_atr(r['atributo'])} = {val} {_v(r['unidade'])}. {_v(r['contexto'])}"
        t += f" Fonte: {r['fonte'].split(' (via')[0]}; {_v(r['pagina'])}."
        out.append(_fato(t, "tabela_culturas", "tabela_com_fonte", "lacuna" if lac or not val else "alta", f"Tabela de culturas: {nome}",
                         r["url"], r["data_consulta"] or data, cid=cid,
                         aviso="Valor de base global (não específico do semiárido); confira no campo." if not lac else "Lacuna: não há dado verificado."))
    return out


def fatos_fao(data: str) -> list[dict]:
    out = []
    for r in _ler_csv(TABELAS["fao_staging"]):
        nome = _nome_cultura(r["cultura_id"])
        val = _v(r["valor"])
        t = (f"FAO, {nome}: {_atr(r['atributo'])} = {val} {_v(r['unidade'])}; região da fonte: {_v(r['regiao_da_fonte'])}. "
             f"Fonte: {r['fonte']}, {_v(r['pagina_tabela'])}. {_v(r['observacao'])}")
        out.append(_fato(t, "fao_staging", "tabela_com_fonte", "alta" if val else "lacuna", f"FAO: {nome}", r["url"], data, cid=r["cultura_id"],
                         aviso="Valor da FAO para outra região/data de plantio; não é medida do semiárido do Ceará."))
    return out


def fatos_solo(data: str) -> list[dict]:
    out = []
    for r in _ler_csv(TABELAS["solo_staging"]):
        nome = _nome_cultura(r["cultura_id"])
        lac = r["status"] != "verificado" or not _v(r["valor"])
        t = (f"Exigência de solo, {nome}: {_atr(r['atributo'])}: " + ("LACUNA (campo vazio na fonte)" if lac else f"{r['valor']} {_v(r['unidade'])}")
             + f". Fonte: FAO EcoCrop.")
        out.append(_fato(t, "solo_staging", "tabela_com_fonte", "lacuna" if lac else "alta", f"Solo: {nome}", r["url"], r["data_consulta"] or data,
                         cid=r["cultura_id"], aviso="Lacuna: sem dado." if lac else "Faixa de uma base global; o solo do talhão pode diferir."))
    return out


def fatos_ler(data: str) -> list[dict]:
    out = []
    for r in _ler_csv(TABELAS["ler_staging"]):
        a, b = _nome_cultura(r["par_a"]), _nome_cultura(r["par_b"]) if r["par_b"] else ""
        comp = r["componentes"].replace("_", " ").replace("|", " + ")
        ler = _v(r["ler_min"]) + (f" a {r['ler_max']}" if _v(r["ler_max"]) and r["ler_max"] != r["ler_min"] else "")
        t = (f"Consórcio {comp} ({a}{' com ' + b if b else ''}), {_v(r['local'])}/{_v(r['uf'])}, {_v(r['anos'])}, {_v(r['regime'])}: "
             f"LER {ler or 'não calculado na fonte'}. Arranjo: {_v(r['arranjo'])}. {('Chuva no período: ' + r['chuva_mm_periodo'] + ' mm. ') if _v(r['chuva_mm_periodo']) else ''}"
             f"Entra na faixa de referência: {r['entra_na_faixa']}. Evidência: {_v(r['tipo_evidencia']).replace('_', ' ')}. "
             f"Fonte: {r['fonte']}; {_v(r['pagina_tabela'])}. {_v(r['observacao'])} {_v(r['conferencia'])}")
        ok = _v(r["ler_min"]) and r["acesso"].startswith("texto integral lido") and r["tipo_evidencia"] == "experimento_pareado" and not _v(r["conferencia"])
        out.append(_fato(t, "ler_staging", "estudo_publicado", "alta" if ok else "media", f"LER {comp}", r["url_aberta"], r["data_consulta"] or data,
                         cids=[c for c in r["componentes"].split("|") if c], municipio=None,
                         aviso="LER > 1 indica vantagem do consórcio sobre as culturas solteiras no experimento citado; vale para aquele local, ano e arranjo."))
    return out


def fatos_matriz(data: str) -> list[dict]:
    out = []
    for r in _ler_csv(TABELAS["matriz_rotacao"]):
        a, b = _nome_cultura(r["anterior"]), _nome_cultura(r["seguinte"])
        if r["grau"] == "LACUNA":
            t = f"Rotação, {a} seguido de {b}: LACUNA (nenhum documento do acervo trata este par de culturas)."
            conf = "lacuna"
        else:
            t = (f"Rotação, {a} seguido de {b}: efeito {r['grau']} ({_v(r['criterio']).replace('_', ' ')}). {_v(r['motivo'])} "
                 f"Fonte: {_v(r['arquivo'])}, p. {_v(r['pagina'])}: \"{_v(r['trecho'])}\" Região do estudo: {_v(r['regiao_estudo'])}. {_v(r['ressalva'])}")
            conf = "alta" if _v(r["trecho"]) else "media"
        out.append(_fato(t, "matriz_rotacao", "tabela_com_fonte", conf, f"Rotação: {a} depois de {b}", "", r["data_verificacao"] or data,
                         cids=[r["anterior"], r["seguinte"]],
                         aviso="Lacuna: não há evidência sobre este par." if conf == "lacuna" else "Evidência qualitativa de fonte técnica; muitas vezes de outra região, não prova rendimento."))
    return out


_SEQ = [0]


def _fato(texto, origem, tipo, conf, secao, url, data, cid=None, cids=None, municipio=None, aviso="") -> dict:
    ids = cids if cids is not None else ([cid] if cid else [])
    return {"texto": re.sub(r"\s+", " ", texto).strip(), "tipo": tipo, "arquivo": secao, "secao": secao, "fonte": origem, "url": url or "",
            "data": data, "confianca": conf, "municipio": municipio, "culturas": [c for c in ids if c],
            "pode_citar_ao_agricultor": True, "aviso": aviso}


# ---------------------------------------------------------------- 3) externos (CONAB, SIGEF) com aviso
AV_PRECO = "Preço não é lucro: é o valor pago/recebido no mês, sem custo, frete ou perdas; não diz quanto o agricultor ganha."
AV_CUSTO = "Custo de produção da CONAB é referência de outra escala e região; custo não é lucro."
AV_SIGEF = "Campo de produção de semente inscrito no MAPA, não lavoura comercial; não representa o calendário do agricultor."
_MES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _num(s):
    s = _v(s)
    try:
        return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
    except ValueError:
        return None


def fatos_externos(data: str) -> list[dict]:
    out = []
    man = json.loads((RAIZ / EXTERNOS["manifesto_externos"]).read_text(encoding="utf-8"))
    url = {k: v.get("url", "") for k, v in man.items()}
    for r in _ler_csv(EXTERNOS["conab_precos_uf"]):
        t = (f"CONAB, preço de {r['produto'].lower()} ({r['classificao_produto'].lower()}), Ceará, {_MES[int(r['mes']) - 1]} de {r['ano']}, nível "
             f"{r['dsc_nivel_comercializacao'].lower()}: R$ {r['valor_produto_kg']} por kg. {AV_PRECO}")
        out.append(_fato(t, "conab_precos_uf", "dado_minerado", "media", "CONAB: preços no Ceará", url["conab_precos_mensal_uf_ce.csv"], data,
                         cids=_detectar_culturas(r["produto"]), aviso=AV_PRECO))
    for r in _ler_csv(EXTERNOS["conab_precos_municipio"]):
        mun = r["nom_municipio"].split("-")[0].strip().title()
        t = (f"CONAB, preço de {r['produto'].lower()} ({r['classificao_produto'].lower()}), município {mun}, {_MES[int(r['mes']) - 1]} de {r['ano']}, "
             f"nível {r['dsc_nivel_comercializacao'].lower()}: R$ {r['valor_produto_kg']} por kg. {AV_PRECO}")
        out.append(_fato(t, "conab_precos_municipio", "dado_minerado", "media", f"CONAB: preços em {mun}", url["conab_precos_mensal_municipio_ce.csv"], data,
                         cids=_detectar_culturas(r["produto"]), municipio=mun, aviso=AV_PRECO))
    for r in _ler_csv(EXTERNOS["conab_custos"]):
        mun = r["municipio"].split("-")[0].strip().title()
        t = (f"CONAB, custo de produção de {r['produto'].lower()} ({r['empreendimento'].lower()}), {mun}/{r['uf']}, {_MES[int(r['mes']) - 1]} de {r['ano']}: "
             f"custo variável R$ {r['vlr_custo_variavel_ha']} por hectare, custo fixo R$ {r['vlr_custo_fixo_ha']} por hectare, unidade de venda {r['unidade_comercializacao']}. {AV_CUSTO}")
        out.append(_fato(t, "conab_custos", "dado_minerado", "media", f"CONAB: custo de {r['produto'].lower()}", url["conab_custos_producao_nordeste.csv"], data,
                         cids=_detectar_culturas(r["produto"]), municipio=mun if r["uf"] == "CE" else None, aviso=AV_CUSTO))
    # SIGEF agregado por especie e por municipio
    import collections
    linhas = _ler_csv(EXTERNOS["sigef"])
    por_esp = collections.defaultdict(list)
    por_mun = collections.defaultdict(lambda: collections.defaultdict(int))
    for r in linhas:
        esp = re.sub(r"\s+(L\.|var\..*|subsp\..*)$", "", r["Especie"]).strip()
        por_esp[esp].append(r)
        por_mun[r["Municipio"]][esp] += 1
    for esp, rs in sorted(por_esp.items()):
        meses = collections.Counter()
        for r in rs:
            m = re.match(r"\d{2}/(\d{2})/\d{4}", r["Data do Plantio"])
            if m:
                meses[int(m.group(1))] += 1
        muns = collections.Counter(r["Municipio"] for r in rs).most_common(8)
        safras = sorted({r["Safra"] for r in rs})
        area = sum(_num(r["Area"]) or 0 for r in rs)
        t = (f"SIGEF/MAPA, campos de produção de sementes no Ceará, espécie {esp}: {len(rs)} campos inscritos nas safras {safras[0]} a {safras[-1]}, "
             f"área somada de {area:.0f} ha. Municípios com mais campos: {', '.join(f'{m} ({n})' for m, n in muns)}. "
             + (f"Meses de plantio mais frequentes: {', '.join(f'{_MES[m - 1]} ({n})' for m, n in meses.most_common(3))}. " if meses else "") + AV_SIGEF)
        out.append(_fato(t, "sigef", "dado_minerado", "media", f"SIGEF: sementes de {esp}", url["sigef_campos_sementes_ce.csv"], data,
                         cids=_detectar_culturas(esp), aviso=AV_SIGEF))
    for mun, d in sorted(por_mun.items()):
        top = sorted(d.items(), key=lambda x: -x[1])[:8]
        t = (f"SIGEF/MAPA, campos de produção de sementes em {mun}/CE: " + "; ".join(f"{e} ({n})" for e, n in top) + f". {AV_SIGEF}")
        out.append(_fato(t, "sigef", "dado_minerado", "media", f"SIGEF: sementes em {mun}", url["sigef_campos_sementes_ce.csv"], data, municipio=mun,
                         cids=_detectar_culturas(" ".join(e for e, _ in top)), aviso=AV_SIGEF))
    return out


# ---------------------------------------------------------------- 4) dados minerados agregados (sem lat/lon)
def _dec_data(k: int) -> str:
    m, p = (k - 1) // 3, (k - 1) % 3
    return f"{(1, 11, 21)[p]} {_MES[m][:3]}"


def _faixas(decs: list[int]) -> str:
    if not decs:
        return "nenhum decêndio"
    grupos, ini, ant = [], decs[0], decs[0]
    for d in decs[1:] + [None]:
        if d is None or d != ant + 1:
            grupos.append((ini, ant)); ini = d
        ant = d if d is not None else ant
    fim = lambda k: {1: "10", 2: "20", 0: "30"}[(k - 1) % 3 + 1 if (k - 1) % 3 < 2 else 0] + " " + _MES[(k - 1) // 3][:3]
    return "; ".join(f"de {_dec_data(a)} a {fim(b)}" for a, b in grupos)


def fatos_zarc(data: str) -> list[dict]:
    import pandas as pd
    z = pd.read_parquet(RAIZ / MINERADOS["zarc"])
    z = z[z["Cod_Outros_Manejos"].astype(str) == "1"].copy()          # sequeiro
    pref = ["safra_2026_2027", "safra_2025_2026", "safra_2024_2025", "perene_olericola_sem_safra"]
    z["_p"] = z["recurso"].map({k: i for i, k in enumerate(pref)}).fillna(9)
    dec = [f"dec{i}" for i in range(1, 37)]
    out = []
    for (mun, cult), g in z.groupby(["municipio", "Nome_cultura"], sort=True):
        g = g[g["_p"] == g["_p"].min()]
        X = g[dec].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy()
        X = np.where(X > 0, X, 99)
        mn = X.min(axis=0)
        j = {r: [i + 1 for i in range(36) if mn[i] <= r] for r in (20, 30, 40)}
        if not j[40]:
            continue
        saf = g.iloc[0]["recurso"].replace("safra_", "safra ").replace("_", "/").replace("perene/olericola/sem/safra", "perene/olerícola sem safra")
        nome = re.sub(r"\s+", " ", str(cult)).strip()
        t = (f"ZARC (MAPA), {mun}/CE, {nome}, sequeiro, {saf}: plantio indicado com risco de até 20% em {_faixas(j[20])}; "
             f"com risco de até 30% em {_faixas(j[30])}; com risco de até 40% em {_faixas(j[40])}. "
             f"Vale se algum solo ou ciclo de cultivar indicar o decêndio; o resultado depende do solo e do ciclo da cultivar escolhida.")
        out.append(_fato(t, "zarc", "dado_minerado", "media", f"ZARC: {nome} em {mun}", "https://dados.agricultura.gov.br", data,
                         cids=_detectar_culturas(nome), municipio=str(mun),
                         aviso="Zoneamento oficial por município: indica risco climático de perda, não garante produção; confira com técnico local."))
    return out


def fatos_pam(data: str) -> list[dict]:
    import pandas as pd
    p = pd.read_parquet(RAIZ / MINERADOS["pam"])
    p = p[p["valor"].notna()]
    ult = int(p["ano"].max())
    out = []
    for (mun, prod), g in p[p["ano"] == ult].groupby(["municipio", "produto"], sort=True):
        d = {r.variavel: r.valor for r in g.itertuples()}
        if not (d.get("area_colhida_ha") or d.get("quantidade_produzida")):
            continue
        nome = prod.replace("*", "")
        mun_s = re.sub(r"\s*-\s*CE$", "", mun)
        partes = []
        if "area_colhida_ha" in d: partes.append(f"área colhida {d['area_colhida_ha']:.0f} ha")
        if "quantidade_produzida" in d: partes.append(f"produção {d['quantidade_produzida']:.0f} t")
        if "rendimento_medio" in d: partes.append(f"rendimento médio {d['rendimento_medio']:.0f} kg/ha")
        if "valor_producao_mil_reais" in d: partes.append(f"valor da produção R$ {d['valor_producao_mil_reais']:.0f} mil")
        t = f"IBGE/PAM {ult}, município {mun_s}/CE, {nome}: " + ", ".join(partes) + "."
        out.append(_fato(t, "pam", "dado_minerado", "media", f"PAM: {nome} em {mun_s}", "https://sidra.ibge.gov.br", data,
                         cids=_detectar_culturas(nome), municipio=mun_s,
                         aviso="Média do município no ano; não vale para um talhão. Rendimento de um ano não é tendência."))
    return out


def _nomes_pontos() -> dict:
    import csv
    with open(RAIZ / MINERADOS["pontos"], encoding="utf-8", newline="") as f:
        return {r["ponto_id"]: re.sub(r"\s*\(\w\w\)\s*$", "", r["nome"]) for r in csv.DictReader(f)}


def _uf_de(ponto_id: str) -> str:
    return ponto_id.rsplit("_", 1)[-1].upper()


def fatos_solo_municipio(data: str) -> list[dict]:
    import pandas as pd
    s = pd.read_parquet(RAIZ / MINERADOS["solo"])
    nomes = _nomes_pontos()
    out = []
    for r in s.itertuples(index=False):
        d = r._asdict() if hasattr(r, "_asdict") else {}
        row = dict(zip(s.columns, r))
        mun = nomes.get(row["ponto_id"])
        if not mun:
            continue

        def m(p): return f"{row[p + '_0-5cm']:.0f}% (0-5 cm), {row[p + '_15-30cm']:.0f}% (15-30 cm)"
        t = (f"Solo estimado (SoilGrids) em {mun}/{_uf_de(row['ponto_id'])}: areia {m('sand')}; argila {m('clay')}; silte {m('silt')}; "
             f"carbono orgânico {row['soc_0-5cm']:.1f} g/kg (0-5 cm); pH em água {row['phh2o_0-5cm']:.1f} (0-5 cm). "
             f"Fração de pixels válidos da janela: {row['fracao_pixels_validos']:.0%}.")
        out.append(_fato(t, "solo", "dado_minerado", "media", f"Solo estimado em {mun}", "https://soilgrids.org", data, municipio=mun,
                         aviso="Estimativa de satélite/modelo em células de 250 m; não substitui análise de solo do talhão."))
    return out


def fatos_diagnostico(data: str) -> list[dict]:
    d = json.loads((RAIZ / MINERADOS["diagnostico"]).read_text(encoding="utf-8"))
    nomes = _nomes_pontos()
    out = []
    av = ("Dado de satélite/reanálise em células grandes (clima ~50 km, vegetação 250 m, umidade ~9 km): descreve o passado e a região, "
          "não prevê chuva nem colheita nem enxerga o talhão.")
    for e in d:
        mun = nomes.get(e["ponto_id"])
        if not mun:
            continue
        uf = _uf_de(e["ponto_id"])
        per = f"{e['periodo'][0][:4]} a {e['periodo'][1][:4]}"
        sn = e.get("solo_nu") or {}
        if sn.get("meses_tipicos"):
            ms = ", ".join(_MES[m - 1] for m in sn["meses_tipicos"])
            t = (f"Diagnóstico de {mun}/{uf} ({per}): a terra costuma ficar com pouca cobertura vegetal (solo nu) em {ms}; "
                 f"critério: vegetação abaixo do percentil 20 do próprio local em pelo menos 50% dos anos. Limiar relativo ao local, não valor agronômico absoluto.")
            out.append(_fato(t, "diagnostico", "dado_minerado", "media", f"Solo nu em {mun}", "", data, municipio=mun, aviso=av))
        v = e.get("veranicos") or {}
        dist = v.get("distribuicao")
        if dist:
            t = (f"Diagnóstico de {mun}/{uf} ({per}): veranico (maior sequência de dias com chuva abaixo de 1 mm dentro da estação chuvosa) "
                 f"com mediana de {dist['mediana']:.0f} dias, percentil 90 de {dist['p90']:.0f} dias e máximo de {dist['max']} dias em {v['n_estacoes']} estações.")
            out.append(_fato(t, "diagnostico", "dado_minerado", "media", f"Veranicos em {mun}", "", data, municipio=mun, aviso=av))
        cl = (e.get("climatologia_quinzenal") or {}).get("chuva_mm_quinzena")
        if cl:
            mes = [0.0] * 12
            for q, x in cl.items():
                mes[(int(q) - 1) // 2] += x["media"]
            top = sorted(range(12), key=lambda i: -mes[i])[:3]
            tr = (e.get("tendencias") or {}).get("chuva_anual_mm") or {}
            tt = (e.get("tendencias") or {}).get("temperatura_media_c") or {}
            t = (f"Diagnóstico de {mun}/{uf} ({per}): meses mais chuvosos em média: " + ", ".join(f"{_MES[i]} ({mes[i]:.0f} mm)" for i in top)
                 + f"; chuva média anual cerca de {sum(mes):.0f} mm. Tendência da chuva anual: "
                 + (f"{tr.get('mann_kendall')} (p = {tr['p_valor']:.2f})" if tr.get("p_valor") is not None else "não calculada")
                 + "; temperatura média: " + (f"{tt.get('mann_kendall')} (p = {tt['p_valor']:.2f})." if tt.get("p_valor") is not None else "não calculada."))
            out.append(_fato(t, "diagnostico", "dado_minerado", "media", f"Chuva em {mun}", "", data, municipio=mun, aviso=av))
    return out


# ---------------------------------------------------------------- 5) lacunas declaradas (ensina a dizer "nao tenho esse dado")
def _frases_limpas(cel: str) -> str:
    cel = re.sub(r"`[^`]*`", "", _limpar_md(cel))
    fr = re.split(r"(?<=[.!?])\s+", cel)
    return " ".join(f for f in fr if f.strip() and not bloco_proibido(f)).strip()


def fatos_lacunas(data: str) -> list[dict]:
    """Uma linha das tabelas de docs/31 = um fato 'lacuna' (o que falta + o que existe no lugar + onde esta registrado).
    A secao 'Como o assistente deve usar este documento' (instrucoes) NAO e conteudo citavel e e ignorada."""
    txt = (RAIZ / LACUNAS_DOC).read_text(encoding="utf-8")
    out, sec = [], ""
    for l in txt.splitlines():
        if l.startswith("## "):
            sec = re.sub(r"\s*\(conferido[^)]*\)", "", re.sub(r"^##\s*\d+[a-z]?\.\s*", "", l)).strip()
            continue
        if re.match(r"^##?\s*(8\.|Como o assistente)", l) or "Como o assistente deve usar" in sec:
            break
        if not l.startswith("|") or re.match(r"^\|[\s:|-]+\|?$", l) or "O que falta" in l:
            continue
        cel = [c.strip() for c in l.strip().strip("|").split("|")]
        falta = _frases_limpas(cel[0]).rstrip(".:")
        if not falta:
            continue
        existe = _frases_limpas(cel[1]) if len(cel) >= 3 else ""
        t = f"LACUNA, {sec.lower()}: não temos esse dado: {falta}." + (f" O que existe no lugar: {existe}" if existe else "")
        a = "Lacuna declarada: diga que não tem o dado, ofereça só o que existe no lugar e sugira conversar com o técnico local."
        out.append(_fato(t, "lacunas", "lacuna", "alta", f"Lacuna de dados: {sec}", "", data, cids=_detectar_culturas(t), aviso=a))
    return out


# ---------------------------------------------------------------- construcao (idempotente, por sha256 de cada fonte)
def _fontes() -> dict[str, Path]:
    f = {c: RAIZ / c for c in DOCS_BRANCOS}
    for d in (TABELAS, EXTERNOS, MINERADOS):
        f.update({v: RAIZ / v for v in d.values()})
    f[LACUNAS_DOC] = RAIZ / LACUNAS_DOC
    return f


def _hash_texto(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def gerar_registros(contadores: dict | None = None) -> list[dict]:
    """Todos os trechos/fatos (sem embeddings), na ordem deterministica, ja filtrados e validados."""
    c = contadores if contadores is not None else {}
    reg: list[dict] = []
    for cam, (rot, tipo, conf) in DOCS_BRANCOS.items():
        p = RAIZ / cam
        data = datetime.fromtimestamp(p.stat().st_mtime).date().isoformat()
        reg += trechos_de_markdown(cam, p.read_text(encoding="utf-8"), rot, tipo, conf, data, c)
    hoje = date.today().isoformat()
    for fn in (fatos_tabela_culturas, fatos_fao, fatos_solo, fatos_ler, fatos_matriz, fatos_externos,
               fatos_zarc, fatos_pam, fatos_solo_municipio, fatos_diagnostico, fatos_lacunas):
        reg += fn(hoje)
    # varredura final: nenhum registro com segredo, termo proibido de projeto ou coordenada
    bons = []
    for r in reg:
        if bloco_proibido(r["texto"]):
            c["registros_bloqueados_na_varredura"] = c.get("registros_bloqueados_na_varredura", 0) + 1
            continue
        bons.append(r)
    for i, r in enumerate(bons, 1):
        r["id"] = f"agr{i:05d}"
        r["hash"] = _hash_texto(r["texto"])
    return bons


def _embed(textos: list[str], lote: int = 16) -> np.ndarray:
    m = _carregar_modelo()
    try:
        import torch
        torch.set_num_threads(2)
    except Exception:
        pass
    partes = []
    for i in range(0, len(textos), lote):
        partes.append(m.encode(["passage: " + t for t in textos[i:i + lote]], normalize_embeddings=True,
                               batch_size=lote, show_progress_bar=False).astype(np.float32))
    return np.vstack(partes) if partes else np.zeros((0, 384), np.float32)


def construir(dir_indice: Path = DIR_INDICE, manifesto: Path = MANIFESTO, forcar: bool = False,
              com_embeddings: bool = True, registros: list[dict] | None = None, verbose: bool = True) -> dict:
    """Constroi/atualiza o indice. Reconstroi so o que mudou (sha256 das fontes; embeddings reaproveitados por hash do texto)."""
    dir_indice = Path(dir_indice)
    dir_indice.mkdir(parents=True, exist_ok=True)
    if registros is None:
        shas = {k: _sha256(p) for k, p in _fontes().items()}
        antigo = json.loads(manifesto.read_text(encoding="utf-8")) if manifesto.exists() else {}
        pronto = (dir_indice / "trechos.jsonl").exists() and (not com_embeddings or (dir_indice / "embeddings.npy").exists())
        if not forcar and pronto and antigo.get("fontes", {}).keys() == shas.keys() and \
                all(antigo["fontes"][k]["sha256"] == v for k, v in shas.items()):
            return {"reconstruido": False, "motivo": "nenhuma fonte mudou", "n_trechos": antigo.get("n_trechos")}
        mudou = [k for k, v in shas.items() if antigo.get("fontes", {}).get(k, {}).get("sha256") != v]
        cont: dict = {}
        registros = gerar_registros(cont)
    else:
        shas, antigo, mudou, cont = {}, {}, [], {}
    # embeddings: reaproveita por hash de texto
    emb_antigo: dict[str, np.ndarray] = {}
    ta, ea = dir_indice / "trechos.jsonl", dir_indice / "embeddings.npy"
    if com_embeddings and ta.exists() and ea.exists() and not forcar:
        old = [json.loads(l) for l in ta.read_text(encoding="utf-8").splitlines() if l]
        E = np.load(ea)
        if len(old) == E.shape[0]:
            emb_antigo = {o["hash"]: E[i] for i, o in enumerate(old)}
    emb = None
    if com_embeddings:
        novos = [r["texto"] for r in registros if r["hash"] not in emb_antigo]
        if verbose:
            print(f"embeddings novos: {len(novos)} de {len(registros)}", file=sys.stderr)
        calc = _embed(novos) if novos else np.zeros((0, 384), np.float32)
        it = iter(calc)
        emb = np.vstack([emb_antigo[r["hash"]] if r["hash"] in emb_antigo else next(it) for r in registros]).astype(np.float32)
    ta.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n", encoding="utf-8")
    if emb is not None:
        np.save(ea, emb)
    contagem: dict = {}
    for r in registros:
        contagem[r["tipo"]] = contagem.get(r["tipo"], 0) + 1
    man = {"construido_em": datetime.now().isoformat(timespec="seconds"), "modelo_embeddings": MODELO_EMB if com_embeddings else None,
           "n_trechos": len(registros), "por_tipo": contagem, "descartes": cont,
           "lista_branca": sorted(_fontes_rel()),
           "fontes": {k: {"sha256": v, "data": datetime.fromtimestamp((RAIZ / k).stat().st_mtime).date().isoformat()} for k, v in shas.items()},
           "reconstruido_por_mudanca_em": mudou}
    if shas:
        manifesto.parent.mkdir(parents=True, exist_ok=True)
        manifesto.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    (dir_indice / "manifesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    man["reconstruido"] = True
    return man


def _fontes_rel() -> list[str]:
    return list(_fontes().keys())


# ---------------------------------------------------------------- busca hibrida
class IndiceAgronomia:
    def __init__(self, dir_indice: Path = DIR_INDICE, usar_embeddings: bool = True):
        self.dir = Path(dir_indice)
        self.trechos = [json.loads(l) for l in (self.dir / "trechos.jsonl").read_text(encoding="utf-8").splitlines() if l]
        self.tok = [tokenizar(t["texto"]) for t in self.trechos]
        self.sets = [set(t) for t in self.tok]
        self.bm25 = BM25(self.tok)
        self.emb = None
        ea = self.dir / "embeddings.npy"
        if usar_embeddings and ea.exists():
            e = np.load(ea)
            if e.shape[0] == len(self.trechos):
                self.emb = e
        self.modo = "hibrido" if self.emb is not None else "bm25"
        self.mun_norm = [_sem_acento((t.get("municipio") or "").lower()) for t in self.trechos]

    def _cos(self, pergunta: str):
        if self.emb is None:
            return None
        try:
            q = _carregar_modelo().encode(["query: " + pergunta], normalize_embeddings=True)[0]
        except Exception:
            return None
        return self.emb @ q

    def buscar(self, pergunta: str, k: int = 5, municipio: str | None = None, cultura: str | None = None,
               so_agricultor: bool = True, lim_cobertura: float = LIM_COBERTURA, lim_cos: float = LIM_COS) -> dict:
        q = tokenizar(pergunta)
        if not q:
            return _sem_ev()
        qset = set(q)
        mun = _sem_acento(municipio.lower()) if municipio else None
        ok = np.ones(len(self.trechos), bool)
        for i, t in enumerate(self.trechos):
            if so_agricultor and not t.get("pode_citar_ao_agricultor"):
                ok[i] = False
            elif mun and self.mun_norm[i] and self.mun_norm[i] != mun:
                ok[i] = False                      # fato de OUTRO municipio nunca responde por este
            elif cultura and t.get("culturas") and cultura not in t["culturas"]:
                ok[i] = False
        bm = np.where(ok, self.bm25.scores(q), 0.0)
        cos = self._cos(pergunta)
        if cos is not None:
            cos = np.where(ok, cos, -1.0)
        ranks = []
        for sc in (bm, cos):
            if sc is None:
                continue
            ranks.append({i: r for r, i in enumerate(np.argsort(-sc)[:60]) if ok[i] and sc[i] > (0 if sc is bm else -1)})
        cand = set().union(*[set(r) for r in ranks]) if ranks else set()
        pont = {}
        for i in cand:
            cob = len(qset & self.sets[i]) / len(qset)
            passa = (cob >= lim_cobertura and len(qset & self.sets[i]) >= min(2, len(qset))) or (cos is not None and cos[i] >= lim_cos)
            if passa:
                pont[i] = sum(1.0 / (RRF_K + r[i]) for r in ranks if i in r)
        if not pont:
            return _sem_ev()
        top = sorted(pont, key=lambda i: -pont[i])[:k]
        return {"sem_evidencia": False, "mensagem": "", "modo": self.modo, "trechos": [self._saida(n, i, pont[i]) for n, i in enumerate(top, 1)]}

    def _saida(self, n: int, i: int, score: float) -> dict:
        t = self.trechos[i]
        return {"n": n, "id": t["id"], "arquivo": t["arquivo"], "pagina": t["secao"], "secao": t["secao"], "texto": t["texto"],
                "fonte": t["url"] or t["fonte"], "tipo": t["tipo"], "data": t["data"], "confianca": t["confianca"],
                "aviso": t["aviso"], "municipio": t.get("municipio"), "culturas": t.get("culturas", []),
                "pode_citar_ao_agricultor": t["pode_citar_ao_agricultor"], "score": round(float(score), 5)}


def _sem_ev() -> dict:
    return {"sem_evidencia": True, "mensagem": MSG_SEM_EVIDENCIA, "trechos": []}


_cache: dict[str, IndiceAgronomia] = {}


def buscar_agronomia(pergunta: str, k: int = 5, municipio: str | None = None, cultura: str | None = None,
                     dir_indice: Path = DIR_INDICE, **kw) -> dict:
    """Busca no conhecimento agronomico. Devolve {"sem_evidencia","mensagem","trechos":[{n,id,arquivo,pagina,texto,fonte,tipo,
    data,confianca,aviso,municipio,culturas,pode_citar_ao_agricultor,score}]}; mesmo formato de `src.rag.busca.buscar`."""
    ch = str(dir_indice)
    if ch not in _cache:
        _cache[ch] = IndiceAgronomia(Path(dir_indice))
    return _cache[ch].buscar(pergunta, k=k, municipio=municipio, cultura=cultura, **kw)


buscar_projeto = buscar_agronomia  # alias do nome antigo

if __name__ == "__main__":
    r = construir(forcar="--forcar" in sys.argv, com_embeddings="--sem-embeddings" not in sys.argv)
    print(json.dumps({k: v for k, v in r.items() if k not in ("fontes", "lista_branca")}, ensure_ascii=False, indent=1))
