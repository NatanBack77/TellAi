import numpy as np
import pandas as pd
import pytest

from src.modelos import relatorio
from src.modelos.conformal_aci import aci_walk_forward, atualizar_alpha, q_nivel
from src.modelos.entrada import carregar_config
from src.modelos.features import construir_dataset
from src.modelos.preditivo import avaliar, salvar_metricas
from src.modelos.sintetico import gerar_sinteticos


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


@pytest.fixture(scope="module")
def dataset(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("sint_aci")
    arqs = gerar_sinteticos(d, n_celulas=6, pontos_por_celula=2, ano_ini=2003, ano_fim=2018)
    return construir_dataset({k: pd.read_parquet(v) for k, v in arqs.items()}, cfg)


def test_q_nivel_e_atualizacao_do_alpha():
    r = np.arange(1.0, 11.0)
    assert q_nivel(r, 0.0) == float("inf") and q_nivel(r, 1.0) == 0.0
    assert q_nivel(r, 0.2) == 9.0 and q_nivel(r[:2], 0.05) == float("inf") and q_nivel(np.array([]), 0.2) == float("inf")
    assert atualizar_alpha(0.2, 0.2, 0.5, 0.05) < 0.2      # errou mais que o permitido => alpha cai => faixa alarga
    assert atualizar_alpha(0.2, 0.2, 0.0, 0.05) > 0.2      # errou menos => alpha sobe => faixa estreita
    assert atualizar_alpha(0.2, 0.2, 0.2, 0.05) == pytest.approx(0.2)


def test_aci_formato_e_valores_plausiveis(dataset, cfg):
    r = aci_walk_forward(dataset, cfg, [2012, 2013, 2014], [2015, 2016, 2017])
    assert set(r["metas"]) == {"80", "90"} and r["anos_teste"] == [2015, 2016, 2017]
    for k, v in r["metas"].items():
        assert 0.5 < v["cobertura"] <= 1.0 and v["pior_estacao"] <= v["cobertura"] + 1e-9 and len(v["por_ano"]) == 3
    assert r["metas"]["90"]["cobertura"] >= r["metas"]["80"]["cobertura"]
    assert "longo prazo" in r["aviso"] and r["estado_final_alpha"]


def test_aci_so_usa_o_passado(dataset, cfg):
    a = aci_walk_forward(dataset, cfg, [2012, 2013], [2014])
    alt = dataset.copy()
    alt.loc[alt["ano"] > 2014, "ndvi"] = 0.99                 # futuro alterado
    b = aci_walk_forward(alt, cfg, [2012, 2013], [2014])
    assert a["metas"] == b["metas"]


def test_aci_reprodutivel_e_falha_sem_anos(dataset, cfg):
    assert aci_walk_forward(dataset, cfg, [2012], [2014])["metas"] == aci_walk_forward(dataset, cfg, [2012], [2014])["metas"]
    with pytest.raises(ValueError):
        aci_walk_forward(dataset, cfg, [], [2004])


def test_avaliar_traz_aci_e_relatorio_mostra(dataset, cfg, tmp_path):
    res = avaliar(dataset, cfg, sintetico=True)
    assert res["conformal_aci"] is not None and res["conformal_aci"]["anos_teste"] == res["divisao"]["anos_teste"]
    real = dict(res, dados_sinteticos=False)
    md = relatorio.gerar(salvar_metricas(real, tmp_path)).read_text(encoding="utf-8")
    assert "ACI por estação" in md and "Pior estação" in md
