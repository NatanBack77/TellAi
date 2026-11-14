"""ETo de Hargreaves-Samani e saldo hídrico `chuva - ETo` por quinzena. Funções puras (numpy/pandas), sem Streamlit.

FONTE LIDA (FAO Irrigation and Drainage Paper 56, Allen et al. 1998, cap. 3, https://www.fao.org/4/x0490e/x0490e07.htm, lida em 2026-11-13):
  Eq. 52: "ETo = 0.0023 (Tmean + 17.8) (Tmax - Tmin)^0.5 Ra", "Units for both ETo and Ra in Equation 52 are mm day-1".
  Eq. 9: "Tmean for 24-hour periods is defined as the mean of the daily maximum (Tmax) and minimum temperatures (Tmin)".
  Ra diária (Eq. 21 a 25): Gsc = 0.0820 MJ m-2 min-1; Ra = 24(60)/pi * Gsc * dr * [ws sin(fi) sin(d) + cos(fi) cos(d) sin(ws)];
  dr = 1 + 0.033 cos(2 pi J/365); d = 0.409 sin(2 pi J/365 - 1.39); ws = arccos[-tan(fi) tan(d)]; fi em radianos (negativo no sul);
  "equivalent evaporation in mm day-1 is obtained by multiplying Ra by 0.408 (Equation 20)".
  (As equações 21, 23 e 24 são imagens na página; a forma acima foi lida no Exemplo 8 da mesma página, que as substitui com números.
  O teste reproduz o Exemplo 8: 20°S, J=246 -> Ra = 32.2 MJ m-2 d-1 = 13.1 mm/dia.)
  A FAO diz: "Equation 52 should be verified in each new region by comparing with estimates by the FAO Penman-Monteith equation";
  ESSA VERIFICAÇÃO NÃO FOI FEITA neste projeto (faltam vento e umidade): a ETo daqui é ESTIMATIVA, sem validação local.

AVISOS OBRIGATÓRIOS: ETo NÃO é o consumo da cultura (ETc = Kc x ETo; o Kc NÃO está na tabela de culturas: lacuna). `chuva - ETo` é um
indicador de oferta x demanda atmosférica, NÃO é o balanço hídrico do solo (sem armazenamento, escoamento, infiltração nem irrigação).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GSC = 0.0820            # MJ m-2 min-1 (FAO-56, Eq. 21)
EQUIV_EVAP = 0.408      # mm por MJ m-2 (FAO-56, Eq. 20)
COEF_HS = 0.0023        # FAO-56, Eq. 52
DESLOC_T = 17.8         # FAO-56, Eq. 52

FONTE = {"nome": "FAO-56 (Allen et al., 1998), cap. 3, Eq. 52 e Eq. 20 a 25", "url": "https://www.fao.org/4/x0490e/x0490e07.htm"}
AVISO_ETO = ("ETo (Hargreaves-Samani) é a evapotranspiração de REFERÊNCIA, NÃO o consumo da cultura: ETc = Kc x ETo, e o Kc NÃO está "
             "na tabela de culturas (lacuna). 'chuva - ETo' não é balanço hídrico do solo (sem armazenamento, escoamento, infiltração "
             "nem irrigação). A equação não foi verificada contra Penman-Monteith neste local (faltam vento e umidade). A avaliar com técnico local.")
LACUNA_KC = "Kc (coeficiente de cultura) não consta na tabela de culturas: ETc = Kc x ETo não é calculada."
PENMAN_PARAMETROS_A_CONFIRMAR = ["vento a 2 m (ex.: WS2M no POWER)", "umidade relativa (ex.: RH2M no POWER)",
                                 "NÃO coletados; nomes de parâmetros a confirmar na documentação do POWER antes de qualquer coleta"]


def dia_do_ano(datas) -> np.ndarray:
    """J = dia do ano (1 a 365/366), como no FAO-56."""
    return pd.DatetimeIndex(datas).day_of_year.to_numpy().astype(float)


def radiacao_extraterrestre_mj(lat_graus: float, j) -> np.ndarray:
    """Ra diária (MJ m-2 dia-1), FAO-56 Eq. 21-25. `lat_graus` negativa no hemisfério sul."""
    if not -90.0 <= lat_graus <= 90.0:
        raise ValueError("latitude fora de [-90, 90]")
    j = np.asarray(j, float)
    fi = np.deg2rad(lat_graus)
    dr = 1.0 + 0.033 * np.cos(2.0 * np.pi * j / 365.0)
    d = 0.409 * np.sin(2.0 * np.pi * j / 365.0 - 1.39)
    ws = np.arccos(np.clip(-np.tan(fi) * np.tan(d), -1.0, 1.0))
    return 24.0 * 60.0 / np.pi * GSC * dr * (ws * np.sin(fi) * np.sin(d) + np.cos(fi) * np.cos(d) * np.sin(ws))


def radiacao_extraterrestre_mm(lat_graus: float, j) -> np.ndarray:
    """Ra em mm/dia de evaporação equivalente (Eq. 20)."""
    return EQUIV_EVAP * radiacao_extraterrestre_mj(lat_graus, j)


def eto_hargreaves(tmax, tmin, ra_mm) -> np.ndarray:
    """ETo (mm/dia), Eq. 52. Tmean = (Tmax+Tmin)/2. Tmax < Tmin ou NaN -> NaN (nunca preenchido nem truncado em silêncio)."""
    tmax, tmin, ra_mm = (np.asarray(x, float) for x in (tmax, tmin, ra_mm))
    amp = tmax - tmin
    ok = np.isfinite(amp) & (amp >= 0) & np.isfinite(ra_mm)
    out = np.full(np.broadcast(tmax, tmin, ra_mm).shape, np.nan)
    tmean = (tmax + tmin) / 2.0
    with np.errstate(invalid="ignore"):
        val = COEF_HS * (tmean + DESLOC_T) * np.sqrt(np.where(ok, amp, np.nan)) * ra_mm
    return np.where(ok, val, out)


def quinzena_id(datas) -> np.ndarray:
    """1 a 24: mês*2-1 (dias 1-15) ou mês*2 (dia 16 até o fim do mês). DEFINIÇÃO deste projeto, não da FAO."""
    d = pd.DatetimeIndex(datas)
    return ((d.month - 1) * 2 + 1 + (d.day > 15)).to_numpy()


def eto_diaria(clima: pd.DataFrame, lat_graus: float) -> pd.DataFrame:
    """Colunas esperadas: data, chuva_mm, tmax_c, tmin_c (e radiacao opcional). Devolve o DataFrame com ra_mm e eto_mm."""
    d = clima.sort_values("data").reset_index(drop=True).copy()
    d["ra_mm"] = radiacao_extraterrestre_mm(lat_graus, dia_do_ano(d["data"]))
    d["eto_mm"] = eto_hargreaves(d["tmax_c"], d["tmin_c"], d["ra_mm"])
    return d


def saldo_quinzenal(clima: pd.DataFrame, lat_graus: float, min_dias: int = 12) -> pd.DataFrame:
    """Saldo `chuva - ETo` por quinzena de cada ano (mm). Quinzena com menos de `min_dias` dias com dado completo = NaN (lacuna)."""
    d = eto_diaria(clima, lat_graus)
    d["ano"], d["quinzena"] = d["data"].dt.year, quinzena_id(d["data"])
    d["ok"] = d["eto_mm"].notna() & d["chuva_mm"].notna()
    d["chuva_ok"] = d["chuva_mm"].where(d["ok"])
    d["eto_ok"] = d["eto_mm"].where(d["ok"])
    g = d.groupby(["ano", "quinzena"]).agg(chuva_mm=("chuva_ok", "sum"), eto_mm=("eto_ok", "sum"), dias_com_dado=("ok", "sum"),
                                           dias=("ok", "size")).reset_index()
    inc = g["dias_com_dado"] < min_dias
    g.loc[inc, ["chuva_mm", "eto_mm"]] = np.nan
    g["saldo_mm"] = g["chuva_mm"] - g["eto_mm"]
    return g


def climatologia_quinzenal(clima: pd.DataFrame, lat_graus: float, min_anos: int = 10) -> pd.DataFrame:
    """Média e faixa p10-p90 (entre anos) por quinzena (1-24). Quinzena com menos de `min_anos` anos com dado = NaN."""
    s = saldo_quinzenal(clima, lat_graus)
    def agg(g):
        v = g["saldo_mm"].dropna()
        if len(v) < min_anos:
            return pd.Series({"chuva_mm": np.nan, "eto_mm": np.nan, "saldo_mm": np.nan, "saldo_p10": np.nan, "saldo_p90": np.nan, "n_anos": len(v)})
        return pd.Series({"chuva_mm": g["chuva_mm"].mean(), "eto_mm": g["eto_mm"].mean(), "saldo_mm": v.mean(),
                          "saldo_p10": v.quantile(0.10), "saldo_p90": v.quantile(0.90), "n_anos": len(v)})
    return s.groupby("quinzena").apply(agg, include_groups=False).reset_index()


def conferencia_radiacao(clima: pd.DataFrame, lat_graus: float) -> dict:
    """CONFERÊNCIA (não entra no cálculo): ALLSKY_SFC_SW_DWN do POWER (coluna `radiacao`, MJ m-2 dia-1, ver observação) contra Ra.
    Radiação na superfície não pode passar da extraterrestre; a razão média é só um sinal de sanidade, não uma validação da ETo."""
    if "radiacao" not in clima:
        return {"disponivel": False, "motivo": "coluna radiacao ausente"}
    d = clima.sort_values("data")
    ra = radiacao_extraterrestre_mj(lat_graus, dia_do_ano(d["data"]))
    r = d["radiacao"].to_numpy(float)
    ok = np.isfinite(r) & np.isfinite(ra)
    if ok.sum() < 30:
        return {"disponivel": False, "motivo": "poucos dias com radiação"}
    return {"disponivel": True, "razao_media_rs_ra": float(np.mean(r[ok] / ra[ok])), "frac_dias_rs_maior_que_ra": float(np.mean(r[ok] > ra[ok])),
            "n_dias": int(ok.sum()),
            "nota": "Conferência apenas. A unidade da coluna `radiacao` (MJ m-2 dia-1, ALLSKY_SFC_SW_DWN) deve ser confirmada na documentação do POWER; "
                    "a ETo de Hargreaves NÃO usa essa radiação (usa Tmax, Tmin e Ra por latitude e dia)."}
