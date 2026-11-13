"""Conformal adaptativo por estação (ACI; Gibbs e Candès, NeurIPS 2021, arXiv 2106.00170) para a anomalia de NDVI.

Por quê: o split conformal supõe dados intercambiáveis, mas um ano seco ou úmido desloca os resíduos de TODOS os pontos juntos, e a faixa fica
curta demais (cobertura de ~76% / 87% para metas de 80% / 90%). O ACI atualiza o nível online a cada composto:
    alpha_{t+1} = alpha_t + gamma * (alpha - err_t),   err_t = fração de pontos NÃO cobertos no composto t,
com um alpha por faixa de estação (4 faixas de 6 slots). Validado em experimentos/conformal_A1/RESULTADO.md: na confirmação selada 2022-2024
cobriu 79,9% / 90,0% (método anterior 75,6% / 86,6%), com pior estação em 77% / 89%.

Procedimento (para cada ano de teste Y, em ordem): climatologia do alvo só dos anos < Y; modelo (Ridge) ajustado nos anos < Y-3; resíduos de
calibração = |erro| dos 3 anos anteriores a Y; os compostos de Y são percorridos em ordem de data e o alpha de cada faixa é atualizado com o erro
observado ali (informação já conhecida quando o composto seguinte começa). O estado de alpha segue de um ano para o outro; anos de aquecimento
levam o estado até o início da janela avaliada e não entram nas métricas. Gamma é fixo a priori (config), nunca ajustado olhando o teste.

A garantia do ACI é de cobertura de LONGO PRAZO, não de cada ano: anos individuais ainda fogem da meta.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import adicionar_anomalia, adicionar_persistencia, nomes_features
from .preditivo import ajustar_modelo, quantil_conformal

N_FAIXAS = 4


def q_nivel(r_ordenado: np.ndarray, alpha: float) -> float:
    """Quantil empírico de nível 1-alpha com correção de amostra finita. alpha <= 0 cobre tudo (inf); alpha >= 1 vira 0."""
    n = len(r_ordenado)
    if alpha <= 0:
        return float("inf")
    if alpha >= 1:
        return 0.0
    k = int(np.ceil((n + 1) * (1 - alpha)))
    return float("inf") if (n == 0 or k > n) else float(r_ordenado[k - 1])


def atualizar_alpha(alpha_atual: float, alvo_alpha: float, nao_coberto: float, gamma: float) -> float:
    return alpha_atual + gamma * (alvo_alpha - nao_coberto)


def _tabela_ano(df: pd.DataFrame, cfg: dict, Y: int, usar_persistencia: bool, usar_umidade: bool = False):
    anos_tr = sorted(int(a) for a in df["ano"].unique() if a < Y)
    d = adicionar_anomalia(df, anos_tr, cfg)
    cols = nomes_features(cfg, usar_umidade and any(c.startswith("sm_raiz") for c in df.columns))
    d, novas = adicionar_persistencia(d, cfg["preditivo"].get("persistencia_max_gap_dias", 17))
    cf = cols + (novas if usar_persistencia else [])
    ok = d["completo"] & d["anomalia_ndvi"].notna() & d[cf].notna().all(axis=1)
    d = d[ok].reset_index(drop=True)
    d["faixa"] = (d["slot"] // 6).clip(upper=N_FAIXAS - 1)
    return d, cf, anos_tr


def aci_walk_forward(df: pd.DataFrame, cfg: dict, anos_aquecimento: list[int], anos_teste: list[int],
                     usar_persistencia: bool = True, retornar_faixas: bool = False) -> dict:
    """Roda o ACI por estação em `anos_aquecimento` (só atualiza o estado) e `anos_teste` (mede a cobertura).

    `retornar_faixas=True` acrescenta `faixas_finais` (ver `faixas_aci`) sem alterar nenhum outro número."""
    a = cfg["preditivo"].get("conformal_aci", {})
    gamma, k_cal = float(a.get("gamma", 0.05)), int(a.get("anos_calibracao", 3))
    alvos = cfg["preditivo"]["cobertura_alvos"]
    estado = {}
    linhas = []
    ultimo = None
    for Y in list(anos_aquecimento) + list(anos_teste):
        medir = Y in anos_teste
        d, cf, anos_tr = _tabela_ano(df, cfg, Y, usar_persistencia)
        if len(anos_tr) <= k_cal:
            raise ValueError(f"ACI: ano {Y} sem anos de treino suficientes para calibrar com {k_cal} anos.")
        tr, te = d[d["ano"] < Y], d[d["ano"] == Y].copy()
        if te.empty:
            continue
        corte = anos_tr[-k_cal]
        prop, cal = tr[tr["ano"] < corte], tr[tr["ano"] >= corte]
        mod, _ = ajustar_modelo("ridge", prop[cf], prop["anomalia_ndvi"].to_numpy(), prop["celula_power"].to_numpy(), cfg)
        r_cal = np.abs(cal["anomalia_ndvi"].to_numpy() - mod.predict(cal[cf]))
        r_faixa = {f: np.sort(r_cal[(cal["faixa"] == f).to_numpy()]) for f in range(N_FAIXAS)}
        ultimo = (Y, r_faixa)
        te["err"] = np.abs(te["anomalia_ndvi"].to_numpy() - mod.predict(te[cf]))
        for alvo in alvos:
            a0 = 1 - alvo
            cob = pd.Series(False, index=te.index)
            for _, ix in te.groupby("data").groups.items():
                for f, jx in te.loc[ix].groupby("faixa").groups.items():
                    chave = (alvo, int(f))
                    al = estado.get(chave, a0)
                    c = te.loc[jx, "err"].to_numpy() <= q_nivel(r_faixa[int(f)], al)
                    cob.loc[jx] = c
                    estado[chave] = atualizar_alpha(al, a0, 1 - float(c.mean()), gamma)
            if medir:
                for f, x in te.assign(cob=cob).groupby("faixa"):
                    linhas.append({"ano": Y, "alvo": float(alvo), "faixa": int(f), "n": int(len(x)), "cobertura": float(x["cob"].mean())})
    t = pd.DataFrame(linhas)
    saida = {"metodo": "ACI por estação (Gibbs e Candès 2021)", "gamma": gamma, "anos_calibracao": k_cal,
             "anos_aquecimento": [int(x) for x in anos_aquecimento], "anos_teste": [int(x) for x in anos_teste],
             "modelo": "ridge", "estado_final_alpha": {f"{k[0]:.2f}_faixa{k[1]}": float(v) for k, v in estado.items()}, "metas": {}}
    for alvo in alvos:
        x = t[np.isclose(t["alvo"], alvo)]
        por_ano = x.groupby("ano").apply(lambda z: np.average(z["cobertura"], weights=z["n"]), include_groups=False)
        por_faixa = x.groupby("faixa").apply(lambda z: np.average(z["cobertura"], weights=z["n"]), include_groups=False)
        saida["metas"][f"{int(round(alvo * 100))}"] = {
            "meta": float(alvo), "cobertura": float(np.average(x["cobertura"], weights=x["n"])),
            "pior_ano": float(por_ano.min()), "pior_estacao": float(por_faixa.min()),
            "por_ano": {int(k): float(v) for k, v in por_ano.items()}, "por_estacao": {int(k): float(v) for k, v in por_faixa.items()}}
    if retornar_faixas:
        saida["faixas_finais"] = {
            "ano_referencia": int(ultimo[0]),
            "alpha_final": {f"{int(round(alvo * 100))}": {f: float(estado.get((alvo, f), 1 - alvo)) for f in range(N_FAIXAS)}
                            for alvo in alvos},
            "residuos_ordenados": {f: ultimo[1][f] for f in range(N_FAIXAS)}}
    saida["aviso"] = ("Cobertura de longo prazo (média dos anos de teste); anos individuais fogem da meta (ver pior_ano). "
                      "Validado para o Ridge; a mesma faixa vale para a previsão do modelo escolhido apenas como aproximação.")
    return saida


def faixas_aci(faixas_finais: dict) -> dict:
    """Meia-largura da faixa por meta ("80"/"90") e faixa de estação (0..3): q_nivel(resíduos do último ano, alpha final).

    inf = calibração insuficiente (sem número); 0.0 só ocorre se o ACI levou alpha a >= 1."""
    r = faixas_finais["residuos_ordenados"]
    return {meta: {f: q_nivel(r[f], al) for f, al in por_faixa.items()} for meta, por_faixa in faixas_finais["alpha_final"].items()}
