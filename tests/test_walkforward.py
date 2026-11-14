import numpy as np
import pandas as pd
import pytest

from src.modelos.entrada import DadosInvalidos, carregar_config
from src.modelos.sintetico import gerar_sinteticos
from src.modelos.walkforward import VARIANTES, Variante, anos_da_execucao, extra_persistencia, resumir, walk_forward


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


@pytest.fixture(scope="module")
def entradas(tmp_path_factory):
    d = tmp_path_factory.mktemp("sint_wf")
    arqs = gerar_sinteticos(d, n_celulas=6, pontos_por_celula=1, ano_ini=2003, ano_fim=2018)
    return {k: pd.read_parquet(v) for k, v in arqs.items()}


VS = [VARIANTES["base"], VARIANTES["persistencia"]]


def _rodar(ent, cfg, anos, **kw):
    return walk_forward(ent, cfg, kw.pop("variantes", VS), anos, modelos=("ridge",), **kw)


def test_fluxo_e_colunas(entradas, cfg):
    r = _rodar(entradas, cfg, [2014, 2015])
    assert set(r["variante"]) == {"base", "persistencia"} and set(r["ano_teste"]) == {2014, 2015}
    assert {"ridge", "ingenua"} <= set(r["modelo"])
    assert r["rmse"].notna().all() and (r["rmse_clim"] > 0).all()


def test_sem_vazamento_do_futuro(entradas, cfg):
    """Alterar clima e NDVI de anos POSTERIORES ao ano de teste não pode mudar o resultado desse ano."""
    a = _rodar(entradas, cfg, [2013])
    alt = {k: (None if v is None else v.copy()) for k, v in entradas.items()}
    alt["clima"].loc[alt["clima"]["data"].dt.year > 2013, ["chuva_mm", "tmax_c"]] *= 7.0
    alt["ndvi"].loc[alt["ndvi"]["data"].dt.year > 2013, "ndvi"] = 0.99
    b = _rodar(alt, cfg, [2013])
    pd.testing.assert_frame_equal(a, b)


def test_mesmas_linhas_de_teste_para_todas_as_variantes(entradas, cfg):
    r = _rodar(entradas, cfg, [2014, 2016])
    n = r[r["modelo"] == "ridge"].groupby(["ano_teste", "variante"])["n"].first().unstack("variante")
    assert (n["base"] == n["persistencia"]).all()


def test_placebo_zera_a_skill_e_o_sinal_real_existe(entradas, cfg):
    real = _rodar(entradas, cfg, [2013, 2014, 2015, 2016, 2017, 2018])
    plc = _rodar(entradas, cfg, [2013, 2014, 2015, 2016, 2017, 2018], placebo=True)
    sk = lambda r: r[(r["variante"] == "base") & (r["modelo"] == "ridge")]["skill"].mean()
    assert sk(real) > 0.05          # sintético tem sinal chuva->NDVI por construção (teste de fluxo)
    assert sk(plc) < 0.02           # sem relação clima->NDVI não pode haver ganho


def test_persistencia_e_causal(entradas, cfg):
    d = pd.DataFrame({"ponto_id": ["p"] * 5, "data": pd.to_datetime(["2010-01-01", "2010-01-17", "2010-02-02",
                                                                    "2010-03-06", "2010-03-22"]),
                      "anomalia_ndvi": [1.0, 2.0, 3.0, 4.0, 5.0]})
    out, novas = extra_persistencia(d)
    assert novas == ["anom_lag1", "anom_lag2"]
    assert np.isnan(out.loc[0, "anom_lag1"]) and out.loc[1, "anom_lag1"] == 1.0 and out.loc[2, "anom_lag1"] == 2.0
    assert np.isnan(out.loc[1, "anom_lag2"]) and out.loc[2, "anom_lag2"] == 1.0
    assert np.isnan(out.loc[3, "anom_lag1"])        # buraco de 32 dias: não usa lag antigo
    assert out.loc[4, "anom_lag1"] == 4.0 and np.isnan(out.loc[4, "anom_lag2"])


def test_anos_de_treino_insuficientes_falha(entradas, cfg):
    with pytest.raises(DadosInvalidos):
        _rodar(entradas, cfg, [2005])


def test_reprodutivel(entradas, cfg):
    pd.testing.assert_frame_equal(_rodar(entradas, cfg, [2014]), _rodar(entradas, cfg, [2014]))


def test_alvo_z_devolve_escala_original(entradas, cfg):
    r = _rodar(entradas, cfg, [2014, 2015], variantes=[VARIANTES["base"], VARIANTES["alvo_z"]])
    a = r[r["variante"] == "base"]["rmse_clim"].to_numpy()
    b = r[r["variante"] == "alvo_z"]["rmse_clim"].to_numpy()
    np.testing.assert_allclose(a, b)                # mesma climatologia/linhas => mesma escala


def _tabela(skills_base, skills_var, anos):
    linhas = []
    for nome, sk in (("base", skills_base), ("v", skills_var)):
        for a, s in zip(anos, sk):
            linhas.append({"ano_teste": a, "variante": nome, "modelo": "ridge", "n": 100, "rmse": 1 - s,
                           "rmse_clim": 1.0, "skill": s})
    return pd.DataFrame(linhas)


def test_resumir_exige_melhoria_pareada_e_confirmacao():
    anos = list(range(2010, 2022)) + [2022, 2023, 2024]
    forte = _tabela([0.0] * 15, [0.20] * 15, anos)
    t = resumir(forte, range(2010, 2022), range(2022, 2025), n_variantes=2).set_index("variante")
    assert bool(t.loc["v", "melhoria_valida"]) and not bool(t.loc["base", "melhoria_valida"])
    reprova_conf = _tabela([0.0] * 15, [0.20] * 12 + [-0.1] * 3, anos)
    t2 = resumir(reprova_conf, range(2010, 2022), range(2022, 2025), n_variantes=2).set_index("variante")
    assert not bool(t2.loc["v", "melhoria_valida"])                 # falha na confirmação selada


def test_correcao_por_numero_de_variantes_endurece_o_criterio():
    anos = list(range(2010, 2022))
    rng = np.random.default_rng(0)
    r = _tabela([0.0] * 12, list(0.01 + 0.03 * rng.standard_normal(12)), anos)
    poucas = resumir(r, anos, [], n_variantes=2).set_index("variante").loc["v", "skill_ic_inf_corrigido"]
    muitas = resumir(r, anos, [], n_variantes=40).set_index("variante").loc["v", "skill_ic_inf_corrigido"]
    assert muitas <= poucas


def test_anos_da_execucao_padrao_seguro_nao_inclui_confirmacao(cfg):
    w = cfg["walkforward"]
    anos, sel, con = anos_da_execucao(w)            # padrão = só seleção
    assert con == [] and anos == sel
    assert max(sel) == w["anos_selecao"][1] and max(anos) < w["anos_confirmacao"][0]
    anos2, sel2, con2 = anos_da_execucao(w, so_selecao=False)
    assert sel2 == sel and con2 and anos2 == sel + con2


def test_resumir_sem_confirmacao_nao_declara_melhoria_valida(entradas, cfg):
    res = _rodar(entradas, cfg, [2014, 2015])
    tab = resumir(res, [2014, 2015], [], n_variantes=2)
    assert (tab["anos_confirmacao"] == 0).all() and tab["skill_confirmacao"].isna().all()
    assert not tab["melhoria_valida"].any()
