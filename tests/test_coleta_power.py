"""D5: o coletor POWER não pode apagar colunas de pontos.csv que ele não produz (ex.: ibge)."""
import pandas as pd

from src.coleta.power import gravar_pontos


def test_gravar_pontos_preserva_ibge_e_deixa_ponto_novo_vazio(tmp_path):
    dest = tmp_path / "pontos.csv"
    pd.DataFrame({"ponto_id": ["a_ce", "b_ce"], "lat": [1.0, 2.0], "lon": [3.0, 4.0],
                  "celula_power": ["x", "y"], "ibge": [2300001, 2300002]}).to_csv(dest, index=False)
    pontos = [{"ponto_id": "a_ce", "lat": 1.0, "lon": 3.0}, {"ponto_id": "b_ce", "lat": 2.0, "lon": 4.0},
              {"ponto_id": "c_ce", "lat": 5.0, "lon": 6.0}]
    gravar_pontos(pontos, {"a_ce": "x", "b_ce": "y", "c_ce": "z"}, dest)
    d = pd.read_csv(dest, dtype={"ibge": "Int64"})
    assert list(d.columns) == ["ponto_id", "lat", "lon", "celula_power", "ibge"]
    assert d.set_index("ponto_id")["ibge"].to_dict()["a_ce"] == 2300001
    assert pd.isna(d.set_index("ponto_id").loc["c_ce", "ibge"])      # ponto novo: lacuna, não inventado


def test_gravar_pontos_sem_arquivo_previo(tmp_path):
    dest = tmp_path / "pontos.csv"
    d = gravar_pontos([{"ponto_id": "a_ce", "lat": 1.0, "lon": 3.0}], {"a_ce": "x"}, dest)
    assert list(d.columns) == ["ponto_id", "lat", "lon", "celula_power"]
