from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.coleta.smap import agregar_diario, carimbo_do_nome, parse_csv_opendap
from src.modelos.entrada import DadosInvalidos

CSV = """Dataset: SMAP_L4_SM_gph_20200101T013000_Vv8010_001.h5
/Geophysical_Data/sm_rootzone[0], 0.30, -9999, 0.28
/Geophysical_Data/sm_rootzone[1], 0.31, 0.32, 0.33
/Geophysical_Data/sm_surface[0], 0.10, 0.12, -9999
/Geophysical_Data/sm_surface[1], 0.11, 0.13, 0.14
"""


def test_carimbo_do_nome():
    assert carimbo_do_nome("SMAP_L4_SM_gph_20150331T013000_Vv8010_001.h5") == datetime(2015, 3, 31, 1, 30)
    with pytest.raises(DadosInvalidos):
        carimbo_do_nome("outro_arquivo.h5")


def test_parse_csv_fill_vira_nan_e_nao_mistura_variaveis():
    sup = parse_csv_opendap(CSV, "sm_surface", -9999.0)
    raiz = parse_csv_opendap(CSV, "sm_rootzone", -9999.0)
    assert sup.shape == raiz.shape == (2, 3)
    assert np.isnan(sup[0, 2]) and np.isnan(raiz[0, 1])
    assert np.isnan(sup).sum() == 1 and np.isnan(raiz).sum() == 1  # nada preenchido
    assert sup[1, 2] == pytest.approx(0.14) and raiz[1, 0] == pytest.approx(0.31)


def test_parse_erro_e_variavel_ausente():
    with pytest.raises(DadosInvalidos):
        parse_csv_opendap("Dataset: ERROR\nstatus, 400\n", "sm_surface", -9999.0)
    with pytest.raises(DadosInvalidos):
        parse_csv_opendap(CSV, "sm_profile", -9999.0)


def test_agregar_diario_media_e_minimo_de_granulos():
    h = pd.date_range("2020-01-01 01:30", periods=16, freq="3h")  # dia 1 (8) e dia 2 (8)
    v = np.linspace(0.1, 0.3, 16)
    reg = pd.DataFrame({"ponto_id": "a", "carimbo": h, "sm_superficie": v, "sm_raiz": v})
    reg.loc[8:13, "sm_superficie"] = np.nan  # dia 2 fica com 2 granulos validos
    reg.loc[0, "sm_superficie"] = np.nan     # dia 1 fica com 7
    out = agregar_diario(reg, min_granulos=6).set_index("data")
    d1, d2 = out.loc["2020-01-01"], out.loc["2020-01-02"]
    assert d1["sm_superficie"] == pytest.approx(v[1:8].mean())
    assert d1["n_granulos_superficie"] == 7
    assert np.isnan(d2["sm_superficie"]) and d2["n_granulos_superficie"] == 2
    assert d2["sm_raiz"] == pytest.approx(v[8:].mean())  # outra variavel nao e afetada
