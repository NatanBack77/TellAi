"""ZARC (Tábua de Risco, MAPA) como filtro OPCIONAL dos inícios de plantio do motor (`Parametros.usar_zarc`, padrão desligado).

Fonte: data/processed/zarc_ce.parquet (gerado por `python -m src.coleta.zarc`; CC BY). Leitura dos dados (observada nas
linhas, o dicionário oficial não descreve): `decN` = 0 sem indicação de plantio no decêndio N; 20/30/40 = nível de risco
máximo em que o plantio é indicado. Um decêndio é PERMITIDO ao risco r se 0 < decN <= r.

Regras:
- só mapeia culturas com nome claro; as demais ficam "sem ZARC" (lacuna; o motor NÃO restringe e avisa);
- manejo sequeiro (Cod_Outros_Manejos = 1);
- vários tipos de solo e grupos de ciclo por (município, cultura): `solo="qualquer"` (permitido se algum solo/grupo indica;
  mais permissivo), `solo="todos"` (só se TODOS indicam; mais conservador) ou um solo específico (`arenoso`, `medio`, `argiloso`; Cod_Solo 1, 2, 3)
  quando o solo é conhecido (informado pelo agricultor ou estimado pelo SoilGrids). Sem linhas para aquele solo, cai em "qualquer" e avisa;
- cultura SEM ZARC (sorgo, adubação verde): janela APROXIMADA = união dos decêndios permitidos às culturas ANUAIS com ZARC no município
  (SUPOSIÇÃO: sem isso, essas culturas ficariam sem restrição e levariam vantagem sobre as zoneadas);
- safra: usa o arquivo mais recente que tenha a cultura no município (2026/27, 2025/26, 2024/25, depois perene/olerícola);
- o ZARC mede risco de perda de produtividade por clima; não é a nota climática do EcoCrop.
"""
from __future__ import annotations

import functools
import unicodedata

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ

CAMINHO = RAIZ / "data/processed/zarc_ce.parquet"
PREFERENCIA = ("safra_2026_2027", "safra_2025_2026", "safra_2024_2025", "perene_olericola_sem_safra")
DEC = [f"dec{i}" for i in range(1, 37)]
SEM_INDICACAO = 99  # "risco" de um decêndio sem indicação
SOLOS = {"arenoso": 1, "medio": 2, "argiloso": 3}      # Cod_Solo do ZARC (os grupos AD1-AD6 ficam só em "qualquer"/"todos")
ANUAIS = ("algodao", "amendoim", "feijao_caupi", "feijao_comum", "gergelim", "girassol", "mamona", "milho", "milheto")

# cultura_id da nossa tabela -> nomes ZARC (normalizados). Só nomes claros; ausente = sem ZARC.
# feijao_comum -> "Feijão 2ª Safra" (única entrada de sequeiro no CE); milho -> "Milho 1ª Safra" (sem o consorciado); sorgo fica de fora (granífero x forrageiro é ambíguo).
MAPA_CULTURAS = {
    "algodao": ("algodao herbaceo",),
    "amendoim": ("amendoim",),
    "feijao_caupi": ("feijao caupi",),
    "feijao_comum": ("feijao 2a safra",),   # no CE o "Feijão" 1ª safra é só irrigado; sequeiro = "2ª Safra" (SUPOSIÇÃO a validar)
    "gergelim": ("gergelim",),
    "girassol": ("girassol",),
    "mamona": ("mamona",),
    "mandioca": ("mandioca (aipim, macaxeira)",),
    "milheto": ("milheto",),
    "milho": ("milho 1a safra",),
    "palma_forrageira": ("palma forrageira",),
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).replace("\xa0", " ")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split()).replace("1ª", "1a")


@functools.lru_cache(maxsize=1)
def _indice() -> dict:
    """{(geocodigo, nome_norm, recurso): (risco_uniao[36], risco_todos[36])} só para sequeiro."""
    if not CAMINHO.exists():
        return {}
    d = pd.read_parquet(CAMINHO)
    d = d[d["Cod_Outros_Manejos"] == 1].copy()
    d["_n"] = d["Nome_cultura"].map(_norm)
    out = {}
    for (geo, n, rec), g in d.groupby(["geocodigo", "_n", "recurso"]):
        m = g[DEC].to_numpy(float)
        m = np.where(m > 0, m, SEM_INDICACAO)
        out[(int(geo), n, rec)] = (m.min(axis=0), m.max(axis=0))
        for nome, cod in SOLOS.items():
            gs = g[g["Cod_Solo"] == cod]
            if not gs.empty:
                ms = np.where(gs[DEC].to_numpy(float) > 0, gs[DEC].to_numpy(float), SEM_INDICACAO)
                out[(int(geo), n, rec, nome)] = (ms.min(axis=0), ms.max(axis=0))
    return out


@functools.lru_cache(maxsize=1)
def _geocodigos() -> dict:
    p = RAIZ / "data/processed/pontos.csv"
    d = pd.read_csv(p)
    if "ibge" not in d.columns:
        return {}
    return {r["ponto_id"]: int(r["ibge"]) for _, r in d.dropna(subset=["ibge"]).iterrows()}


def geocodigo_do_ponto(ponto_id: str) -> int | None:
    return _geocodigos().get(ponto_id)


def janela(geocodigo: int | None, cultura_id: str, risco: int = 30, solo: str = "qualquer") -> dict:
    """Decêndios permitidos (vetor bool de 36) ou {'permitido': None, motivo} se não houver ZARC. Nunca inventa."""
    if solo not in ("qualquer", "todos") and solo not in SOLOS:
        raise ValueError("solo deve ser 'qualquer', 'todos', 'arenoso', 'medio' ou 'argiloso'")
    if geocodigo is None:
        return {"permitido": None, "motivo": "ponto sem código IBGE: ZARC não aplicado"}
    nomes = MAPA_CULTURAS.get(cultura_id)
    if not nomes:
        return {"permitido": None, "motivo": f"cultura '{cultura_id}' sem correspondência clara no ZARC (ou sem ZARC)"}
    idx = _indice()
    if not idx:
        return {"permitido": None, "motivo": "arquivo do ZARC ausente (rode python -m src.coleta.zarc)"}
    for rec in PREFERENCIA:
        for n in nomes:
            par = idx.get((int(geocodigo), n, rec, solo)) if solo in SOLOS else idx.get((int(geocodigo), n, rec))
            solo_usado, aviso = solo, None
            if par is None and solo in SOLOS:                      # sem linhas deste solo: usa "qualquer" e avisa
                par, solo_usado = idx.get((int(geocodigo), n, rec)), "qualquer"
                aviso = f"ZARC sem linhas para solo {solo} nesta cultura/município: usado 'qualquer'"
            if par is not None:
                r = par[1] if solo_usado == "todos" else par[0]
                return {"permitido": r <= risco, "recurso": rec, "risco": int(risco), "solo": solo_usado,
                        "n_decendios": int((r <= risco).sum()), "motivo": None, "aviso": aviso}
    return {"permitido": None, "motivo": f"ZARC não traz '{cultura_id}' para o município {geocodigo} (sequeiro)"}


def decendios_do_inicio(offsets_dias: np.ndarray) -> np.ndarray:
    """Decêndio (0..35) de cada início, a partir do deslocamento em dias desde 1º/jan."""
    return np.minimum(np.asarray(offsets_dias) // 10, 35)


def janela_aproximada_anuais(geocodigo: int | None, risco: int = 30, solo: str = "qualquer") -> dict:
    """Janela para cultura SEM ZARC: união dos decêndios permitidos às culturas anuais com ZARC no município (SUPOSIÇÃO declarada)."""
    uni, n = None, 0
    for c in ANUAIS:
        j = janela(geocodigo, c, risco, solo)
        if j["permitido"] is not None:
            uni = j["permitido"].copy() if uni is None else (uni | j["permitido"])
            n += 1
    if uni is None:
        return {"permitido": None, "motivo": "sem ZARC de culturas anuais no município: janela aproximada indisponível"}
    return {"permitido": uni, "risco": int(risco), "solo": solo, "n_decendios": int(uni.sum()), "n_culturas_base": n, "motivo": None,
            "aviso": f"janela aproximada: união dos decêndios das {n} culturas anuais com ZARC no município (a cultura não tem ZARC)"}
