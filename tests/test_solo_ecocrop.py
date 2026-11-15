"""Critério opcional de solo (solo_modo='ecocrop'): staging com fonte, notas, padrão inalterado, efeito."""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.app import mvp as M
from src.culturas import solo_ecocrop as SE
from src.culturas.motor import avaliar_local
from src.culturas.parametros import Parametros

RAIZ = Path(__file__).resolve().parents[1]
BASE = json.loads((RAIZ / "experimentos/calendario_solo/baseline_padrao.json").read_text())


def test_staging_16_culturas_com_fonte_e_trecho():
    d = pd.read_csv(RAIZ / "data/culturas/solo_staging.csv", dtype=str, keep_default_na=False)
    assert d.cultura_id.nunique() == 16
    v = d[d.status == "verificado"]
    assert len(v) > 200 and (v.valor != "").all()
    for col in ("fonte", "url", "coluna", "trecho", "data_consulta"):
        assert (d[col] != "").all(), col
    assert (v.apply(lambda r: f"{r.coluna}={r.valor}" in r.trecho, axis=1)).all()
    assert set(d[d.status == "lacuna"].valor) == {""}          # lacuna nunca vira valor inventado


def test_staging_bate_com_o_csv_do_ecocrop_quando_presente():
    arq = RAIZ / "experimentos/calendario_solo/entrada/EcoCrop_DB.csv"
    if not arq.exists():
        pytest.skip("espelho do EcoCrop não está local")
    e = pd.read_csv(arq, encoding="latin-1", dtype=str).set_index("EcoPortCode")
    d = pd.read_csv(RAIZ / "data/culturas/solo_staging.csv", dtype=str, keep_default_na=False)
    for r in d[d.status == "verificado"].itertuples():
        assert e.loc[r.ecoport_code, r.coluna].strip() == r.valor


SOLO = {"ph_agua": 6.0, "textura": "médio", "fracao_pixels_validos": 1.0, "pixel_central_valido": True}


def test_nota_ph_trapezio_e_palma_sem_ph_ate_6_5():
    assert SE.nota_solo("milho", SOLO)["ph"]["nota"] == 1.0                        # faixa ótima 5-7
    assert SE.nota_solo("milho", {**SOLO, "ph_agua": 4.5})["ph"]["nota"] == 0.0    # PHMIN 4.5
    assert SE.nota_solo("palma_forrageira", SOLO)["nota"] == 0.0                   # PHMIN 6.5 do EcoCrop


def test_textura_otima_faixa_e_lacuna():
    n = SE.nota_solo("milho", SOLO)
    assert n["textura"] is None and "textura" in n["sem_dado"]                      # milho sem TEXT no EcoCrop: lacuna, não nota
    assert SE.nota_solo("feijao_caupi", {**SOLO, "textura": "argiloso"})["textura"]["nota"] == 0.5   # heavy só na faixa absoluta
    assert SE.nota_solo("feijao_caupi", SOLO)["textura"]["nota"] == 1.0


def test_fatores_sem_dado_ficam_como_lacuna_e_aviso_de_mapa_global():
    n = SE.nota_solo("algodao", SOLO)
    assert set(SE.FATORES_SEM_DADO) <= set(n["sem_dado"])
    assert "mapa global" in " ".join(n["avisos"]) and "não análise" in " ".join(n["avisos"])


def test_sem_dado_do_ponto_nao_aplica():
    n = SE.nota_solo("milho", None)
    assert n["aplicado"] is False and n["nota"] is None


def test_aviso_de_pixels_validos():
    n = SE.nota_solo("milho", {**SOLO, "fracao_pixels_validos": 0.05})
    assert any("baixa confiança" in a for a in n["avisos"])


def test_parametro_invalido():
    with pytest.raises(ValueError):
        Parametros(solo_modo="x")
    assert Parametros().solo_modo == "sem"


@pytest.mark.parametrize("zarc", [False, True])
def test_padrao_nao_muda_o_resultado(zarc):
    tab = M.carregar_tabela()
    av = avaliar_local(tab, M.clima_ponto("quixada_ce"), Parametros(usar_zarc=zarc, n_sorteios=100))["culturas"]
    esp = BASE[f"quixada_ce|zarc={zarc}"]
    for c, e in esp.items():
        assert av[c]["estado"] == e["estado"]
        assert (av[c]["res"] or {}).get("decendio") == e["decendio"]
        if e["adeq_media"] is not None:
            assert av[c]["res"]["adeq_media"] == pytest.approx(e["adeq_media"], abs=1e-9)
        assert (av[c]["av"] or {}).get("solo") is None


def test_ligado_palma_fica_inviavel_e_so_reduz_nota():
    tab = M.carregar_tabela()
    cl = M.clima_ponto("quixada_ce")
    a = avaliar_local(tab, cl, Parametros(n_sorteios=100))["culturas"]
    b = avaliar_local(tab, cl, Parametros(n_sorteios=100, solo_modo="ecocrop"))["culturas"]
    assert b["palma_forrageira"]["estado"] == "inviavel" and b["palma_forrageira"]["av"]["solo"]["aplicado"]
    for c in a:
        if a[c]["res"] and b[c]["res"]:
            assert b[c]["res"]["adeq_media"] <= a[c]["res"]["adeq_media"] + 1e-12     # o solo só limita
    assert any("solo LIGADO" in s for s in Parametros(solo_modo="ecocrop").suposicoes())
