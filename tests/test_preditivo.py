import copy
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.modelos.preditivo as preditivo
from src.modelos.entrada import DadosInvalidos, carregar_config
from src.modelos.features import construir_dataset
from src.modelos.preditivo import (
    avaliar, dividir_anos, metricas, preparar_tabela_modelagem, salvar_metricas, skill,
)
from src.modelos.sintetico import gerar_sinteticos


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


@pytest.fixture(scope="module")
def dataset(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("sint_pred")
    arqs = gerar_sinteticos(d, n_celulas=6, pontos_por_celula=2, ano_ini=2005, ano_fim=2019)
    ent = {k: pd.read_parquet(v) for k, v in arqs.items()}
    return construir_dataset(ent, cfg)


@pytest.fixture(scope="module")
def res(dataset, cfg):
    return avaliar(dataset, cfg, sintetico=True)


# --- métricas ---------------------------------------------------------------------------
def test_metricas_valores_conhecidos():
    m = metricas(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 5.0]))
    assert m["mae"] == pytest.approx(2 / 3)
    assert m["rmse"] == pytest.approx(np.sqrt(4 / 3))
    assert m["r2"] == pytest.approx(1 - 4 / 2)


def test_skill_formula():
    assert skill(0.5, 1.0) == pytest.approx(0.5)
    assert skill(1.0, 1.0) == pytest.approx(0.0)
    assert skill(2.0, 1.0) < 0
    assert np.isnan(skill(1.0, 0.0))


def test_baseline_climatologia_e_rmse_da_anomalia(dataset, cfg, res):
    d, _, teste_anos, _ = preparar_tabela_modelagem(dataset, cfg)
    y = d[d["ano"].isin(teste_anos)]["anomalia_ndvi"].to_numpy()
    h = res["holdout_temporal"]["modelos"]["climatologia"]
    assert h["rmse"] == pytest.approx(np.sqrt(np.mean(y ** 2)))
    assert h["skill_vs_climatologia"] == 0.0


# --- divisão temporal ------------------------------------------------------------------
def test_holdout_so_ultimos_anos_e_sem_sobreposicao(res):
    tr, te = res["divisao"]["anos_treino"], res["divisao"]["anos_teste"]
    assert te == [2017, 2018, 2019] and max(tr) < min(te) and not set(tr) & set(te)


def test_anos_insuficientes_falha():
    with pytest.raises(DadosInvalidos):
        dividir_anos([2010, 2011, 2012, 2013], 3)


def test_climatologia_do_alvo_so_dos_anos_de_treino(dataset, cfg):
    a, _, teste_anos, _ = preparar_tabela_modelagem(dataset, cfg)
    alt = dataset.copy()
    alt.loc[alt["ano"].isin(teste_anos), "ndvi"] += 5.0   # muda só o NDVI do período de teste
    b, _, _, _ = preparar_tabela_modelagem(alt, cfg)
    pd.testing.assert_series_equal(a["ndvi_clim"], b["ndvi_clim"])


def test_features_no_treino_nao_veem_teste(dataset, cfg):
    _, treino_anos, _, cols = preparar_tabela_modelagem(dataset, cfg)
    assert not {"ponto_id", "celula_power", "lat", "lon", "ndvi", "anomalia_ndvi", "ndvi_clim"} & set(cols)


# --- validação agrupada ----------------------------------------------------------------
def test_groupkfold_sem_celula_em_treino_e_validacao(res):
    assert len(res["cv_grupos"]["folds"]) == res["divisao"]["n_folds"] >= 2
    vistas = []
    for f in res["cv_grupos"]["folds"]:
        assert not set(f["celulas_treino"]) & set(f["celulas_validacao"])
        vistas += f["celulas_validacao"]
    assert sorted(vistas) == sorted(set(vistas))          # cada célula valida em um único fold
    assert len(vistas) == res["divisao"]["n_celulas_treino"]


def test_cv_so_usa_anos_de_treino(dataset, cfg):
    d, treino_anos, teste_anos, _ = preparar_tabela_modelagem(dataset, cfg)
    r = avaliar(dataset, cfg)
    n_cv = sum(f["n_validacao"] for f in r["cv_grupos"]["folds"])
    assert n_cv == int(d["ano"].isin(treino_anos).sum())


def test_codigo_nao_usa_cv_aleatoria():
    src = Path(preditivo.__file__).read_text(encoding="utf-8")
    assert not re.search(r"(?<!Group)KFold\(|ShuffleSplit|train_test_split|cross_val_score", src)
    assert "GroupKFold" in src


def test_poucas_celulas_falha(dataset, cfg):
    um = dataset[dataset["celula_power"] == dataset["celula_power"].iloc[0]]
    with pytest.raises(DadosInvalidos, match="2 células"):
        avaliar(um, cfg)


# --- saída ------------------------------------------------------------------------------
def test_saida_tem_lacunas_confianca_e_aviso(res):
    assert isinstance(res["lacunas"], list) and res["confianca"] in {"alta", "media", "baixa"}
    assert res["confianca"] == "baixa"                      # 6 células < 15
    assert any("células POWER distintas" in x for x in res["lacunas"])
    assert "causalidade" in res["aviso"] and "não prevê o clima" in res["aviso"]


def test_sintetico_sinalizado(res, tmp_path):
    assert res["dados_sinteticos"] and "SINTÉTICOS" in res["lacunas"][0]
    assert salvar_metricas(res, tmp_path).name == "SINTETICO_metricas.json"


def test_resumo_media_e_desvio_por_fold(res):
    r = res["cv_grupos"]["resumo"]
    for nome in ("climatologia", "ridge", "xgboost"):
        for m in ("mae", "rmse", "r2", "skill_vs_climatologia"):
            assert {"media", "desvio"} == set(r[nome][m])
    assert "skill_vs_ridge" in r["xgboost"]


def test_ridge_alpha_vem_do_grid(res, cfg):
    for f in res["cv_grupos"]["folds"]:
        assert f["modelos"]["ridge"]["info"]["alpha"] in cfg["preditivo"]["ridge_alphas"]


def test_fluxo_detecta_sinal_sintetico(res):
    """Teste de FLUXO (não é resultado): no sintético o NDVI depende da chuva por construção,
    então um Ridge correto tem de superar a climatologia no holdout."""
    assert res["holdout_temporal"]["modelos"]["ridge"]["skill_vs_climatologia"] > 0


def test_reprodutivel(dataset, cfg, res):
    outra = avaliar(copy.deepcopy(dataset), cfg, sintetico=True)
    assert outra["holdout_temporal"] == res["holdout_temporal"]
    assert outra["cv_grupos"]["resumo"] == res["cv_grupos"]["resumo"]
