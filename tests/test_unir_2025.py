"""União original + 2025+ (src/coleta/unir_2025.py): schema, ordem, de-duplicação declarada, NaN intacto, idempotência e originais intocados."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.coleta import unir_2025 as U
from src.modelos.entrada import RAIZ, DadosInvalidos, carregar_config


def _clima(pid, ini, fim, cel="-5_-60", nan_final=0, v=1.0):
    d = pd.date_range(ini, fim)
    df = pd.DataFrame({"ponto_id": pid, "celula_power": cel, "data": d, "chuva_mm": v, "tmax_c": 33.0, "tmin_c": 22.0, "radiacao": 20.0})
    if nan_final:
        df.loc[df.index[-nan_final:], ["chuva_mm", "tmax_c", "tmin_c", "radiacao"]] = np.nan
    return df


def _ndvi(pid, datas, conf, ndvi=0.5):
    return pd.DataFrame({"ponto_id": pid, "data": pd.to_datetime(datas), "ndvi": ndvi, "confiabilidade": np.asarray(conf, dtype=float)})


def test_unir_sem_sobreposicao_ordena_mantem_schema_e_nan():
    o = pd.concat([_clima("b_ce", "2024-12-01", "2024-12-31"), _clima("a_ce", "2024-12-01", "2024-12-31", cel="-6_-60")])
    n = pd.concat([_clima("b_ce", "2025-01-01", "2025-01-10", nan_final=3), _clima("a_ce", "2025-01-01", "2025-01-10", cel="-6_-60", nan_final=3)])
    s, rel = U.unir(o, n, "clima")
    assert list(s.columns) == list(o.columns) and (s.dtypes == o.dtypes).all()
    assert not s.duplicated(["ponto_id", "data"]).any()
    assert s.equals(s.sort_values(["ponto_id", "data"]).reset_index(drop=True))
    assert rel["duplicadas_removidas"] == 0 and rel["linhas_saida"] == len(o) + len(n)
    assert int(s["chuva_mm"].isna().sum()) == 6                       # os 3 últimos dias de cada ponto continuam NaN: nada é preenchido
    assert s[s["chuva_mm"].isna()]["data"].min() == pd.Timestamp("2025-01-08")


def test_unir_deduplica_de_forma_declarada_e_fica_com_o_original():
    o = _clima("a_ce", "2024-12-25", "2024-12-31", v=1.0)
    n = pd.concat([_clima("a_ce", "2024-12-30", "2025-01-03", v=9.0), _clima("a_ce", "2025-01-02", "2025-01-02", v=7.0)])   # sobrepõe 2 dias + 1 repetido
    s, rel = U.unir(o, n, "clima")
    assert not s.duplicated(["ponto_id", "data"]).any()
    assert rel["duplicadas_removidas"] == 3 and rel["grupos_duplicados_com_valores_diferentes"] == 3
    assert s.set_index("data").loc["2024-12-30", "chuva_mm"] == 1.0    # original vence
    assert s.set_index("data").loc["2025-01-02", "chuva_mm"] == 9.0    # primeira ocorrência na ordem [original, 2025plus]


def test_unir_recusa_schema_ou_celula_diferente():
    o, n = _clima("a_ce", "2024-12-30", "2024-12-31"), _clima("a_ce", "2025-01-01", "2025-01-02")
    with pytest.raises(DadosInvalidos, match="colunas"):
        U.unir(o, n.drop(columns="radiacao"), "clima")
    with pytest.raises(DadosInvalidos, match="celula_power"):
        U.unir(o, _clima("a_ce", "2025-01-01", "2025-01-02", cel="-9_-9"), "clima")


def test_unir_ndvi_mantem_todas_as_confiabilidades_e_nan():
    o = _ndvi("a_ce", ["2024-12-02", "2024-12-18"], [1, 3])
    n = _ndvi("a_ce", ["2025-01-01", "2025-01-17", "2025-02-02"], [0, 3, np.nan], ndvi=0.6)
    n.loc[2, "ndvi"] = np.nan
    s, rel = U.unir(o, n, "ndvi")
    assert s["confiabilidade"].tolist()[:4] == [1, 3, 0, 3] and np.isnan(s["confiabilidade"].iloc[4]) and np.isnan(s["ndvi"].iloc[4])
    assert (s.dtypes == o.dtypes).all()


def _cfg_tmp(tmp_path):
    cfg = carregar_config()
    cfg["caminhos"] = {**cfg["caminhos"], **{k: f"{k}.parquet" for k in ("clima", "ndvi", "clima_2025plus", "ndvi_2025plus", "clima_atual", "ndvi_atual")}}
    _clima("a_ce", "2024-12-25", "2024-12-31").to_parquet(tmp_path / "clima.parquet")
    _clima("a_ce", "2025-01-01", "2025-01-10", nan_final=3).to_parquet(tmp_path / "clima_2025plus.parquet")
    _ndvi("a_ce", ["2024-12-18"], [1]).to_parquet(tmp_path / "ndvi.parquet")
    _ndvi("a_ce", ["2025-01-01"], [0]).to_parquet(tmp_path / "ndvi_2025plus.parquet")
    return cfg


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_unir_tudo_idempotente_e_nao_toca_os_originais(tmp_path):
    cfg = _cfg_tmp(tmp_path)
    antes = {k: _sha(tmp_path / f"{k}.parquet") for k in ("clima", "ndvi", "clima_2025plus", "ndvi_2025plus")}
    r1 = U.unir_tudo(cfg, tmp_path)
    a1 = pd.read_parquet(tmp_path / "clima_atual.parquet")
    r2 = U.unir_tudo(cfg, tmp_path)
    assert r1["clima"]["regravado"] and not r2["clima"]["regravado"] and not r2["ndvi"]["regravado"]
    assert pd.read_parquet(tmp_path / "clima_atual.parquet").equals(a1)
    assert antes == {k: _sha(tmp_path / f"{k}.parquet") for k in antes}
    assert r1["clima"]["ultimo_dia_com_chuva_e_tmax"] == "2025-01-07" and r1["clima"]["linhas_com_chuva_nan"] == 3
    assert r1["ndvi"]["confiabilidade_contagem"] == {"1": 1, "0": 1} and "provisórios" in r1["clima"]["nota"]
    assert json.loads((tmp_path / "unir_2025_relatorio.json").read_text(encoding="utf-8"))["clima"]["linhas_saida"] == 17


def test_garantir_atuais_gera_se_faltar_e_nao_regrava_se_atual(tmp_path):
    cfg = _cfg_tmp(tmp_path)
    assert not (tmp_path / "clima_atual.parquet").exists()
    U.garantir_atuais(cfg, tmp_path)
    m = (tmp_path / "clima_atual.parquet").stat().st_mtime_ns
    U.garantir_atuais(cfg, tmp_path)
    assert (tmp_path / "clima_atual.parquet").stat().st_mtime_ns == m


# ---- dados reais (pulados sem os parquets locais)
_P = RAIZ / "data/processed"
_REAL = all((_P / f).is_file() for f in ("clima_diario.parquet", "ndvi_16d.parquet", "clima_2025plus.parquet", "ndvi_2025plus.parquet"))


@pytest.mark.skipif(not _REAL, reason="parquets locais ausentes")
def test_dados_reais_atuais_sem_duplicata_em_nenhum_ponto_e_originais_intactos():
    U.garantir_atuais(carregar_config())
    for tipo, o, n, a in (("clima", "clima_diario", "clima_2025plus", "clima_diario_atual"), ("ndvi", "ndvi_16d", "ndvi_2025plus", "ndvi_16d_atual")):
        orig, novo, atual = (pd.read_parquet(_P / f"{x}.parquet") for x in (o, n, a))
        assert not atual.duplicated(["ponto_id", "data"]).any(), f"{tipo}: data duplicada (algum ponto)"
        assert len(atual) == len(orig) + len(novo) and list(atual.columns) == list(orig.columns) and (atual.dtypes == orig.dtypes).all()
        assert atual["ponto_id"].nunique() == 195 and orig["data"].max() < novo["data"].min()
        assert atual.equals(atual.sort_values(["ponto_id", "data"]).reset_index(drop=True))
        # o trecho original aparece idêntico dentro do atual (NaN inclusive)
        pd.testing.assert_frame_equal(atual[atual["data"] <= orig["data"].max()].reset_index(drop=True),
                                      orig.sort_values(["ponto_id", "data"]).reset_index(drop=True))
    assert atual["confiabilidade"].isin([0, 1, 3]).sum() + atual["confiabilidade"].isna().sum() == len(atual)
