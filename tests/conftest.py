"""Fixtures compartilhadas. Clima aqui é SINTÉTICO: só testa lógica, nunca é resultado real."""
import numpy as np
import pandas as pd
import pytest


def clima_sintetico(pid="x_ce", anos=range(2001, 2025), chuva_pico=8.0, chuva_base=0.0, meses_chuva=(1, 2, 3, 4, 5),
                    tmax=34.0, tmin=22.0, fator_ano=None) -> pd.DataFrame:
    """Chuva diária = `chuva_pico` nos meses chuvosos e `chuva_base` no resto; `fator_ano` {ano: multiplicador}."""
    datas = pd.date_range(f"{min(anos)}-01-01", f"{max(anos)}-12-31")
    chuva = np.where(datas.month.isin(meses_chuva), chuva_pico, chuva_base).astype(float)
    if fator_ano:
        chuva = chuva * np.array([fator_ano.get(a, 1.0) for a in datas.year])
    return pd.DataFrame({"ponto_id": pid, "celula_power": "-1_-1", "data": datas, "chuva_mm": chuva,
                         "tmax_c": tmax, "tmin_c": tmin, "radiacao": 20.0})


@pytest.fixture
def fabrica_clima():
    return clima_sintetico
