"""Testes do pipeline de cenários. Dados de clima/RAG aqui são SINTÉTICOS (só verificam lógica e formato)."""
import json

import pandas as pd
import pytest

from src.culturas.motor import AVISO, validar_cenario
from src.culturas.tabela_culturas import carregar
from src.pipeline import gerar_cenarios as G


def _clima(pid="x_ce", anos=range(2001, 2025), chuva_dia=2.0, tmax=34.0, tmin=22.0):
    datas = pd.date_range(f"{min(anos)}-01-01", f"{max(anos)}-12-31")
    return pd.DataFrame({"ponto_id": pid, "celula_power": "-1_-1", "data": datas, "chuva_mm": chuva_dia,
                         "tmax_c": tmax, "tmin_c": tmin, "radiacao": 20.0})


PONTO = {"ponto_id": "x_ce", "lat": -5.0, "lon": -39.0, "celula_power": "-1_-1"}


def test_perfil_calculado_do_arquivo():
    p, lac = G.perfil_local(PONTO, _clima(), None)
    assert p["temp_media_c"] == 28.0 and p["tmax_media_c"] == 34.0
    assert p["chuva_anual_media_mm"] == pytest.approx(2.0 * 365.25, abs=1.0)
    assert p["anos_chuva"] == [2001, 2024, 24]
    assert p["sm_superficie_media"] is None
    assert any("SMAP" in l for l in lac)


def test_perfil_sem_clima_vira_lacuna():
    p, lac = G.perfil_local({"ponto_id": "outro"}, _clima(), None)
    assert p["temp_media_c"] is None and p["chuva_anual_media_mm"] is None
    assert any(l.startswith("clima:") for l in lac)


def test_ano_incompleto_nao_entra_na_media():
    c = _clima(anos=range(2001, 2025))
    c = c[~((c["data"].dt.year == 2010) & (c["data"].dt.month > 6))]
    p, lac = G.perfil_local(PONTO, c, None)
    assert p["anos_chuva"][2] == 23 and any("23 de 24" in l for l in lac)


def test_solo_entra_quando_existe():
    solo = pd.DataFrame({"ponto_id": ["x_ce"] * 2, "data": pd.to_datetime(["2015-04-01", "2015-04-02"]),
                         "sm_superficie": [0.1, 0.3], "sm_raiz": [0.2, 0.2]})
    p, _ = G.perfil_local(PONTO, _clima(), solo)
    assert p["sm_superficie_media"] == 0.2 and p["sm_periodo"][0] == "2015-04-01"


def _busca_vazia(q, k):
    return {"sem_evidencia": True, "mensagem": "sem evidência", "trechos": []}


def test_cenarios_sem_rag_declaram_sem_evidencia():
    tab = carregar()
    cens = G.montar_cenarios(PONTO, "milho", _clima(), None, tab, busca=_busca_vazia)
    assert len(cens) >= 1 and cens[0]["atual"] is True
    for c in cens:
        assert c["trechos"] == [] and isinstance(c["faixa_incerteza"], dict)
        assert c["faixa_incerteza"]["min"] <= c["faixa_incerteza"]["max"]
        assert c["aviso"] == AVISO and validar_cenario(c) == []
        assert not any(l.startswith("faixa_incerteza") for l in c["lacunas"])
        assert any("DENTRO do ciclo" in s for s in c["suposicoes"]) and not any("chuva anual média" in s for s in c["suposicoes"])
        assert all(d["evidencia_rag"]["sem_evidencia"] for d in c["criterios"].values())


def test_sem_clima_do_ponto_so_atual_sem_score():
    cens = G.montar_cenarios({"ponto_id": "outro_ce"}, "milho", _clima(), None, carregar(), busca=_busca_vazia)
    assert len(cens) == 1 and cens[0]["score"] is None and cens[0]["faixa_incerteza"] is None
    assert any("clima" in l for l in cens[0]["lacunas"])


def test_locais_com_clima_diferente_diferem_nos_cenarios():
    tab = carregar()
    seco = _clima("seco_ce", chuva_dia=0.9)
    umido = _clima("umido_ce", chuva_dia=3.0)
    clima = pd.concat([seco, umido])
    a = G.montar_cenarios({"ponto_id": "umido_ce"}, "milho", clima, None, tab, busca=_busca_vazia)
    b = G.montar_cenarios({"ponto_id": "seco_ce"}, "milho", clima, None, tab, busca=_busca_vazia)
    assert a[0]["score"] != b[0]["score"]
    assert a[0]["janela_plantio"]["chuva_ciclo_mm"] != b[0]["janela_plantio"]["chuva_ciclo_mm"]
    assert a[0]["faixa_incerteza"] != b[0]["faixa_incerteza"]


def test_trecho_so_entra_se_citar_cultura_e_criterio():
    def busca(q, k):
        return {"sem_evidencia": False, "trechos": [
            {"n": 1, "arquivo": "a.pdf", "pagina": 3, "texto": "O milho exige temperatura elevada para germinar."},
            {"n": 2, "arquivo": "b.pdf", "pagina": 1, "texto": "Texto sobre outra planta e temperatura."}]}
    ev = G.evidencias("milho", "Milho", busca=busca)
    assert [t["arquivo"] for t in ev["temperatura"]["trechos"]] == ["a.pdf"]
    assert ev["chuva"]["sem_evidencia"] is True  # "chuva" não aparece no trecho


def test_anexar_renumera_e_deduplica():
    c = {"criterios": {"temperatura": {}, "chuva": {}}}
    t = {"arquivo": "a.pdf", "pagina": 3, "texto": "x"}
    G.anexar_evidencias(c, {"temperatura": {"sem_evidencia": False, "trechos": [t]},
                            "chuva": {"sem_evidencia": False, "trechos": [t]}})
    assert len(c["trechos"]) == 1 and c["trechos"][0]["n"] == 1
    assert c["criterios"]["chuva"]["trecho_n"] == 1


def test_cultura_atual_obrigatoria(tmp_path):
    with pytest.raises(SystemExit):
        G.rodar(None, 1, None, None, saida=tmp_path)


def test_cultura_inexistente_falha(tmp_path):
    with pytest.raises(SystemExit):
        G.rodar(["quixada_ce"], 1, "banana_inventada", None, saida=tmp_path)


def test_escolha_de_pontos_determinista():
    pts = pd.DataFrame({"ponto_id": [f"m{i}_ce" for i in range(30)] + ["z_pe"]})
    a = G.escolher_pontos(pts, None, 10)
    assert a == G.escolher_pontos(pts, None, 10) and len(a) == 10
    assert all(p["ponto_id"].endswith("_ce") for p in a)


def test_rodar_grava_json_no_contrato_e_app_le(tmp_path):
    arqs = G.rodar(["quixada_ce"], 1, "milho", None, saida=tmp_path, busca=_busca_vazia)
    dado = json.loads(arqs[0].read_text(encoding="utf-8"))
    from src.app import logica as L
    cens, erros = L.carregar_cenarios(tmp_path)
    assert erros == [] and len(cens) == len(dado)
    assert L.local_id(cens[0]["local"]) == "quixada_ce"
    assert {k for k in L.CAMPOS_CENARIO} <= set(cens[0])
    assert all(isinstance(c["faixa_incerteza"], dict) and L.faixa(c) is not None for c in cens)
    assert L.resumo_incerteza(cens[1])["disponivel"]


def test_parametros_chegam_ao_cenario_e_cli(tmp_path, monkeypatch):
    # a CLI usa o RAG real, que depende de indice/ (ignorado pelo git): o teste não pode depender dele
    monkeypatch.setattr(G.rag, "buscar", lambda q, k=5, **kw: _busca_vazia(q, k))
    pr = G.Parametros(ciclo_modo="min", n_sorteios=200, semente=5)
    cens = G.montar_cenarios(PONTO, "milho", _clima(chuva_dia=6.0), None, carregar(), busca=_busca_vazia, params=pr)
    f = cens[1]["faixa_incerteza"]
    assert f["n_sorteios"] == 200 and f["semente"] == 5 and cens[1]["janela_plantio"]["ciclo_modo"] == "min"
    assert any("MÍNIMO" in s for s in cens[1]["suposicoes"])
    G.main(["--pontos", "quixada_ce", "--cultura-atual", "milho", "--saida", str(tmp_path), "--ciclo-modo", "max",
            "--n-sorteios", "200"])
    dado = json.loads((tmp_path / "quixada_ce.json").read_text(encoding="utf-8"))
    assert dado[0]["janela_plantio"]["ciclo_modo"] == "max"
