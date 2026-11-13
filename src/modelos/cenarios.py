"""Módulo 3: sensibilidade a cenários ("e se a chuva fosse 20% menor?").

Entrada: fatores aplicados às features de um ponto/quinzena. Saída: anomalia de NDVI prevista + faixa de
incerteza: por padrão o ACI por estação (conformal_aci.py; cobre ~81% / 91% no holdout); o split conformal por
células (cobre ~76% / 87%) segue disponível com `metodo_faixa="split"`. Se alguma feature do cenário sai da faixa vista no treino, NÃO há número:
"extrapolação não confiável".

Como o cenário altera as features:
- `chuva_ac_*` é multiplicada por `fator_chuva`; `tmax_media_*` soma `delta_tmax_c`.
- `dias_secos_consecutivos`, sazonalidade e umidade do solo NÃO são alteradas (limitação declarada na saída).
- Persistência (`anom_lag1/2`, D52): NÃO muda sob cenário de chuva/temperatura (é NDVI observado). O ganho do modelo
  vem dessa memória; por isso os cenários reagem pouco. `sensibilidade_comparada` mede isso com e sem persistência.

O modelo captura associações históricas, não causalidade, e não prevê o clima futuro.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .conformal_aci import N_FAIXAS, aci_walk_forward, faixas_aci
from .entrada import DadosInvalidos
from .preditivo import (
    AVISO_ASSOCIACAO, ajustar_modelo, dividir_celulas_calibracao, preparar_tabela_modelagem, quantil_conformal,
    usar_persistencia_cfg,
)

LIMITES_CENARIO = ("Dias secos consecutivos, sazonalidade e umidade do solo não são alterados pelo cenário; "
                   "o efeito de veranicos mais longos ou de menos umidade não está representado.")
LIMITE_PERSISTENCIA = (" As features de persistência (anomalia dos 2 compostos anteriores) NÃO mudam sob cenário de "
                       "chuva/temperatura: o ganho vem da memória do NDVI; cenários de clima reagem pouco "
                       "(ver a sensibilidade medida em `sensibilidade_comparada`).")


@dataclass
class ModeloCenarios:
    nome: str
    modelo: object
    cols: list[str]
    faixas: dict[str, tuple[float, float]]
    quantis: dict[str, float]            # método "split": meta ("80", "90") -> meia-largura da faixa
    n_celulas_treino: int
    lacunas: list[str] = field(default_factory=list)
    metodo_faixa: str = "split"
    quantis_estacao: dict[str, dict[int, float]] = field(default_factory=dict)   # método "aci": meta -> faixa de estação (0..3) -> meia-largura
    metodo_descricao: str = "split conformal por células de calibração"


def treinar_para_cenarios(df: pd.DataFrame, cfg: dict, nome: str = "ridge",
                          usar_persistencia: bool | None = None, metodo_faixa: str = "aci") -> ModeloCenarios:
    """Ajusta o modelo escolhido (use `resultado['decisao']['modelo']`) nas células de treino próprio,
    calibra a faixa conformal nas células de calibração e guarda a faixa de cada feature vista no treino.

    `usar_persistencia=None` segue o config (padrão: com persistência). A faixa de `anom_lag1/2` também entra
    na regra de extrapolação: fora de [min, max] do treino => sem número.

    `metodo_faixa="aci"` (padrão): meia-largura = q_nivel(resíduos do último ano, alpha final do ACI) por meta e por
    estação (aquecimento e anos de teste como em `avaliar`). `"split"`: método antigo (quantis por células de calibração)."""
    if metodo_faixa not in ("aci", "split"):
        raise ValueError("metodo_faixa deve ser 'aci' ou 'split'.")
    p = cfg["preditivo"]
    d, treino_anos, teste_anos, cols = preparar_tabela_modelagem(df, cfg, usar_persistencia)
    treino = d[d["ano"].isin(treino_anos)]
    if len(treino) < p["min_linhas_treino"]:
        raise DadosInvalidos(f"Linhas de treino insuficientes ({len(treino)}) para cenários.")
    cel_tr, cel_cal = dividir_celulas_calibracao(treino["celula_power"].unique(),
                                                 p["conformal_fracao_calibracao"], cfg["semente"])
    tr, cal = treino[treino["celula_power"].isin(cel_tr)], treino[treino["celula_power"].isin(cel_cal)]
    mod, _ = ajustar_modelo(nome, tr[cols], tr["anomalia_ndvi"].to_numpy(), tr["celula_power"].to_numpy(), cfg)
    res = np.abs(cal["anomalia_ndvi"].to_numpy() - mod.predict(cal[cols]))
    quantis = {f"{int(round(a * 100))}": quantil_conformal(res, 1 - a) for a in p["cobertura_alvos"]}
    lacunas = []
    quantis_est, descricao = {}, "split conformal por células de calibração (método antigo; cobre menos que o ACI)"
    if metodo_faixa == "aci":
        a = p.get("conformal_aci", {})
        aquec = [y for y in treino_anos if y >= treino_anos[0] + int(a.get("min_anos_treino_aquecimento", 8))]
        try:
            r = aci_walk_forward(df, cfg, aquec, teste_anos, usar_persistencia_cfg(cfg, usar_persistencia), retornar_faixas=True)
            quantis_est = faixas_aci(r["faixas_finais"])
            descricao = (f"ACI por estação, gamma {r['gamma']}, resíduos de calibração dos {r['anos_calibracao']} anos anteriores a "
                         f"{r['faixas_finais']['ano_referencia']} (Ridge)")
        except ValueError as e:
            lacunas.append(f"Faixa ACI indisponível ({e}): sem faixa de incerteza.")
            quantis_est = {f"{int(round(x * 100))}": {f: float("inf") for f in range(N_FAIXAS)} for x in p["cobertura_alvos"]}
            descricao = "ACI por estação (indisponível: calibração insuficiente)"
        quantis = {}
    n_cel = int(treino["celula_power"].nunique())
    if n_cel < p["min_celulas_aviso"]:
        lacunas.append(f"Apenas {n_cel} células POWER no treino (< {p['min_celulas_aviso']}): faixas pouco confiáveis.")
    if any(not np.isfinite(q) for q in quantis.values()) or any(not np.isfinite(q) for v in quantis_est.values() for q in v.values()):
        lacunas.append("Calibração com poucas linhas: faixa de incerteza indisponível em alguma meta.")
    faixas = {c: (float(treino[c].min()), float(treino[c].max())) for c in cols}
    return ModeloCenarios(nome, mod, cols, faixas, quantis, n_cel, lacunas, metodo_faixa, quantis_est, descricao)


def aplicar_cenario(base: pd.DataFrame, cols: list[str], fator_chuva: float = 1.0, delta_tmax_c: float = 0.0) -> pd.DataFrame:
    if fator_chuva < 0:
        raise ValueError("fator_chuva não pode ser negativo.")
    x = base[cols].copy()
    for c in cols:
        if c.startswith("chuva_ac_"):
            x[c] = x[c] * fator_chuva
        elif c.startswith("tmax_media_"):
            x[c] = x[c] + delta_tmax_c
    return x


def simular(mc: ModeloCenarios, base: pd.DataFrame, fator_chuva: float = 1.0, delta_tmax_c: float = 0.0) -> dict:
    """Anomalia de NDVI média prevista para as linhas `base` (ex.: um ponto numa quinzena, vários anos).

    `base` precisa ter as colunas de features sem NaN. Fora da faixa do treino => sem número.
    """
    if base.empty:
        raise DadosInvalidos("Base do cenário vazia.")
    x = aplicar_cenario(base, mc.cols, fator_chuva, delta_tmax_c)
    if x.isna().any().any():
        raise DadosInvalidos("A base do cenário tem features ausentes; não preenchemos em silêncio.")
    fora = []
    for c, (lo, hi) in mc.faixas.items():
        if ((x[c] < lo) | (x[c] > hi)).any():
            fora.append({"feature": c, "faixa_treino": [lo, hi], "valor_min": float(x[c].min()), "valor_max": float(x[c].max())})
    com_pers = any(c.startswith("anom_lag") for c in mc.cols)
    saida = {"fator_chuva": float(fator_chuva), "delta_tmax_c": float(delta_tmax_c), "modelo": mc.nome,
             "com_persistencia": com_pers,
             "n_linhas_base": int(len(x)), "limites": LIMITES_CENARIO + (LIMITE_PERSISTENCIA if com_pers else ""),
             "lacunas": list(mc.lacunas),
             "aviso": AVISO_ASSOCIACAO + " Cenário a avaliar com técnico local."}
    if fora:
        saida.update(extrapolacao=True, anomalia_ndvi_prevista=None, faixa_incerteza=None, features_fora_da_faixa=fora,
                     mensagem="Extrapolação não confiável: o cenário sai da faixa vista no treino. Sem número.")
        return saida
    pred = float(np.mean(mc.modelo.predict(x)))
    saida["metodo_faixa"] = mc.metodo_descricao
    if mc.metodo_faixa == "aci":
        est = _estacoes_da_base(base)
        if not est:
            saida["lacunas"].append("Base sem coluna `slot`: estação desconhecida; faixa ACI pelo valor mais largo entre as 4 estações.")
            est = list(range(N_FAIXAS))
        por_est = {f: {k: v[f] for k, v in mc.quantis_estacao.items()} for f in est}
        quantis = {k: max(por_est[f][k] for f in est) for k in mc.quantis_estacao}
        saida["estacoes_base"] = est
        saida["faixa_por_estacao"] = {f: {k: ([pred - q, pred + q] if np.isfinite(q) else None) for k, q in por_est[f].items()}
                                      for f in est}
        saida["faixa_usada"] = ("estação %d" % est[0]) if len(est) == 1 else "a mais larga entre as estações %s" % est
    else:
        quantis = mc.quantis
    faixa = {k: ([pred - q, pred + q] if np.isfinite(q) else None) for k, q in quantis.items()}
    saida.update(extrapolacao=False, anomalia_ndvi_prevista=pred, faixa_incerteza=faixa, features_fora_da_faixa=[],
                 mensagem="Faixa conformal por linha, não da média: a incerteza da média é menor, a da linha é esta.")
    return saida


def _estacoes_da_base(base: pd.DataFrame) -> list[int]:
    """Faixas de estação (slot // 6, no máximo 3) presentes na base; [] se não há `slot` válido."""
    if "slot" not in base.columns or base["slot"].isna().any():
        return []
    return sorted({int(min(int(s) // 6, N_FAIXAS - 1)) for s in base["slot"]})


# ----------------------------------------------------------------------------- sensibilidade medida (D52)
def simular_comparado(mc_pers: ModeloCenarios, mc_clima: ModeloCenarios, base: pd.DataFrame,
                      fator_chuva: float = 1.0, delta_tmax_c: float = 0.0) -> dict:
    """Mesmo cenário nas MESMAS linhas, com e sem persistência. Variação = previsão do cenário - previsão neutra.

    `base` precisa ter as colunas dos dois modelos. Se algum cenário extrapolar a faixa de algum modelo, sem número.
    """
    saida = {"fator_chuva": float(fator_chuva), "delta_tmax_c": float(delta_tmax_c), "n_linhas_base": int(len(base))}
    ok = True
    for rot, mc in (("com_persistencia", mc_pers), ("so_clima", mc_clima)):
        neutro, cen = simular(mc, base), simular(mc, base, fator_chuva, delta_tmax_c)
        if neutro["extrapolacao"] or cen["extrapolacao"]:
            saida[rot] = {"extrapolacao": True, "variacao": None}
            ok = False
            continue
        saida[rot] = {"extrapolacao": False, "neutro": neutro["anomalia_ndvi_prevista"],
                      "cenario": cen["anomalia_ndvi_prevista"],
                      "variacao": cen["anomalia_ndvi_prevista"] - neutro["anomalia_ndvi_prevista"]}
    v_p, v_c = saida["com_persistencia"].get("variacao"), saida["so_clima"].get("variacao")
    saida["razao_com_sobre_so_clima"] = float(v_p / v_c) if ok and v_c not in (0, 0.0) else None
    return saida


def sensibilidade_comparada(df: pd.DataFrame, cfg: dict, nomes=("ridge", "xgboost"),
                            cenarios=((0.8, 0.0), (1.2, 0.0), (1.0, 1.0))) -> dict:
    """Mede (número de código) quanto a previsão muda sob cenários, com e sem persistência.

    Linhas-base = períodos de TREINO que têm persistência válida (as mesmas para os dois modelos); para cada cenário
    só entram as linhas cujo valor de cenário fica dentro de [min, max] do treino de AMBOS os modelos (o resto seria
    extrapolação e não recebe número); `n_linhas_usadas`/`n_linhas_fora_da_faixa` mostram quantas.
    O modelo só-clima é o anterior (treinado em todas as suas linhas); o com persistência, o de produção.
    """
    d, treino_anos, _, _ = preparar_tabela_modelagem(df, cfg, True)
    base_all = d[d["ano"].isin(treino_anos)]
    saida = {"base": "períodos de treino (anos %d–%d) com 2 compostos anteriores consecutivos" % (treino_anos[0], treino_anos[-1]),
             "modelos": {}}
    for nome in nomes:
        mc_p = treinar_para_cenarios(df, cfg, nome, usar_persistencia=True)
        mc_c = treinar_para_cenarios(df, cfg, nome, usar_persistencia=False)
        lista = []
        for fator, delta in cenarios:
            x_p = aplicar_cenario(base_all, mc_p.cols, fator, delta)
            x_c = aplicar_cenario(base_all, mc_c.cols, fator, delta)
            dentro = pd.Series(True, index=base_all.index)
            for mc, x in ((mc_p, x_p), (mc_c, x_c)):
                for c, (lo, hi) in mc.faixas.items():
                    dentro &= (x[c] >= lo) & (x[c] <= hi)
            base = base_all[dentro]
            if base.empty:
                lista.append({"fator_chuva": fator, "delta_tmax_c": delta, "n_linhas_usadas": 0,
                              "n_linhas_fora_da_faixa": int((~dentro).sum()), "sem_numero": "todas as linhas extrapolam"})
                continue
            r = simular_comparado(mc_p, mc_c, base, fator, delta)
            r["n_linhas_usadas"], r["n_linhas_fora_da_faixa"] = int(len(base)), int((~dentro).sum())
            lista.append(r)
        saida["modelos"][nome] = lista
    saida["leitura"] = ("variacao = previsão sob cenário - previsão neutra (média das linhas-base, anomalia de NDVI). "
                        "razão = variação com persistência / variação só-clima. Associação histórica, não causalidade.")
    return saida
