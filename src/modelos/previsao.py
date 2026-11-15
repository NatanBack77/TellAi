"""Previsão de 1 composto à frente para UM ponto, com o modelo persistido em disco (usado pela API).

O que é: anomalia de NDVI (NDVI - climatologia do slot) prevista para o PRÓXIMO composto de 16 dias depois do último
composto válido do ponto, com a faixa ACI de `treinar_para_cenarios` (mesmo código dos cenários) e os limites declarados.

Por que só 1 composto: as features do composto t usam só dias <= t-1 (features.py) e as de persistência usam a anomalia
dos 2 compostos anteriores. O clima observado vai até o último dia com chuva e tmax não vazios dos arquivos "atuais"; sem clima
futuro não há como calcular as features de t+2 em diante. Se o composto-alvo exigir clima que não existe, NÃO há número (lacuna).

DOIS CONJUNTOS DE DADOS (2026-11-14):
- TREINO (modelo, climatologia do alvo, faixa ACI): arquivos ORIGINAIS (`caminhos.clima/ndvi`, até 2024) e anos fixos do config
  (`preditivo.anos_treino` 2001-2021 e `anos_holdout` 2022-2024). Nada de 2025+ entra no modelo; `metricas.json` não muda.
- INFERÊNCIA (último composto válido, anomalias dos 2 compostos anteriores, features de clima): arquivos "atuais"
  (`caminhos.clima_atual/ndvi_atual` = original + 2025+, gerados por `src/coleta/unir_2025.py`).

Modelo: treinado uma vez e guardado em `data/processed/modelos/cache_api_previsao.joblib`; a chamada seguinte só lê o arquivo.
O cache leva uma impressão digital dos arquivos de TREINO e do config (os arquivos atuais não entram: o modelo não depende deles;
a impressão deles vai em `impressao_dados_atuais` só para conferência). Se treino ou config mudarem, retreina (nunca se usa
modelo velho em silêncio).
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
from src.coleta.unir_2025 import garantir_atuais
from .preditivo import preparar_tabela_modelagem

ARQ_CACHE = RAIZ / "data/processed/modelos/cache_api_previsao.joblib"
ARQ_METRICAS = RAIZ / "data/processed/modelos/metricas.json"
PASSO_DIAS = 16
MAX_GAP_DIAS = 17


def _impressao(cfg: dict, nome: str, chaves=("clima", "ndvi", "umidade_solo"), com_config: bool = True) -> str:
    h = hashlib.sha256()
    for k in chaves:
        arq = RAIZ / cfg["caminhos"][k]
        h.update(f"{k}:{arq.stat().st_size if arq.exists() else None}:{int(arq.stat().st_mtime) if arq.exists() else None}".encode())
    if com_config:
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
    # INFERÊNCIA: original + 2025+ (se faltar a fonte 2025+, usa só os originais e DECLARA a lacuna; nunca mistura em silêncio)
    lac_dados = None
    try:
        garantir_atuais(cfg)
        entradas = carregar_entradas(cfg, atual=True)
        arquivos_atuais = "clima_atual/ndvi_atual (original + 2025+)"
    except (DadosInvalidos, OSError) as e:
        entradas = carregar_entradas(cfg)
        arquivos_atuais = "clima_diario/ndvi_16d ORIGINAIS (até 2024)"
        lac_dados = (f"dados de 2025+ indisponíveis ({e}): a previsão usa só os dados originais, que terminam em "
                     f"{entradas['ndvi']['data'].max().date()}.")
    ds = construir_dataset(entradas, cfg)
    imp_atual = _impressao(cfg, nome, ("clima_atual", "ndvi_atual"), com_config=False) if lac_dados is None else None
    extra = {"ds": ds, "entradas": entradas, "cfg": cfg, "lacuna_modelo": lac, "lacuna_dados": lac_dados,
             "arquivos_inferencia": arquivos_atuais, "impressao_dados_atuais": imp_atual}
    if not forcar and ARQ_CACHE.is_file():
        try:
            c = joblib.load(ARQ_CACHE)
            if c.get("impressao") == imp:
                return {**c, **extra, "origem": "cache em disco", "segundos": time.perf_counter() - t0}
        except Exception:   # cache corrompido/incompatível: retreina
            pass
    # TREINO: sempre os arquivos ORIGINAIS e os anos fixos do config (a tabela de treino nunca vê 2025+)
    ds_treino = construir_dataset(carregar_entradas(cfg), cfg)
    _, treino_anos, teste_anos, _ = preparar_tabela_modelagem(ds_treino, cfg)
    mc = treinar_para_cenarios(ds_treino, cfg, nome)
    c = {"mc": mc, "treino_anos": [int(a) for a in treino_anos], "teste_anos": [int(a) for a in teste_anos], "impressao": imp,
         "nome": nome}
    ARQ_CACHE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(c, ARQ_CACHE)
    return {**c, **extra, "origem": "treinado agora e gravado em disco", "segundos": time.perf_counter() - t0}


def _aviso_clima_recente(fim_clima: pd.Timestamp) -> str:
    return (f"O clima observado mais recente nos arquivos vai até {fim_clima.date()}; os dias mais recentes do NASA POWER podem ser provisórios e "
            "ser revistos depois (hipótese, não verificada). Dias finais vazios não são preenchidos.")


def _proxima_data(ultima: pd.Timestamp) -> pd.Timestamp:
    """Próxima data da grade de 16 dias (1º jan + 16*slot) depois de `ultima`."""
    slot = int((ultima.day_of_year - 1) // PASSO_DIAS)
    if slot + 1 <= 22:
        return pd.Timestamp(ultima.year, 1, 1) + pd.Timedelta(days=PASSO_DIAS * (slot + 1))
    return pd.Timestamp(ultima.year + 1, 1, 1)


def prever_um_composto(ponto_id: str, ctx: dict, composto_alvo: str | pd.Timestamp | None = None) -> dict:
    """Previsão para o composto seguinte ao último válido de `ponto_id`. Sempre devolve dict; `anomalia_ndvi_prevista=None` + `lacuna` se não der.

    `composto_alvo` (só para conferência retrospectiva, ex.: contra o prospectivo 2025+): faz de conta que o presente é o dia anterior
    ao alvo, isto é, só compostos com data < alvo contam como observados; o alvo é o dado, não derivado. Em produção fica None."""
    mc: ModeloCenarios = ctx["mc"]
    cfg, ds, ent = ctx["cfg"], ctx["ds"], ctx["entradas"]
    base_out = {"ponto_id": ponto_id, "modelo": mc.nome, "horizonte": "1 composto de 16 dias à frente do último composto válido",
                "anos_treino": [ctx["treino_anos"][0], ctx["treino_anos"][-1]], "dados_inferencia": ctx.get("arquivos_inferencia")}
    d = ds[ds["ponto_id"] == ponto_id].sort_values("data")
    if d.empty:
        return {**base_out, "anomalia_ndvi_prevista": None, "faixa_incerteza": None, "lacuna": "ponto sem NDVI no dataset"}
    d = adicionar_anomalia(d, ctx["treino_anos"], cfg).sort_values("data")
    d = d[d["anomalia_ndvi"].notna()]
    forcado = pd.Timestamp(composto_alvo) if composto_alvo is not None else None
    if forcado is not None:
        d = d[d["data"] < forcado]
    if len(d) < 2:
        return {**base_out, "anomalia_ndvi_prevista": None, "faixa_incerteza": None,
                "lacuna": "menos de 2 compostos com anomalia: sem persistência, sem previsão"}
    ult, pen = d.iloc[-1], d.iloc[-2]
    alvo = forcado if forcado is not None else _proxima_data(ult["data"])
    base_out.update(ultimo_composto_observado=str(ult["data"].date()), anomalia_observada_ultimo=float(ult["anomalia_ndvi"]),
                    composto_alvo=str(alvo.date()))
    cl = ent["clima"]
    cl = cl[cl["ponto_id"] == ponto_id].sort_values("data")
    # fim do clima OBSERVADO = último dia com chuva e tmax não vazios (os últimos dias do POWER podem vir NaN: D18, não se preenche)
    ok_cl = cl.dropna(subset=["chuva_mm", "tmax_c"])
    if ok_cl.empty:
        return {**base_out, "anomalia_ndvi_prevista": None, "faixa_incerteza": None, "lacuna": "ponto sem clima observado"}
    fim_clima = ok_cl["data"].max()
    cl = cl[cl["data"] <= fim_clima]
    sem_num = lambda motivo: {**base_out, "anomalia_ndvi_prevista": None, "faixa_incerteza": None, "lacuna": motivo,
                              "clima_ate": str(fim_clima.date()), "clima_disponivel_ate": str(fim_clima.date())}
    if (alvo - ult["data"]).days > MAX_GAP_DIAS or (ult["data"] - pen["data"]).days > MAX_GAP_DIAS:
        return sem_num("compostos anteriores não consecutivos (buraco > %d dias): persistência indisponível, sem número" % MAX_GAP_DIAS)
    if alvo - pd.Timedelta(days=1) > fim_clima:
        return sem_num(f"o composto-alvo ({alvo.date()}) exige clima até {(alvo - pd.Timedelta(days=1)).date()}, mas o clima observado "
                       f"termina em {fim_clima.date()}: sem clima futuro não há previsão para este ponto")
    # As features do dia-alvo só olham dias <= alvo-1. Se o alvo já está na série de clima (ex.: último composto válido é anterior a
    # um composto inválido), NÃO se acrescenta linha (acrescentar duplicava a data: era o erro de 'sobral_ce'); se o alvo é o dia
    # seguinte ao fim do clima, entra uma linha vazia só para o índice existir.
    cols_cl = ["ponto_id", "celula_power", "data", "chuva_mm", "tmax_c"]
    if alvo in set(cl["data"]):
        ext = cl[cols_cl].reset_index(drop=True)
    else:
        ext = pd.concat([cl[cols_cl], pd.DataFrame({"ponto_id": [ponto_id], "celula_power": [cl["celula_power"].iloc[0]],
                                                    "data": [alvo], "chuva_mm": [np.nan], "tmax_c": [np.nan]})], ignore_index=True)
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
    # clima_ate = último dia de clima que o modelo de fato lê (alvo-1); clima_disponivel_ate = fim do clima observado nos arquivos
    saida = {**base_out, "clima_ate": str(min(fim_clima, alvo - pd.Timedelta(days=1)).date()),
             "clima_disponivel_ate": str(fim_clima.date()), "extrapolacao": r["extrapolacao"],
             "anomalia_ndvi_prevista": r["anomalia_ndvi_prevista"], "faixa_incerteza": r["faixa_incerteza"],
             "metodo_faixa": r.get("metodo_faixa"), "features_fora_da_faixa": r["features_fora_da_faixa"],
             "limites": r["limites"], "lacunas": r["lacunas"] + ([ctx["lacuna_modelo"]] if ctx.get("lacuna_modelo") else [])
             + ([ctx["lacuna_dados"]] if ctx.get("lacuna_dados") else []) + [_aviso_clima_recente(fim_clima)],
             "aviso": r["aviso"]}
    if r["extrapolacao"]:
        saida["lacuna"] = r["mensagem"]
    return saida


if __name__ == "__main__":   # pré-aquece o cache: python -m src.modelos.previsao
    c = carregar_ou_treinar()
    print(c["origem"], f"{c['segundos']:.1f}s", "->", ARQ_CACHE)
