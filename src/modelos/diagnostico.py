"""Módulo 1: diagnóstico por local (estatística descritiva, SEM previsão).

Entrada: NDVI 16 d (MOD13Q1), clima diário (POWER), umidade do solo (SMAP, opcional).
Saída por ponto: dict com sazonalidade (STL), climatologia/anomalias, janelas de solo nu,
tendências (Theil-Sen + Mann-Kendall), veranicos, `n_anos_validos`, `lacunas` e `confianca`.

`confianca` é heurística de cobertura de dados (anos válidos e interpolação), não probabilidade.
Nada aqui prevê clima, produtividade ou "rendimento" de rotação.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy.stats import theilslopes
from statsmodels.tsa.seasonal import STL

N_QUINZENAS = 24

LIMITES = [
    "NDVI vem de pixels de 250 m: pode misturar o seu talhão com mato, estrada ou vizinhos.",
    "Clima do POWER vem de células de ~50 km: chuva local de uma roça pode ser bem diferente.",
    "Umidade do solo (SMAP) tem ~9 km: não enxerga o solo do seu talhão.",
    "NDVI mostra verdor da vegetação, não é produtividade nem qualidade do solo.",
    "Este diagnóstico descreve o passado; não prevê chuva nem colheita.",
]


# ----------------------------------------------------------------------------- utilidades
def _quinzena(datas) -> np.ndarray:
    idx = pd.DatetimeIndex(datas)
    return (idx.month.to_numpy() - 1) * 2 + np.where(idx.day.to_numpy() <= 15, 1, 2)


def _agg_periodo(df: pd.DataFrame, col: str, how: str, por: str, min_cob: float) -> pd.Series:
    """Agrega série diária por 'quinzena' (index ano, quinzena) ou 'ano' (index ano).

    Períodos com cobertura de dias < min_cob viram NaN (nunca preenchidos em silêncio).
    """
    d = df[["data", col]].copy()
    cal = pd.DataFrame({"data": pd.date_range(df["data"].min().normalize(), df["data"].max().normalize())})
    for t in (d, cal):
        t["ano"] = t["data"].dt.year
        if por == "quinzena":
            t["quinzena"] = _quinzena(t["data"])
    chaves = ["ano", "quinzena"] if por == "quinzena" else ["ano"]
    esperado = cal.groupby(chaves).size().rename("esperado")
    g = d.dropna(subset=[col]).groupby(chaves)[col]
    valor = {"soma": g.sum, "media": g.mean, "max": g.max}[how]().rename("valor")
    out = pd.concat([valor, g.count().rename("n")], axis=1).join(esperado, how="right")
    out["cob"] = out["n"].fillna(0) / out["esperado"]
    out.loc[out["cob"] < min_cob, "valor"] = np.nan
    return out["valor"]


def _climatologia_e_z(s: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """s indexada por (ano, quinzena). Devolve climatologia por quinzena e z-score."""
    g = s.dropna().groupby(level="quinzena")
    clim = pd.DataFrame({"media": g.mean(), "desvio": g.std(ddof=1), "n_anos": g.count()})
    clim = clim.reindex(range(1, N_QUINZENAS + 1))
    q = s.index.get_level_values("quinzena")
    mu = clim["media"].reindex(q).to_numpy()
    sd = clim["desvio"].reindex(q).to_numpy()
    n = clim["n_anos"].reindex(q).to_numpy()
    ok = (n >= 3) & (sd > 0)
    z = np.where(ok, (s.to_numpy() - mu) / np.where(sd > 0, sd, np.nan), np.nan)
    return clim, pd.Series(z, index=s.index, name="z")


def _maior_sequencia(bools: np.ndarray) -> int:
    melhor = atual = 0
    for b in bools:
        atual = atual + 1 if b else 0
        melhor = max(melhor, atual)
    return int(melhor)


# ----------------------------------------------------------------------------- NDVI
def preparar_ndvi(ndvi_p: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Grade regular (ano x 23 slots). Descarta baixa confiabilidade; interpolação limitada e marcada."""
    c = cfg["ndvi"]
    n_slots = c["observacoes_por_ano"]
    d = ndvi_p.copy()
    aceita = d["confiabilidade"].isin(c["confiabilidade_aceita"])
    n_descartadas = int((~aceita).sum())
    d.loc[~aceita, "ndvi"] = np.nan
    d["ano"] = d["data"].dt.year
    d["slot"] = ((d["data"].dt.day_of_year - 1) // 16).clip(upper=n_slots - 1)
    g = d.groupby(["ano", "slot"])["ndvi"].mean()

    anos = np.arange(d["ano"].min(), d["ano"].max() + 1)
    idx = pd.MultiIndex.from_product([anos, range(n_slots)], names=["ano", "slot"])
    grade = g.reindex(idx).rename("ndvi").reset_index()
    grade["data"] = [pd.Timestamp(int(a), 1, 1) + pd.Timedelta(days=16 * int(s))
                     for a, s in zip(grade["ano"], grade["slot"])]
    grade["valido_original"] = grade["ndvi"].notna()

    # interpola só buracos curtos e internos; buracos longos permanecem NaN (lacuna)
    ausente = grade["ndvi"].isna()
    cheio = grade["ndvi"].interpolate(limit_area="inside")
    corrida = (ausente != ausente.shift()).cumsum()
    tam = ausente.groupby(corrida).transform("sum")
    preenche = ausente & (tam <= c["max_interpolacao_consecutiva"]) & cheio.notna()
    grade["ndvi_i"] = grade["ndvi"].where(~preenche, cheio)
    grade["interpolado"] = preenche

    por_ano = grade.groupby("ano")["valido_original"].sum()
    anos_validos = por_ano[por_ano >= c["min_obs_ano_valido"]].index.to_numpy()
    info = {
        "n_descartadas_baixa_confiabilidade": n_descartadas,
        "n_interpoladas": int(preenche.sum()),
        "n_ausentes_restantes": int(grade["ndvi_i"].isna().sum()),
        "frac_interpolada": float(preenche.sum() / max(1, len(grade))),
        "anos_validos": [int(a) for a in anos_validos],
    }
    return grade, info


def sazonalidade_stl(grade: pd.DataFrame, cfg: dict) -> tuple[dict | None, list[str]]:
    n_slots = cfg["ndvi"]["observacoes_por_ano"]
    lacunas: list[str] = []
    v = grade["ndvi_i"]
    corrida = (v.isna() != v.isna().shift()).cumsum()
    validos = v.notna()
    if not validos.any():
        return None, ["STL não executado: NDVI sem nenhum valor válido."]
    comprimentos = validos.groupby(corrida).sum()
    melhor_id = comprimentos.idxmax()
    seg = grade[(corrida == melhor_id) & validos]
    if len(seg) < 2 * n_slots:
        return None, [f"STL não executado: maior trecho contínuo de NDVI tem {len(seg)} observações "
                      f"(mínimo {2 * n_slots})."]
    if len(seg) < validos.sum():
        lacunas.append(f"STL usou o maior trecho contínuo ({len(seg)} de {int(validos.sum())} observações "
                       "válidas); o resto foi deixado de fora por buracos longos.")
    res = STL(seg["ndvi_i"].to_numpy(), period=n_slots, robust=cfg["ndvi"].get("stl_robusto", True)).fit()
    sazonal = pd.Series(res.seasonal).groupby(seg["slot"].to_numpy()).mean()
    var_t = float(np.var(res.resid + res.seasonal))
    forca = max(0.0, 1.0 - float(np.var(res.resid)) / var_t) if var_t > 0 else 0.0
    return {
        "periodo": n_slots,
        "n_observacoes": int(len(seg)),
        "perfil_sazonal_por_slot": {int(k): float(x) for k, x in sazonal.items()},
        "slot_pico": int(sazonal.idxmax()),
        "slot_vale": int(sazonal.idxmin()),
        "forca_sazonalidade": float(forca),
        "desvio_residual": float(np.std(res.resid)),
    }, lacunas


# ----------------------------------------------------------------------------- blocos
def solo_nu(ndvi_q: pd.Series, cfg: dict) -> tuple[dict | None, list[str]]:
    c = cfg["solo_nu"]
    valores = ndvi_q.dropna()
    if valores.empty:
        return None, ["Solo nu não calculado: sem NDVI válido."]
    if c["metodo"] == "fixo":
        if c.get("limiar_fixo") is None:
            raise ValueError("solo_nu.metodo = fixo exige solo_nu.limiar_fixo no config.yaml")
        limiar = float(c["limiar_fixo"])
    else:
        limiar = float(np.percentile(valores, c["percentil"]))
    nu = (ndvi_q < limiar).where(ndvi_q.notna())
    g = nu.groupby(level="quinzena")
    freq = (g.sum() / g.count()).reindex(range(1, N_QUINZENAS + 1))
    n_anos = g.count().reindex(range(1, N_QUINZENAS + 1)).fillna(0).astype(int)
    tipicas = [int(q) for q in freq.index if n_anos[q] >= 3 and freq[q] >= 0.5]
    meses = sorted({(q - 1) // 2 + 1 for q in tipicas})
    lacunas = []
    if c["metodo"] == "percentil":
        lacunas.append(f"Limiar de solo nu = percentil {c['percentil']} do próprio ponto ({limiar:.3f}): "
                       "é relativo ao local, não um valor agronômico absoluto.")
    return {
        "metodo": c["metodo"], "limiar_ndvi": limiar,
        "frequencia_por_quinzena": {int(q): (None if math.isnan(freq[q]) else float(freq[q])) for q in freq.index},
        "n_anos_por_quinzena": {int(q): int(n_anos[q]) for q in n_anos.index},
        "quinzenas_tipicas": tipicas, "meses_tipicos": meses,
        "criterio_tipica": "solo nu em pelo menos 50% dos anos, com no mínimo 3 anos de dados",
    }, lacunas


def _tendencia(anos: np.ndarray, valores: np.ndarray, min_anos: int, nome: str) -> tuple[dict, list[str]]:
    ok = ~np.isnan(valores)
    anos, valores = anos[ok], valores[ok]
    if len(valores) < min_anos:
        return ({"n_anos": int(len(valores)), "resultado": None},
                [f"Tendência de {nome} não calculada: {len(valores)} anos válidos (mínimo {min_anos})."])
    slope, _, lo, hi = theilslopes(valores, anos)
    m = mk.original_test(valores)
    return {"n_anos": int(len(valores)), "inclinacao_por_ano": float(slope),
            "ic95": [float(lo), float(hi)], "mann_kendall": m.trend, "p_valor": float(m.p),
            "resultado": "calculada"}, []


def tendencias(clima_p: pd.DataFrame, ndvi_anual_pico: pd.Series, cfg: dict) -> tuple[dict, list[str]]:
    mc = cfg["cobertura_minima_dados"]
    mn = cfg["tendencia"]["min_anos"]
    cl = clima_p.copy()
    cl["tmedia_c"] = (cl["tmax_c"] + cl["tmin_c"]) / 2
    series = {
        "chuva_anual_mm": _agg_periodo(cl, "chuva_mm", "soma", "ano", mc),
        "temperatura_media_c": _agg_periodo(cl, "tmedia_c", "media", "ano", mc),
        "ndvi_pico": ndvi_anual_pico,
    }
    out, lac = {}, []
    for nome, s in series.items():
        out[nome], l = _tendencia(s.index.to_numpy(), s.to_numpy(dtype=float), mn, nome)
        lac += l
    return out, lac


def veranicos(clima_p: pd.DataFrame, chuva_clim: pd.DataFrame, cfg: dict) -> tuple[dict | None, list[str]]:
    n = cfg["estacao_chuvosa"]["n_quinzenas"]
    media = chuva_clim["media"].reindex(range(1, N_QUINZENAS + 1))
    if media.isna().all():
        return None, ["Veranicos não calculados: sem climatologia de chuva."]
    media = media.fillna(0.0)
    melhor, inicio = -1.0, 1
    for i in range(1, N_QUINZENAS + 1):  # janela circular de n quinzenas com mais chuva
        bloco = [(i - 1 + k) % N_QUINZENAS + 1 for k in range(n)]
        tot = float(media[bloco].sum())
        if tot > melhor:
            melhor, inicio = tot, i
    bloco = [(inicio - 1 + k) % N_QUINZENAS + 1 for k in range(n)]
    dobra = inicio + n - 1 > N_QUINZENAS

    def estacao(datas):
        d = pd.DatetimeIndex(datas)
        q = _quinzena(d)
        dentro = np.isin(q, bloco)
        ano = d.year.to_numpy() - np.where(dobra & (q < inicio), 1, 0)
        return dentro, ano

    cal = pd.DataFrame({"data": pd.date_range(clima_p["data"].min().normalize(), clima_p["data"].max().normalize())})
    cal["dentro"], cal["ano_estacao"] = estacao(cal["data"])
    cal = cal[cal["dentro"]]
    esperado = cal.groupby("ano_estacao").size()
    chuva = clima_p.set_index("data")["chuva_mm"]
    lim = cfg["veranico"]["limiar_chuva_mm"]
    lista = []
    for ano, dias in cal.groupby("ano_estacao"):
        obs = chuva.reindex(dias["data"])
        if obs.notna().sum() / esperado[ano] < cfg["cobertura_minima_dados"]:
            continue
        lista.append({"ano_estacao": int(ano), "maior_veranico_dias": _maior_sequencia((obs < lim).to_numpy())})
    if not lista:
        return None, ["Veranicos não calculados: nenhuma estação chuvosa com dados suficientes."]
    v = np.array([x["maior_veranico_dias"] for x in lista])
    return {
        "quinzenas_estacao_chuvosa": bloco, "limiar_chuva_mm": lim, "n_estacoes": len(lista),
        "por_estacao": lista,
        "distribuicao": {"min": int(v.min()), "mediana": float(np.median(v)),
                         "p90": float(np.percentile(v, 90)), "max": int(v.max())},
        "definicao": f"maior sequência de dias com chuva < {lim} mm dentro das {n} quinzenas mais chuvosas "
                     "da climatologia do ponto",
    }, []


def _confianca(n_anos: dict, frac_interp: float, cfg: dict, n_lacunas_criticas: int) -> str:
    c = cfg["confianca"]
    base = min(n_anos.get("ndvi", 0), n_anos.get("chuva", 0))
    nivel = 2 if base >= c["anos_alta"] else 1 if base >= c["anos_media"] else 0
    if frac_interp > 0.10:
        nivel -= 1
    if n_lacunas_criticas > 0:
        nivel -= 1
    return ["baixa", "media", "alta"][max(0, nivel)]


# ----------------------------------------------------------------------------- orquestração
def diagnosticar_ponto(
    ndvi_p: pd.DataFrame, clima_p: pd.DataFrame, umid_p: pd.DataFrame | None, cfg: dict
) -> tuple[dict, pd.DataFrame]:
    """Diagnóstico de um ponto. Devolve (resultado_json, tabela_anomalias_longa)."""
    mc = cfg["cobertura_minima_dados"]
    clima_p = clima_p.sort_values("data")
    ndvi_p = ndvi_p.sort_values("data")
    lacunas: list[str] = []
    criticas = 0

    # --- NDVI
    grade, info = preparar_ndvi(ndvi_p, cfg)
    anos_ok = info["anos_validos"]
    if info["n_descartadas_baixa_confiabilidade"]:
        lacunas.append(f"{info['n_descartadas_baixa_confiabilidade']} observações de NDVI descartadas "
                       "por baixa confiabilidade do pixel.")
    if info["n_interpoladas"]:
        lacunas.append(f"{info['n_interpoladas']} observações de NDVI interpoladas (buracos de até "
                       f"{cfg['ndvi']['max_interpolacao_consecutiva']} observações); estão marcadas.")
    if info["n_ausentes_restantes"]:
        lacunas.append(f"{info['n_ausentes_restantes']} observações de NDVI seguem ausentes (buracos longos "
                       "ou bordas); não foram preenchidas.")
    grade_ok = grade[grade["ano"].isin(anos_ok)].copy()
    if not anos_ok:
        lacunas.append("Nenhum ano com NDVI suficiente.")
        criticas += 1
    elif len(anos_ok) < cfg["tendencia"]["min_anos"]:
        lacunas.append(f"Poucos anos válidos de NDVI ({len(anos_ok)}).")

    saz, lac = sazonalidade_stl(grade_ok if len(grade_ok) else grade, cfg)
    lacunas += lac

    grade_ok["quinzena"] = _quinzena(grade_ok["data"]) if len(grade_ok) else []
    ndvi_q = (grade_ok.dropna(subset=["ndvi_i"]).groupby(["ano", "quinzena"])["ndvi_i"].mean()
              if len(grade_ok) else pd.Series(dtype=float))
    ndvi_q.index.names = ["ano", "quinzena"]

    # --- clima
    chuva_q = _agg_periodo(clima_p, "chuva_mm", "soma", "quinzena", mc)
    series_q = {"ndvi": ndvi_q, "chuva_mm_quinzena": chuva_q}
    n_anos = {"ndvi": len(anos_ok),
              "chuva": int(_agg_periodo(clima_p, "chuva_mm", "soma", "ano", mc).notna().sum())}
    if umid_p is not None:
        um = umid_p[umid_p["ponto_id"] == clima_p["ponto_id"].iloc[0]].sort_values("data")
        if um.empty:
            lacunas.append("Umidade do solo (SMAP) sem dados para este ponto.")
        else:
            for col in ("sm_superficie", "sm_raiz"):
                series_q[col] = _agg_periodo(um, col, "media", "quinzena", mc)
            n_anos["umidade_solo"] = int(_agg_periodo(um, "sm_raiz", "media", "ano", mc).notna().sum())
    else:
        lacunas.append("Umidade do solo (SMAP) não fornecida; anomalias de umidade não calculadas.")

    climatologia, resumo_anom, tabelas = {}, {}, []
    chuva_clim = None
    for nome, s in series_q.items():
        if s.dropna().empty:
            lacunas.append(f"Sem dados válidos para anomalias de {nome}.")
            continue
        clim, z = _climatologia_e_z(s)
        if nome == "chuva_mm_quinzena":
            chuva_clim = clim
        climatologia[nome] = {int(q): {k: (None if pd.isna(v) else float(v)) for k, v in r.items()}
                              for q, r in clim.iterrows()}
        zv = z.dropna()
        ultimo = zv.index[-1] if len(zv) else None
        resumo_anom[nome] = {
            "n_z_validos": int(len(zv)),
            "n_extremos_secos_ou_baixos(z<=-2)": int((zv <= -2).sum()),
            "n_extremos_altos(z>=2)": int((zv >= 2).sum()),
            "z_mais_recente": None if ultimo is None else {
                "ano": int(ultimo[0]), "quinzena": int(ultimo[1]), "z": float(zv.iloc[-1])},
        }
        t = pd.DataFrame({"valor": s, "z": z}).reset_index()
        t.insert(0, "variavel", nome)
        tabelas.append(t)
        if int((clim["n_anos"] < 3).sum()):
            lacunas.append(f"{nome}: {int((clim['n_anos'] < 3).sum())} quinzenas com menos de 3 anos; "
                           "z-score não calculado nelas.")

    # --- solo nu
    nu, lac = solo_nu(ndvi_q, cfg) if len(ndvi_q) else (None, ["Solo nu não calculado: sem NDVI válido."])
    lacunas += lac

    # --- tendências (pico de NDVI por ano válido)
    pico = (grade_ok.groupby("ano")["ndvi_i"].max() if len(grade_ok) else pd.Series(dtype=float))
    tend, lac = tendencias(clima_p, pico, cfg)
    lacunas += lac

    # --- veranicos
    ver, lac = (veranicos(clima_p, chuva_clim, cfg) if chuva_clim is not None
                else (None, ["Veranicos não calculados: sem climatologia de chuva."]))
    lacunas += lac
    if ver is None:
        criticas += 1

    anomalias = pd.concat(tabelas, ignore_index=True) if tabelas else pd.DataFrame(
        columns=["variavel", "ano", "quinzena", "valor", "z"])
    anomalias.insert(0, "ponto_id", clima_p["ponto_id"].iloc[0])

    resultado = {
        "ponto_id": str(clima_p["ponto_id"].iloc[0]),
        "celula_power": str(clima_p["celula_power"].iloc[0]),
        "periodo": [str(clima_p["data"].min().date()), str(clima_p["data"].max().date())],
        "n_anos_validos": n_anos,
        "ndvi_qualidade": info,
        "sazonalidade_ndvi": saz,
        "climatologia_quinzenal": climatologia,
        "anomalias_resumo": resumo_anom,
        "solo_nu": nu,
        "tendencias": tend,
        "veranicos": ver,
        "lacunas": lacunas,
        "confianca": _confianca(n_anos, info["frac_interpolada"], cfg, criticas),
        "confianca_nota": "heurística de cobertura de dados (anos válidos, interpolação); não é probabilidade",
        "limites": LIMITES,
    }
    return resultado, anomalias


def diagnosticar_todos(entradas: dict, cfg: dict) -> tuple[list[dict], pd.DataFrame]:
    clima, ndvi, umid = entradas["clima"], entradas["ndvi"], entradas["umidade_solo"]
    resultados, tabelas = [], []
    for pid, cl in clima.groupby("ponto_id"):
        nd = ndvi[ndvi["ponto_id"] == pid]
        if nd.empty:
            resultados.append({"ponto_id": str(pid), "celula_power": str(cl["celula_power"].iloc[0]),
                               "lacunas": ["Sem NDVI para este ponto; diagnóstico não calculado."],
                               "confianca": "baixa", "n_anos_validos": {"ndvi": 0}})
            continue
        r, t = diagnosticar_ponto(nd, cl, umid, cfg)
        resultados.append(r)
        tabelas.append(t)
    return resultados, (pd.concat(tabelas, ignore_index=True) if tabelas else pd.DataFrame())


def _json_seguro(o):
    if isinstance(o, dict):
        return {str(k): _json_seguro(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_seguro(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


def salvar_diagnostico(resultados: list[dict], anomalias: pd.DataFrame, pasta: str | Path) -> dict[str, Path]:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho_json = pasta / "diagnostico.json"
    caminho_json.write_text(json.dumps(_json_seguro(resultados), ensure_ascii=False, indent=2), encoding="utf-8")
    caminho_pq = pasta / "anomalias.parquet"
    anomalias.to_parquet(caminho_pq, index=False)
    return {"json": caminho_json, "anomalias": caminho_pq}


if __name__ == "__main__":
    import sys

    from .entrada import RAIZ, carregar_config, carregar_entradas

    cfg = carregar_config()
    if "--sintetico" in sys.argv:
        d = "data/processed/sintetico"
        cfg["caminhos"].update(clima=f"{d}/SINTETICO_clima_diario.parquet", ndvi=f"{d}/SINTETICO_ndvi_16d.parquet",
                               umidade_solo=f"{d}/SINTETICO_umidade_solo.parquet", saida=f"{d}/modelos")
    res, anom = diagnosticar_todos(carregar_entradas(cfg), cfg)
    print(salvar_diagnostico(res, anom, RAIZ / cfg["caminhos"]["saida"]))
    for r in res:
        print(r["ponto_id"], r["confianca"], r["n_anos_validos"], len(r["lacunas"]), "lacunas")
