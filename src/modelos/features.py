"""Features do modelo preditivo (módulo 2): "quanto a vegetação responde ao clima?".

Regras anti-vazamento:
- Cada linha é um período t do NDVI (data = início do composto de 16 d).
- TODA feature usa só dias estritamente ANTERIORES a t (janela [t-W, t-1]); dado de t em diante nunca entra.
- Janelas de soma exigem cobertura completa; janelas de média exigem `cobertura_minima_dados`.
  Faltou dado => NaN (nunca preenchido em silêncio).
- Latitude/longitude e ids NÃO são features (evita memorizar lugar).
- O alvo (anomalia de NDVI) é calculado à parte em `adicionar_anomalia`, com a climatologia vinda só dos
  `anos_referencia` informados. No holdout temporal, passe apenas os anos de TREINO.
- Só observações de NDVI originais e confiáveis viram linha (interpoladas não são alvo).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .diagnostico import _quinzena, preparar_ndvi
from .entrada import DadosInvalidos

N_QUINZENAS = 24


def nomes_features(cfg: dict, com_umidade: bool) -> list[str]:
    p = cfg["preditivo"]
    nomes = [f"chuva_ac_{w}d" for w in p["janelas_chuva_dias"]]
    nomes += [f"tmax_media_{p['janela_tmax_dias']}d", "dias_secos_consecutivos", "quinzena_sin", "quinzena_cos"]
    if com_umidade:
        nomes += [f"sm_superficie_{p['janela_umidade_dias']}d", f"sm_raiz_{p['janela_umidade_dias']}d"]
    return nomes


def _dias_secos_consecutivos(chuva_anterior: pd.Series, limiar: float, teto: int) -> pd.Series:
    """Dias secos seguidos terminando no dia anterior a t. NaN se a sequência toca dado ausente."""
    v = chuva_anterior.to_numpy(dtype=float)
    saida = np.full(len(v), np.nan)
    corrida, perdido = 0, True  # início da série: antes dele é desconhecido
    for i, x in enumerate(v):
        if np.isnan(x):
            perdido = True
            corrida = 0
        elif x >= limiar:
            perdido, corrida = False, 0
            saida[i] = 0
        else:
            if perdido:
                continue  # limite inferior apenas: mantém NaN
            corrida += 1
            saida[i] = min(corrida, teto)
    return pd.Series(saida, index=chuva_anterior.index)


def _diario(df: pd.DataFrame, col: str, ponto: str) -> pd.Series:
    if df["data"].duplicated().any():
        raise DadosInvalidos(f"Datas duplicadas em '{col}' do ponto {ponto}; corrija a coleta.")
    s = df.set_index("data")[col].sort_index()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))


def features_diarias_ponto(
    clima_p: pd.DataFrame, umid_p: pd.DataFrame | None, cfg: dict
) -> pd.DataFrame:
    """Features por dia t, calculadas só com dias <= t-1. Índice = data."""
    p = cfg["preditivo"]
    mc = cfg["cobertura_minima_dados"]
    pid = str(clima_p["ponto_id"].iloc[0])
    chuva = _diario(clima_p, "chuva_mm", pid).shift(1)   # shift(1): janela termina em t-1
    tmax = _diario(clima_p, "tmax_c", pid).shift(1)
    out = pd.DataFrame(index=chuva.index)
    for w in p["janelas_chuva_dias"]:
        out[f"chuva_ac_{w}d"] = chuva.rolling(w, min_periods=w).sum()          # cobertura completa
    w = p["janela_tmax_dias"]
    out[f"tmax_media_{w}d"] = tmax.rolling(w, min_periods=int(np.ceil(mc * w))).mean()
    out["dias_secos_consecutivos"] = _dias_secos_consecutivos(
        chuva, cfg["veranico"]["limiar_chuva_mm"], max(p["janelas_chuva_dias"]))
    q = _quinzena(out.index)
    out["quinzena_sin"] = np.sin(2 * np.pi * q / N_QUINZENAS)
    out["quinzena_cos"] = np.cos(2 * np.pi * q / N_QUINZENAS)
    if umid_p is not None and not umid_p.empty:
        wu = p["janela_umidade_dias"]
        for col in ("sm_superficie", "sm_raiz"):
            s = _diario(umid_p, col, pid).shift(1).reindex(out.index)
            out[f"{col}_{wu}d"] = s.rolling(wu, min_periods=int(np.ceil(mc * wu))).mean()
    return out


def construir_dataset(entradas: dict, cfg: dict) -> pd.DataFrame:
    """Uma linha por (ponto, período de NDVI observado). Sem alvo ainda (ver `adicionar_anomalia`)."""
    clima, ndvi, umid = entradas["clima"], entradas["ndvi"], entradas["umidade_solo"]
    linhas = []
    for pid, cl in clima.groupby("ponto_id"):
        nd = ndvi[ndvi["ponto_id"] == pid]
        if nd.empty:
            continue
        grade, _ = preparar_ndvi(nd, cfg)
        obs = grade[grade["valido_original"]][["ano", "slot", "data", "ndvi"]].copy()
        um = None if umid is None else umid[umid["ponto_id"] == pid]
        feats = features_diarias_ponto(cl, um, cfg).reindex(obs["data"])
        feats.index = obs.index
        d = pd.concat([obs, feats], axis=1)
        d.insert(0, "celula_power", str(cl["celula_power"].iloc[0]))
        d.insert(0, "ponto_id", str(pid))
        d["quinzena"] = _quinzena(d["data"])
        linhas.append(d)
    if not linhas:
        raise DadosInvalidos("Nenhum ponto com clima e NDVI em comum; dataset vazio.")
    df = pd.concat(linhas, ignore_index=True)
    cols = nomes_features(cfg, com_umidade=any(c.startswith("sm_raiz") for c in df.columns))
    df["completo"] = df[cols].notna().all(axis=1)
    return df


def adicionar_anomalia(df: pd.DataFrame, anos_referencia, cfg: dict) -> pd.DataFrame:
    """Alvo = NDVI - climatologia do slot (por ponto), com climatologia calculada SÓ nos `anos_referencia`.

    Slots com menos de `min_anos_climatologia_slot` anos de referência ficam NaN (lacuna).
    """
    ref = df[df["ano"].isin(list(anos_referencia))]
    if ref.empty:
        raise DadosInvalidos("anos_referencia sem nenhuma observação de NDVI.")
    g = ref.groupby(["ponto_id", "slot"])["ndvi"]
    clim = pd.DataFrame({"ndvi_clim": g.mean(), "n_ref": g.count()}).reset_index()
    clim.loc[clim["n_ref"] < cfg["preditivo"]["min_anos_climatologia_slot"], "ndvi_clim"] = np.nan
    out = df.drop(columns=[c for c in ("ndvi_clim", "n_ref", "anomalia_ndvi") if c in df.columns]).merge(
        clim, on=["ponto_id", "slot"], how="left")
    out["anomalia_ndvi"] = out["ndvi"] - out["ndvi_clim"]
    return out


def resumir_dataset(df: pd.DataFrame, cfg: dict) -> dict:
    """Contagens e avisos (lacunas) do dataset, para o relatório e para o preditivo."""
    p = cfg["preditivo"]
    n_cel = int(df["celula_power"].nunique())
    lacunas = []
    if n_cel < p["min_celulas_aviso"]:
        lacunas.append(f"Apenas {n_cel} células POWER distintas (< {p['min_celulas_aviso']}): o tamanho efetivo "
                       "da amostra é o número de células, não de pontos; métricas têm pouca força estatística.")
    nao_completas = int((~df["completo"]).sum())
    if nao_completas:
        lacunas.append(f"{nao_completas} períodos de NDVI sem alguma feature (janela incompleta ou dado ausente); "
                       "ficam fora do treino, não são preenchidos.")
    if not any(c.startswith("sm_raiz") for c in df.columns):
        lacunas.append("Umidade do solo (SMAP) ausente: modelo sem features de umidade.")
    return {"n_linhas": int(len(df)), "n_completas": int(df["completo"].sum()), "n_pontos": int(df["ponto_id"].nunique()),
            "n_celulas": n_cel, "anos": [int(df["ano"].min()), int(df["ano"].max())], "lacunas": lacunas}


if __name__ == "__main__":
    from .entrada import carregar_config, carregar_entradas
    import sys

    cfg = carregar_config()
    if "--sintetico" in sys.argv:
        d = "data/processed/sintetico"
        cfg["caminhos"].update(clima=f"{d}/SINTETICO_clima_diario.parquet", ndvi=f"{d}/SINTETICO_ndvi_16d.parquet",
                               umidade_solo=f"{d}/SINTETICO_umidade_solo.parquet")
    ds = construir_dataset(carregar_entradas(cfg), cfg)
    print(resumir_dataset(ds, cfg))
