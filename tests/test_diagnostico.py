import copy
import json

import numpy as np
import pandas as pd
import pytest

from src.modelos.diagnostico import (
    N_QUINZENAS, diagnosticar_ponto, diagnosticar_todos, preparar_ndvi, salvar_diagnostico,
)
from src.modelos.entrada import carregar_config
from src.modelos.sintetico import gerar_sinteticos


@pytest.fixture(scope="module")
def cfg():
    return carregar_config()


@pytest.fixture(scope="module")
def dados(tmp_path_factory):
    d = tmp_path_factory.mktemp("sint")
    arqs = gerar_sinteticos(d, n_celulas=2, pontos_por_celula=1, ano_ini=2005, ano_fim=2019)
    return {k: pd.read_parquet(v) for k, v in arqs.items()}


@pytest.fixture(scope="module")
def resultado(dados, cfg):
    pid = "P000"
    return diagnosticar_ponto(
        dados["ndvi"][dados["ndvi"].ponto_id == pid], dados["clima"][dados["clima"].ponto_id == pid],
        dados["umidade_solo"], cfg)


def test_campos_obrigatorios(resultado):
    r, anom = resultado
    for k in ("n_anos_validos", "lacunas", "confianca", "sazonalidade_ndvi", "solo_nu",
              "tendencias", "veranicos", "climatologia_quinzenal", "limites"):
        assert k in r
    assert isinstance(r["lacunas"], list) and r["confianca"] in {"alta", "media", "baixa"}
    assert set(anom.columns) >= {"ponto_id", "variavel", "ano", "quinzena", "valor", "z"}


def test_json_serializavel(resultado, tmp_path):
    r, anom = resultado
    caminhos = salvar_diagnostico([r], anom, tmp_path)
    lido = json.loads(caminhos["json"].read_text(encoding="utf-8"))
    assert lido[0]["ponto_id"] == "P000"
    assert "NaN" not in caminhos["json"].read_text(encoding="utf-8")


def test_stl_e_sazonalidade(resultado):
    s = resultado[0]["sazonalidade_ndvi"]
    assert s["periodo"] == 23 and len(s["perfil_sazonal_por_slot"]) == 23
    assert 0 <= s["forca_sazonalidade"] <= 1


def test_baixa_confiabilidade_descartada(cfg):
    datas = [pd.Timestamp(2010, 1, 1) + pd.Timedelta(days=16 * k) for k in range(23)]
    df = pd.DataFrame({"ponto_id": "X", "data": datas, "ndvi": 0.5, "confiabilidade": 0})
    df.loc[3, "confiabilidade"] = 2
    df.loc[3, "ndvi"] = 0.99
    grade, info = preparar_ndvi(df, cfg)
    assert info["n_descartadas_baixa_confiabilidade"] == 1
    # o valor ruim não pode vazar; o buraco curto é interpolado e marcado
    assert grade.loc[3, "ndvi_i"] == pytest.approx(0.5)
    assert bool(grade.loc[3, "interpolado"]) and not bool(grade.loc[3, "valido_original"])


def test_buraco_longo_nao_e_preenchido(cfg):
    datas = [pd.Timestamp(2010, 1, 1) + pd.Timedelta(days=16 * k) for k in range(23)]
    df = pd.DataFrame({"ponto_id": "X", "data": datas, "ndvi": 0.5, "confiabilidade": 0})
    df.loc[5:9, "ndvi"] = np.nan  # 5 seguidas > limite (2)
    grade, info = preparar_ndvi(df, cfg)
    assert grade.loc[5:9, "ndvi_i"].isna().all()
    assert info["n_interpoladas"] == 0 and info["n_ausentes_restantes"] == 5


def test_solo_nu_frequencia_valida(resultado):
    nu = resultado[0]["solo_nu"]
    freqs = [f for f in nu["frequencia_por_quinzena"].values() if f is not None]
    assert freqs and all(0 <= f <= 1 for f in freqs)
    assert any("percentil" in x for x in resultado[0]["lacunas"])  # aviso do limiar relativo


def test_solo_nu_limiar_fixo(dados, cfg):
    c = copy.deepcopy(cfg)
    c["solo_nu"].update(metodo="fixo", limiar_fixo=0.0)  # nenhum NDVI abaixo de 0 => nunca solo nu
    r, _ = diagnosticar_ponto(dados["ndvi"][dados["ndvi"].ponto_id == "P000"],
                              dados["clima"][dados["clima"].ponto_id == "P000"], None, c)
    assert r["solo_nu"]["quinzenas_tipicas"] == []
    assert r["solo_nu"]["limiar_ndvi"] == 0.0


def test_tendencia_poucos_anos_vira_lacuna(dados, cfg):
    pid = "P000"
    cl = dados["clima"][(dados["clima"].ponto_id == pid) & (dados["clima"].data.dt.year <= 2009)]
    nd = dados["ndvi"][(dados["ndvi"].ponto_id == pid) & (dados["ndvi"].data.dt.year <= 2009)]
    r, _ = diagnosticar_ponto(nd, cl, None, cfg)
    assert r["tendencias"]["chuva_anual_mm"]["resultado"] is None
    assert any("Tendência" in x and "mínimo" in x for x in r["lacunas"])
    assert r["confianca"] == "baixa"


def test_umidade_ausente_vira_lacuna(dados, cfg):
    r, _ = diagnosticar_ponto(dados["ndvi"][dados["ndvi"].ponto_id == "P000"],
                              dados["clima"][dados["clima"].ponto_id == "P000"], None, cfg)
    assert any("Umidade do solo" in x for x in r["lacunas"])
    assert "umidade_solo" not in r["n_anos_validos"]


def test_veranico_conhecido(dados, cfg):
    """Chuva 5 mm/dia em jan-mar, exceto 12 dias secos (1-12 fev) todo ano => maior veranico = 12."""
    dias = pd.date_range("2000-01-01", "2014-12-31")
    chuva = np.where(dias.month.isin([1, 2, 3]), 5.0, 0.0)
    chuva[(dias.month == 2) & (dias.day <= 12)] = 0.0
    clima = pd.DataFrame({"ponto_id": "V", "celula_power": "C", "data": dias, "chuva_mm": chuva,
                          "tmax_c": 30.0, "tmin_c": 20.0, "radiacao": 20.0})
    nd = dados["ndvi"][dados["ndvi"].ponto_id == "P000"].copy()
    nd["data"] = nd["data"] - pd.DateOffset(years=5)  # 2000-2014
    nd["ponto_id"] = "V"
    c = copy.deepcopy(cfg)
    c["estacao_chuvosa"]["n_quinzenas"] = 6
    r, _ = diagnosticar_ponto(nd, clima, None, c)
    v = r["veranicos"]
    assert v["quinzenas_estacao_chuvosa"] == [1, 2, 3, 4, 5, 6]
    assert v["distribuicao"]["max"] == 12 and v["distribuicao"]["min"] == 12


def test_anomalia_z_media_zero(resultado):
    _, anom = resultado
    z = anom[anom.variavel == "chuva_mm_quinzena"].dropna(subset=["z"])
    assert abs(z["z"].mean()) < 0.1
    assert anom["quinzena"].between(1, N_QUINZENAS).all()


def test_todos_os_pontos_e_ponto_sem_ndvi(dados, cfg):
    ent = {"clima": dados["clima"], "ndvi": dados["ndvi"][dados["ndvi"].ponto_id != "P001"],
           "umidade_solo": dados["umidade_solo"]}
    res, anom = diagnosticar_todos(ent, cfg)
    assert [r["ponto_id"] for r in res] == ["P000", "P001"]
    sem = res[1]
    assert sem["confianca"] == "baixa" and "Sem NDVI" in sem["lacunas"][0]
    assert set(anom["ponto_id"]) == {"P000"}


def test_determinismo(dados, cfg):
    a = diagnosticar_ponto(dados["ndvi"][dados["ndvi"].ponto_id == "P000"],
                           dados["clima"][dados["clima"].ponto_id == "P000"], None, cfg)[0]
    b = diagnosticar_ponto(dados["ndvi"][dados["ndvi"].ponto_id == "P000"],
                           dados["clima"][dados["clima"].ponto_id == "P000"], None, cfg)[0]
    assert a == b
