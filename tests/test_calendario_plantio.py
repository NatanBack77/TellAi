"""Calendário de plantio (src/culturas/calendario_plantio.py): puro, com data de hoje injetada e dados SINTÉTICOS controlados (clima, verde, diagnóstico, ZARC).
Só a tabela de culturas e o ciclo da FAO são os reais do projeto (valores conferidos pelos próprios testes de staging). Sem rede, sem IA."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.culturas import calendario_plantio as CP

HOJE = date(2026, 11, 14)
CULTURAS = ["milho", "feijao_caupi", "sorgo", "mandioca", "guandu", "palma_forrageira"]


def clima(fator_ano=None, pico=2.0, meses=(2, 3, 4, 5), anos=range(2001, 2027), seca=None):
    """Chuva diária = `pico` nos `meses`, 0 no resto; `fator_ano` {ano: multiplicador}; `seca` = (ini, fim) com chuva 0."""
    datas = pd.date_range(f"{min(anos)}-01-01", f"{max(anos)}-12-31")
    v = np.where(datas.month.isin(meses), pico, 0.0)
    if fator_ano:
        v = v * np.array([fator_ano.get(a, 1.0) for a in datas.year])
    if seca:
        v = np.where((datas >= pd.Timestamp(seca[0])) & (datas <= pd.Timestamp(seca[1])), 0.0, v)
    return pd.DataFrame({"ponto_id": "x_ce", "data": datas, "chuva_mm": v})


def zarc_fake(janelas):
    """`janelas` {risco: [índices dos decêndios 0..35 permitidos]}; cultura fora de `sem` tem zoneamento."""
    def fn(geo, cid, risco, solo):
        if cid in ("sorgo", "guandu", "palma_forrageira"):
            return {"permitido": None, "motivo": f"cultura '{cid}' sem correspondência clara no ZARC (ou sem ZARC)"}
        v = np.zeros(36, bool)
        v[janelas[risco]] = True
        return {"permitido": v, "recurso": "safra_teste", "risco": risco, "solo": solo}
    return fn


JAN = {20: [4, 5], 30: [4, 5, 6], 40: [3, 4, 5, 6, 7]}        # dec 4 = 2º dec. de fev.; 6 = 1º de mar.
DIAG = {"veranicos": {"quinzenas_estacao_chuvosa": [3, 4, 5, 6, 7, 8, 9, 10], "distribuicao": {"mediana": 7, "p90": 12, "max": 20}, "n_estacoes": 20, "limiar_chuva_mm": 1.0},
        "solo_nu": {"quinzenas_tipicas": [19, 20, 21], "limiar_ndvi": 0.25}}


def ctx(**kw):
    base = dict(clima=clima(), ndvi=None, diagnostico=DIAG, geocodigo=123, zarc_fn=zarc_fake(JAN), proximas_fn=lambda cid, c: {"disponivel": True, "de": cid},
                proibidas=())
    base.update(kw)
    return CP.Contexto("x_ce", **base)


def um(cultura, quando, hoje=HOJE, **kw):
    pl = {"cultura": cultura, "quando": quando}
    for k in ("ciclo_dias", "manejo"):
        if k in kw:
            pl[k] = kw.pop(k)
    return CP.calcular("x_ce", [pl], hoje, contexto=ctx(**kw))["plantios"][0]


# ------------------------------------------------------------------------------------------------ 'quando'
def test_mes_sem_ano_e_o_mais_recente_que_ja_comecou():
    assert CP.resolver_quando({"mes": 2}, HOJE)["ini"] == date(2026, 2, 1)
    assert CP.resolver_quando({"mes": 12}, HOJE)["ini"] == date(2025, 12, 1)          # dezembro de 2026 ainda não começou
    q = CP.resolver_quando({"mes": 11}, HOJE)                                         # o mês corrente já começou: vale até hoje
    assert q["ini"] == date(2026, 11, 1) and q["fim"] == HOJE and q["ano_inferido"]
    assert CP.resolver_quando({"mes": 11, "parte": "fim"}, HOJE)["ini"] == date(2025, 11, 21)   # 'fim de novembro' dito dia 14: o do ano passado
    assert CP.resolver_quando({"mes": 2, "ano": 2025}, HOJE)["ano_inferido"] is False


def test_parte_do_mes_data_exata_e_faixa():
    q = CP.resolver_quando({"mes": 2, "parte": "meio"}, HOJE)
    assert (q["ini"], q["fim"], q["ref"], q["precisao"]) == (date(2026, 2, 11), date(2026, 2, 20), date(2026, 2, 15), "decendio")
    assert CP.resolver_quando({"mes": 2, "parte": "fim"}, HOJE)["fim"] == date(2026, 2, 28)
    assert CP.resolver_quando("2026-03-05", HOJE)["precisao"] == "dia"
    f = CP.resolver_quando({"de": "2026-03-01", "ate": "2026-03-07", "precisao": "semana"}, HOJE)
    assert f["ref"] == date(2026, 3, 4) and f["precisao"] == "semana"


def test_schema_estrito_dos_plantios():
    ok = CP.validar_plantios([{"cultura": "milho", "quando": {"mes": 2}}], CULTURAS)
    assert ok == [{"cultura": "milho", "quando": {"mes": 2}, "ciclo_dias": None, "manejo": "sequeiro"}]
    ruins = [{"cultura": "melancia", "quando": {"mes": 2}}, {"cultura": "milho", "quando": {"mes": 13}}, {"cultura": "milho", "quando": {"mes": 2, "x": 1}},
             {"cultura": "milho", "quando": {"mes": 2}, "ciclo_dias": 5}, {"cultura": "milho", "quando": {"mes": 2}, "ciclo_dias": True},
             {"cultura": "milho", "quando": {"mes": 2}, "nome": "João"}, {"cultura": "milho", "quando": "ontem"}, {"cultura": "milho", "quando": {"mes": 2}, "manejo": "x"},
             {"cultura": "milho"}, "milho", {"cultura": "milho", "quando": {"data": "2026-02-30"}}, {"cultura": "milho", "quando": {"de": "2026-03-07", "ate": "2026-03-01"}}]
    for r in ruins:
        with pytest.raises(ValueError):
            CP.validar_plantios([r], CULTURAS)
    with pytest.raises(ValueError):
        CP.validar_plantios([{"cultura": "milho", "quando": {"mes": 2}}] * 13, CULTURAS)
    with pytest.raises(ValueError):
        CP.validar_plantios({"cultura": "milho"}, CULTURAS)


# ------------------------------------------------------------------------------------------------ fase e colheita (6 culturas, inclusive sem FAO)
@pytest.mark.parametrize("cultura,fonte,dias_ref,dmin,dmax", [("milho", "fao", 140, 125, 180), ("feijao_caupi", "fao", 100, 100, 100), ("sorgo", "fao", 130, 125, 130),
                                                              ("mandioca", "fao", 210, 210, 210), ("guandu", "ecocrop", 228, 90, 365),
                                                              ("palma_forrageira", "ecocrop", 205, 140, 270)])
def test_ciclo_e_colheita_por_cultura_com_a_fonte(cultura, fonte, dias_ref, dmin, dmax):
    p = um(cultura, {"data": "2026-10-01"})
    c = p["ciclo"]
    assert (c["fonte"], c["dias_ref"], c["dias_min"], c["dias_max"]) == (fonte, dias_ref, dmin, dmax)
    assert c["origem"].startswith("FAO-56") if fonte == "fao" else c["origem"].startswith("EcoCrop")
    assert p["colheita"]["de"] == str(date(2026, 10, 1).toordinal() and date.fromordinal(date(2026, 10, 1).toordinal() + dmin))
    assert p["colheita"]["ate"] == str(date.fromordinal(date(2026, 10, 1).toordinal() + dmax))
    assert (c["estagios"] is not None) == (fonte == "fao")


def test_fase_fao_por_estagio_com_data_injetada():
    # milho FAO: ini 25, dev 40, mid 45, late 30 (acumulado 25, 65, 110, 140)
    casos = {"2026-10-25": "ini", "2026-10-10": "dev", "2026-09-01": "mid", "2026-07-20": "late", "2026-06-01": "depois"}
    for d, esperado in casos.items():
        f = um("milho", {"data": d})["fase"]
        dias = (HOJE - date.fromisoformat(d)).days
        assert f["tipo"] == "fao" and f["dias_ref"] == dias
        assert (f["fase_min"] == esperado) and (f["depois_do_ciclo"] == (esperado == "depois")), (d, dias, f)


def test_fase_por_fracao_quando_nao_ha_estagios_da_fao():
    p = um("guandu", {"data": "2026-07-04"})                     # 133 dias de um ciclo de referência de 228
    f = p["fase"]
    assert f["tipo"] == "fracao" and f["dias_ref"] == 133 and abs(f["fracao_min"] - 133 / 228) < 1e-9 and f["ciclo_total"] == 228
    assert p["status"] == "em_andamento"


def test_status_ciclo_concluido_so_depois_da_janela_de_colheita():
    p = um("milho", {"data": "2026-06-01"})                                       # 166 dias: fase 'depois' (140), mas ainda dentro da janela de colheita (até 180)
    assert p["status"] == "em_andamento" and p["fase"]["depois_do_ciclo"] is True
    assert um("milho", {"data": "2026-04-01"})["status"] == "ciclo_concluido"      # 227 dias > 180


def test_mes_dito_vira_faixa_de_dias_e_de_fases():
    p = um("milho", {"mes": 9})                                   # setembro: 45 a 74 dias
    assert p["quando"]["precisao"] == "mes" and p["dias_desde"] == {"min": 45, "ref": 60, "max": 74}
    f = p["fase"]
    assert f["fase_min"] == "dev" and f["fase_max"] == "mid" and f["fases"] == ["dev", "mid"]
    assert p["colheita"]["de"] == "2026-11-09" or p["colheita"]["de"] < p["colheita"]["ate"]


def test_ciclo_da_semente_sobrepoe_a_referencia():
    p = um("milho", {"data": "2026-10-01"}, ciclo_dias=90)
    assert p["ciclo"]["fonte"] == "informado" and p["ciclo"]["dias_ref"] == 90 and p["ciclo"]["estagios"] is None
    assert p["colheita"] == {**p["colheita"], "de": "2026-12-30", "ate": "2026-12-30", "unica": True}
    assert p["fase"]["tipo"] == "fracao" and abs(p["fase"]["fracao_min"] - 44 / 90) < 1e-9


# ------------------------------------------------------------------------------------------------ ZARC
def test_zarc_dentro_com_o_menor_risco_que_permite():
    z = um("milho", {"data": "2026-02-15"})["zarc"]                  # dec 4: permitido já no risco 20
    assert z["situacao"] == "dentro" and z["risco_ate"] == 20 and z["solo"] == "qualquer"
    z = um("milho", {"data": "2026-03-05"})["zarc"]                  # dec 6: só no risco 30
    assert z["situacao"] == "dentro" and z["risco_ate"] == 30
    z = um("milho", {"data": "2026-03-15"})["zarc"]                  # dec 7: só no risco 40
    assert z["situacao"] == "dentro" and z["risco_ate"] == 40
    assert z["janela_30"] == "do 2º decêndio de fevereiro ao 1º decêndio de março" and z["datas_30"] == [["2026-02-11", "2026-03-10"]]


def test_zarc_fora_parcial_sem_zoneamento_e_irrigado():
    assert um("milho", {"data": "2026-05-15"})["zarc"]["situacao"] == "fora"
    z = um("milho", {"mes": 3})["zarc"]                               # março inteiro: dec 6, 7 (permitidos no 40) e 8 (não)
    assert z["situacao"] == "parcial" and z["por_decendio"]["3º decêndio de março"] is None
    sem = um("sorgo", {"data": "2026-03-05"})["zarc"]
    assert sem["disponivel"] is False and sem["situacao"] == "sem_zoneamento" and "sem ZARC" in sem["motivo"]
    irr = um("milho", {"data": "2026-03-05"}, manejo="irrigado")["zarc"]
    assert irr["disponivel"] is False and irr["situacao"] == "nao_se_aplica"
    assert any("zoneamento" in x for x in um("sorgo", {"data": "2026-03-05"})["lacunas"])


# ------------------------------------------------------------------------------------------------ chuva desde o plantio
def test_chuva_acumulada_e_posicao_entre_os_anos_anteriores():
    # 2001..2025 com fator 0,5 + 0,04*k (k = 0..24); 2026 com fator 1,0. Plantio 2026-03-01 de milho com ciclo informado de 60 dias: 01/03 a 29/04 (60 dias).
    fatores = {2001 + k: 0.5 + 0.04 * k for k in range(25)}
    p = um("milho", {"data": "2026-03-01"}, ciclo_dias=60, clima=clima(fator_ano=fatores))
    ch = p["chuva"]
    assert ch["disponivel"] and ch["ini"] == "2026-03-01" and ch["fim"] == "2026-04-29" and ch["dias"] == 60
    assert ch["mm"] == 120.0                                                            # 60 dias x 2 mm
    assert ch["n_anos"] == 25 and ch["historico"]
    assert ch["anos_com_menos"] == 13 and ch["posicao"] == "perto"                      # fatores < 1,0: k = 0..12
    assert ch["min_mm"] == 60.0 and ch["max_mm"] == 175.2 and ch["mediana_mm"] == 117.6
    # ano seco e ano úmido
    seco = um("milho", {"data": "2026-03-01"}, ciclo_dias=60, clima=clima(fator_ano={**fatores, 2026: 0.2}))["chuva"]
    umido = um("milho", {"data": "2026-03-01"}, ciclo_dias=60, clima=clima(fator_ano={**fatores, 2026: 2.0}))["chuva"]
    assert (seco["posicao"], seco["anos_com_menos"]) == ("abaixo", 0) and (umido["posicao"], umido["anos_com_menos"]) == ("acima", 25)


def test_chuva_corta_no_ultimo_dia_do_dado_e_diz_a_lacuna():
    d = clima(anos=range(2001, 2027))
    d = d[d["data"] <= "2026-03-20"]                                                   # dado termina em 20/03
    ch = um("milho", {"data": "2026-03-01"}, ciclo_dias=60, clima=d)["chuva"]
    assert ch["fim"] == "2026-03-20" and ch["cortado_no_dado"] and ch["dias"] == 20 and ch["mm"] == 40.0
    sem = um("milho", {"data": "2026-03-01"}, clima=None)
    assert sem["chuva"]["disponivel"] is False and "sem série" in sem["chuva"]["motivo"] and any("chuva" in x for x in sem["lacunas"])
    poucos = um("milho", {"data": "2026-03-01"}, ciclo_dias=60, clima=clima(anos=range(2020, 2027)))["chuva"]
    assert poucos["historico"] is False and "só 6 anos" in poucos["motivo_historico"]


# ------------------------------------------------------------------------------------------------ veranico
def test_veranico_so_conta_dias_da_epoca_de_chuva_e_compara_com_o_local():
    # seca de 12 dias dentro da época de chuva (março: quinzenas 5 e 6) e outra, maior, depois da época (julho) que NÃO conta
    d = clima(seca=("2026-03-02", "2026-03-13"), meses=(2, 3, 4, 5, 7))
    d.loc[(d["data"] >= "2026-07-01") & (d["data"] <= "2026-07-30"), "chuva_mm"] = 0.0
    v = um("milho", {"data": "2026-02-20"}, ciclo_dias=150, clima=d)["veranico"]
    assert v["disponivel"] and v["maior_dias"] == 12 and v["termina_em"] == "2026-03-13" and v["so_epoca_de_chuva"]
    assert v["mediana_local"] == 7.0 and v["p90_local"] == 12.0 and v["passou_do_comum"] is True and v["passou_de_1_em_10"] is False
    longo = um("milho", {"data": "2026-02-20"}, ciclo_dias=150, clima=clima(seca=("2026-03-02", "2026-03-20")))["veranico"]
    assert longo["maior_dias"] == 19 and longo["passou_de_1_em_10"] is True
    sem_diag = um("milho", {"data": "2026-02-20"}, ciclo_dias=150, diagnostico=None)["veranico"]
    assert sem_diag["so_epoca_de_chuva"] is False and "motivo_comparacao" in sem_diag


def test_veranico_fora_da_epoca_nao_e_contado():
    v = um("milho", {"data": "2026-10-01"}, ciclo_dias=40)["veranico"]
    assert v["disponivel"] is False and v["fora_da_epoca"] is True


# ------------------------------------------------------------------------------------------------ planejamento, esclarecimento
def test_plantio_futuro_vira_planejamento_sem_chuva_nem_fase():
    p = um("milho", {"data": "2026-12-01"})
    assert p["status"] == "planejamento" and p["dias_para_plantar"] == 17
    assert "chuva" not in p and "veranico" not in p and p["fase"]["disponivel"] is False and p["colheita"]["disponivel"]
    assert p["zarc"]["situacao"] == "fora"
    q = um("milho", {"mes": 2, "ano": 2027})
    assert q["status"] == "planejamento"


def test_data_impossivel_vira_esclarecimento():
    longe = um("milho", {"data": "2028-03-01"})
    assert longe["status"] == "esclarecimento" and "longe" in longe["esclarecimento"]
    antigo = um("milho", {"data": "2023-03-01"})
    assert antigo["status"] == "esclarecimento" and "2 anos" in antigo["esclarecimento"]
    assert "chuva" not in antigo and "colheita" not in antigo


# ------------------------------------------------------------------------------------------------ verde da região
def ndvi_sintetico(valor_2026, base=0.5, anos=range(2001, 2027)):
    linhas = []
    for a in anos:
        for k in range(23):
            d = pd.Timestamp(f"{a}-01-01") + pd.Timedelta(days=16 * k)
            if d.year != a or (a == 2026 and d > pd.Timestamp("2026-10-16")):
                continue
            linhas.append({"ponto_id": "x_ce", "data": d, "ndvi": valor_2026 if a == 2026 else base, "confiabilidade": 0})
    return pd.DataFrame(linhas)


def test_verde_da_regiao_e_anomalia_contra_os_anos_anteriores():
    p = um("milho", {"data": "2026-03-01"}, ciclo_dias=90, ndvi=ndvi_sintetico(0.40))
    v = p["verde"]
    assert v["disponivel"] and v["anomalia_ultimo"] == -0.1 and v["anomalia_media"] == -0.1 and v["n_anos"] == 25
    assert CP.nivel_verde(v["anomalia_ultimo"]) == "bem mais fraco do que o normal"
    assert CP.nivel_verde(0.03) == "um pouco mais forte do que o normal" and CP.nivel_verde(0.0) == "parecido com o normal"
    sem = um("milho", {"data": "2026-03-01"}, ndvi=None)["verde"]
    assert sem["disponivel"] is False
    pouco = um("milho", {"data": "2026-03-01"}, ndvi=ndvi_sintetico(0.4, anos=range(2021, 2027)))["verde"]
    assert pouco["disponivel"] is False and "menos de 8 anos" in pouco["motivo"]


# ------------------------------------------------------------------------------------------------ solo nu e rotação
def test_solo_nu_depois_da_colheita():
    p = um("milho", {"data": "2026-10-01"}, ciclo_dias=100)         # colheita em 09/01/2027; quinzenas típicas 19-21 (início de out a 1ª metade de nov)
    sn = p["solo_nu"]
    assert sn["disponivel"] and sn["meses"] == [10, 11] and sn["colheita_dentro_da_epoca"] is False and sn["comeca_em"] == "2027-10-01"
    assert sn["dias_ate_comecar"] == (date(2027, 10, 1) - date(2027, 1, 9)).days
    dentro = um("milho", {"data": "2026-07-10"}, ciclo_dias=100)["solo_nu"]            # colhe em 17/10: dentro da época
    assert dentro["colheita_dentro_da_epoca"] is True and dentro["dias_ate_comecar"] == 0
    assert um("milho", {"data": "2026-10-01"}, diagnostico={})["solo_nu"]["disponivel"] is False


def test_proximas_filtra_regras_e_viabilidade_sem_ranking():
    graus = {"feijao_caupi": {"grau": "favoravel"}, "milheto": {"grau": "favoravel"}, "sorgo": {"grau": "neutro"}, "algodao": {"grau": "desfavoravel"},
             "mandioca": {"grau": "LACUNA"}, "girassol": {"grau": "favoravel"}}
    r = CP.organizar_proximas("milho", graus, {"feijao_caupi", "milheto", "sorgo", "algodao", "mandioca"}, proibidas=["milheto"])
    assert r["favoraveis"] == ["feijao_caupi"] and r["nao_quer"] == ["milheto"] and r["inviaveis_no_local"] == ["girassol"]
    assert r["neutras"] == ["sorgo"] and r["desfavoraveis"] == ["algodao"] and r["sem_dado"] == ["mandioca"] and r["viabilidade_conferida"]
    dois = CP.organizar_proximas("milho", graus, None)
    assert dois["empate_entre_favoraveis"] is True and dois["viabilidade_conferida"] is False
    assert um("milho", {"data": "2026-10-01"}, proximas_fn=lambda c, x: (_ for _ in ()).throw(RuntimeError("x")))["proximas"]["disponivel"] is False


def test_proximas_real_usa_a_matriz_de_rotacao():
    r = CP.proximas_padrao("milho", ctx(proximas_fn=None, tabela=None))      # viabilidade real do motor pode falhar sem clima do ponto: vira lacuna, não erro
    assert r["disponivel"] and r["origem"].startswith("src.culturas.matriz_rotacao")
    assert set(r["favoraveis"]) | set(r["neutras"]) | set(r["desfavoraveis"]) | set(r["sem_dado"]) | set(r["inviaveis_no_local"]) == set(CP._tabela_padrao()) - {"milho"}


def test_blocos_pesados_so_quando_pedidos():
    chamadas = []
    c = ctx(proximas_fn=lambda cid, x: chamadas.append(cid) or {"disponivel": True, "de": cid})
    CP.calcular("x_ce", [{"cultura": "milho", "quando": {"data": "2026-10-01"}}], HOJE, contexto=c, blocos=set())
    assert chamadas == []
    CP.calcular("x_ce", [{"cultura": "milho", "quando": {"data": "2026-10-01"}}], HOJE, contexto=c)
    assert chamadas == ["milho"]


def test_toda_saida_numerica_tem_origem_ou_motivo():
    r = um("milho", {"data": "2026-03-01"}, ciclo_dias=60, ndvi=ndvi_sintetico(0.45))
    for k in ("ciclo", "colheita", "zarc", "chuva", "veranico", "verde", "solo_nu"):
        b = r[k]
        assert b.get("origem") or b.get("motivo"), k
    assert r["periodo"]["ate_o_fim_do_ciclo"] is True


def test_calcular_nao_aceita_plantio_fora_do_schema():
    with pytest.raises(ValueError):
        CP.calcular("x_ce", [{"cultura": "melancia", "quando": {"mes": 2}}], HOJE, contexto=ctx())
