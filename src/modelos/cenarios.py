"""Módulo 3: sensibilidade a cenários ("e se a chuva fosse 20% menor?").

Entrada: fatores aplicados às features de um ponto/quinzena. Saída: anomalia de NDVI prevista + faixa de
incerteza (split conformal). Se alguma feature do cenário sai da faixa vista no treino, NÃO há número:
"extrapolação não confiável".

Como o cenário altera as features:
- `chuva_ac_*` é multiplicada por `fator_chuva`; `tmax_media_*` soma `delta_tmax_c`.
- `dias_secos_consecutivos`, sazonalidade e umidade do solo NÃO são alteradas (limitação declarada na saída).

O modelo captura associações históricas, não causalidade, e não prevê o clima futuro.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .entrada import DadosInvalidos
from .preditivo import (
    AVISO_ASSOCIACAO, ajustar_modelo, dividir_celulas_calibracao, preparar_tabela_modelagem, quantil_conformal,
)

LIMITES_CENARIO = ("Dias secos consecutivos, sazonalidade e umidade do solo não são alterados pelo cenário; "
                   "o efeito de veranicos mais longos ou de menos umidade não está representado.")


@dataclass
class ModeloCenarios:
    nome: str
    modelo: object
    cols: list[str]
    faixas: dict[str, tuple[float, float]]
    quantis: dict[str, float]            # meta ("80", "90") -> meia-largura da faixa
    n_celulas_treino: int
    lacunas: list[str] = field(default_factory=list)


def treinar_para_cenarios(df: pd.DataFrame, cfg: dict, nome: str = "ridge") -> ModeloCenarios:
    """Ajusta o modelo escolhido (use `resultado['decisao']['modelo']`) nas células de treino próprio,
    calibra a faixa conformal nas células de calibração e guarda a faixa de cada feature vista no treino."""
    p = cfg["preditivo"]
    d, treino_anos, _, cols = preparar_tabela_modelagem(df, cfg)
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
    n_cel = int(treino["celula_power"].nunique())
    if n_cel < p["min_celulas_aviso"]:
        lacunas.append(f"Apenas {n_cel} células POWER no treino (< {p['min_celulas_aviso']}): faixas pouco confiáveis.")
    if any(not np.isfinite(q) for q in quantis.values()):
        lacunas.append("Calibração com poucas linhas: faixa de incerteza indisponível em alguma meta.")
    faixas = {c: (float(treino[c].min()), float(treino[c].max())) for c in cols}
    return ModeloCenarios(nome, mod, cols, faixas, quantis, n_cel, lacunas)


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
    saida = {"fator_chuva": float(fator_chuva), "delta_tmax_c": float(delta_tmax_c), "modelo": mc.nome,
             "n_linhas_base": int(len(x)), "limites": LIMITES_CENARIO, "lacunas": list(mc.lacunas),
             "aviso": AVISO_ASSOCIACAO + " Cenário a avaliar com técnico local."}
    if fora:
        saida.update(extrapolacao=True, anomalia_ndvi_prevista=None, faixa_incerteza=None, features_fora_da_faixa=fora,
                     mensagem="Extrapolação não confiável: o cenário sai da faixa vista no treino. Sem número.")
        return saida
    pred = float(np.mean(mc.modelo.predict(x)))
    faixa = {k: ([pred - q, pred + q] if np.isfinite(q) else None) for k, q in mc.quantis.items()}
    saida.update(extrapolacao=False, anomalia_ndvi_prevista=pred, faixa_incerteza=faixa, features_fora_da_faixa=[],
                 mensagem="Faixa conformal por linha, não da média: a incerteza da média é menor, a da linha é esta.")
    return saida
