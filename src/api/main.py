"""Back-end offline do SULCO (FastAPI). Só lê arquivos locais. Lacuna = campo explícito, nunca valor inventado."""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.culturas import ciclo as ciclo_mod
from src.culturas.motor import gerar_cenarios
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar as carregar_tabela

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "data/processed"
AVISO = "Cenário a avaliar com técnico local. Não decide e não promete que a rotação rende mais."

# Prioridades: ORDEM ordinal entre critérios (faixas), nunca pesos exatos. SUPOSIÇÃO a validar com técnico.
PRIORIDADES = {
    "sem": {"ordem": None, "bloco": "principal", "regra": "Sem ordem entre critérios (pesos livres)."},
    "agua": {"ordem": ("chuva", "temperatura", "familia_diferente"), "bloco": "principal",
             "regra": "SUPOSIÇÃO: chuva > temperatura > família. Não mede consumo de água nem irrigação."},
    "solo": {"ordem": ("palha", "n_na_biomassa", "familia_diferente", "chuva", "temperatura"), "bloco": "completo",
             "regra": "SUPOSIÇÃO: palha > N > família > chuva > temperatura. Dado ausente de N/palha entra como incerteza."},
    "renda": {"ordem": None, "bloco": "principal",
              "regra": "LACUNA: sem dado de preço/custo/mercado; não altera o ranking.",
              "lacuna": "renda: sem dado de preço/custo/mercado; prioridade não altera o ranking"},
}

app = FastAPI(title="SULCO API", version="0.1.0",
              description="Back-end offline do SULCO. Apoia a conversa com o técnico; não decide.")
LATENCIAS: dict[str, list[float]] = {}


@app.middleware("http")
async def medir(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    rota = request.scope.get("route")
    LATENCIAS.setdefault(getattr(rota, "path", request.url.path), []).append(ms)
    resp.headers["X-Latencia-ms"] = f"{ms:.1f}"
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


# ------------------------------------------------------------------ schemas
class Municipio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    lat: float
    lon: float
    celula_power: str


class Saude(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    arquivos: dict[str, bool]
    n_pontos: int | None
    latencias_ms: dict[str, dict[str, float]]


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


class CenarioOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ponto_id: str
    cultura_atual: str
    prioridade: str
    regra_prioridade: str
    cenarios: list[dict]   # contrato docs/01 seção 7 (+ janela_plantio, suposicoes, viabilidade do motor)
    lacunas_gerais: list[str]
    aviso: str
    segundos: float


class Previsao501(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    lacuna: str


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
                 n_pontos=len(pontos()) if ok["pontos.csv"] else None, latencias_ms=lat)


@app.get("/municipios", response_model=list[Municipio])
def municipios():
    p = pontos()
    return [Municipio(ponto_id=r.ponto_id, lat=r.lat, lon=r.lon, celula_power=str(r.celula_power)) for r in p.itertuples()]


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
    kw = {k: v for k, v in (("ciclo_modo", req.ciclo_modo), ("chuva_modo", req.chuva_modo), ("risco_max", req.risco_max),
                            ("n_sorteios", req.n_sorteios)) if v is not None}
    try:
        p = Parametros(ordem_pesos=pr["ordem"], bloco_ranking=pr["bloco"], **kw)
    except ValueError as e:
        raise HTTPException(422, str(e))
    cens = gerar_cenarios({"local": req.ponto_id}, req.cultura_atual, tab, clima=clima_ponto(req.ponto_id), params=p)
    gerais = []
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
                      regra_prioridade=pr["regra"], cenarios=cens, lacunas_gerais=gerais, aviso=AVISO,
                      segundos=time.perf_counter() - t0)


@app.get("/evidencias")
def evidencias(q: str = Query(min_length=3), k: int = Query(5, ge=1, le=10)):
    try:
        from src.rag.busca import buscar   # carrega índice/modelos de forma lazy e uma única vez (cache do módulo)
        return buscar(q, k=k)
    except Exception as e:   # índice ou modelo ausente => lacuna explícita
        raise HTTPException(503, f"LACUNA: RAG indisponível ({e.__class__.__name__}); sem evidência")


@app.get("/modelo/previsao/{ponto_id}", response_model=Previsao501, status_code=501)
def previsao(ponto_id: str):
    exigir_ponto(ponto_id)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=501, content={
        "status": "nao_implementado",
        "lacuna": "previsão por persistência com faixa conformal ainda não exposta pela API (requer treinar/cachear "
                  "o modelo de src/modelos). Limites reais do modelo: GET /limites."})


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
