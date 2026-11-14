"""Adequação climática DENTRO DO CICLO: temperatura média e chuva acumulada para cada início de plantio e cada ano.

Ideia (não código) do modelo EcoCrop descrito no README do OpenCLIM/ecocrop: avaliar muitos inícios de plantio e
tomar o MÍNIMO entre a nota de temperatura e a de chuva (fator limitante). Implementação própria em numpy.

Regras: faixas e duração do ciclo vêm da tabela de culturas (nada embutido aqui); janela com dado faltante é
descartada (nunca preenchida); cultura sem faixa completa ou sem ciclo => 'indeterminada'.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .parametros import Parametros

CHAVES_T = ("temp_min_abs_c", "temp_otima_min_c", "temp_otima_max_c", "temp_max_abs_c")
CHAVES_R = ("chuva_min_abs_mm", "chuva_otima_min_mm", "chuva_otima_max_mm", "chuva_max_abs_mm")
DIAS_ANO_REF = 365  # janelas 'anual' usam 365 dias; offsets de início contados em dias desde 1º/jan


@dataclass
class ClimaPonto:
    """Série diária contínua (ano_ini-01-01 a ano_fim-12-31) de um ponto; NaN onde faltar dado."""
    ponto_id: str
    ano_ini: int
    ano_fim: int
    tmed: np.ndarray
    chuva: np.ndarray
    lacunas: list[str] = field(default_factory=list)

    @property
    def anos(self) -> list[int]:
        return list(range(self.ano_ini, self.ano_fim + 1))

    @classmethod
    def de_dataframe(cls, df: pd.DataFrame, ponto_id: str, ano_ini: int = 2001, ano_fim: int = 2024) -> "ClimaPonto":
        d = df[(df["ponto_id"] == ponto_id) & (df["data"].dt.year.between(ano_ini, ano_fim))]
        idx = pd.date_range(f"{ano_ini}-01-01", f"{ano_fim}-12-31", freq="D")
        lac = []
        if d.empty:
            lac.append(f"clima: sem linhas diárias para {ponto_id}.")
            nan = np.full(len(idx), np.nan)
            return cls(ponto_id, ano_ini, ano_fim, nan, nan.copy(), lac)
        d = d.drop_duplicates("data").set_index("data").reindex(idx)
        tmed = ((d["tmax_c"] + d["tmin_c"]) / 2).to_numpy(float)
        chuva = d["chuva_mm"].to_numpy(float)
        falt = int(np.isnan(tmed).sum() + np.isnan(chuva).sum())
        if falt:
            lac.append(f"clima: {falt} valores diários ausentes (temperatura+chuva); janelas que os contêm foram descartadas.")
        return cls(ponto_id, ano_ini, ano_fim, tmed, chuva, lac)


def trapezio(x, mn, omn, omx, mx):
    """Nota 0-1 trapezoidal (vetorizada; NaN em x => NaN). Mesma forma de motor._nota_trapezio."""
    x = np.asarray(x, dtype=float)
    sobe = (x - mn) / (omn - mn) if omn > mn else np.where(x > mn, 1.0, 0.0)
    desce = (mx - x) / (mx - omx) if mx > omx else np.where(x < mx, 1.0, 0.0)
    nota = np.where((x <= mn) | (x >= mx), 0.0, np.where(x < omn, sobe, np.where(x <= omx, 1.0, desce)))
    return np.where(np.isnan(x), np.nan, nota)


def _faixa(tab: dict, cid: str, chaves: tuple) -> tuple | None:
    vals = []
    for k in chaves:
        d = tab[cid]["atributos"].get(k)
        if d is None:
            return None
        vals.append(d["valor"])
    return tuple(vals)


def duracao_ciclo(tab: dict, cid: str, modo: str) -> tuple[int | None, list[str]]:
    """Duração (dias) pelo modo declarado; None + lacuna se a tabela não tem ciclo_min/max (ou são incoerentes)."""
    a, b = (tab[cid]["atributos"].get("ciclo_min_dias"), tab[cid]["atributos"].get("ciclo_max_dias"))
    if a is None or b is None:
        return None, [f"EcoCrop sem ciclo_min/ciclo_max para {cid}: lacuna (duração do ciclo indeterminada)"]
    lo, hi = float(a["valor"]), float(b["valor"])
    if lo <= 0 or hi < lo:
        return None, [f"ciclo incoerente na tabela para {cid} ({lo}–{hi})"]
    dur = {"min": lo, "max": hi, "medio": (lo + hi) / 2}[modo]
    return int(round(dur)), []


def indices_inicio(clima: ClimaPonto, passo: int) -> np.ndarray:
    """Índice (na série contínua) de cada início: matriz [ano, início]. Inícios: 1º/jan + k*passo (k*passo < 365)."""
    offs = np.arange(0, DIAS_ANO_REF, passo)
    base = np.array([(np.datetime64(f"{a}-01-01") - np.datetime64(f"{clima.ano_ini}-01-01")).astype(int)
                     for a in clima.anos])
    return base[:, None] + offs[None, :]


def _somas_janela(x: np.ndarray, ini: np.ndarray, dur: int) -> tuple[np.ndarray, np.ndarray]:
    """Soma de x em [ini, ini+dur) e máscara de janela válida (dentro da série e sem NaN)."""
    ok = ~np.isnan(x)
    c = np.concatenate([[0.0], np.cumsum(np.where(ok, x, 0.0))])
    n = np.concatenate([[0], np.cumsum(ok.astype(int))])
    fim = ini + dur
    dentro = fim <= len(x)
    f = np.minimum(fim, len(x))
    soma = c[f] - c[ini]
    valido = dentro & ((n[f] - n[ini]) == dur)
    return np.where(valido, soma, np.nan), valido


def notas_ciclo(tab: dict, cid: str, clima: ClimaPonto, p: Parametros) -> dict:
    """Notas [ano, início] de temperatura e de chuva da cultura. Devolve estado 'avaliavel' ou 'indeterminada'."""
    ft, fr = _faixa(tab, cid, CHAVES_T), _faixa(tab, cid, CHAVES_R)
    lac = []
    if ft is None:
        lac.append(f"EcoCrop sem faixa completa de temperatura para {cid}: lacuna")
    if fr is None:
        lac.append(f"EcoCrop sem faixa completa de chuva para {cid}: lacuna")
    dur, l2 = duracao_ciclo(tab, cid, p.ciclo_modo)
    lac += l2
    ov = dict(p.ciclo_override)
    if cid in ov and not l2:      # injeção opcional da duração (padrão: vazio, nada muda)
        dur = int(ov[cid])
    if lac:
        return {"estado": "indeterminada", "lacunas": lac, "dur": dur}
    ini = indices_inicio(clima, p.passo_inicio_dias)
    soma_t, vt = _somas_janela(clima.tmed, ini, dur)
    dur_r = dur if p.chuva_modo == "ciclo" else DIAS_ANO_REF
    soma_r, vr = _somas_janela(clima.chuva, ini, dur_r)
    tmedia = soma_t / dur
    nt, nr = trapezio(tmedia, *ft), trapezio(soma_r, *fr)
    zinfo = None
    if p.usar_zarc:
        from . import zarc
        geo = zarc.geocodigo_do_ponto(clima.ponto_id)
        z = zarc.janela(geo, cid, p.zarc_risco, p.zarc_solo)
        aprox = False
        if z["permitido"] is None and cid not in zarc.MAPA_CULTURAS and geo is not None:    # sem ZARC: janela aproximada (anuais)
            za = zarc.janela_aproximada_anuais(geo, p.zarc_risco, p.zarc_solo)
            if za["permitido"] is not None:
                z, aprox = {**za, "recurso": "aproximada pelas culturas anuais"}, True
        if z["permitido"] is None:
            zinfo = {"aplicado": False, "motivo": z["motivo"]}
        else:
            offs = np.arange(0, DIAS_ANO_REF, p.passo_inicio_dias)
            ok_ini = z["permitido"][zarc.decendios_do_inicio(offs)]            # [início]
            nt = np.where(ok_ini[None, :] | np.isnan(nt), nt, 0.0)           # fora da janela: nota 0 (NaN segue NaN)
            nr = np.where(ok_ini[None, :] | np.isnan(nr), nr, 0.0)
            zinfo = {"aplicado": True, "recurso": z["recurso"], "risco": z["risco"], "solo": z["solo"],
                     "decendios_permitidos": z["n_decendios"], "inicios_permitidos": int(ok_ini.sum()), "aproximada": aprox,
                     "aviso": z.get("aviso")}
    return {"estado": "avaliavel", "lacunas": [], "zarc": zinfo, "dur": dur, "dur_chuva": dur_r, "tmedia": tmedia, "chuva": soma_r,
            "nt": nt, "nr": nr, "valido": vt & vr}


def data_do_inicio(k: int, passo: int) -> str:
    """Rótulo 'dd/mm' do início k em ano não bissexto (referência de calendário; o cálculo usa dias corridos)."""
    d = pd.Timestamp("2001-01-01") + pd.Timedelta(days=int(k * passo))
    return f"{d.day:02d}/{d.month:02d}"


def resumir(av: dict, anos_ok: np.ndarray, p: Parametros) -> dict:
    """Resumo da cultura sobre os anos `anos_ok` (máscara). Escolhe a melhor janela por adequação média entre anos.

    Empate na média (platô de inícios igualmente bons): desempata pela fração de anos viáveis e, persistindo, pelo
    início central do platô (não por nome).
    """
    nt, nr = av["nt"][anos_ok], av["nr"][anos_ok]
    adeq = np.minimum(nt, nr)
    media = np.round(np.nanmean(adeq, axis=0), 9)
    p_viavel = np.round((adeq > 0).mean(axis=0), 9)
    melhor_media = media.max()
    plato = np.flatnonzero(media == melhor_media)
    melhor_pv = p_viavel[plato].max()
    plato = plato[p_viavel[plato] == melhor_pv]
    k = int(plato[(len(plato) - 1) // 2])
    viavel_algum = bool((p_viavel >= 1 - p.risco_max - 1e-12).any())
    a = adeq[:, k]
    return {"k": k, "inicio": data_do_inicio(k, p.passo_inicio_dias), "decendio": k + 1, "plato": [int(x) for x in plato],
            "adeq_media": float(media[k]), "p_ano_viavel": float(p_viavel[k]),
            "adeq_por_ano": a, "nt_por_ano": nt[:, k], "nr_por_ano": nr[:, k],
            "adeq_p10": float(np.percentile(a, 10)), "adeq_p50": float(np.percentile(a, 50)),
            "adeq_p90": float(np.percentile(a, 90)),
            "tmedia_ciclo": float(np.mean(av["tmedia"][anos_ok][:, k])),
            "chuva_ciclo_mm": float(np.mean(av["chuva"][anos_ok][:, k])),
            "viavel_no_risco": viavel_algum, "media_por_inicio": media, "p_viavel_por_inicio": p_viavel}


def anos_comuns(avaliacoes: list[dict], clima: ClimaPonto) -> np.ndarray:
    """Máscara de anos em que TODOS os inícios de TODAS as culturas avaliáveis têm janela completa."""
    ok = np.ones(len(clima.anos), dtype=bool)
    for av in avaliacoes:
        if av["estado"] == "avaliavel":
            ok &= av["valido"].all(axis=1)
    return ok
