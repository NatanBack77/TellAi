import numpy as np
import pandas as pd
import pytest

from src.app.secao_balanco_renda import secao_renda
from src.culturas import ciclo, renda
from src.culturas.parametros import Parametros
from src.culturas.rotacao import gerar_rotacoes
from src.culturas.tabela_culturas import carregar
from src.modelos.entrada import RAIZ


@pytest.fixture(scope="module")
def tab():
    return carregar()


@pytest.fixture(scope="module")
def clima():
    d = pd.read_parquet(RAIZ / "data/processed/clima_diario.parquet")
    return ciclo.ClimaPonto.de_dataframe(d, "quixada_ce")


@pytest.fixture()
def pam(tmp_path):
    L = []
    for ano, val, area in [(2021, 100, 50), (2022, 300, 100), (2023, 0, 0)]:   # 2023: área 0 -> sem dado
        L += [(1, "Milho (em grão)", ano, "valor_producao_mil_reais", val), (1, "Milho (em grão)", ano, "area_colhida_ha", area)]
    L += [(1, "Mandioca", 2021, "valor_producao_mil_reais", 10.0), (1, "Mandioca", 2021, "area_colhida_ha", 5.0)]   # só 1 ano
    d = pd.DataFrame(L, columns=["ibge", "produto", "ano", "variavel", "valor"])
    d["municipio"], d["unidade"] = "x", "u"
    f = tmp_path / "pam.parquet"
    d.to_parquet(f)
    return str(f)


def test_receita_por_ano_e_divisao_segura():
    r = renda.receita_bruta_por_ano([100, 5, np.nan], [50, 0, 10])
    assert r[0] == pytest.approx(2000.0) and np.isnan(r[1]) and np.isnan(r[2])      # mil R$ x 1000 / ha


def test_media_dos_anos_validos_e_minimo(pam):
    r = renda.renda_municipio(1, pam)
    assert r["milho"]["receita_bruta_r_ha"] == pytest.approx((2000 + 3000) / 2) and r["milho"]["anos_usados"] == [2021, 2022]
    assert r["mandioca"]["receita_bruta_r_ha"] is None and "menos de" in r["mandioca"]["motivo_lacuna"]
    assert renda.renda_municipio(None)["milho"]["receita_bruta_r_ha"] is None


def test_cultura_sem_pam_e_lacuna_visivel(pam):
    s = secao_renda(1, ["milho", "palma_forrageira"], pam)
    palma = next(i for i in s["itens"] if i["cultura"] == "palma_forrageira")
    assert palma["lacuna"] and "C8" in palma["motivo_lacuna"] and s["renda_por_cultura"]["palma_forrageira"] is None
    assert "NÃO é lucro" in s["aviso"] and "inflação" in s["aviso"]
    assert any("palma_forrageira" in x for x in s["lacunas"])


def test_feijao_nao_separa_e_avisa():
    r = renda.renda_municipio(2311306)
    assert r["feijao_caupi"]["receita_bruta_r_ha"] == r["feijao_comum"]["receita_bruta_r_ha"]
    assert "não separa" in r["feijao_caupi"]["nota"]


def test_dados_reais_do_municipio_tem_valor_plausivel():
    r = renda.renda_municipio(2311306)       # Quixadá
    v = r["milho"]["receita_bruta_r_ha"]
    assert v is not None and v > 0 and r["milho"]["anos_usados"]


def test_renda_vira_criterio_so_com_dado(tab, clima):
    ids = list(tab)
    p = Parametros(n_sorteios=1500)
    base = gerar_rotacoes({"local": "x"}, "milho", tab, clima, p, prioridade="sem")
    sem_dado = gerar_rotacoes({"local": "x"}, "milho", tab, clima, p, prioridade="renda", renda_por_cultura={c: None for c in ids})
    assert [e["sequencia"] for e in base["estrategias"]] == [e["sequencia"] for e in sem_dado["estrategias"]]
    assert sem_dado["usa_renda"] is False
    renda_c = {c: None for c in ids} | {"milho": 500.0, "feijao_caupi": 1200.0, "mandioca": 8000.0, "algodao": 1700.0}
    com = gerar_rotacoes({"local": "x"}, "milho", tab, clima, p, prioridade="renda", renda_por_cultura=renda_c)
    assert com["usa_renda"] and "renda" in com["criterios"]
    assert any("NÃO é lucro" in l for e in com["estrategias"] for l in e["lacunas"])
    assert all("renda" in e["criterios"] for e in com["estrategias"])
    # renda deixa de ser igual a 'sem prioridade': o criterio entra e a ordem de pesos muda a simulacao
    assert [e["faixa_score"] for e in com["estrategias"]] != [e["faixa_score"] for e in base["estrategias"]]
    sem_prio = gerar_rotacoes({"local": "x"}, "milho", tab, clima, p, prioridade="sem", renda_por_cultura=renda_c)
    assert sem_prio["usa_renda"] is False       # dado de renda sozinho nao muda outras prioridades


def test_sequencia_com_cultura_sem_pam_e_lacuna(tab, clima):
    ids = list(tab)
    renda_c = {c: None for c in ids} | {"milho": 500.0, "feijao_caupi": 1200.0}
    r = gerar_rotacoes({"local": "x"}, "milho", tab, clima, Parametros(n_sorteios=1500), prioridade="renda", renda_por_cultura=renda_c)
    for e in r["estrategias"]:
        com = all(renda_c.get(c) is not None for c in e["sequencia"])
        assert e["criterios"]["renda"]["lacuna"] is (not com)
