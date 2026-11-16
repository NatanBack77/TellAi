"""Plano de plantio em 10 etapas: dado curado (src/plano/dados.py), montagem (montar.py) e rota POST /plano-plantio (src/api/rota_plano.py).
Sem rede e sem IA. A rota roda contra o motor e os dados reais do repositório (clima/ZARC/tabela), como os demais testes de API."""
import csv
import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rota_plano import router as rota_plano
from src.plano import construir, dados, montar
from src.plano.etapas import ETAPAS, ETAPAS_CURADAS, PROIBIDOS

PID = "quixada_ce"
TITULOS = ["Introdução ao Plantio", "Recomendação de Plantação", "Clima e Época de Plantio", "Preparação do Solo", "Semeadura e Plantio",
           "Irrigação e Cuidados com a Água", "Adubação e Nutrição", "Desenvolvimento e Manutenção", "Colheita", "Pós-colheita e Armazenamento"]


def linha(**kw):
    base = {"cultura_id": "milho", "etapa": "5", "atributo": "espacamento", "valor": "80 cm", "unidade": "cm", "status": "verificado", "fonte": "Embrapa X",
            "url": "https://exemplo.org/x.pdf", "pagina": "10", "trecho": "espaçamento de 80 cm", "contexto": "fonte nacional", "requer_tecnico": "0",
            "motivo_interno": "", "data_consulta": "2026-11-15"}
    base.update(kw)
    return base


def ds_de(*linhas):
    out = {}
    for r in linhas:
        ln = dados._linha(r)
        out.setdefault((ln.cultura_id, ln.etapa), []).append(ln)
    return out


# ---------------------------------------------------------------- contrato das etapas
def test_as_10_etapas_tem_os_nomes_e_a_ordem_do_usuario():
    assert [t for _, _, t, _ in ETAPAS] == TITULOS
    assert [n for n, *_ in ETAPAS] == list(range(1, 11))
    assert {n for n, _, _, o in ETAPAS if o == "motor"} == {2, 3}
    assert ETAPAS_CURADAS == {1, 4, 5, 6, 7, 8, 9, 10}


# ---------------------------------------------------------------- validação do dado curado
def test_linha_boa_passa():
    assert dados.validar([linha()]) == []


@pytest.mark.parametrize("mudanca, trecho_do_erro", [
    ({"fonte": ""}, "sem fonte"), ({"trecho": ""}, "sem fonte ou sem trecho"), ({"pagina": ""}, "página numérica"), ({"valor": ""}, "sem valor"),
    ({"cultura_id": "inventada"}, "fora da tabela"), ({"status": "talvez"}, "status inválido"), ({"etapa": "2"}, "não é de dado curado"),
    ({"valor": "aplicar inseticida na lavoura"}, "termo proibido no valor"), ({"valor": "fazer expurgo do lote"}, "termo proibido no valor"),
    ({"contexto": "usar herbicida"}, "termo proibido no contexto"), ({"requer_tecnico": "talvez"}, "requer_tecnico"),
])
def test_validacao_barra_dado_ruim(mudanca, trecho_do_erro):
    erros = dados.validar([linha(**mudanca)])
    assert any(trecho_do_erro in e for e in erros), erros


def test_lacuna_e_nao_se_aplica_nunca_tem_valor():
    assert any("não pode ter valor" in e for e in dados.validar([linha(status="lacuna")]))
    assert any("não pode ter valor" in e for e in dados.validar([linha(status="nao_se_aplica")]))
    assert dados.validar([linha(status="lacuna", valor="", fonte="", url="", pagina="", trecho="")]) == []


def test_linha_duplicada_e_barrada():
    assert any("duplicada" in e for e in dados.validar([linha(), linha()]))


# ---------------------------------------------------------------- o dado real do repositório
def test_dado_real_carrega_e_cobre_as_16_culturas():
    ds = dados.carregar()
    assert {c for c, _ in ds} == dados.culturas_da_tabela()
    assert len(dados.culturas_da_tabela()) == 16
    assert {e for _, e in ds} == ETAPAS_CURADAS


def test_dado_real_toda_linha_verificada_tem_fonte_pagina_e_trecho():
    for lns in dados.carregar().values():
        for ln in lns:
            if ln.status == "verificado":
                assert ln.fonte and ln.pagina and ln.trecho and ln.valor, ln
            else:
                assert not ln.valor and not ln.trecho, ln


def test_dado_real_nenhum_produto_ou_defensivo_no_valor_nem_no_contexto():
    pad = re.compile("|".join(PROIBIDOS), re.I)
    for lns in dados.carregar().values():
        for ln in lns:
            assert not pad.search(ln.valor) and not pad.search(ln.contexto), ln


def test_csv_do_repositorio_esta_em_dia_com_a_curadoria():
    """O CSV versionado é exatamente o que `python -m src.plano.construir` gera hoje (ninguém editou à mão nem esqueceu de regerar)."""
    esperado = construir.construir()
    with open(dados.ARQ_DADOS, encoding="utf-8", newline="") as f:
        atual = list(csv.DictReader(f))
    assert [tuple(r.values()) for r in atual] == [tuple(str(v) for v in r.values()) for r in esperado]


# ---------------------------------------------------------------- montagem
def test_montar_devolve_10_etapas_na_ordem_e_com_lacuna_onde_falta():
    ds = ds_de(linha(), linha(etapa="7", atributo="adubacao_referencia", status="lacuna", valor="", fonte="", url="", pagina="", trecho="", contexto="ainda não coletado"))
    p = montar.montar(PID, "milho", ds=ds)
    assert [e["titulo"] for e in p["etapas"]] == TITULOS and [e["numero"] for e in p["etapas"]] == list(range(1, 11))
    e5, e7, e4 = p["etapas"][4], p["etapas"][6], p["etapas"][3]
    assert len(e5["itens"]) == 1 and e5["itens"][0]["valor"] == "80 cm" and e5["itens"][0]["fonte"] == {"nome": "Embrapa X", "pagina": 10, "url": "https://exemplo.org/x.pdf"}
    assert e7["itens"] == [] and any("ainda não coletado" in x for x in e7["lacunas"])
    assert e4["itens"] == [] and e4["lacunas"], "etapa sem nenhum dado precisa declarar a lacuna"
    assert p["cobertura_itens"]["5"] == 1 and p["aviso"] and p["limites"]


def test_etapa_de_adubacao_e_marcada_como_referencia_da_fonte():
    p = montar.montar(PID, "milho", ds=ds_de(linha(etapa="7", atributo="fosforo_referencia")))
    assert p["etapas"][6]["itens"][0]["referencia_da_fonte"] is True


def test_nao_se_aplica_aparece_e_nao_some_quando_misturado_com_lacuna():
    ds = ds_de(linha(cultura_id="mucuna", etapa="10", atributo="armazenamento_umidade_segura", status="nao_se_aplica", valor="", fonte="", url="", pagina="", trecho="",
                     contexto="cultura de cobertura"),
               linha(cultura_id="mucuna", etapa="10", atributo="comercializacao_preco", status="lacuna", valor="", fonte="", url="", pagina="", trecho="", contexto="sem preço"))
    e = montar.montar(PID, "mucuna", ds=ds)["etapas"][9]
    assert any("não se aplica" in x for x in e["lacunas"]) and any("sem preço" in x for x in e["lacunas"])
    so_na = montar.montar(PID, "mucuna", ds=ds_de(linha(cultura_id="mucuna", etapa="10", atributo="a", status="nao_se_aplica", valor="", fonte="", url="", pagina="", trecho="",
                                                       contexto="cultura de cobertura")))["etapas"][9]
    assert so_na["nao_se_aplica"] is True


def test_caminho_de_arquivo_nunca_sai_e_url_http_sai():
    ds = ds_de(linha(url="file://data/plano_staging/material/x.pdf"), linha(atributo="b", valor="70 cm", url="https://exemplo.org/y.pdf"))
    its = montar.montar(PID, "milho", ds=ds)["etapas"][4]["itens"]
    assert {i["fonte"]["url"] for i in its} == {None, "https://exemplo.org/y.pdf"}
    assert "file://" not in json.dumps(montar.montar(PID, "milho", ds=ds))


def test_trecho_que_cita_produto_nao_sai_e_pede_tecnico():
    it = montar.montar(PID, "milho", ds=ds_de(linha(etapa="10", atributo="monitoramento_armazem", valor="Monitorar a infestação",
                                                   trecho="deve ser submetido a tratamento curativo (expurgo)")))["etapas"][9]["itens"][0]
    assert it["trecho"] is None and it["requer_tecnico"] is True and it["fonte"]["nome"]


def test_nota_interna_de_revisao_tecnica_nao_sai():
    ds = ds_de(linha(requer_tecnico="1", motivo_interno="a fonte cita fumigação com produto", contexto="fonte nacional"))
    p = montar.montar(PID, "milho", ds=ds)
    txt = json.dumps(p, ensure_ascii=False)
    assert "fumigação" not in txt and "motivo_interno" not in txt and p["etapas"][4]["itens"][0]["requer_tecnico"] is True


def test_falha_do_motor_vira_lacuna_e_nao_derruba_o_plano():
    def quebra(pid, cid):
        raise RuntimeError("motor fora do ar")
    p = montar.montar(PID, "milho", ds=ds_de(linha()), fornecedores={2: quebra})
    e2, e3 = p["etapas"][1], p["etapas"][2]
    assert e2["itens"] == [] and any("falhou" in x for x in e2["lacunas"])
    assert e3["itens"] == [] and e3["lacunas"], "sem fornecedor a etapa também declara lacuna"
    assert "RuntimeError" not in json.dumps(p) and "motor fora do ar" not in json.dumps(p)


def test_cultura_sem_plano_e_erro():
    with pytest.raises(ValueError):
        montar.montar(PID, "inexistente", ds=ds_de(linha()))


# ---------------------------------------------------------------- rota (motor e dados reais)
@pytest.fixture(scope="module")
def cli():
    app = FastAPI()
    app.include_router(rota_plano)
    return TestClient(app)


def _ver(plano):
    for e in plano["etapas"]:
        for i in e["itens"]:
            yield e, i


def test_rota_devolve_o_plano_de_milho_com_as_10_etapas_e_fontes(cli):
    r = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": "milho"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert [e["titulo"] for e in p["etapas"]] == TITULOS and p["cultura_nome"] == "Milho"
    assert [e["origem"] for e in p["etapas"]] == ["dado_curado", "motor", "motor"] + ["dado_curado"] * 7
    e2, e3 = p["etapas"][1], p["etapas"][2]
    assert e2["itens"] and e3["itens"] and all(i["status"] == "calculado" for i in e2["itens"] + e3["itens"])
    assert [i["atributo"] for i in e2["itens"] if i["atributo"].startswith("cultura_recomendada_")][:2] == ["cultura_recomendada_1", "cultura_recomendada_2"]
    assert any(i["atributo"] == "janela_zarc" for i in e3["itens"]) and any(i["atributo"] == "estacao_chuvosa" for i in e3["itens"])
    for e, i in _ver(p):
        if i["status"] == "verificado":
            assert i["fonte"]["nome"] and i["fonte"]["pagina"] and (i["trecho"] or i["requer_tecnico"]), i
        assert i["valor"], i


def test_rota_nao_vaza_caminho_de_arquivo_nota_interna_nem_produto(cli):
    pad = re.compile("|".join(PROIBIDOS), re.I)
    for cult in sorted(dados.culturas_da_tabela()):   # as 16: o vazamento que a tela real mostrou (caminho de CSV na fonte do ciclo) só aparecia no motor
        p = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": cult}).json()
        txt = json.dumps(p, ensure_ascii=False)
        assert not re.search(r"file://|[A-Za-z]:\\|docs_rag|plano_staging|motivo_interno|REVISÃO TÉCNICA|\bdata/|\.csv|\.parquet|\.json|safra_\d", txt), cult
        for e, i in _ver(p):
            assert not pad.search(i["valor"] or "") and not pad.search(i["contexto"]) and not pad.search(i["trecho"] or ""), (cult, i)


def test_rota_nenhuma_lacuna_tem_valor_e_toda_etapa_declara_o_que_falta_ou_tem_itens(cli):
    for cult in dados.culturas_da_tabela():
        p = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": cult}).json()
        assert len(p["etapas"]) == 10
        for e in p["etapas"]:
            assert e["itens"] or e["lacunas"], (cult, e["numero"])
            assert all(i["valor"] for i in e["itens"])


def test_rota_cultura_de_cobertura_declara_que_a_pos_colheita_nao_se_aplica(cli):
    p = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": "mucuna"}).json()
    assert any("não se aplica" in x for x in p["etapas"][9]["lacunas"])


def test_rota_erros_ponto_cultura_e_corpo(cli):
    assert cli.post("/plano-plantio", json={"ponto_id": "nao_existe", "cultura": "milho"}).status_code == 404
    assert cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": "inventada"}).status_code == 422
    assert cli.post("/plano-plantio", json={"ponto_id": PID}).status_code == 200, "sem cultura vale o exemplo do local"
    assert cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": "milho", "extra": 1}).status_code == 422


def test_rota_lista_de_culturas_e_contrato_das_etapas(cli):
    cs = cli.get("/plano-plantio/culturas").json()
    assert len(cs) == 16 and all(set(c["itens_por_etapa"]) == {str(e) for e in ETAPAS_CURADAS} for c in cs)
    et = cli.get("/plano-plantio/etapas").json()
    assert [e["titulo"] for e in et] == TITULOS


def test_rota_esta_no_app_principal():
    from src.api.main import app
    caminhos = set(app.openapi()["paths"])
    assert {"/plano-plantio", "/plano-plantio/culturas", "/plano-plantio/etapas"} <= caminhos


# ---------------------------------------------------------------- caminhos internos nunca saem (o que a tela real mostrou)
@pytest.mark.parametrize("entrada, esperado", [
    ("FAO-56 (Allen et al., 1998), cap. 6, Tabela 11, via data/culturas/fao_staging.csv", "FAO-56 (Allen et al., 1998), cap. 6, Tabela 11"),
    ("EcoCrop (FAO), faixa de ciclo em data/culturas/tabela_culturas.csv", "EcoCrop (FAO), faixa de ciclo"),
    ("Sem caminho nenhum aqui", "Sem caminho nenhum aqui"),
])
def test_limpar_caminhos(entrada, esperado):
    from src.plano.etapas import limpar_caminhos
    assert limpar_caminhos(entrada) == esperado


def test_itens_do_motor_passam_pela_limpeza_mesmo_que_o_fornecedor_deixe_escapar():
    def sujo(pid, cid):
        return {"itens": [{"atributo": "x", "rotulo": "X", "valor": "140 dias", "unidade": "", "status": "calculado", "trecho": None, "contexto": "ver data/a/b.csv",
                           "fonte": {"nome": "FAO via data/culturas/y.csv", "pagina": None, "url": None}, "requer_tecnico": False,
                           "referencia_da_fonte": False, "experimento": False}], "lacunas": ["falta em data/z.parquet"]}
    e = montar.montar(PID, "milho", ds=ds_de(linha()), fornecedores={2: sujo})["etapas"][1]
    assert "data/" not in json.dumps(e) and ".csv" not in json.dumps(e) and ".parquet" not in json.dumps(e)
    assert e["itens"][0]["fonte"]["nome"] == "FAO"


# ---------------------------------------------------------------- resposta objetiva: destaques e Kc numa linha
def test_toda_etapa_com_itens_tem_de_1_a_3_destaques(cli):
    for cult in sorted(dados.culturas_da_tabela()):
        p = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": cult}).json()
        for e in p["etapas"]:
            n = sum(1 for i in e["itens"] if i["destaque"])
            if e["itens"]:
                assert 1 <= n <= 3, (cult, e["numero"], n)
            else:
                assert n == 0


def test_destaque_escolhe_pela_prioridade_da_etapa():
    ds = ds_de(linha(atributo="semente_kg_ha", valor="6 a 10"), linha(atributo="profundidade_semeadura", valor="2", unidade="cm"),
               linha(atributo="espacamento", valor="80 cm"), linha(atributo="densidade_plantas_ha", valor="50 mil"), linha(atributo="inoculacao_referencia", valor="x"))
    its = montar.montar(PID, "milho", ds=ds)["etapas"][4]["itens"]
    marcados = {i["atributo"] for i in its if i["destaque"]}
    assert marcados == {"espacamento", "densidade_plantas_ha", "semente_kg_ha"}, "prioridade: espaçamento, densidade, semente, profundidade"


def test_kc_vira_uma_linha_so_com_virgula_decimal_e_sem_nota_de_rodape():
    def kc(a, v):
        return linha(etapa="6", atributo=a, valor=v, fonte="FAO-56", pagina="1", trecho="x")
    ds = ds_de(kc("kc_inicial", "0.4"), kc("kc_medio", "1.15 (nota 2)"), kc("kc_final", "0.60-0.35 (nota 6)"))
    its = montar.montar(PID, "milho", ds=ds)["etapas"][5]["itens"]
    assert len(its) == 1 and its[0]["atributo"] == "kc"
    assert its[0]["valor"] == "inicial 0,4 · médio 1,15 · final 0,60 a 0,35" and its[0]["destaque"] is True
    assert its[0]["fonte"]["nome"] == "FAO-56"


def test_kc_na_rota_real_do_milho_e_uma_linha(cli):
    e6 = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": "milho"}).json()["etapas"][5]
    kcs = [i for i in e6["itens"] if i["atributo"].startswith("kc")]
    assert len(kcs) == 1 and kcs[0]["valor"].startswith("inicial ") and "nota" not in kcs[0]["valor"]


# ---------------------------------------------------------------- sem escolher cultura: exemplo do local
def test_sem_cultura_o_plano_segue_pela_planta_mais_indicada_e_a_etapa_2_lista_as_opcoes(cli):
    from src.plano.motor_etapas import ADUBOS_VERDES
    p = cli.post("/plano-plantio", json={"ponto_id": PID, "solo": "medio"}).json()
    assert p["cultura_exemplo"] is True and p["cultura"] not in ADUBOS_VERDES
    cult = [i for i in p["etapas"][1]["itens"] if i["atributo"].startswith("cultura_recomendada_")]
    assert len(cult) >= 3 and cult[0]["rotulo"] == p["cultura_nome"], "o plano segue pela 1ª planta indicada"
    assert all("Época de plantio" in i["valor"] or "não ajuda" in i["valor"] or "Pode ser plantada" in i["valor"] for i in cult)
    assert "solo médio" in cult[0]["valor"] or "não ajuda" in cult[0]["valor"], "a época é a do solo que a pessoa informou"
    assert "exemplo" not in json.dumps(p["etapas"], ensure_ascii=False).lower() and "empate" not in json.dumps(p["etapas"][1], ensure_ascii=False).lower()


def test_o_solo_informado_entra_no_calculo_e_quem_esta_no_zoneamento_vem_primeiro():
    from src.plano import motor_etapas as ME
    for solo in ("arenoso", "medio", "argiloso"):
        lista = ME.culturas_viaveis(PID, solo)
        assert lista, solo
        vistos_fora = False
        for c in lista:
            vistos_fora = vistos_fora or not c["no_zoneamento"]
            assert not (vistos_fora and c["no_zoneamento"]), "quem está no zoneamento do solo vem antes de quem não está"


def test_com_cultura_nao_e_exemplo_do_servidor(cli):
    assert cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": "milho"}).json()["cultura_exemplo"] is False


def test_exemplo_e_estavel_e_nunca_e_adubo_verde():
    from src.plano import motor_etapas as ME
    a, b = ME.cultura_exemplo(PID), ME.cultura_exemplo(PID)
    assert a == b and a is not None and a not in ME.ADUBOS_VERDES
    assert all(c["fracao"] >= 0 for c in ME.culturas_viaveis(PID))


def test_etapa_2_destaca_as_tres_plantas_mais_indicadas(cli):
    e2 = cli.post("/plano-plantio", json={"ponto_id": PID}).json()["etapas"][1]
    dest = [i["atributo"] for i in e2["itens"] if i["destaque"]]
    assert dest == ["cultura_recomendada_1", "cultura_recomendada_2", "cultura_recomendada_3"]


# ---------------------------------------------------------------- linguagem simples nos valores curados
@pytest.mark.parametrize("entrada, esperado", [
    ("6 a 10", "6 a 10"),
    ("0,75 m x 0,20 m (66.667 plantas/ha)", "0,75 m x 0,20 m (66.667 plantas por hectare)"),
    ("40 a 80 kg/ha de P2O5, sendo 40", "40 a 80 kg por hectare de fósforo (P2O5), sendo 40"),
    ("20 t/ha de esterco", "20 toneladas por hectare de esterco"),
    ("0.60-0.35 (nota 6)", "0.60-0.35"),
])
def test_simplificar_troca_so_a_forma_e_nao_mexe_nos_numeros(entrada, esperado):
    import re as _re
    from src.plano.texto_simples import simplificar
    assert simplificar(entrada) == esperado
    def numeros(t):   # os números do texto, sem as fórmulas químicas e sem a nota de rodapé
        return _re.findall(r"\d[\d.,]*", _re.sub(r"P2O5|K2O|\(nota \d+\)", "", t))
    assert numeros(simplificar(entrada)) == numeros(entrada)


def test_resposta_real_nao_tem_sigla_por_ha(cli):
    for cult in ("milho", "feijao_caupi", "mandioca", "algodao"):
        p = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": cult}).json()
        # só o que aparece na tela (o trecho é a citação literal da fonte e não é mostrado)
        txt = json.dumps([[(i["rotulo"], i["valor"], i["unidade"], i["contexto"]) for i in e["itens"]] for e in p["etapas"]], ensure_ascii=False)
        assert "/ha" not in txt and "(nota " not in txt, cult


def test_cultura_pedida_pelo_nome_tambem_mostra_a_epoca_de_plantio(cli):
    e2 = cli.post("/plano-plantio", json={"ponto_id": PID, "cultura": "algodao", "solo": "medio"}).json()["etapas"][1]
    primeira = next(i for i in e2["itens"] if i["atributo"] == "cultura_recomendada_1")
    assert primeira["rotulo"] == "Algodão" and "Época de plantio" in primeira["valor"]
