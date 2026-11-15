"""Back-end offline do SULCO (FastAPI). Só lê arquivos locais. Lacuna = campo explícito, nunca valor inventado."""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.llm.ambiente import carregar_env

carregar_env()  # .env da raiz (só SULCO_*, DEEPSEEK_*, API_*, APP_*); antes de LimiteTaxa.do_ambiente()

from src.api.limite_taxa import LimiteTaxa, cabecalhos  # noqa: E402
from src.app import mvp as M   # lógica do app (sem Streamlit): reutilizada por import, não copiada
from src.app import perfil as PF   # perfil do agricultor (schema, regras, texto sem identificador)
from src.culturas import ciclo as ciclo_mod
from src.culturas import zarc as zarc_mod
from src.culturas.motor import gerar_cenarios
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar as carregar_tabela
from src.modelos import previsao as _prev

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "data/processed"
AVISO = "Cenário a avaliar com técnico local. Não decide e não promete que a rotação rende mais."

# Prioridades: ORDEM ordinal entre critérios (faixas), nunca pesos exatos. SUPOSIÇÃO a validar com técnico.
# Definição única em src/app/mvp.py (mesma do app): a API não mantém cópia.
PRIORIDADES = M.PRIORIDADES

LATENCIAS: dict[str, list[float]] = {}
AQUECIMENTO: dict[str, str] = {}   # etapa -> "pendente" | "ok" | "erro: ..." (preenchido pela thread de pré-aquecimento)
PERGUNTA_AQUECIMENTO = "feijao caupi palha"   # consulta real: passa por embeddings E reranker


def _aquecer() -> None:
    """Carrega RAG (embeddings + reranker) e o modelo de previsão em segundo plano, para a 1ª chamada real não pagar o custo."""
    for etapa, fn in (("rag", lambda: _buscar_rag(PERGUNTA_AQUECIMENTO, 1)), ("previsao", contexto_previsao)):
        t0 = time.perf_counter()
        try:
            fn()
            AQUECIMENTO[etapa] = f"ok ({time.perf_counter() - t0:.1f} s)"
        except Exception as e:
            AQUECIMENTO[etapa] = f"erro: {e.__class__.__name__}"


@asynccontextmanager
async def _vida(_app):
    # SULCO_PREAQUECER=0 desliga. Só roda quando o servidor sobe de fato (TestClient sem `with` não dispara).
    if os.environ.get("SULCO_PREAQUECER", "1") != "0":
        AQUECIMENTO.update(rag="pendente", previsao="pendente")
        threading.Thread(target=_aquecer, daemon=True, name="aquecimento").start()
    yield


app = FastAPI(title="SULCO API", version="0.2.0", lifespan=_vida,
              description="Back-end offline do SULCO. Apoia a conversa com o técnico; não decide.")

from src.api.rota_calendario import router as _rota_calendario  # noqa: E402
from src.api.rota_conversa import router as _rota_conversa  # noqa: E402

app.include_router(_rota_conversa)       # POST /conversa (conversa consultiva)
app.include_router(_rota_calendario)     # POST /calendario (calendário de plantio do agricultor)


from src.api.cabecalhos_seguranca import aplicar_cabecalhos  # noqa: E402


@app.middleware("http")
async def cabecalhos_de_seguranca(request, call_next):
    return aplicar_cabecalhos(await call_next(request), request.url.path)


@app.middleware("http")
async def medir(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    rota = request.scope.get("route")
    LATENCIAS.setdefault(getattr(rota, "path", request.url.path), []).append(ms)
    resp.headers["X-Latencia-ms"] = f"{ms:.1f}"
    return resp


LIMITE = LimiteTaxa.do_ambiente()   # SULCO_RATE_LIMIT / SULCO_RATE_GERAL / SULCO_RATE_PESADO / SULCO_CONFIAR_PROXY (ver limite_taxa.py)


@app.middleware("http")
async def limitar_taxa(request: Request, call_next):
    """Janela deslizante por cliente. 429 + Retry-After ao estourar; /saude é isenta. O contador é do processo (ver limite_taxa.py)."""
    grupo = LIMITE.grupo(request.url.path) if LIMITE.ligado else None
    if grupo is None:
        return await call_next(request)
    ip = request.client.host if request.client else None
    r = LIMITE.verificar(LIMITE.cliente(ip, request.headers.get("x-forwarded-for")), grupo)
    if not r["ok"]:
        return JSONResponse(status_code=429, headers=cabecalhos(r),
                            content={"detail": f"Muitas requisições ({r['limite']} por janela, grupo '{grupo}'). Tente de novo em {r['retry_after']} s.",
                                     "lacuna": "limite de taxa: a resposta não foi calculada", "grupo": grupo})
    resp = await call_next(request)
    for k, v in cabecalhos(r).items():
        resp.headers[k] = v
    return resp



# ------------------------------------------------------------------ dados (cache em memória)
@lru_cache(maxsize=1)
def pontos() -> pd.DataFrame:
    p = pd.read_csv(DADOS / "pontos.csv")
    return p.set_index("ponto_id", drop=False)


@lru_cache(maxsize=1)
def diagnosticos() -> dict:
    arq = DADOS / "diagnostico/diagnostico.json"
    if not arq.is_file():
        return {}
    return {str(r["ponto_id"]): r for r in json.loads(arq.read_text(encoding="utf-8"))}


@lru_cache(maxsize=1)
def tabela() -> dict:
    return carregar_tabela()


@lru_cache(maxsize=1)
def clima_df() -> pd.DataFrame:
    return pd.read_parquet(DADOS / "clima_diario.parquet", columns=["ponto_id", "data", "chuva_mm", "tmax_c", "tmin_c"])


@lru_cache(maxsize=64)
def clima_ponto(pid: str):
    return ciclo_mod.ClimaPonto.de_dataframe(clima_df(), pid)


@lru_cache(maxsize=1)
def evidencias_cache() -> dict | None:
    arq = DADOS / "mvp/evidencias_rag.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.is_file() else None


def exigir_ponto(pid: str):
    if pid not in pontos().index:
        raise HTTPException(404, f"ponto '{pid}' não existe em pontos.csv")
    return pontos().loc[pid]


def _limpo(x):
    """JSON-seguro: numpy -> python, NaN/inf -> None (lacuna), tuplas -> listas. Nunca preenche valor."""
    if isinstance(x, dict):
        return {str(k): _limpo(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_limpo(v) for v in x]
    if isinstance(x, np.ndarray):
        return _limpo(x.tolist())
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else float(x)
    return x


# ------------------------------------------------------------------ schemas
class Municipio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    nome: str = Field(description="Derivado do ponto_id, sem acentos (pontos.csv não guarda o nome oficial).")
    lat: float
    lon: float
    celula_power: str
    ibge: int | None = Field(None, description="Código IBGE; null = LACUNA (ex.: sobral_ce, coordenada fora do polígono).")


class Saude(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    arquivos: dict[str, bool]
    n_pontos: int | None
    latencias_ms: dict[str, dict[str, float]]
    aquecimento: dict[str, str] = Field(description="Pré-aquecimento em segundo plano (rag, previsao); vazio se desligado.")
    cache_modelo_previsao: bool


class RegrasIn(BaseModel):
    """Regras DURAS do agricultor (src/culturas/regras_duras.py). Todas opcionais; vazio = sem regra. Cultura desconhecida = 422."""
    model_config = ConfigDict(extra="forbid")
    proibidas: list[str] = Field(default_factory=list, max_length=60, description="Culturas que NÃO quer plantar (safras 2 em diante).")
    obrigatorias: list[str] = Field(default_factory=list, max_length=60, description="Culturas que PRECISA incluir (a atual conta).")
    max_seguidas_cultura: int | None = Field(None, ge=1, le=PF.MAX_SEGUIDAS_MAX, description="Máximo de safras seguidas da mesma cultura; null = sem regra.")
    aceita_pousio: bool = Field(False, description="Só registra: pousio NÃO é modelado como safra.")


def _regras_duras(r: RegrasIn | None):
    """RegrasDuras (ou None) a partir do corpo da requisição; 422 se cita cultura fora da tabela ou se se contradiz."""
    if r is None:
        return None
    try:
        return PF.regras_duras({"regras": r.model_dump()}, tabela())
    except ValueError as e:
        raise HTTPException(422, f"regras inválidas: {e}")


class CenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    cultura_atual: str
    prioridade: Literal["sem", "agua", "solo", "renda"] = Field(
        description="Faixa ordinal (SUPOSIÇÃO). 'renda' = lacuna, não altera ranking.")
    ciclo_modo: Literal["min", "medio", "max"] | None = None
    chuva_modo: Literal["ciclo", "anual"] | None = None
    risco_max: float | None = Field(None, ge=0, lt=1)
    n_sorteios: int | None = Field(None, ge=100, le=20000)
    com_evidencias: bool = True
    usar_zarc: bool = Field(M.ZARC_PADRAO, description="Restringe o início do plantio ao ZARC (só municípios do CE com ZARC). "
                            "Padrão = o do app.")
    regras: RegrasIn | None = Field(None, description="Regras duras do agricultor: alternativa que viola nunca aparece; a cultura atual fica sempre.")


class CenarioOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    cultura_atual: str
    prioridade: str
    regra_prioridade: str
    cenarios: list[dict]   # contrato docs/01 seção 7 (+ janela_plantio, suposicoes, viabilidade do motor)
    lacunas_gerais: list[str]
    regras_duras: dict | None = Field(None, description="null = sem regras. Senão: regras ativas, quantas alternativas viáveis foram descartadas e por quê, "
                                      "se foram todas, e o que não é modelado (pousio).")
    aviso: str
    segundos: float


# ------------------------------------------------------------------ endpoints
@app.get("/saude", response_model=Saude)
def saude():
    arqs = {"pontos.csv": DADOS / "pontos.csv", "clima_diario.parquet": DADOS / "clima_diario.parquet",
            "diagnostico.json": DADOS / "diagnostico/diagnostico.json",
            "metricas.json": DADOS / "modelos/metricas.json", "evidencias_rag.json": DADOS / "mvp/evidencias_rag.json",
            "indice_rag": RAIZ / "indice"}
    ok = {k: v.exists() for k, v in arqs.items()}
    lat = {r: {"n": len(v), "media": round(sum(v) / len(v), 1), "max": round(max(v), 1)} for r, v in LATENCIAS.items()}
    return Saude(status="ok" if all(ok.values()) else "parcial", arquivos=ok,
                 n_pontos=len(pontos()) if ok["pontos.csv"] else None, latencias_ms=lat,
                 aquecimento=dict(AQUECIMENTO), cache_modelo_previsao=_prev.ARQ_CACHE.is_file())


@app.get("/municipios", response_model=list[Municipio])
def municipios():
    p = pontos()
    return [Municipio(ponto_id=r.ponto_id, nome=M.nome_do_ponto(r.ponto_id), lat=r.lat, lon=r.lon,
                      celula_power=str(r.celula_power), ibge=None if pd.isna(r.ibge) else int(r.ibge)) for r in p.itertuples()]


@app.get("/diagnostico/{ponto_id}")
def diagnostico(ponto_id: str):
    exigir_ponto(ponto_id)
    r = diagnosticos().get(ponto_id)
    if r is None:
        raise HTTPException(404, "LACUNA: sem diagnóstico pré-calculado para este ponto")
    nu, ver = r.get("solo_nu"), r.get("veranicos")
    return {
        "ponto_id": ponto_id, "celula_power": r.get("celula_power"), "periodo": r.get("periodo"),
        "solo_nu": nu if nu else {"lacuna": "solo nu não calculado"},
        "estresse": r.get("anomalias_resumo", {}).get("ndvi") or {"lacuna": "sem resumo de anomalias de NDVI"},
        "estacao_chuvosa": ({"quinzenas": ver.get("quinzenas_estacao_chuvosa")} if ver else {"lacuna": "sem estação chuvosa"}),
        "veranicos": ver if ver else {"lacuna": "veranicos não calculados"},
        "tendencia": r.get("tendencias") or {"lacuna": "sem tendências"},
        "sazonalidade_ndvi": {k: v for k, v in (r.get("sazonalidade_ndvi") or {}).items() if k != "perfil_sazonal_por_slot"}
        or {"lacuna": "sem sazonalidade"},
        "confianca": r.get("confianca"), "confianca_nota": r.get("confianca_nota"),
        "n_anos_validos": r.get("n_anos_validos"),
        "lacunas": r.get("lacunas") or [], "limites": r.get("limites") or [],
        "aviso": AVISO,
    }


@app.post("/cenarios", response_model=CenarioOut)
def cenarios(req: CenarioIn):
    t0 = time.perf_counter()
    linha = exigir_ponto(req.ponto_id)
    tab = tabela()
    if req.cultura_atual not in tab:
        raise HTTPException(422, f"cultura '{req.cultura_atual}' fora da tabela: {sorted(tab)}")
    pr = PRIORIDADES[req.prioridade]
    rd = _regras_duras(req.regras)
    rm = PF.regras_para_motor(rd)
    kw = {k: v for k, v in (("ciclo_modo", req.ciclo_modo), ("chuva_modo", req.chuva_modo), ("risco_max", req.risco_max),
                            ("n_sorteios", req.n_sorteios)) if v is not None}
    try:
        p = Parametros(ordem_pesos=pr["ordem"], bloco_ranking=pr["bloco"], usar_zarc=req.usar_zarc, **kw)
    except ValueError as e:
        raise HTTPException(422, str(e))
    cens = gerar_cenarios({"local": req.ponto_id}, req.cultura_atual, tab, clima=clima_ponto(req.ponto_id), params=p, regras=rm)
    gerais = []
    info_regras = None
    if rd is not None:
        from src.culturas.motor import avaliar_local
        desc = M.descartes_caminhos(avaliar_local(tab, clima_ponto(req.ponto_id), p), tab, req.cultura_atual, rm) if rm is not None else {
            "n_viaveis": None, "n_descartadas": 0, "n_restantes": None, "todas_descartadas": False, "descartadas_por_motivo": {}, "descartadas": []}
        info_regras = _limpo({"regras": rd.para_dict(), **desc, "nao_modelado": rd.nao_modelado()})
    ev = evidencias_cache() if req.com_evidencias else None
    for c in cens:
        alvo = c["rotacao"][1]
        c["atual"] = alvo == req.cultura_atual
        c["local"] = {"ponto_id": req.ponto_id, "lat": float(linha.lat), "lon": float(linha.lon),
                      "celula_power": str(linha.celula_power)}
        c["prioridade"] = req.prioridade
        if ev is not None and alvo in ev:
            from src.pipeline.gerar_cenarios import anexar_evidencias
            anexar_evidencias(c, ev[alvo])
        else:
            c["trechos"] = []
            c["lacunas"].append("evidências: sem cache do acervo para esta cultura; nenhum trecho citado."
                                if req.com_evidencias else "evidências não solicitadas (com_evidencias=false).")
        if pr.get("lacuna"):
            c["lacunas"].append(pr["lacuna"])
        c.setdefault("riscos_revisao_local", [])
        c["riscos_revisao_local"].append("Avaliar com técnico local; satélite/clima não enxergam o talhão.")
    if ev is None and req.com_evidencias:
        gerais.append("cache evidencias_rag.json ausente: sem evidências")
    return CenarioOut(ponto_id=req.ponto_id, cultura_atual=req.cultura_atual, prioridade=req.prioridade,
                      regra_prioridade=pr["regra"], cenarios=cens, lacunas_gerais=gerais, regras_duras=info_regras, aviso=AVISO,
                      segundos=time.perf_counter() - t0)


@lru_cache(maxsize=256)
def _buscar_rag(q: str, k: int) -> str:
    """Busca no acervo, com cache de respostas (mesma pergunta = ~0 ms). Devolve JSON (imutável p/ o cache)."""
    from src.rag.busca import buscar   # índice, embeddings e reranker carregam uma vez (lazy, cache do módulo)
    return json.dumps(buscar(q, k=k), ensure_ascii=False)


@app.get("/evidencias")
def evidencias(q: str = Query(min_length=3), k: int = Query(5, ge=1, le=10)):
    try:
        return json.loads(_buscar_rag(" ".join(q.split()), k))
    except Exception as e:   # índice ou modelo ausente => lacuna explícita
        raise HTTPException(503, f"LACUNA: RAG indisponível ({e.__class__.__name__}); sem evidência")


# ---- previsão de 1 composto (modelo persistido em disco; ver src/modelos/previsao.py)
_TRAVA_PREVISAO = threading.Lock()
_CTX_PREVISAO: dict = {}


def contexto_previsao() -> dict:
    """Modelo + dataset em memória; o modelo vem do cache em disco (treina e grava só se faltar ou se os dados mudaram)."""
    with _TRAVA_PREVISAO:
        if not _CTX_PREVISAO:
            _CTX_PREVISAO.update(_prev.carregar_ou_treinar())
        return _CTX_PREVISAO


class PrevisaoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    modelo: str
    horizonte: str
    anos_treino: list[int]
    dados_inferencia: str | None = Field(None, description="Arquivos de onde saem o último composto e o clima (original + 2025+); o modelo é treinado só com os originais.")
    ultimo_composto_observado: str | None = None
    anomalia_observada_ultimo: float | None = None
    composto_alvo: str | None = None
    clima_ate: str | None = Field(None, description="Último dia de clima que o modelo lê para este composto (no máximo o dia anterior ao alvo).")
    clima_disponivel_ate: str | None = Field(None, description="Último dia com chuva e temperatura não vazias nos arquivos de entrada.")
    anomalia_ndvi_prevista: float | None = Field(None, description="Anomalia de NDVI (NDVI - climatologia do slot). null = sem número (ver `lacuna`).")
    faixa_incerteza: dict[str, list[float] | None] | None = Field(None, description="Faixa ACI por cobertura ('80', '90'): [inferior, superior].")
    metodo_faixa: str | None = None
    extrapolacao: bool | None = None
    features_fora_da_faixa: list[dict] = []
    lacuna: str | None = None
    lacunas: list[str] = []
    limites_declarados: list[str]
    origem_modelo: str
    aviso: str


LIMITES_PREVISAO = [
    "Vale só 1 composto de 16 dias à frente do último composto válido: sem previsão de clima, o composto seguinte é o único cujas "
    "features (clima observado até o dia anterior + anomalia dos 2 compostos anteriores) existem. Além disso, sem número.",
    "A anomalia prevista vem em grande parte da persistência (NDVI dos compostos anteriores); a chuva/temperatura contribuem pouco.",
    "A faixa ACI calibra a cobertura média por estação nos anos de teste (alvo 80%/90%); não garante a cobertura de um ponto isolado.",
    "NDVI de 250 m e clima de ~50 km não enxergam o talhão. Não é previsão de produtividade, de safra nem de renda.",
    M.AVISO,
]


@app.get("/modelo/previsao/{ponto_id}", response_model=PrevisaoOut)
def previsao(ponto_id: str):
    exigir_ponto(ponto_id)
    try:
        ctx = contexto_previsao()
        r = _prev.prever_um_composto(ponto_id, ctx)
    except Exception as e:
        raise HTTPException(503, f"LACUNA: modelo de previsão indisponível ({e.__class__.__name__}: {e})")
    campos = set(PrevisaoOut.model_fields)
    out = _limpo({k: v for k, v in r.items() if k in campos and k not in ("lacunas", "aviso", "limites")})
    return PrevisaoOut(**out, lacunas=r.get("lacunas", []), limites_declarados=LIMITES_PREVISAO,
                       origem_modelo=f"{ctx['origem']} ({ctx['nome']}; treino {ctx['treino_anos'][0]}–{ctx['treino_anos'][-1]})",
                       aviso=r.get("aviso") or M.AVISO)


def _tabela_md(txt: str, titulo: str) -> list[list[str]]:
    ls = txt.splitlines()
    for i, ln in enumerate(ls):
        if ln.startswith("#") and titulo in ln:
            tab = []
            for l2 in ls[i + 1:]:
                if l2.strip().startswith("|"):
                    c = [x.strip() for x in l2.strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-{2,}:?", x) for x in c):
                        tab.append(c)
                elif tab:
                    break
            return tab
    return []


@app.get("/limites")
def limites():
    arq = DADOS / "modelos/metricas.json"
    rel = DADOS / "modelos/relatorio_modelos.md"
    if not arq.is_file():
        raise HTTPException(404, "LACUNA: metricas.json ausente")
    m = json.loads(arq.read_text(encoding="utf-8"))
    return {
        "fonte": [str(arq.relative_to(RAIZ)), str(rel.relative_to(RAIZ)) if rel.is_file() else "relatorio ausente (lacuna)"],
        "holdout_temporal": {"anos_teste": m["holdout_temporal"]["anos_teste"],
                             "modelos": {k: {"rmse": v["rmse"], "skill_vs_climatologia": v["skill_vs_climatologia"]}
                                         for k, v in m["holdout_temporal"]["modelos"].items()},
                             "conformal": m["holdout_temporal"].get("conformal")},
        "decisao": m.get("decisao"), "confianca": m.get("confianca"), "dados_sinteticos": m.get("dados_sinteticos"),
        "lacunas": m.get("lacunas", []), "aviso": m.get("aviso"),
        "tabela_holdout_relatorio": _tabela_md(rel.read_text(encoding="utf-8"), "Holdout temporal") if rel.is_file() else None,
        "limites_fixos": ["Satélite não enxerga o talhão (NDVI 250 m, clima ~50 km, SMAP ~9 km).",
                          "Renda: sem dado de mercado (lacuna).", AVISO],
    }


# ================================================================== Fase 5: o que o app calcula e a API ainda não expunha
# Tudo abaixo chama as funções de src/app/mvp.py e src/culturas por import; a API só valida, serializa e rotula.
def _exigir_cultura(cid: str) -> None:
    if cid not in tabela():
        raise HTTPException(422, f"cultura '{cid}' fora da tabela: {sorted(tabela())}")


class SoloOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    estimado: dict | None = Field(description="null = LACUNA (ponto sem dado SoilGrids).")
    lacuna: str | None = None
    aviso: str


@app.get("/solo/{ponto_id}", response_model=SoloOut)
def solo(ponto_id: str):
    """Solo ESTIMADO pelo mapa global SoilGrids (250 m, mediana ~2 km, 0–30 cm). Não é análise de solo."""
    exigir_ponto(ponto_id)
    est = M.solo_estimado(ponto_id)
    return SoloOut(ponto_id=ponto_id, estimado=_limpo(est), lacuna=None if est else "LACUNA: sem dado SoilGrids para este ponto",
                   aviso="Estimativa do mapa global SoilGrids; confirme com o técnico. " + M.AVISO)


class ZarcOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    cultura_id: str
    geocodigo_ibge: int | None
    risco_max_aceito: int
    solo: str
    decendios_permitidos: list[bool] | None = Field(description="36 decêndios a partir de 1º jan; null = sem ZARC (ver `motivo`).")
    n_decendios_permitidos: int | None
    recurso_zarc: str | None = Field(None, description="Safra/portaria do ZARC usada (a mais recente com linhas).")
    motivo: str | None = Field(None, description="Por que não há janela (lacuna explícita).")
    aviso_solo: str | None = None
    aviso: str


@app.get("/zarc/{ponto_id}/{cultura_id}", response_model=ZarcOut)
def zarc(ponto_id: str, cultura_id: str, risco: int = Query(30, description="Risco máximo aceito: 20, 30 ou 40 (%)."),
         solo: Literal["qualquer", "todos", "arenoso", "medio", "argiloso"] = "qualquer"):
    """Janela de plantio do ZARC (Zoneamento Agrícola de Risco Climático, sequeiro) por município, cultura, risco e solo."""
    exigir_ponto(ponto_id)
    _exigir_cultura(cultura_id)
    if risco not in (20, 30, 40):
        raise HTTPException(422, "risco deve ser 20, 30 ou 40")
    geo = zarc_mod.geocodigo_do_ponto(ponto_id)
    j = zarc_mod.janela(geo, cultura_id, risco, solo)
    perm = j.get("permitido")
    return ZarcOut(ponto_id=ponto_id, cultura_id=cultura_id, geocodigo_ibge=geo, risco_max_aceito=risco,
                   solo=j.get("solo", solo), decendios_permitidos=None if perm is None else [bool(x) for x in perm],
                   n_decendios_permitidos=j.get("n_decendios"), recurso_zarc=j.get("recurso"), motivo=j.get("motivo"),
                   aviso_solo=j.get("aviso"),
                   aviso="O ZARC é do MAPA/Embrapa (sequeiro); aqui só restringe o início do plantio. " + M.AVISO)


class RotacaoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    cultura_atual: str
    prioridade: Literal["sem", "agua", "solo", "renda"] = "sem"
    rotacao_atual: list[str] | None = Field(None, min_length=3, max_length=3,
                                            description="Rotação que o agricultor já faz: 3 culturas, a 1ª = cultura_atual. Sem ela, repete a atual.")
    textura: Literal["não sei", "arenoso", "médio", "argiloso"] = "não sei"
    materia_organica: Literal["não sei", "baixa", "média", "alta"] = "não sei"
    usar_zarc: bool = M.ZARC_PADRAO
    n_sorteios: int = Field(1000, ge=100, le=5000)
    regras: RegrasIn | None = Field(None, description="Regras duras do agricultor. A rotação_atual dele nunca some (se violar, vai em detalhes.regras_duras.base_viola).")


class RotacaoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    estrategias: list[dict] = Field(description="Atual/rotação do agricultor + alternativas de 3 safras, com faixa de incerteza e lacunas.")
    lacunas: list[str]
    suposicoes: list[str]
    horizonte_safras: int
    prioridade: str
    usar_zarc: bool
    solo_informado: dict | None
    solo_estimado: dict | None
    empate_tecnico_todos: bool | None = None
    aviso: str
    segundos: float
    detalhes: dict = Field(description="Demais campos do motor de rotação (critérios, anos de clima, contagens).")


@app.post("/rotacao", response_model=RotacaoOut)
def rotacao(req: RotacaoIn):
    """Rotação de 3 safras (SMAA sobre critérios com dado e fonte). Cenário a avaliar com técnico, não recomendação."""
    exigir_ponto(req.ponto_id)
    _exigir_cultura(req.cultura_atual)
    if req.rotacao_atual is not None:
        for c in req.rotacao_atual:
            _exigir_cultura(c)
        if req.rotacao_atual[0] != req.cultura_atual:
            raise HTTPException(422, "rotacao_atual deve começar pela cultura_atual")
    rd = _regras_duras(req.regras)
    r = M.calcular_rotacao(req.ponto_id, req.cultura_atual, req.prioridade, req.rotacao_atual, req.textura,
                           req.materia_organica, req.usar_zarc, req.n_sorteios, regras=PF.regras_para_motor(rd))
    r = _limpo(r)
    r.setdefault("prioridade", req.prioridade)
    if rd is not None and rd.aceita_pousio:
        r["lacunas"] = list(r.get("lacunas") or []) + [PF.AVISO_POUSIO]
    topo = {"estrategias", "lacunas", "suposicoes", "horizonte_safras", "prioridade", "usar_zarc", "solo_informado",
            "solo_estimado", "empate_tecnico_todos", "aviso", "segundos", "local"}
    return RotacaoOut(ponto_id=req.ponto_id, detalhes={k: v for k, v in r.items() if k not in topo},
                      **{k: r.get(k) for k in topo - {"local"} if k in RotacaoOut.model_fields and k != "detalhes"})


class ClimaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    cultura_atual: str
    prioridade: Literal["sem", "agua", "solo", "renda"] = "sem"
    fator_chuva: float = Field(1.0, ge=M.CHUVA_FATOR_MIN, le=M.CHUVA_FATOR_MAX,
                               description="Multiplica a chuva diária (limites de apresentação do app, não previsão).")
    delta_t: float = Field(0.0, ge=M.TEMP_DELTA_MIN, le=M.TEMP_DELTA_MAX, description="Soma °C às temperaturas.")


class ClimaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    fator_chuva: float
    delta_t: float
    extrapolacao: bool = Field(description="true = o cenário sai do que ocorreu no local (2001–2024); ver `avisos`.")
    avisos: list[str]
    mudou_alternativas: bool
    alternativas_base: list[str]
    alternativas_cenario: list[str]
    linhas: list[dict]
    aviso: str


@app.post("/cenarios/clima", response_model=ClimaOut)
def cenario_de_clima(req: ClimaIn):
    """"E se chover X% menos / fizer Y °C a mais?": mesmo motor, clima perturbado, comparando as MESMAS estratégias. Não é previsão."""
    exigir_ponto(req.ponto_id)
    _exigir_cultura(req.cultura_atual)
    r = _limpo(M.cenario_clima(req.ponto_id, req.cultura_atual, req.prioridade, req.fator_chuva, req.delta_t))
    return ClimaOut(ponto_id=req.ponto_id, aviso="Cenário hipotético, não previsão de clima. " + M.AVISO,
                    **{k: r[k] for k in ("fator_chuva", "delta_t", "extrapolacao", "avisos", "mudou_alternativas",
                                         "alternativas_base", "alternativas_cenario", "linhas")})


class PlanoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    cultura_atual: str
    prioridade: Literal["sem", "agua", "solo", "renda"] = "sem"
    horizonte: int = Field(5, ge=2, le=8, description="Nº de safras do plano.")
    nunca_repetir_seguida: bool = True
    min_leguminosas: int = Field(2, ge=0, le=4)
    usar_zarc: bool = M.ZARC_PADRAO
    n_sorteios: int = Field(150, ge=20, le=500)


class PlanoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    status: Literal["proposta", "sem_plano"] = Field(description="Sempre 'proposta' (nunca decisão) ou 'sem_plano' (lacuna).")
    lacuna: str | None = None
    top: list[dict] = Field(description="Sequências mais frequentes como ótimas sob incerteza; a frequência mostra que nenhuma domina.")
    detalhes: dict
    aviso: str


@app.post("/plano", response_model=PlanoOut)
def plano(req: PlanoIn):
    """Plano de várias safras por MILP com regras duras, repetido sob incerteza. PROPOSTA a conversar com o técnico."""
    exigir_ponto(req.ponto_id)
    _exigir_cultura(req.cultura_atual)
    r = _limpo(M.calcular_plano(req.ponto_id, req.cultura_atual, req.prioridade, req.horizonte, req.nunca_repetir_seguida,
                                req.min_leguminosas, req.usar_zarc, req.n_sorteios))
    top = r.pop("top", [])
    lac = r.pop("lacuna", None)
    return PlanoOut(ponto_id=req.ponto_id, status="sem_plano" if lac else "proposta", lacuna=lac, top=top,
                    detalhes={k: v for k, v in r.items() if k != "aviso"},
                    aviso="PROPOSTA, não decisão: cada sequência é a ótima em uma fração dos sorteios; "
                          "sem dado de renda/pragas. " + M.AVISO)


# ================================================================== Chat com RAG (DeepSeek opcional; ver src/llm/chat.py e docs/14_LLM.md)
from src.llm import chat as chat_mod  # noqa: E402


class InformativosIn(BaseModel):
    """Campos que só REGISTRAM (não mudam nenhum cálculo)."""
    model_config = ConfigDict(extra="forbid")
    area_ha: float | None = Field(None, gt=0, le=PF.AREA_MAX_HA)
    mes_plantio: int | None = Field(None, ge=1, le=12)
    declive: Literal["plano", "suave", "forte"] | None = None
    acesso_mercado: Literal["sim", "não", "não sei"] | None = None


class PerfilChatIn(BaseModel):
    """Perfil do agricultor aceito pelo /chat: NUNCA município, ponto_id, nome, lat, lon (campo extra = 422)."""
    model_config = ConfigDict(extra="forbid")
    prioridade: Literal["sem", "agua", "solo", "renda"] = "sem"
    manejo: Literal["sequeiro", "irrigado"] = "sequeiro"
    agua_irrigacao_mm: float = Field(0, ge=0, le=PF.AGUA_MAX_MM)
    equipamento: str = PF.F.EQUIPAMENTOS[0]
    mercado: str = PF.F.MERCADOS[0]
    textura: Literal["não sei", "arenoso", "médio", "argiloso"] = "não sei"
    materia_organica: Literal["não sei", "baixa", "média", "alta"] = "não sei"
    safra_2: str | None = None
    safra_3: str | None = None
    tambem_considero: list[str] = Field(default_factory=list, max_length=60)
    quer_conversar: bool = False
    regras: RegrasIn = Field(default_factory=RegrasIn)
    informativos: InformativosIn = Field(default_factory=InformativosIn)


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pergunta: str = Field(min_length=1, max_length=2000, description=f"Máx. {chat_mod.MAX_PERGUNTA} letras úteis (acima, a resposta é uma recusa).")
    ponto_id: str | None = Field(None, description="Com `cultura_atual`: usa o cenário deste local como contexto (sem lat/lon na API externa).")
    cultura_atual: str | None = None
    prioridade: Literal["sem", "agua", "solo", "renda"] = "sem"
    perfil: PerfilChatIn | None = Field(None, description="O que o agricultor informou (sem identificador). Entra nos fatos do local; só com `ponto_id`.")


class ChatTrecho(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    arquivo: str
    pagina: int | str | None = None
    texto: str


class ChatFato(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="Id do fato na folha do local, citado no texto como [F3].")
    tema: str
    rotulo: str
    texto: str = Field(description="Texto TÉCNICO do fato (para conferência), números em pt-BR; sem nome do município, ponto_id, IBGE, lat nem lon.")
    texto_simples: str = Field("", description="Frase em linguagem simples para o agricultor: é a que vai ao prompt da IA e ao texto padrão. Vazia = fato sem frase simples.")
    origem: str = Field(description="Função/arquivo e campo de onde o fato veio (para conferir).")
    lacuna: bool


class ChatVerificacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool | None = Field(description="true = texto da IA aprovado; false = rejeitado (veja `motivos`); null = não houve texto de IA.")
    motivos: list[str]


class ChatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resposta: str = Field(description="Texto LIMPO para exibir ao agricultor: sem marcadores [F#] nem [n] (removidos DEPOIS da verificação).")
    resposta_com_citacoes: str = Field(description="Texto original (verificado) com os marcadores [F#] e [n], para conferência.")
    origem: Literal["llm", "template", "sem_evidencia", "recusa"]
    trechos: list[ChatTrecho]
    fatos: list[ChatFato] = Field(description="Fatos do local enviados como fonte ([F#]); vazio se a pergunta não é sobre os dados do local.")
    citados: list[int]
    citados_fatos: list[str] = Field(description="Ids [F#] que o texto da IA citou.")
    sem_evidencia: bool
    verificacao: ChatVerificacao
    aviso: str
    motivo: str
    uso: dict | None = Field(None, description="`usage` do provedor (tokens), quando houve chamada.")
    provedor: str
    modelo: str
    em_cache: bool
    modo: str


@lru_cache(maxsize=64)
def _folha_chat(ponto_id: str, cultura: str, prioridade: str) -> dict:
    """Folha de fatos do local (src/llm/fatos.py); usa as mesmas funções desta API e do app. Em cache por (local, cultura, prioridade)."""
    from src.llm import fatos as fatos_mod
    return fatos_mod.montar_folha(ponto_id, cultura, prioridade)


@lru_cache(maxsize=64)
def _contexto_chat(ponto_id: str, cultura: str, prioridade: str) -> dict | None:
    calc = M.calcular(ponto_id, cultura, prioridade)
    return chat_mod.montar_contexto(calc["cenarios"], cultura, prioridade)


@app.post("/chat", response_model=ChatOut)
def chat(req: ChatIn):
    """Pergunta ao acervo (RAG), à fonte 'sobre o Sulco' e, com `ponto_id`, à folha de fatos do local. A IA só reescreve fontes citadas
    ([F#] e [n]); sem chave ou sem evidência, devolve texto padrão. Nenhum identificador do local vai à API externa."""
    folha = ctx = None
    if (req.ponto_id is None) != (req.cultura_atual is None):
        raise HTTPException(422, "informe `ponto_id` e `cultura_atual` juntos (ou nenhum dos dois)")
    if req.ponto_id is not None:
        exigir_ponto(req.ponto_id)
        _exigir_cultura(req.cultura_atual)
        try:
            folha = _folha_chat(req.ponto_id, req.cultura_atual, req.prioridade)
        except Exception:   # noqa: BLE001 - sem a folha o chat tenta o contexto do cenário e, sem ele, segue só com o acervo
            folha = None
        if folha is None:
            try:
                ctx = _contexto_chat(req.ponto_id, req.cultura_atual, req.prioridade)
            except Exception:   # noqa: BLE001
                ctx = None
    if req.perfil is not None:
        try:
            pc = PF.para_chat(PF.validar(req.perfil.model_dump(), tabela(), como_chat=True))
        except PF.PerfilErro as e:
            raise HTTPException(422, "perfil inválido: " + "; ".join(e.erros))
        folha = PF.folha_com_perfil(folha, pc, M.culturas_disponiveis())
        ctx = PF.contexto_com_perfil(ctx, pc)
    return chat_mod.responder_chat(req.pergunta, contexto=ctx, folha=folha)


@app.get("/chat/gasto")
def chat_gasto():
    """Contador de gasto do dia da camada LLM (chamadas e tokens; nunca a chave). Serve à página /teste."""
    from src.llm import provedores as prov_mod
    d = prov_mod._ler_gasto()
    return {"data": d.get("data"), "chamadas_dia": d.get("chamadas_dia", 0), "teto_chamadas_dia": prov_mod._teto_dia(),
            "tokens_entrada_dia": d.get("tokens_entrada_dia", 0), "tokens_saida_dia": d.get("tokens_saida_dia", 0),
            "total_chamadas": d.get("total_chamadas", 0)}


@app.get("/teste", response_class=HTMLResponse, include_in_schema=False)
def pagina_teste():
    """Página de teste do chat (HTML puro). Ferramenta de desenvolvimento; ver src/api/pagina_teste.py."""
    from src.api import pagina_teste as pt
    return HTMLResponse(pt.renderizar(M.culturas_disponiveis()))


@app.get("/chat/estado")
def chat_estado():
    """Modo, provedor, modelo e se há chave configurada (a chave nunca é devolvida)."""
    return chat_mod.estado()
