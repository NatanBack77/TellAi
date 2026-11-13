import pytest

from src.app import quadra as Q


def test_indicador_quadra_formato_e_coerencia():
    i = Q.indicador_quadra("quixada_ce")
    assert i["n_anos"] >= 20 and i["anos"][0] == 2001
    assert 200 < i["media_mm"] < 1500 and i["pior_mm"] <= i["media_mm"] <= i["melhor_mm"]
    assert i["n_secos"] == len(i["anos_secos"]) and 0 <= i["n_secos"] <= i["n_anos"]
    assert all(a["fma_mm"] < i["limiar_seco_mm"] for _, a in i["serie"][i["serie"]["ano"].isin(i["anos_secos"])].iterrows())


def test_ponto_sem_dado_vira_lacuna():
    assert "lacuna" in Q.indicador_quadra("ponto_que_nao_existe")


def test_efeito_rendimento_sinal_e_ressalvas():
    e = Q.efeito_rendimento()
    assert {"milho", "feijao", "mandioca"} <= set(e)
    for v in e.values():
        assert v["rend_ano_seco_pct"] < 0 < v["rend_ano_umido_pct"]      # chuva e rendimento andam juntos nos dados
        assert 0 < v["r2"] < 0.6 and v["n_municipios"] >= 30
    assert e["milho"]["r2"] > e["feijao"]["r2"]


def test_tela_mostra_quadra_e_aviso_funceme():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "src/app/app.py"), default_timeout=120).run()
    assert not at.exception
    assert any("2b. A chuva da quadra" in x.value for x in at.subheader)
    texto = " ".join(x.value for x in list(at.markdown) + list(at.caption) + list(at.info))
    assert "FUNCEME" in texto and "associação histórica" in texto
