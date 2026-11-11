import pandas as pd
import pytest

from src.modelos.entrada import DadosInvalidos, carregar_config, carregar_entradas
from src.modelos.sintetico import gerar_sinteticos


def _cfg_para(tmp_path, arqs):
    cfg = carregar_config()
    cfg["caminhos"] = {
        "clima": str(arqs["clima"].relative_to(tmp_path)),
        "ndvi": str(arqs["ndvi"].relative_to(tmp_path)),
        "umidade_solo": str(arqs.get("umidade_solo", tmp_path / "nao_existe.parquet").relative_to(tmp_path)),
        "saida": "saida",
    }
    return cfg


def test_config_tem_semente():
    assert carregar_config()["semente"] == 42


def test_nomes_sinteticos(tmp_path):
    arqs = gerar_sinteticos(tmp_path, n_celulas=2, ano_ini=2020, ano_fim=2021)
    assert all("SINTETICO" in p.name for p in arqs.values())


def test_carga_completa(tmp_path):
    arqs = gerar_sinteticos(tmp_path, n_celulas=2, ano_ini=2020, ano_fim=2021)
    ent = carregar_entradas(_cfg_para(tmp_path, arqs), tmp_path)
    assert ent["umidade_solo"] is not None
    assert pd.api.types.is_datetime64_any_dtype(ent["clima"]["data"])


def test_umidade_opcional(tmp_path):
    arqs = gerar_sinteticos(tmp_path, n_celulas=2, ano_ini=2020, ano_fim=2021, com_umidade=False)
    ent = carregar_entradas(_cfg_para(tmp_path, arqs), tmp_path)
    assert ent["umidade_solo"] is None


def test_arquivo_ausente_para(tmp_path):
    arqs = gerar_sinteticos(tmp_path, n_celulas=2, ano_ini=2020, ano_fim=2021)
    arqs["ndvi"].unlink()
    with pytest.raises(DadosInvalidos, match="ausente"):
        carregar_entradas(_cfg_para(tmp_path, arqs), tmp_path)


def test_coluna_ausente_para(tmp_path):
    arqs = gerar_sinteticos(tmp_path, n_celulas=2, ano_ini=2020, ano_fim=2021)
    df = pd.read_parquet(arqs["clima"]).drop(columns=["celula_power"])
    df.to_parquet(arqs["clima"])
    with pytest.raises(DadosInvalidos, match="celula_power"):
        carregar_entradas(_cfg_para(tmp_path, arqs), tmp_path)


def test_sintetico_reprodutivel(tmp_path):
    a = gerar_sinteticos(tmp_path / "a", n_celulas=2, ano_ini=2020, ano_fim=2021, semente=7)
    b = gerar_sinteticos(tmp_path / "b", n_celulas=2, ano_ini=2020, ano_fim=2021, semente=7)
    pd.testing.assert_frame_equal(pd.read_parquet(a["ndvi"]), pd.read_parquet(b["ndvi"]))
