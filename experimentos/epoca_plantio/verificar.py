"""Verifica a ÉPOCA de plantio do motor (epoca_modo='zarc_ou_ciclo') contra o ZARC e a estação chuvosa, em 15 municípios do CE.

Para cada município x cultura: melhor início ANTIGO (anual_legado), NOVO (zarc_ou_ciclo), decêndios do ZARC (se houver) e se o início
novo cai na estação chuvosa do local. Estação chuvosa = os 4 meses consecutivos de maior chuva média (2001-2024) + o mês anterior
(plantio antecipado ao 1º mês chuvoso); é um CRITÉRIO DE CHECAGEM nosso, não norma agronômica. Divergências são listadas, não escondidas.
Uso: python -m experimentos.epoca_plantio.verificar
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from experimentos.fao_melhorias import comum as C
from src.culturas import ciclo, motor, zarc
from src.culturas.parametros import Parametros
from src.culturas.tabela_culturas import carregar

SAIDA = Path(__file__).parent / "saida"
SAIDA.mkdir(exist_ok=True)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def estacao_chuvosa(serie) -> tuple[set[int], list[float]]:
    d = pd.DataFrame({"data": pd.date_range(f"{serie.ano_ini}-01-01", periods=len(serie.chuva)), "c": serie.chuva})
    m = d.groupby([d.data.dt.year, d.data.dt.month]).c.sum().groupby(level=1).mean().reindex(range(1, 13)).to_numpy()
    soma4 = [sum(m[(i + j) % 12] for j in range(4)) for i in range(12)]
    i0 = int(np.argmax(soma4))
    bloco = {(i0 + j) % 12 + 1 for j in range(4)}
    return bloco | {(i0 - 1) % 12 + 1}, [round(float(x), 1) for x in m]


def mes_do_inicio(k: int, passo: int) -> int:
    return int((pd.Timestamp("2001-01-01") + pd.Timedelta(days=k * passo)).month)


def rodar():
    tab, clima = carregar(), C.carregar_clima()
    novo, velho = Parametros(), Parametros(epoca_modo="anual_legado", usar_zarc=False)
    linhas = []
    for m in C.escolher_municipios(15):
        pid = m["ponto_id"]
        serie = ciclo.ClimaPonto.de_dataframe(clima, pid, 2001, 2024)
        chuvoso, mensal = estacao_chuvosa(serie)
        av_n, av_v = motor.avaliar_local(tab, serie, novo), motor.avaliar_local(tab, serie, velho)
        geo = zarc.geocodigo_do_ponto(pid)
        for cid in tab:
            rn, rv = av_n["culturas"][cid], av_v["culturas"][cid]
            if rn["res"] is None:
                continue
            o = motor._origem_epoca(rn["av"], novo)
            z = zarc.janela(geo, cid, 30)["permitido"]
            mz = sorted({mes_do_inicio(k, 10) for k in range(37) if k < 36 and z[min(k, 35)]}) if z is not None else None
            kn, kv = rn["res"]["k"], rv["res"]["k"]
            mn = mes_do_inicio(kn, 10)
            linhas.append({"ponto_id": pid, "chuva_anual_mm": round(m["chuva_anual"]), "cultura": cid, "estado": rn["estado"],
                           "epoca_fonte": o["epoca_fonte"], "inicio_novo": rn["res"]["inicio"], "mes_novo": MESES[mn - 1],
                           "inicio_antigo": rv["res"]["inicio"], "mes_antigo": MESES[mes_do_inicio(kv, 10) - 1],
                           "meses_zarc": None if mz is None else [MESES[x - 1] for x in mz],
                           "novo_dentro_zarc": None if z is None else bool(z[min(kn, 35)]),
                           "novo_na_estacao_chuvosa": mn in chuvoso, "meses_chuvosos": [MESES[x - 1] for x in sorted(chuvoso)],
                           "adeq_novo": round(rn["res"]["adeq_media"], 3), "adeq_antigo": round(rv["res"]["adeq_media"], 3),
                           "dur_dias": rn["av"]["dur"], "agua_epoca": rn["av"].get("epoca_agua")})
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    df = rodar()
    df.to_csv(SAIDA / "epoca_verificacao.csv", index=False)
    print(len(df), "linhas")
    for fonte, g in df.groupby("epoca_fonte"):
        print(fonte, len(g), "dentro ZARC:", g.novo_dentro_zarc.dropna().mean() if g.novo_dentro_zarc.notna().any() else None,
              "na estação chuvosa:", round(g.novo_na_estacao_chuvosa.mean(), 3))
    print(df.groupby("cultura").agg(n=("ponto_id", "size"), chuvosa=("novo_na_estacao_chuvosa", "mean"),
                                    meses_novo=("mes_novo", lambda s: ",".join(sorted(set(s)))),
                                    meses_antigo=("mes_antigo", lambda s: ",".join(sorted(set(s))))).to_string())
    print("\nDIVERGENTES (início novo fora da estação chuvosa):")
    print(df[~df.novo_na_estacao_chuvosa][["ponto_id", "cultura", "epoca_fonte", "mes_novo", "meses_chuvosos", "dur_dias"]].to_string())
