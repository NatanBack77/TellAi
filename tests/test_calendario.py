"""Calendário verificado (ZARC x motor x PAM) e frase de limite da viabilidade gerada dos critérios aplicados."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.culturas import avaliar_sequencia as AS
from src.culturas import zarc as Z
from src.llm import fatos as F

RAIZ = Path(__file__).resolve().parents[1]
DEC = Z.DEC


def test_leitura_dec_valores_e_monotonia_do_risco():
    d = pd.read_parquet(RAIZ / "data/processed/zarc_ce.parquet")
    d = d[d.Cod_Outros_Manejos == 1]
    assert set(np.unique(d[DEC].to_numpy())) == {0, 20, 30, 40}
    for geo in (2311306, 2304202, 2313401):
        for c in ("milho", "feijao_caupi", "mandioca", "gergelim"):
            j = {r: Z.janela(geo, c, r)["permitido"] for r in (20, 30, 40)}
            assert (j[20] <= j[30]).all() and (j[30] <= j[40]).all()


def test_janela_bate_com_as_linhas_brutas():
    d = pd.read_parquet(RAIZ / "data/processed/zarc_ce.parquet")
    d = d[(d.Cod_Outros_Manejos == 1) & (d.geocodigo == 2311306) & (d.Nome_cultura == "Feijão Caupi")]
    rec = next(r for r in Z.PREFERENCIA if (d.recurso == r).any())
    X = d[d.recurso == rec][DEC].to_numpy(float)
    esperado = ((X > 0) & (X <= 30)).any(axis=0)
    assert (Z.janela(2311306, "feijao_caupi", 30)["permitido"] == esperado).all()


def test_sem_zarc_vira_none_nunca_inventa():
    for c in ("guandu", "crotalaria_juncea", "feijao_de_porco", "mucuna", "sorgo"):
        assert Z.janela(2311306, c, 30)["permitido"] is None


def test_arquivos_do_calendario():
    r = pd.read_csv(RAIZ / "experimentos/calendario_solo/saida/calendario_resumo.csv")
    assert r.ponto_id.nunique() == 15 and r.cultura.nunique() == 16 and len(r) == 240
    assert set(r[r.zarc == "sem ZARC"].cultura) == {"sorgo", "guandu", "crotalaria_juncea", "feijao_de_porco", "mucuna"}
    # cultura com ZARC e motor COM ZARC viável: início dentro da janela
    i = pd.read_csv(RAIZ / "experimentos/calendario_solo/saida/inconsistencias.csv")
    assert not i.tipo.str.contains("COM ZARC sugere início fora").any()


def _av(zarcs):
    return {"culturas": {f"c{i}": {"av": {"estado": "avaliavel", "zarc": z}} for i, z in enumerate(zarcs)}}


def test_criterios_zarc_sim_parcial_nao():
    ok = {"aplicado": True, "risco": 30, "solo": "qualquer", "aproximada": False}
    ap = {**ok, "aproximada": True}
    assert AS.criterios_aplicados(_av([ok, ok]))["zarc"] == "sim"
    assert AS.criterios_aplicados(_av([ok, ap]))["zarc"] == "parcial"
    c = AS.criterios_aplicados(_av([{"aplicado": False}, None]))
    assert c["zarc"] == "nao" and c["semente"] is False and c["mercado"] is False and c["solo_ecocrop"] is False


def test_frase_gerada_dos_criterios():
    com = AS.criterios_aplicados(_av([{"aplicado": True, "risco": 30, "solo": "qualquer", "aproximada": False}]))
    tx, sp = F.texto_limite_viabilidade(com)
    assert "zoneamento" in sp and "semente" in sp and "preço" in sp and "solo" in sp
    assert "só chuva" not in sp.lower() and "não olha o zoneamento" not in sp
    sem = AS.criterios_aplicados(_av([{"aplicado": False}]))
    assert "ainda não olha as datas do zoneamento" in F.texto_limite_viabilidade(sem)[1]
    com["solo_ecocrop"] = True
    sp2 = F.texto_limite_viabilidade(com)[1]
    assert "o solo (pelo mapa" in sp2 and "ainda não olha o solo" not in sp2
    assert "zoneamento" not in F.texto_limite_viabilidade(None)[1]       # sem critérios: não afirma o que não sabe


def test_fato_do_limite_vem_da_sugestao_real():
    s = AS.sugerir_por_foco("quixada_ce", None)
    assert s["criterios"]["zarc"] in ("sim", "parcial")           # o ZARC (padrão do app) ENTRA na sugestão
    c = F._Coletor()
    F.fatos_sugestao(c, s, {k: k for k in s["viaveis"]})
    f = next(x for x in c.fatos if x.get("papel") == "limite")
    assert "zoneamento" in f["texto_simples"] and "olha só chuva" not in f["texto_simples"]
