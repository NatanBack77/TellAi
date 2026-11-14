"""Previsão de 1 composto à frente para UM ponto, com o modelo persistido em disco (usado pela API).

O que é: anomalia de NDVI (NDVI - climatologia do slot) prevista para o PRÓXIMO composto de 16 dias depois do último
composto válido do ponto, com a faixa ACI de `treinar_para_cenarios` (mesmo código dos cenários) e os limites declarados.

Por que só 1 composto: as features do composto t usam só dias <= t-1 (features.py) e as de persistência usam a anomalia
dos 2 compostos anteriores. O clima observado vai até o fim de `clima_diario.parquet`; sem clima futuro não há como
calcular as features de t+2 em diante. Se o composto-alvo exigir clima que não existe, NÃO há número (lacuna).

Modelo: treinado uma vez (anos de treino do config) e guardado em `data/processed/modelos/cache_api_previsao.joblib`; a
chamada seguinte só lê o arquivo. O cache leva uma impressão digital dos arquivos de entrada e do config; se mudarem,
o modelo é retreinado (nunca se usa modelo velho em silêncio).
"""
from __future__ import annotations

import hashlib
import json
import time

import joblib
import numpy as np
import pandas as pd

from .cenarios import ModeloCenarios, simular, treinar_para_cenarios
from .entrada import RAIZ, DadosInvalidos, carregar_config, carregar_entradas
from .features import adicionar_anomalia, construir_dataset, features_diarias_ponto
from .preditivo import preparar_tabela_modelagem

ARQ_CACHE = RAIZ / "data/processed/modelos/cache_api_previsao.joblib"
ARQ_METRICAS = RAIZ / "data/processed/modelos/metricas.json"
PASSO_DIAS = 16
MAX_GAP_DIAS = 17


def _impressao(cfg: dict, nome: str) -> str:
    h = hashlib.sha256()
    for k in ("clima", "ndvi", "umidade_solo"):
        arq = RAIZ / cfg["caminhos"][k]
        h.update(f"{k}:{arq.stat().st_size if arq.exists() else None}:{int(arq.stat().st_mtime) if arq.exists() else None}".encode())
    h.update(json.dumps(cfg["preditivo"], sort_keys=True, default=str).encode())
    h.update(f"{nome}:{cfg.get('semente')}".encode())
    return h.hexdigest()[:16]


def nome_do_modelo() -> tuple[str, str | None]:
    """Modelo escolhido no relatório (metricas.json); sem o arquivo, Ridge e a lacuna é declarada."""
    if ARQ_METRICAS.is_file():
        return json.loads(ARQ_METRICAS.read_text(encoding="utf-8"))["decisao"]["modelo"], None
    return "ridge", "metricas.json ausente: modelo padrão Ridge (decisão do relatório não disponível)."


def carregar_ou_treinar(forcar: bool = False) -> dict:
    """Devolve {'mc', 'treino_anos', 'ds', 'cfg', 'origem', 'segundos', ...}. `ds` = dataset de NDVI+features (NÃO vai para o disco)."""
    t0 = time.perf_counter()
    cfg = carregar_config()
    nome, lac = nome_do_modelo()
    imp = _impressao(cfg, nome)
    entradas = carregar_entradas(cfg)
    ds = construir_dataset(entradas, cfg)
    if not forcar and ARQ_CACHE.is_file():
        try:
            c = joblib.load(ARQ_CACHE)
            if c.get("impressao") == imp:
                return {**c, "ds": ds, "entradas": entradas, "cfg": cfg, "origem": "cache em disco",
                        "segundos": time.perf_counter() - t0, "lacuna_modelo": lac}
        except Exception:   # cache corrompido/incompatível: retreina
            pass
    _, treino_anos, teste_anos, _ = preparar_tabela_modelagem(ds, cfg)
    mc = treinar_para_cenarios(ds, cfg, nome)
    c = {"mc": mc, "treino_anos": [int(a) for a in treino_anos], "teste_anos": [int(a) for a in teste_anos], "impressao": imp,
         "nome": nome}
    ARQ_CACHE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(c, ARQ_CACHE)
    return {**c, "ds": ds, "entradas": entradas, "cfg": cfg, "origem": "treinado agora e gravado em disco",
            "segundos": time.perf_counter() - t0, "lacuna_modelo": lac}


def _proxima_data(ultima: pd.Timestamp) -> pd.Timestamp:
    """Próxima data da grade de 16 dias (1º jan + 16*slot) depois de `ultima`."""
    slot = int((ultima.day_of_year - 1) // PASSO_DIAS)
    if slot + 1 <= 22:
        return pd.Timestamp(ultima.year, 1, 1) + pd.Timedelta(days=PASSO_DIAS * (slot + 1))
    return pd.Timestamp(ultima.year + 1, 1, 1)


def prever_um_composto(ponto_id: str, ctx: dict) -> dict:
    """Previsão para o composto seguinte ao último válido de `ponto_id`. Sempre devolve dict; `anomalia_ndvi_prevista=None` + `lacuna` se não der."""
    mc: ModeloCenarios = ctx["mc"]
    cfg, ds, ent = ctx["cfg"], ctx["ds"], ctx["entradas"]
    base_out = {"ponto_id": ponto_id, "modelo": mc.nome, "horizonte": "1 composto de 16 dias à frente do último composto válido",
                "anos_treino": [ctx["treino_anos"][0], ctx["treino_anos"][-1]]}
    d = ds[ds["ponto_id"] == ponto_id].sort_values("data")
    if d.empty:
        return {**base_out, "anomalia_ndvi_prevista": None, "faixa_incerteza": None, "lacuna": "ponto sem NDVI no dataset"}
    d = adicionar_anomalia(d, ctx["treino_anos"], cfg).sort_values("data")
    d = d[d["anomalia_ndvi"].notna()]
    if len(d) < 2:
        return {**base_out, "anomalia_ndvi_prevista": None, "faixa_incerteza": None,
                "lacuna": "menos de 2 compostos com anomalia: sem persistência, sem previsão"}
    ult, pen = d.iloc[-1], d.iloc[-2]
    alvo = _proxima_data(ult["data"])
    base_out.update(ultimo_composto_observado=str(ult["data"].date()), anomalia_observada_ultimo=float(ult["anomalia_ndvi"]),
                    composto_alvo=str(alvo.date()))
    cl = ent["clima"]
    cl = cl[cl["ponto_id"] == ponto_id]
    fim_clima = cl["data"].max()
    sem_num = lambda motivo: {**base_out, "anomalia_ndvi_prevista": None, "faixa_incerteza": None, "lacuna": motivo,
                              "clima_ate": str(fim_clima.date())}
    if (alvo - ult["data"]).days > MAX_GAP_DIAS or (ult["data"] - pen["data"]).days > MAX_GAP_DIAS:
        return sem_num("compostos anteriores não consecutivos (buraco > %d dias): persistência indisponível, sem número" % MAX_GAP_DIAS)
    if alvo - pd.Timedelta(days=1) > fim_clima:
        return sem_num(f"o composto-alvo ({alvo.date()}) exige clima até {(alvo - pd.Timedelta(days=1)).date()}, mas o clima observado "
                       f"termina em {fim_clima.date()}: sem clima futuro não há previsão para este ponto")
    # linha do dia-alvo (clima NaN: as features só olham dias <= alvo-1)
    ext = pd.concat([cl[["ponto_id", "celula_power", "data", "chuva_mm", "tmax_c"]],
                     pd.DataFrame({"ponto_id": [ponto_id], "celula_power": [cl["celula_power"].iloc[0]], "data": [alvo],
                                   "chuva_mm": [np.nan], "tmax_c": [np.nan]})], ignore_index=True)
    f = features_diarias_ponto(ext, None, cfg)
    if alvo not in f.index:
        return sem_num("features do composto-alvo indisponíveis")
    linha = f.loc[[alvo]].copy()
    linha["anom_lag1"], linha["anom_lag2"] = float(ult["anomalia_ndvi"]), float(pen["anomalia_ndvi"])
    linha["slot"] = int((alvo.day_of_year - 1) // PASSO_DIAS)
    if linha[mc.cols].isna().any().any():
        faltam = [c for c in mc.cols if pd.isna(linha[c].iloc[0])]
        return sem_num(f"features ausentes para o composto-alvo ({', '.join(faltam)}): não preenchidas, sem número")
    r = simular(mc, linha)
    saida = {**base_out, "clima_ate": str(fim_clima.date()), "extrapolacao": r["extrapolacao"],
             "anomalia_ndvi_prevista": r["anomalia_ndvi_prevista"], "faixa_incerteza": r["faixa_incerteza"],
             "metodo_faixa": r.get("metodo_faixa"), "features_fora_da_faixa": r["features_fora_da_faixa"],
             "limites": r["limites"], "lacunas": r["lacunas"] + ([ctx["lacuna_modelo"]] if ctx.get("lacuna_modelo") else []),
             "aviso": r["aviso"]}
    if r["extrapolacao"]:
        saida["lacuna"] = r["mensagem"]
    return saida


if __name__ == "__main__":   # pré-aquece o cache: python -m src.modelos.previsao
    c = carregar_ou_treinar()
    print(c["origem"], f"{c['segundos']:.1f}s", "->", ARQ_CACHE)
