"""Testes do RAG: fidelidade ao arquivo de origem, 'sem evidencia' e taxa de acerto.

As perguntas de acerto foram escritas por mim; a frase esperada e a pagina foram
conferidas manualmente no texto extraido do PDF (nao de memoria). O teste de
fidelidade reextrai cada pagina com `pdftotext -f p -l p` (chamada independente
do codigo de producao) e exige que cada trecho do indice seja substring dela.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.rag import busca as B
from src.rag import rag_docs as R

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs_rag"
INDICE = RAIZ / "indice"


def _pagina_independente(pdf: Path, p: int) -> str:
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", "-f", str(p), "-l", str(p), str(pdf), "-"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    return " ".join(out.split())


@pytest.fixture(scope="module")
def indice():
    if not (INDICE / "trechos.jsonl").exists():
        R.construir_indice()
    return B.Indice(INDICE)


@pytest.fixture(scope="module")
def trechos_indexados():
    return [json.loads(l) for l in (INDICE / "trechos.jsonl").read_text(encoding="utf-8").splitlines()]


# ------------------------------------------------------------------ acervo
def test_manifesto_completo_e_sha_confere():
    man = R.carregar_manifesto()
    assert len(man["documentos"]) >= 10
    for d in man["documentos"]:
        assert d["url"].startswith("https://")
        assert d["data_download"] == "2026-11-11" or len(d["data_download"]) == 10
        assert R.sha256_arquivo(DOCS / d["arquivo"]) == d["sha256"], d["arquivo"]
    # todo PDF do acervo esta no manifesto (nada sem proveniencia)
    listados = {d["arquivo"] for d in man["documentos"]}
    assert {p.name for p in DOCS.glob("*.pdf")} == listados


def test_todo_trecho_e_substring_da_pagina_correta(trechos_indexados):
    cache = {}
    assert len(trechos_indexados) > 500
    for t in trechos_indexados:
        chave = (t["arquivo"], t["pagina"])
        if chave not in cache:
            cache[chave] = _pagina_independente(DOCS / t["arquivo"], t["pagina"])
        assert t["texto"] in cache[chave], f"trecho {t['id']} nao e substring de {chave}"


def test_trecho_nao_aparece_em_pagina_errada(trechos_indexados):
    """Sanidade do teste: um trecho longo nao deve casar com a pagina vizinha (se casar, o teste e fraco)."""
    t = next(x for x in trechos_indexados if len(x["texto"]) > 400 and x["pagina"] > 1)
    outra = _pagina_independente(DOCS / t["arquivo"], t["pagina"] - 1)
    assert t["texto"] not in outra


def test_chunking_unidades():
    texto = ("Frase um sobre a rotação de culturas no semiárido. " * 30).strip()
    for a, b in R.cortar_pagina(texto):
        assert b > a and b - a <= R.MAX_CHARS
        assert texto[a:b] in texto
    assert R.cortar_pagina("") == []


# ------------------------------------------------------------------- busca
def test_formato_da_saida(indice):
    r = indice.buscar("Quais adubos verdes foram usados antes do milho?")
    assert r["sem_evidencia"] is False
    assert 1 <= len(r["trechos"]) <= 5
    for i, t in enumerate(r["trechos"], start=1):
        assert set(t) == {"n", "arquivo", "pagina", "texto"}
        assert t["n"] == i and isinstance(t["pagina"], int) and t["pagina"] >= 1


def test_trechos_da_busca_sao_substring_verificavel(indice):
    for q in ["rotação de culturas e pragas", "zoneamento agrícola de risco climático seguro rural"]:
        for t in indice.buscar(q)["trechos"]:
            assert t["texto"] in _pagina_independente(DOCS / t["arquivo"], t["pagina"])


FORA_DO_ACERVO = [
    "Qual o preço do dólar hoje?",
    "Como tratar câncer de pele?",
    "Receita de bolo de cenoura com cobertura de chocolate",
    "Quanto custa um trator novo de 100 cavalos?",
    "Qual a previsão de chuva para amanhã em Petrolina?",
    "Quem ganhou a Copa do Mundo de 2002?",
    "asdkjh qwpoei zxmnb",
    "",
]


@pytest.mark.parametrize("pergunta", FORA_DO_ACERVO)
def test_sem_evidencia_explicita(indice, pergunta):
    r = indice.buscar(pergunta)
    assert r["sem_evidencia"] is True
    assert r["mensagem"] == "sem evidência"
    assert r["trechos"] == []


def test_limiar_alto_forca_sem_evidencia(indice):
    r = indice.buscar("rotação de culturas", lim_cobertura=1.01, lim_cos=1.01)
    assert r["sem_evidencia"] and r["trechos"] == []


# (pergunta, arquivo, pagina, frase esperada no trecho -- conferida no PDF)
PERGUNTAS = [
    ("Quais adubos verdes foram usados antes do milho no plantio direto?",
     "pab_milho_sucessao_adubos_verdes.pdf", 3, "mucuna-preta"),
    ("Quanto a crotalária aumentou a produtividade do milho?",
     "pab_milho_sucessao_adubos_verdes.pdf", 1, "18,5%"),
    ("Para que o zoneamento de risco climático é usado no seguro rural?",
     "mapa_zarc_2021.pdf", 1, "Seguro Rural"),
    ("O que é rotação de culturas segundo a FAO?",
     "fao_reosa_conservation_agriculture_2010.pdf", 2,
     "Different crops are planted one after the other in the same field at different seasons or years"),
    ("Quais são os três princípios da agricultura de conservação?",
     "fao_reosa_conservation_agriculture_2010.pdf", 1, "Minimum soil disturbance"),
    ("Qual milho foi consorciado com capim-massai para fazer silagem no semiárido?",
     "mapa_2021_forragem_semiarido_ajustes.pdf", 3, "AL Bandeirante"),
    ("Quais variedades de sorgo foram avaliadas como forragem no Semiárido?",
     "mapa_2021_forrageiras_semiarido.pdf", 3, "BRS 658"),
    ("Consórcio de capim com leguminosa coloca nitrogênio no solo?",
     "univasf_consorcio_gramineas_leguminosas.pdf", 13, "adicionar nitrogênio e proteger o solo"),
    ("As leguminosas ajudam os cereais com nitrogênio na rotação?",
     "fao_reosa_conservation_agriculture_2010.pdf", 3, "Legumes have the added advantage of fixing nitrogen"),
    ("Como a falta de água afeta a planta na época de florescimento?",
     "agrometeoros_zoneamento_metodologias.pdf", 4, "déficit hídrico é extremamente prejudicial"),
    ("Por que a cobertura vegetal do solo se decompõe rápido no Vale do São Francisco irrigado?",
     "univasf_ciclagem_nutrientes_semiarido.pdf", 11, "favorecem a decomposição da cobertura vegetal"),
    ("Para que serve deixar palha de restos de cultura na lavoura?",
     "fao_reosa_conservation_agriculture_2010.pdf", 1, "Crop residues are retained in the field as mulch"),
    ("A rotação de culturas ajuda a controlar pragas e doenças?",
     "fao_reosa_conservation_agriculture_2010.pdf", 1, "breaking their cycles"),
]


def _acerto(indice, q, arq, pag, frase):
    r = indice.buscar(q, k=5)
    return any(t["arquivo"] == arq and t["pagina"] == pag and frase in t["texto"] for t in r["trechos"])


def _taxa(ind, perguntas):
    falhas = [q for q, a, p, f in perguntas if not _acerto(ind, q, a, p, f)]
    return 1 - len(falhas) / len(perguntas), falhas


def _em_ingles(item):
    return item[1].startswith("fao_")


def test_taxa_de_acerto_top5_hibrido(indice):
    """Meta do projeto: >= 80% no top 5. Medida separando documentos em PT e em EN (FAO)."""
    t_all, f_all = _taxa(indice, PERGUNTAS)
    t_pt, f_pt = _taxa(indice, [x for x in PERGUNTAS if not _em_ingles(x)])
    t_en, f_en = _taxa(indice, [x for x in PERGUNTAS if _em_ingles(x)])
    print(f"\nmodo={indice.modo} total={t_all:.0%} pt={t_pt:.0%} en(pergunta PT->doc EN)={t_en:.0%}")
    print("falhas:", f_all)
    assert t_pt >= 0.7, f_pt  # piso de regressao (medido 75%); meta 80% NAO atingida
    assert t_all >= 0.5, f_all  # medido 54%; falhas = vocabulario diferente (PT->EN, "falta de agua" vs "deficit hidrico")


def test_taxa_de_acerto_top5_so_bm25():
    ind = B.Indice(INDICE, usar_embeddings=False)
    assert ind.modo == "bm25"
    falhas = [q for q, a, p, f in PERGUNTAS if not _acerto(ind, q, a, p, f)]
    taxa = 1 - len(falhas) / len(PERGUNTAS)
    print(f"\nmodo=bm25 acerto@5={taxa:.0%} falhas={falhas}")
    # BM25 sozinho nao cruza idiomas (pergunta PT, doc EN): piso menor, so para regressao.
    assert taxa >= 0.4, falhas  # medido 46%


def test_so_bm25_tambem_diz_sem_evidencia():
    ind = B.Indice(INDICE, usar_embeddings=False)
    for q in FORA_DO_ACERVO:
        assert ind.buscar(q)["sem_evidencia"] is True


# ---------------------------------------------------------- construcao do indice
def test_construir_indice_recusa_sha_divergente(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    shutil.copy(DOCS / "mapa_zarc_2021.pdf", d / "mapa_zarc_2021.pdf")
    man = R.carregar_manifesto()
    doc = next(x for x in man["documentos"] if x["arquivo"] == "mapa_zarc_2021.pdf")
    doc = dict(doc, sha256="0" * 64)
    (d / "manifesto.json").write_text(json.dumps({"documentos": [doc]}), encoding="utf-8")
    meta = R.construir_indice(com_embeddings=False, dir_docs=d, dir_indice=tmp_path / "ind")
    assert meta["n_trechos"] == 0 and "sha256" in meta["erros"][0]


def test_construir_indice_pequeno_e_buscar(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    shutil.copy(DOCS / "mapa_zarc_2021.pdf", d / "mapa_zarc_2021.pdf")
    doc = next(x for x in R.carregar_manifesto()["documentos"] if x["arquivo"] == "mapa_zarc_2021.pdf")
    (d / "manifesto.json").write_text(json.dumps({"documentos": [doc]}), encoding="utf-8")
    meta = R.construir_indice(com_embeddings=False, dir_docs=d, dir_indice=tmp_path / "ind")
    assert meta["n_trechos"] > 5 and meta["erros"] == []
    r = B.buscar("zoneamento agrícola de risco climático Proagro", dir_indice=tmp_path / "ind")
    assert not r["sem_evidencia"]
    assert all(t["arquivo"] == "mapa_zarc_2021.pdf" for t in r["trechos"])
