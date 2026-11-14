"""D4: nomes oficiais do IBGE em pontos.csv. Offline: a API é substituída por um dicionário pequeno."""
import pandas as pd

from src.coleta import nomes_ibge as N


def test_atribuir_nomes_oficial_derivado_e_avisos():
    pontos = pd.DataFrame({"ponto_id": ["quixada_ce", "petrolina_pe", "sobral_ce", "x_ce", "crateus_ce"],
                           "ibge": [2311306, 2611101, None, 2399999, 2304202]})
    mun = {2311306: "Quixadá", 2304202: "Outro Nome"}                  # 2304202 não bate com o id 'crateus' => derivado + aviso
    nomes, avisos = N.atribuir_nomes(pontos, mun)
    assert nomes.tolist() == ["Quixadá (CE)", "Petrolina (PE)", "Sobral (CE)", "X (CE)", "Crateus (CE)"]
    assert len(avisos) == 3 and any("sem código" in a for a in avisos) and any("não bate" in a for a in avisos)


def test_main_so_acrescenta_nome_e_preserva_colunas(tmp_path, monkeypatch):
    dest = tmp_path / "pontos.csv"
    pd.DataFrame({"ponto_id": ["quixada_ce"], "lat": ["-4.97"], "lon": ["-39.0"], "celula_power": ["-10_-62"], "ibge": ["2311306"]}).to_csv(dest, index=False)
    monkeypatch.setattr(N, "baixar_municipios_ce", lambda: {2311306: "Quixadá"})
    N.main(destino=dest)
    antes = pd.read_csv(dest, dtype=str)
    assert antes.columns.tolist() == ["ponto_id", "lat", "lon", "celula_power", "ibge", "nome"]
    assert antes.loc[0, "lat"] == "-4.97" and antes.loc[0, "nome"] == "Quixadá (CE)"
    N.main(destino=dest)                                                # idempotente
    assert pd.read_csv(dest, dtype=str).equals(antes)
