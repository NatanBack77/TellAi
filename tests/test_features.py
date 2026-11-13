import copy

import numpy as np
import pandas as pd
import pytest

from src.modelos.entrada import DadosInvalidos, carregar_config
from src.modelos.features import (
    adicionar_anomalia, construir_dataset, features_diarias_ponto, nomes_features, resumir_dataset,
)
from src.modelos.sintetico import gerar_sinteticos


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


@pytest.fixture(scope="module")
def entradas(tmp_path_factory):
    d = tmp_path_factory.mktemp("sint_feat")
    arqs = gerar_sinteticos(d, n_celulas=3, pontos_por_celula=2, ano_ini=2005, ano_fim=2019)
    return {k: pd.read_parquet(v) for k, v in arqs.items()}


def _clima(dias, chuva, tmax=30.0):
    return pd.DataFrame({"ponto_id": "A", "celula_power": "C", "data": dias, "chuva_mm": chuva,
                         "tmax_c": tmax, "tmin_c": 20.0, "radiacao": 20.0})


def test_janela_soma_valor_conhecido(cfg):
    dias = pd.date_range("2010-01-01", "2010-12-31")
    f = features_diarias_ponto(_clima(dias, 2.0), None, cfg)
    t = pd.Timestamp("2010-06-01")
    assert f.loc[t, "chuva_ac_30d"] == pytest.approx(60.0)
    assert f.loc[t, "chuva_ac_90d"] == pytest.approx(180.0)
    assert f.loc[t, "tmax_media_30d"] == pytest.approx(30.0)


def test_janela_so_dias_anteriores(cfg):
    """Chuva só no dia t não pode aparecer na feature de t, apenas na de t+1."""
    dias = pd.date_range("2010-01-01", "2010-12-31")
    chuva = np.zeros(len(dias))
    t = pd.Timestamp("2010-06-01")
    chuva[dias.get_loc(t)] = 100.0
    f = features_diarias_ponto(_clima(dias, chuva), None, cfg)
    assert f.loc[t, "chuva_ac_30d"] == 0.0
    assert f.loc[t + pd.Timedelta(days=1), "chuva_ac_30d"] == 100.0


def test_inicio_da_serie_sem_janela_completa_e_nan(cfg):
    dias = pd.date_range("2010-01-01", "2010-12-31")
    f = features_diarias_ponto(_clima(dias, 2.0), None, cfg)
    assert np.isnan(f.loc["2010-01-20", "chuva_ac_90d"])
    assert np.isnan(f.loc["2010-01-20", "chuva_ac_30d"])


def test_dado_ausente_nao_e_preenchido(cfg):
    dias = pd.date_range("2010-01-01", "2010-12-31")
    chuva = np.full(len(dias), 2.0)
    chuva[dias.get_loc(pd.Timestamp("2010-05-20"))] = np.nan
    f = features_diarias_ponto(_clima(dias, chuva), None, cfg)
    assert np.isnan(f.loc["2010-06-01", "chuva_ac_30d"])  # janela com buraco => NaN


def test_dias_secos_consecutivos(cfg):
    dias = pd.date_range("2010-01-01", "2010-12-31")
    chuva = np.full(len(dias), 5.0)
    chuva[dias.get_loc(pd.Timestamp("2010-06-01")):dias.get_loc(pd.Timestamp("2010-06-10")) + 1] = 0.0
    f = features_diarias_ponto(_clima(dias, chuva), None, cfg)
    assert f.loc["2010-06-11", "dias_secos_consecutivos"] == 10   # 1 a 10 jun
    assert f.loc["2010-06-05", "dias_secos_consecutivos"] == 4    # 1 a 4 jun
    assert f.loc["2010-06-01", "dias_secos_consecutivos"] == 0


def test_features_sem_vazamento_do_futuro(cfg):
    """Mudar clima a partir de D não pode alterar nenhuma feature de datas t <= D."""
    dias = pd.date_range("2010-01-01", "2012-12-31")
    rng = np.random.default_rng(0)
    base = _clima(dias, rng.gamma(1, 5, len(dias)))
    f0 = features_diarias_ponto(base, None, cfg)
    D = pd.Timestamp("2011-07-01")
    alt = base.copy()
    mudar = alt["data"] >= D
    alt.loc[mudar, "chuva_mm"] *= 50
    alt.loc[mudar, "tmax_c"] += 20
    f1 = features_diarias_ponto(alt, None, cfg)
    pd.testing.assert_frame_equal(f0.loc[:D], f1.loc[:D])
    assert not f0.loc[D + pd.Timedelta(days=5):].equals(f1.loc[D + pd.Timedelta(days=5):])  # controle: muda depois


def test_sem_lat_lon_ou_id_nas_features(cfg):
    for com in (True, False):
        nomes = nomes_features(cfg, com)
        assert not {"lat", "lon", "latitude", "longitude", "ponto_id", "celula_power"} & set(nomes)


def test_dataset_formato(entradas, cfg):
    cfg = copy.deepcopy(cfg)
    cfg["preditivo"]["usar_umidade_solo"] = True        # SMAP é opção (D52); aqui testamos o formato com ele
    ds = construir_dataset(entradas, cfg)
    feats = nomes_features(cfg, com_umidade=True)
    assert set(feats) <= set(ds.columns)
    assert {"ponto_id", "celula_power", "data", "ano", "slot", "ndvi", "completo"} <= set(ds.columns)
    assert ds["ndvi"].notna().all()                     # só observações originais
    assert ds["completo"].sum() > 0 and (~ds["completo"]).sum() > 0   # início da série sem janela
    assert (ds.loc[ds["completo"], feats].notna()).all().all()


def test_dataset_sem_umidade(entradas, cfg):
    ent = dict(entradas, umidade_solo=None)
    ds = construir_dataset(ent, cfg)
    assert not any(c.startswith("sm_") for c in ds.columns)
    assert any("Umidade do solo" in x for x in resumir_dataset(ds, cfg)["lacunas"])


def test_aviso_poucas_celulas(entradas, cfg):
    r = resumir_dataset(construir_dataset(entradas, cfg), cfg)
    assert r["n_celulas"] == 3
    assert any("células POWER distintas" in x for x in r["lacunas"])


def test_interpoladas_nao_viram_linha(entradas, cfg):
    ds = construir_dataset(entradas, cfg)
    nd = entradas["ndvi"]
    validos = nd[nd["confiabilidade"].isin(cfg["ndvi"]["confiabilidade_aceita"]) & nd["ndvi"].notna()]
    assert len(ds) == len(validos)


def test_anomalia_usa_so_anos_de_referencia(entradas, cfg):
    ds = construir_dataset(entradas, cfg)
    treino = range(2005, 2017)
    a = adicionar_anomalia(ds, treino, cfg)
    # mudar NDVI de anos fora da referência não altera a climatologia
    alt = ds.copy()
    alt.loc[alt["ano"] > 2016, "ndvi"] += 1.0
    b = adicionar_anomalia(alt, treino, cfg)
    pd.testing.assert_series_equal(a["ndvi_clim"], b["ndvi_clim"])
    fora = a["ano"] > 2016
    assert np.allclose((b.loc[fora, "anomalia_ndvi"] - a.loc[fora, "anomalia_ndvi"]).dropna(), 1.0)


def test_anomalia_media_zero_na_referencia(entradas, cfg):
    ds = construir_dataset(entradas, cfg)
    a = adicionar_anomalia(ds, range(2005, 2020), cfg)
    assert abs(a["anomalia_ndvi"].mean()) < 1e-9


def test_anomalia_poucos_anos_vira_nan(entradas, cfg):
    ds = construir_dataset(entradas, cfg)
    a = adicionar_anomalia(ds, [2005, 2006], cfg)   # 2 anos < min 3
    assert a["anomalia_ndvi"].isna().all()


def test_anomalia_sem_referencia_falha(entradas, cfg):
    with pytest.raises(DadosInvalidos):
        adicionar_anomalia(construir_dataset(entradas, cfg), [1990], cfg)


def test_datas_duplicadas_falham(cfg):
    dias = pd.date_range("2010-01-01", "2010-03-01")
    df = pd.concat([_clima(dias, 1.0), _clima(dias[:3], 1.0)])
    with pytest.raises(DadosInvalidos, match="duplicadas"):
        features_diarias_ponto(df, None, cfg)


def test_determinismo(entradas, cfg):
    pd.testing.assert_frame_equal(construir_dataset(entradas, cfg), construir_dataset(copy.deepcopy(entradas), cfg))
