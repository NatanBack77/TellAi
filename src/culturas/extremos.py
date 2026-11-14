"""A4: calor e chuva extrema por ano, a partir do POWER diário (Tmax, chuva). Funções puras, sem Streamlit.

Definições RELATIVAS ao clima do próprio local (nenhum limiar absoluto foi escolhido):
- dia quente  = Tmax acima do percentil 90 do mesmo dia do calendário (janela de 5 dias centrada) na série do local
  (ETCCDI, índice TX90p: https://etccdi.pacificclimate.org/list_27_indices.shtml ; lido em 2026-11-13).
- dia de chuva extrema = chuva acima do percentil 95 dos dias chuvosos (chuva >= 1 mm) do local
  (ETCCDI, R95p: "wet day w (RR >= 1.0 mm)", percentil 95 dos dias chuvosos).
Diferenças em relação ao ETCCDI (declaradas na saída): o período-base é a série do local (2001-2024 nos dados do projeto),
não 1961-1990 (o POWER usado aqui não tem esse período), e não há bootstrap no período-base.
Tendência: Theil-Sen + Mann-Kendall de `src.modelos.diagnostico._tendencia` (reuso).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.modelos.diagnostico import _tendencia

RAIZ = Path(__file__).resolve().parents[2]
ARQ_CLIMA = RAIZ / "data/processed/clima_diario.parquet"

PERC_QUENTE = 90.0   # ETCCDI TX90p
PERC_CHUVA = 95.0    # ETCCDI R95p
DIA_CHUVOSO_MM = 1.0  # ETCCDI: dia chuvoso = RR >= 1,0 mm
JANELA_DIAS = 5       # ETCCDI: janela de 5 dias centrada no dia do calendário
MIN_ANOS_BASE = 10        # PARÂMETRO (SUPOSIÇÃO): mínimo de anos para definir o percentil do local
MIN_ANOS_TENDENCIA = 10   # PARÂMETRO (SUPOSIÇÃO): mínimo de anos para tendência
MIN_COBERTURA_ANO = 0.9   # PARÂMETRO (SUPOSIÇÃO): fração mínima de dias válidos no ano

FONTE = "ETCCDI, 27 core indices (TX90p, R95p, Rx1day): https://etccdi.pacificclimate.org/list_27_indices.shtml"
AVISO_ESCALA = ("O clima do POWER (reanálise/satélite) vem de células de ~50 km: o calor e a chuva da sua roça podem ser bem "
                "diferentes. Os índices descrevem o passado do local e não preveem nada. A avaliar com técnico local.")
AVISO_TENDENCIA = ("Tendência de poucos anos (série curta) é frágil: use só como sinal para conversar com o técnico local, "
                   "não como prova de mudança do clima.")
AVISO_CHUVA_DIARIA = "Chuva diária (24 h) não mostra a intensidade em minutos; chuva forte e curta pode ficar subestimada."


def _doy365(datas: pd.DatetimeIndex) -> np.ndarray:
    """Dia do ano 1..365 (29/fev vira 28/fev; depois de fev, em ano bissexto, desloca 1 dia)."""
    doy = datas.day_of_year.to_numpy().copy()
    bis = datas.is_leap_year
    doy = np.where(bis & (datas.month > 2), doy - 1, doy)
    doy = np.where(bis & (datas.month == 2) & (datas.day == 29), 59, doy)
    return np.clip(doy, 1, 365)


def limiar_calendario(datas: pd.DatetimeIndex, valores: np.ndarray, perc: float = PERC_QUENTE,
                      janela: int = JANELA_DIAS) -> np.ndarray:
    """Percentil `perc` por dia do calendário (1..365; índice 0 = dia 1), janela centrada, circular. NaN onde faltar dado."""
    doy = _doy365(datas)
    anos = datas.year.to_numpy()
    ua = np.unique(anos)
    mat = np.full((len(ua), 365), np.nan)
    mat[np.searchsorted(ua, anos), doy - 1] = valores
    meio = janela // 2
    out = np.full(365, np.nan)
    for d in range(365):
        bloco = mat[:, [(d + k) % 365 for k in range(-meio, meio + 1)]].ravel()
        bloco = bloco[~np.isnan(bloco)]
        if bloco.size:
            out[d] = np.percentile(bloco, perc)
    return out


def indices_extremos(clima: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Índices por ano. `clima` precisa de colunas data, tmax_c, chuva_mm. Devolve (tabela por ano, parâmetros usados).

    Colunas: ano, dias_validos, dias_quentes (Tmax > P90 do dia do calendário), dias_chuva_extrema (chuva > P95 dos dias
    chuvosos), chuva_em_dias_extremos_mm, rx1day_mm (maior chuva em 1 dia), chuva_total_mm.
    Tabela vazia e `parametros['lacunas']` preenchido quando faltar dado.
    """
    lac: list[str] = []
    cols = {"data", "tmax_c", "chuva_mm"}
    if clima is None or len(clima) == 0 or not cols <= set(clima.columns):
        return pd.DataFrame(), {"lacunas": ["Sem série diária de Tmax e chuva para o local: índices de calor e chuva extrema não calculados."]}
    df = clima.copy()
    df["data"] = pd.to_datetime(df["data"])
    df = df.sort_values("data").drop_duplicates("data")
    n_anos = df["data"].dt.year.nunique()
    if n_anos < MIN_ANOS_BASE:
        return pd.DataFrame(), {"lacunas": [f"Só {n_anos} anos de dados (mínimo {MIN_ANOS_BASE} para definir o percentil do local): índices não calculados."]}
    datas = pd.DatetimeIndex(df["data"])
    tmax = df["tmax_c"].to_numpy(float)
    chuva = df["chuva_mm"].to_numpy(float)
    lim_t = limiar_calendario(datas, tmax, PERC_QUENTE)
    chuvosos = chuva[~np.isnan(chuva) & (chuva >= DIA_CHUVOSO_MM)]
    if chuvosos.size < 30:
        lim_c = np.nan
        lac.append(f"Menos de 30 dias chuvosos (>= {DIA_CHUVOSO_MM:g} mm): percentil de chuva extrema não definido.")
    else:
        lim_c = float(np.percentile(chuvosos, PERC_CHUVA))
    doy = _doy365(datas)
    quente = tmax > lim_t[doy - 1]  # NaN compara como False
    quente_val = ~np.isnan(tmax) & ~np.isnan(lim_t[doy - 1])
    extrema = (chuva > lim_c) if not np.isnan(lim_c) else np.zeros(len(chuva), bool)
    d = pd.DataFrame({"ano": datas.year, "q": quente & quente_val, "e": extrema & ~np.isnan(chuva),
                      "chuva": chuva, "tmax_ok": ~np.isnan(tmax), "chuva_ok": ~np.isnan(chuva)})
    d["chuva_ext"] = np.where(d["e"], d["chuva"], 0.0)
    g = d.groupby("ano")
    tab = pd.DataFrame({
        "dias_validos": g["chuva_ok"].sum().astype(int),
        "dias_quentes": g["q"].sum().astype(int),
        "dias_chuva_extrema": g["e"].sum().astype(int),
        "chuva_em_dias_extremos_mm": g["chuva_ext"].sum().round(2),
        "rx1day_mm": g["chuva"].max(),
        "chuva_total_mm": g["chuva"].sum(min_count=1).round(2),
    })
    dias_ano = pd.Series(pd.DatetimeIndex(pd.date_range(f"{tab.index.min()}-01-01", f"{tab.index.max()}-12-31")).year).value_counts()
    cob = tab["dias_validos"] / dias_ano.reindex(tab.index).to_numpy()
    incompletos = cob[cob < MIN_COBERTURA_ANO].index.tolist()
    if incompletos:
        lac.append(f"Anos com menos de {MIN_COBERTURA_ANO:.0%} dos dias (excluídos das tendências): {incompletos}.")
        tab.loc[incompletos, ["dias_quentes", "dias_chuva_extrema", "chuva_em_dias_extremos_mm", "rx1day_mm", "chuva_total_mm"]] = np.nan
    tab = tab.reset_index()
    params = {
        "calor": f"dia com Tmax acima do percentil {PERC_QUENTE:g} do mesmo dia do calendário (janela de {JANELA_DIAS} dias), na série do próprio local",
        "chuva_extrema": f"dia com chuva acima do percentil {PERC_CHUVA:g} dos dias chuvosos (>= {DIA_CHUVOSO_MM:g} mm) do próprio local",
        "limiar_chuva_extrema_mm": None if np.isnan(lim_c) else round(lim_c, 2),
        "limiar_tmax_c_min": float(np.nanmin(lim_t)), "limiar_tmax_c_max": float(np.nanmax(lim_t)),
        "periodo_base": f"{int(tab['ano'].min())}-{int(tab['ano'].max())} (série do local; o ETCCDI usa 1961-1990, indisponível aqui)",
        "fonte_definicao": FONTE, "n_anos": int(n_anos), "lacunas": lac,
    }
    return tab, params


def tendencia_extremos(tab: pd.DataFrame) -> tuple[dict, list[str]]:
    """Theil-Sen + Mann-Kendall (reuso de diagnostico._tendencia) por índice. Sem dado: resultado None + lacuna."""
    nomes = {"dias_quentes": "dias quentes", "dias_chuva_extrema": "dias de chuva extrema", "rx1day_mm": "maior chuva em 1 dia"}
    saida, lac = {}, []
    for col, nome in nomes.items():
        if tab is None or len(tab) == 0 or col not in tab:
            saida[col] = {"n_anos": 0, "resultado": None}
            lac.append(f"Tendência de {nome} não calculada: sem dados.")
            continue
        r, l = _tendencia(tab["ano"].to_numpy(float), tab[col].to_numpy(float), MIN_ANOS_TENDENCIA, nome)
        saida[col] = r
        lac += l
    return saida, lac


def carregar_clima_ponto(ponto_id: str, arq: Path = ARQ_CLIMA) -> pd.DataFrame | None:
    if not Path(arq).exists():
        return None
    d = pd.read_parquet(arq, filters=[("ponto_id", "==", ponto_id)], columns=["data", "tmax_c", "chuva_mm"])
    return d if len(d) else None


def resumo_extremos(clima: pd.DataFrame | None) -> dict:
    """Pacote pronto para a tela: tabela por ano, parâmetros declarados, tendências, lacunas e avisos."""
    tab, params = indices_extremos(clima) if clima is not None else (pd.DataFrame(), {"lacunas": ["Sem série diária do local."]})
    lac = list(params.get("lacunas", []))
    tend, l2 = tendencia_extremos(tab)
    return {"disponivel": len(tab) > 0, "tabela_por_ano": tab, "definicoes": {k: v for k, v in params.items() if k != "lacunas"},
            "tendencias": tend, "lacunas": lac + l2,
            "avisos": [AVISO_ESCALA, AVISO_TENDENCIA, AVISO_CHUVA_DIARIA]}
