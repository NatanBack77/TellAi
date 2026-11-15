"""Testes do consórcio com respaldo publicado (LER/UET): staging, módulo src/culturas/consorcio.py e o parâmetro opcional do motor.

Clima aqui é SINTÉTICO (tests/conftest.py): só testa lógica, nunca é resultado real.
"""
import copy
import csv
import json
import re

import pytest

from src.culturas import consorcio, motor
from src.culturas.ciclo import ClimaPonto
from src.culturas.parametros import CONSORCIO_MODOS, Parametros
from src.culturas.tabela_culturas import carregar

from tests.conftest import clima_sintetico

PALAVRAS_PROIBIDAS = ("rende mais", "recomend", "melhor que", "garant", "vai render", "aumenta a produ")


@pytest.fixture(scope="module")
def tab():
    return carregar()


@pytest.fixture(scope="module")
def linhas():
    return consorcio.carregar()


def _serie():
    return ClimaPonto.de_dataframe(clima_sintetico(), "x_ce")


def _cen(tab, modo, **kw):
    return motor.gerar_cenarios({"local": "x_ce"}, "milho", tab, clima=_serie(), params=Parametros(n_sorteios=1000, consorcio_modo=modo), **kw)


# ------------------------------------------------------------------ staging
def test_staging_existe_com_colunas_e_ids_unicos(linhas):
    assert len(linhas) >= 40
    ids = [r["id_linha"] for r in linhas]
    assert len(set(ids)) == len(ids)
    for col in ("par_a", "par_b", "ler_min", "ler_max", "entra_na_faixa", "fonte", "url_aberta", "pagina_tabela", "acesso", "tipo_evidencia"):
        assert col in linhas[0]


def test_toda_linha_tem_fonte_url_e_acesso_declarado(linhas):
    for r in linhas:
        assert r["fonte"] and r["url_aberta"].startswith("http") and r["acesso"] and r["pagina_tabela"], r["id_linha"]


def test_linha_na_faixa_tem_numero_coerente_e_criterios(linhas):
    na_faixa = [r for r in linhas if r["entra_na_faixa"] == "sim"]
    assert len(na_faixa) >= 25
    for r in na_faixa:
        assert r["tipo_evidencia"] == "experimento_pareado" and r["semiarido"] in consorcio.SEMIARIDO_OK, r["id_linha"]
        assert "sequeiro" in r["regime"] and r["par_a"] and r["par_b"], r["id_linha"]
        lo, hi = float(r["ler_min"]), float(r["ler_max"])
        assert 0.3 < lo <= hi < 3.0, r["id_linha"]
        # só se admite divergência entre razão das médias e parcial publicado (média das razões por parcela); nunca soma != total
        assert not r["conferencia"] or (("parcial publicado" in r["conferencia"] or "inferido por soma" in r["conferencia"]) and "soma dos parciais" not in r["conferencia"]), r["id_linha"]


def test_irrigado_resumo_citacao_levantamento_e_suspeito_ficam_fora(linhas):
    for r in linhas:
        if r["regime"].startswith("irrigado"):
            assert r["entra_na_faixa"] == "nao", r["id_linha"]
        if r["tipo_evidencia"] in ("resumo_apenas", "citacao_secundaria", "levantamento_sem_testemunha", "sem_LER"):
            assert r["entra_na_faixa"] == "nao", r["id_linha"]
        if r["conferencia"] and "improvável" in r["conferencia"]:
            assert r["entra_na_faixa"] == "nao", r["id_linha"]


def test_parciais_do_staging_somam_o_total_publicado(linhas):
    for r in linhas:
        if r["entra_na_faixa"] != "sim" or r["ler_min"] != r["ler_max"] or not r["ler_parciais"]:
            continue
        partes = [float(x.split("=")[1]) for x in r["ler_parciais"].split("; ") if re.match(r"^[^=]+=[0-9.]+$", x)]
        if len(partes) >= 2:
            assert sum(partes) == pytest.approx(float(r["ler_min"]), abs=0.035), r["id_linha"]


# ------------------------------------------------------------------ consorcios_para
def test_par_nao_tem_ordem():
    a, b = consorcio.consorcios_para("milho", "feijao_caupi"), consorcio.consorcios_para("feijao_caupi", "milho")
    assert a and a == b


def test_valores_lidos_do_estudo_de_tavora_quixada():
    est = {e["id_estudo"]: e for e in consorcio.consorcios_para("milho", "feijao_caupi")}
    t = est["tavora2007"]
    assert (t["ler_min"], t["ler_max"], t["n_arranjos"]) == (1.05, 1.28, 3)       # Tabela 7: 1,28; 1,22; 1,05
    assert t["ler_mediana"] == 1.22
    assert "Quixadá" in t["local"] and t["url"].startswith("https://") and "315" in t["pagina"]
    assert est["essentia2017"]["ler_min"] == est["essentia2017"]["ler_max"] == 1.34


def test_sorgo_caupi_mostra_arranjo_abaixo_de_1():
    (e,) = consorcio.consorcios_para("feijao_caupi", "sorgo")
    assert (e["ler_min"], e["ler_max"]) == (0.87, 1.35)
    assert any("abaixo de 1" in a for a in e["avisos"])


def test_par_sem_estudo_devolve_lista_vazia_e_nao_inventa():
    assert consorcio.consorcios_para("milho", "guandu") == []
    assert consorcio.consorcios_para("milho", "crotalaria_juncea") == []
    assert consorcio.resumo_par("milho", "guandu") is None
    assert consorcio.consorcios_para("milho", "cultura_que_nao_existe") == []


def test_par_so_com_estudo_fora_do_semiarido_confirmado_nao_entra():
    # algodão x caupi: só Gurinhém-PB (agreste, semiárido não confirmado): fica FORA da faixa, mas visível em fora_da_faixa
    assert consorcio.consorcios_para("algodao", "feijao_caupi") == []
    fora = consorcio.fora_da_faixa("algodao", "feijao_caupi")
    assert fora and all("semiárido" in f["motivo"] for f in fora)
    assert {f["ler_max"] for f in fora} == {"1.56", "1.17"}


def test_mandioca_com_parcial_zero_e_irrigado_nao_entram():
    assert consorcio.consorcios_para("mandioca", "milho") == []                # parcial da mandioca 0,00 (raiz não colhida)
    assert consorcio.consorcios_para("mandioca", "feijao_caupi") == []         # Pacajus: semiárido não confirmado (fora da faixa, visível)
    assert consorcio.fora_da_faixa("mandioca", "feijao_caupi")
    assert all(e["id_estudo"] != "tavora_lopes1990" for e in consorcio.consorcios_para("milho", "feijao_caupi"))
    assert all(e["id_estudo"] != "morgado1985" for e in consorcio.consorcios_para("milho", "feijao_caupi"))


def test_levantamento_sem_testemunha_e_valor_suspeito_nunca_entram(linhas):
    for p in consorcio.pares_com_respaldo():
        for e in consorcio.consorcios_para(*p):
            assert not e["id_estudo"].startswith("diaconia") and e["id_estudo"] != "pereira2015"
    assert consorcio.consorcios_para("gergelim", "milho") == []                # só Pereira 2015 (valores > 2, suspeitos)


def test_rotulo_diz_que_nao_e_do_terreno_e_nao_promete_ganho():
    r = consorcio.resumo_par("milho", "feijao_caupi")
    assert r["n_estudos"] >= 2 and r["ler_min"] <= r["ler_max"]
    assert "não é do seu terreno" in r["rotulo"] and "não prevê ganho" in r["rotulo"]
    texto = json.dumps(r, ensure_ascii=False).lower()
    assert not any(p in texto for p in PALAVRAS_PROIBIDAS)
    for e in r["estudos"]:
        assert e["fonte"] and e["url"] and e["pagina"]


def test_avisos_de_todo_estudo_incluem_a_leitura():
    for p in consorcio.pares_com_respaldo():
        for e in consorcio.consorcios_para(*p):
            assert consorcio.LEITURA in e["avisos"]
            assert e["n_estudos_par"] >= 1


def test_so_pares_entre_culturas_da_tabela_ou_declarados(tab):
    # todo par com respaldo envolve culturas que o motor conhece (senão o rótulo nunca apareceria); soja/beterraba ficam só no staging
    for a, b in consorcio.pares_com_respaldo():
        assert a in tab and b in tab, (a, b)


def test_arquivo_ausente_e_lista_vazia(tmp_path):
    assert consorcio.consorcios_para("milho", "feijao_caupi", tmp_path / "nao_existe.csv") == []


def test_criterio_secundario_binario_e_so_sem_estudo_zero():
    c = consorcio.criterio_secundario("milho", ["milho", "feijao_caupi", "guandu", "sorgo"])
    assert c == {"feijao_caupi": 1.0, "guandu": 0.0, "sorgo": 1.0}


# ------------------------------------------------------------------ parâmetro e motor
def test_padrao_e_sem_e_valida_modos():
    assert Parametros().consorcio_modo == "sem" and CONSORCIO_MODOS == ("sem", "rotulo", "desempate")
    with pytest.raises(ValueError):
        Parametros(consorcio_modo="x")


def test_padrao_sem_nao_muda_nada_e_nao_cita_consorcio(tab):
    padrao = motor.gerar_cenarios({"local": "x_ce"}, "milho", tab, clima=_serie(), params=Parametros(n_sorteios=1000))
    sem = _cen(tab, "sem")
    assert json.dumps(padrao, sort_keys=True, default=str) == json.dumps(sem, sort_keys=True, default=str)
    assert all("consorcio" not in c for c in sem)
    assert not any("consórcio" in s.lower() for c in sem for s in c["suposicoes"])
    assert not any("consórcio" in s.lower() for c in sem for s in c["lacunas"])


def _sem_consorcio(c):
    d = {k: v for k, v in c.items() if k not in ("consorcio", "lacunas", "suposicoes")}
    return json.dumps(d, sort_keys=True, default=str)


def test_rotulo_nao_muda_score_faixa_criterios_nem_alternativas(tab):
    sem, rot = _cen(tab, "sem"), _cen(tab, "rotulo")
    assert [c["rotacao"] for c in sem] == [c["rotacao"] for c in rot]
    for a, b in zip(sem, rot):
        assert _sem_consorcio(a) == _sem_consorcio(b)
    assert all("consorcio" in c for c in rot[1:]) and "consorcio" not in rot[0]
    for c in rot[1:]:
        bloco = c["consorcio"]
        assert bloco["modo"] == "rotulo" and "desempate" not in bloco
        if bloco["respaldo"] is None:
            assert bloco["lacuna"] and bloco["lacuna"] in c["lacunas"]
        else:
            assert "não é do seu terreno" in bloco["respaldo"]["rotulo"]


def test_rotulo_nao_traz_palavras_de_ganho(tab):
    rot = _cen(tab, "rotulo")
    texto = json.dumps([c["consorcio"] for c in rot[1:]], ensure_ascii=False).lower()
    assert not any(p in texto for p in PALAVRAS_PROIBIDAS)


def test_desempate_sem_empate_exato_nao_muda_a_escolha(tab):
    sem, des = _cen(tab, "sem"), _cen(tab, "desempate")
    assert [c["rotacao"] for c in sem] == [c["rotacao"] for c in des]
    for a, b in zip(sem, des):
        assert a["score"] == b["score"] and a["faixa_incerteza"] == b["faixa_incerteza"] and a["criterios"] == b["criterios"]


def test_desempate_so_age_em_empate_exato_e_diz_que_nao_e_melhor(tab):
    # clone exato de uma cultura => empate exato no corte; o par com estudo (milho x feijao_caupi) vence só o sorteio
    t2 = copy.deepcopy(tab)
    t2["feijao_caupi_b"] = copy.deepcopy(t2["feijao_caupi"])
    sem = _cen(t2, "sem", n_alternativas=1)
    des = _cen(t2, "desempate", n_alternativas=1)
    assert any("empate exato" in x for c in sem for x in c["lacunas"])
    assert consorcio.tem_respaldo("milho", des[1]["rotacao"][1])
    txt = [x for x in des[1]["lacunas"] if "desempatado pelo critério opcional" in x]
    assert txt and "não significa que a escolhida seja melhor" in txt[0]
    assert des[1]["consorcio"]["desempate"]["este_tem_respaldo"] is True


def test_desempate_nao_altera_empate_tecnico_do_motor(tab):
    sem, des = _cen(tab, "sem"), _cen(tab, "desempate")
    for a, b in zip(sem, des):
        assert a["faixa_incerteza"].get("empate_tecnico") == b["faixa_incerteza"].get("empate_tecnico")
        assert a["faixa_incerteza"].get("empate_tecnico_com") == b["faixa_incerteza"].get("empate_tecnico_com")


def test_suposicao_declara_o_modo_ligado(tab):
    s = " ".join(Parametros(consorcio_modo="desempate").suposicoes())
    assert "consorcio_modo='desempate'" in s and "não significa que a alternativa seja melhor" in s
    assert "consorcio_modo='rotulo'" in " ".join(Parametros(consorcio_modo="rotulo").suposicoes())
    assert "consorcio_modo" not in " ".join(Parametros().suposicoes())


def test_motor_e_parametros_nao_citam_culturas_nem_numeros_de_ler():
    from pathlib import Path

    from src.culturas import parametros
    for mod in (motor, parametros):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert not re.search(r"\b(milho|sorgo|caupi|mamona|palma|girassol)\b", src, re.I), mod.__name__


def test_staging_nao_alimenta_a_tabela_de_culturas(tab):
    # o LER não vira atributo da tabela do motor
    for c, d in tab.items():
        assert not any("ler" in k.lower() or "consorcio" in k.lower() for k in d["atributos"]), c


def test_csv_do_staging_e_legivel_com_csv_padrao():
    with open(consorcio.CAMINHO_PADRAO, newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == len(consorcio.carregar())
