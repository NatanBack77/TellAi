"""Avaliador de ciclo montado pelo agricultor (src/culturas/avaliar_sequencia.py) e folha de fatos da conversa (src/llm/fatos.py). Dados reais de
Quixadá (o motor roda uma vez por processo, ~4 s); SEM rede, SEM LLM."""
import itertools
import re

import pytest

from src.culturas import avaliar_sequencia as AS
from src.culturas.regras_duras import RegrasDuras
from src.llm import fatos as FT
from src.llm.verificador import termos_tecnicos, verificar

PID = "quixada_ce"
M, CA, CRO, SO, MIL, MAN = "milho", "feijao_caupi", "crotalaria_juncea", "sorgo", "milheto", "mandioca"


@pytest.fixture(scope="module")
def tab():
    from src.culturas.tabela_culturas import carregar
    return carregar()


@pytest.fixture(scope="module")
def nomes(tab):
    return {c: v["cultura_pt"] for c, v in tab.items()}


@pytest.fixture(scope="module")
def ciclo3():
    return AS.avaliar(PID, [M, CA, CRO])


def test_tres_culturas_geram_seis_ordens_e_a_dita_vem_primeiro(ciclo3):
    assert ciclo3["n_ordens"] == 6 and len(ciclo3["ordens"]) == 6
    assert ciclo3["ordens"][0]["sequencia"] == [M, CA, CRO] and ciclo3["ordens"][0]["dita"]
    assert sum(o["dita"] for o in ciclo3["ordens"]) == 1
    assert {tuple(o["sequencia"]) for o in ciclo3["ordens"]} == set(itertools.permutations([M, CA, CRO]))


def test_o_que_a_ordem_muda_e_o_que_nao_muda(ciclo3):
    assert set(ciclo3["criterios_que_variam"]) == {"diversidade_familia", "leguminosa_antes"}
    assert ciclo3["criterios_iguais"] == ["adeq_clima"]
    notas = {tuple(o["sequencia"]): {k: v["nota_media"] for k, v in o["criterios"].items()} for o in ciclo3["ordens"]}
    assert notas[(M, CA, CRO)]["diversidade_familia"] == 0.5 and notas[(M, CA, CRO)]["leguminosa_antes"] == 0.0     # milho>caupi (família diferente); caupi>crotalária (igual)
    assert notas[(CA, M, CRO)]["diversidade_familia"] == 1.0 and notas[(CA, M, CRO)]["leguminosa_antes"] == 0.5     # leguminosa, gramínea, leguminosa
    assert len({round(n["adeq_clima"], 6) for n in notas.values()}) == 1                                              # clima igual: mesmas culturas


def test_pareto_empate_na_frente_e_ordem_dita_dominada(ciclo3):
    assert ciclo3["veredito"] == "topo_empatado"
    assert sorted(ciclo3["fronteira"]) == sorted([f"{CA} > {M} > {CRO}", f"{CRO} > {M} > {CA}"])
    assert ciclo3["dita_na_fronteira"] is False and ciclo3["dominada_por"]
    # a ordem dita fica atrás das duas da frente, e o par empatado é de fato empate_total
    par = [p for p in ciclo3["pareto"]["pares"] if {p["a"], p["b"]} == set(ciclo3["fronteira"])][0]
    assert par["relacao"] == "empate_total"


def test_viabilidade_por_cultura_e_lacunas_com_nome(ciclo3):
    pc = ciclo3["per_cultura"]
    assert all(pc[c]["estado"] == "viavel" for c in (M, CA, CRO))
    assert pc[M]["melhor_inicio"] and 0 < pc[M]["p_ano_viavel"] <= 1
    ag = ciclo3["agregados"]
    assert ag["falta_palha"] == [CA] and ag["palha_media_kg_ha"] is None          # caupi sem palha na tabela: lacuna, nunca nota
    assert ag["n_fixado_kg_ha"] == {CRO: pytest.approx(173.215)}
    assert any("Feijão-caupi: sem dado de palha" in x for x in ciclo3["lacunas"])
    assert any("pragas" in x for x in ciclo3["lacunas"]) and any("renda" in x for x in ciclo3["lacunas"])


def test_todas_as_ordens_empatam_quando_a_familia_e_a_mesma():
    r = AS.avaliar(PID, [M, MIL, "sorgo"])      # três gramíneas
    assert r["veredito"] == "todas_iguais" and r["criterios_que_variam"] == []
    assert len(r["fronteira"]) == 6 and r["dita_na_fronteira"]
    assert r["inviaveis"] == ["sorgo"]          # o motor diz que sorgo não fecha em Quixadá: aparece, não some
    assert any("sorgo" in x.lower() or "Sorgo" in x for x in r["lacunas"])


def test_cultura_unica_nao_tem_ordem_nem_nota_de_troca():
    r = AS.avaliar(PID, [M])
    assert r["veredito"] == "uma_ordem" and r["n_ordens"] == 1
    c = r["ordens"][0]["criterios"]
    assert c["diversidade_familia"]["lacuna"] and c["leguminosa_antes"]["lacuna"] and not c["adeq_clima"]["lacuna"]


def test_quatro_culturas_24_ordens_e_limite_de_permutacoes():
    r = AS.avaliar(PID, [M, CA, CRO, MIL])
    assert r["n_ordens"] == 24
    r2 = AS.avaliar(PID, [M, CA, CRO, MIL], max_permutacoes=5)
    assert r2["n_ordens"] == 5 and r2["ordens"][0]["dita"] and any("primeiras 5 ordens" in x for x in r2["lacunas"])


def test_cultura_repetida_nao_gera_ordens_repetidas():
    r = AS.avaliar(PID, [M, CA, M])
    assert r["n_ordens"] == 3                     # permutações distintas de {milho, caupi, milho}


@pytest.mark.parametrize("culturas", [[], [M, CA, CRO, MIL, SO], ["melancia"], ["milho", "nao_existe"]])
def test_entrada_invalida_levanta_erro_claro(culturas):
    with pytest.raises(AS.SequenciaErro):
        AS.avaliar(PID, culturas)


def test_prioridade_invalida():
    with pytest.raises(AS.SequenciaErro):
        AS.avaliar(PID, [M, CA], prioridade="lucro")


def test_regras_duras_do_usuario_valem_em_todas_as_posicoes():
    r = AS.avaliar(PID, [M, CA, CRO], regras=RegrasDuras(proibidas=[CRO]))
    assert all(o["viola_regras"] for o in r["ordens"])                    # todas usam crotalária
    assert all(o["dita"] or o["sequencia"] for o in r["ordens"]) and len(r["descartadas_por_regra"]) == 5     # a dita fica, marcada
    assert r["ordens"][0]["viola_regras"] and "proibida" in r["ordens"][0]["viola_regras"][0]
    r2 = AS.avaliar(PID, [M, CA], regras=RegrasDuras(max_seguidas_cultura=1))
    assert not any(o["viola_regras"] for o in r2["ordens"])
    with pytest.raises(ValueError):
        AS.avaliar(PID, [M, CA], regras=RegrasDuras(proibidas=["cultura_inventada"]))


def test_prioridade_solo_mostra_quais_criterios_dela_variam_com_a_ordem():
    r = AS.avaliar(PID, [M, CA, CRO], prioridade="solo")
    assert r["prioridade_efeito"]["criterios"][:2] == ["palha", "leguminosa_antes"]
    assert "leguminosa_antes" in r["prioridade_efeito"]["variam_com_a_ordem"]
    ra = AS.avaliar(PID, [M, CA, CRO], prioridade="agua")
    assert "agua" not in ra["prioridade_efeito"]["variam_com_a_ordem"]       # a água do ciclo é a mesma em qualquer ordem


def test_deterministico():
    a, b = AS.avaliar(PID, [CRO, M, CA]), AS.avaliar(PID, [CRO, M, CA])
    assert a["fronteira"] == b["fronteira"] and a["pareto"] == b["pareto"]


def test_sugerir_por_foco_ordena_so_pelo_dado_da_tabela(tab):
    s = AS.sugerir_por_foco(PID, "agua")
    assert s["atributo"] == "demanda_hidrica_mm_ciclo" and s["maior_melhor"] is False
    vals = [r["valor"] for r in s["ranking"]]
    assert vals == sorted(vals) and s["top_k"] == [r["id"] for r in s["ranking"][:3]]
    assert set(s["sem_dado"]).isdisjoint(r["id"] for r in s["ranking"])        # sem dado = fora do ranking, nunca nota
    assert "sorgo" in s["inviaveis"] and "sorgo" not in s["viaveis"]
    sn = AS.sugerir_por_foco(PID, "nitrogenio")
    assert [r["id"] for r in sn["ranking"]] == ["crotalaria_juncea", "mucuna", "amendoim"]       # só 3 culturas têm N fixado medido
    assert AS.sugerir_por_foco(PID, "agua", excluir=["feijao_comum"])["ranking"][0]["id"] != "feijao_comum"


def test_sugerir_por_foco_sem_dado_vira_lacuna_declarada():
    for foco in ("renda", "pragas", "forragem"):
        s = AS.sugerir_por_foco(PID, foco, atual=M)
        assert s["ranking"] == [] and s["lacuna_foco"]
    assert set(AS.sugerir_por_foco(PID, "pragas", atual=M)["diferentes_da_atual"]) >= {CA, MAN}


# ------------------------------------------------------------------------------------------------ folha de fatos da conversa
def _folha(nomes, ciclo=None, sug=None, **kw):
    return FT.montar_folha_conversa(nomes, ciclo=ciclo, sugestao=sug, **kw)


def test_fatos_do_ciclo_tem_origem_texto_simples_e_lacuna(nomes, ciclo3):
    f = _folha(nomes, ciclo3, foco="agua", ordem_informada=True)
    assert [x["id"] for x in f["fatos"]] == [f"F{i}" for i in range(1, len(f["fatos"]) + 1)]
    for x in f["fatos"]:
        assert x["origem"] and x["texto"] and x["texto_simples"] and isinstance(x["lacuna"], bool) and x["papel"]
        assert not termos_tecnicos(x["texto_simples"]), x["texto_simples"]
        assert "quixada" not in (x["texto"] + x["texto_simples"]).lower()
    papeis = {x["papel"] for x in f["fatos"]}
    assert {"viab_resumo", "ordem_dita", "veredito", "palha", "n", "agua", "lacuna"} <= papeis
    assert any(x["papel"] == "palha" and x["lacuna"] for x in f["fatos"])         # caupi sem palha: o fato carrega a lacuna


def test_veredito_diz_empate_e_nunca_escolhe_uma_so(nomes, ciclo3):
    v = [x for x in _folha(nomes, ciclo3)["fatos"] if x["papel"] == "veredito"][0]
    assert "empatadas" in v["texto_simples"] and "Com os dados que temos" in v["texto_simples"]
    assert "A que você disse fica atrás" in v["texto_simples"]
    sem_ordem = [x for x in _folha(nomes, ciclo3, ordem_informada=False)["fatos"] if x["papel"] == "veredito"][0]
    assert "você disse" not in sem_ordem["texto_simples"] and not any(x["papel"] == "ordem_dita" for x in _folha(nomes, ciclo3, ordem_informada=False)["fatos"])


def test_todas_iguais_vira_empate_geral(nomes):
    r = AS.avaliar(PID, [M, MIL, "sorgo"])
    v = [x for x in _folha(nomes, r)["fatos"] if x["papel"] == "veredito"][0]
    assert "a ordem não muda nada" in v["texto_simples"] and "empatadas" in v["texto_simples"]


def test_cultura_inviavel_tem_frase_propria_e_franqueza_de_cultura_fora_da_lista(nomes):
    r = AS.avaliar(PID, [M, "sorgo"])
    f = _folha(nomes, r, fora=["melancia"])
    assert any("sorgo fica difícil" in x["texto_simples"] for x in f["fatos"])
    fr = [x for x in f["fatos"] if x["papel"] == "franqueza"][0]
    assert "melancia" in fr["texto_simples"] and "ainda não temos dados" in fr["texto_simples"] and fr["lacuna"]


def test_viabilidade_nunca_diz_cem_por_cento(nomes):
    """'100%' soaria como garantia (e o verificador o proíbe como promessa): o fato diz 'em todos os anos olhados'."""
    r = AS.avaliar(PID, [CRO])
    t = [x for x in _folha(nomes, r)["fatos"] if x["papel"] == "viab"][0]["texto_simples"]
    assert "100" not in t and "em todos os anos olhados" in t


def test_fatos_da_sugestao_por_foco(nomes):
    f = _folha(nomes, sug=AS.sugerir_por_foco(PID, "agua"), foco="agua")
    r = [x for x in f["fatos"] if x["papel"] == "agua"][0]["texto_simples"]
    assert "feijão comum cerca de 300 mm" in r and "estudos diferentes" in r
    assert any(x["papel"] == "lacuna" and "ainda não temos dado de água" in x["texto_simples"].lower() for x in f["fatos"])
    fn = _folha(nomes, sug=AS.sugerir_por_foco(PID, "renda"), foco="renda")
    assert any(x["papel"] == "lacuna_foco" and "não consegue dizer o que dá mais renda" in x["texto_simples"] for x in fn["fatos"])


def test_selecao_respeita_foco_e_teto_de_tokens(nomes, ciclo3):
    f = _folha(nomes, ciclo3, foco="agua")
    sel = FT.selecionar_conversa(f, "agua")
    papeis = [x["papel"] for x in sel]
    assert "agua" in papeis and "palha" not in papeis and "n" not in papeis      # com foco em água, palha e N não gastam o prompt
    assert sum(FT.tokens_aprox(x["texto_simples"]) for x in sel) <= FT.TETO_TOKENS_CONVERSA
    assert len(sel) <= FT.MAX_FATOS_CONVERSA and not any(x["papel"] == "viab_det" for x in sel)
    assert [x["id"] for x in sel] == sorted((x["id"] for x in sel), key=lambda i: int(i[1:]))


def test_verificador_aceita_texto_baseado_no_fato_e_barra_numero_inventado(nomes, ciclo3):
    sel = FT.selecionar_conversa(_folha(nomes, ciclo3, foco="agua"), "agua")
    ag = [x for x in sel if x["papel"] == "agua"][0]["id"]
    ok = f"Entendi, você quer gastar menos água. O milho pede cerca de 500 mm de água no ciclo [{ag}]."
    assert verificar(ok, None, [], exigir_citacao=True, fatos=sel, tom=True, exigir_aviso=False)["ok"]
    ruim = f"O milho pede cerca de 380 mm de água no ciclo [{ag}]."
    assert not verificar(ruim, None, [], exigir_citacao=True, fatos=sel, tom=True, exigir_aviso=False)["ok"]
