"""Testes da matriz 'cultura anterior -> seguinte' com fonte (data/culturas/matriz_rotacao.csv)."""
import copy
import shutil

import pytest

from src.culturas import matriz_rotacao as M

TEM_PDFTOTEXT = shutil.which("pdftotext") is not None


@pytest.fixture(scope="module")
def linhas():
    return M.carregar_linhas()


@pytest.fixture(scope="module")
def matriz():
    return M.carregar()


def test_matriz_real_valida(linhas):
    assert M.validar(linhas) == []


def test_todo_par_ordenado_das_16_culturas_esta_presente(matriz):
    ids = M.culturas_da_tabela()
    assert len(ids) == 16
    for a in ids:
        for s in ids:
            if a != s:
                assert (a, s) in matriz, (a, s)
    assert sum(1 for (a, s) in matriz if a != s) == 240


@pytest.mark.skipif(not TEM_PDFTOTEXT, reason="pdftotext (poppler) ausente")
def test_todo_trecho_esta_na_pagina_citada_do_pdf(linhas):
    # reextrai cada página com pdftotext e confere o trecho (e o complemento); nada de memória
    assert M.verificar_trechos(linhas) == []


@pytest.mark.skipif(not TEM_PDFTOTEXT, reason="pdftotext (poppler) ausente")
def test_validador_pega_trecho_inventado_e_pagina_errada(linhas):
    ev = [r for r in linhas if r["grau"] != "LACUNA"]
    r1 = copy.deepcopy(ev[0])
    r1["trecho"] = "frase que não existe no PDF"
    assert M.verificar_trechos([r1])
    r2 = copy.deepcopy(ev[0])
    r2["pagina"] = str(int(r2["pagina"]) + 1)
    assert M.verificar_trechos([r2])


def test_validador_estrutural_pega_defeitos(linhas):
    ev = next(r for r in linhas if r["grau"] != "LACUNA")
    for campo, valor in [("grau", "otimo"), ("arquivo", "inventado.pdf"), ("trecho", ""), ("pagina", "x"),
                         ("tipo_evidencia", "palpite"), ("regiao_estudo", "")]:
        r = copy.deepcopy(ev)
        r[campo] = valor
        assert M.validar([r]), campo
    # trecho que não cita a cultura do par
    r = copy.deepcopy(ev)
    r["anterior"], r["seguinte"] = "mandioca", "mamona"
    assert any("não menciona" in e for e in M.validar([r]))
    # LACUNA com evidência é proibida
    r = copy.deepcopy(ev)
    r["grau"] = "LACUNA"
    assert M.validar([r])


def test_par_ausente_e_detectado(linhas):
    sem = [r for r in linhas if not (r["anterior"] == "mandioca" and r["seguinte"] == "mamona")]
    assert len(sem) == len(linhas) - 1
    assert any("ausente" in e for e in M.validar(sem))


def test_lacuna_e_a_maioria_e_nao_premia(matriz):
    cob = M.cobertura(matriz)
    assert cob["pares"] == 240
    assert cob["LACUNA_sem_dado"] > cob["com_evidencia"]  # esperado: a maioria sem dado
    c = M.consulta("mandioca", "mamona", matriz)
    assert c["grau"] == "LACUNA" and c["evidencias"] == [] and c["usar_na_nota"] is False


def test_consulta_par_favoravel_traz_motivo_e_evidencia(matriz):
    c = M.consulta("crotalaria_juncea", "milho", matriz)
    assert c["grau"] == "favoravel" and c["usar_na_nota"] is True
    assert c["motivo"]
    e = c["evidencias"][0]
    assert e["arquivo"].endswith(".pdf") and e["pagina"] >= 1 and e["trecho"] and e["url"].startswith("https://")
    assert e["tipo_evidencia"] in M.TIPOS and e["regiao_estudo"]
    assert c["tipo_evidencia_mais_forte"] in M.TIPOS


def test_simetrico_vale_nos_dois_sentidos(matriz):
    assert M.consulta("feijao_caupi", "milho", matriz)["grau"] == "favoravel"
    assert M.consulta("sorgo", "feijao_caupi", matriz)["grau"] == "favoravel"
    assert M.consulta("feijao_caupi", "sorgo", matriz)["grau"] == "favoravel"
    assert M.consulta("feijao_comum", "feijao_caupi", matriz)["grau"] == "desfavoravel"
    assert M.consulta("feijao_caupi", "feijao_comum", matriz)["grau"] == "desfavoravel"


def test_evidencia_divergente_vira_lacuna_sem_decidir(matriz):
    c = M.consulta("milho", "feijao_caupi", matriz)  # sanidade favorável x nitrogênio desfavorável
    assert c["divergente"] is True and c["grau"] == "LACUNA" and c["usar_na_nota"] is False
    assert {e["grau"] for e in c["evidencias"]} >= {"favoravel", "desfavoravel"}


def test_neutro_nao_e_usado_para_preencher_lacuna(matriz):
    # 'neutro' só existe com evidência (fonte cita a opção/prática); nenhuma LACUNA vira neutro
    for (a, s), rows in matriz.items():
        graus = {r["grau"] for r in rows}
        if "LACUNA" in graus:
            assert graus == {"LACUNA"} and len(rows) == 1
        if M.consulta(a, s, matriz)["grau"] == "neutro":
            assert all(r["trecho"] for r in rows)


def test_consulta_par_fora_da_matriz():
    with pytest.raises(KeyError):
        M.consulta("soja", "milho")


def test_sem_intervalo_de_retorno_por_familia(linhas):
    # a pesquisa não achou tabela brasileira com fonte: a matriz não pode ter coluna/valor de intervalo
    assert not any("intervalo" in c for c in M.COLUNAS)
    assert not any("anos" in r["motivo"].lower() and "intervalo" in r["motivo"].lower() for r in linhas)


def test_manifesto_sha_dos_pdfs_citados(linhas):
    import hashlib
    man = M._manifesto()
    for arq in {r["arquivo"] for r in linhas if r["arquivo"]}:
        h = hashlib.sha256((M.DOCS / arq).read_bytes()).hexdigest()
        assert h == man[arq]["sha256"], arq
