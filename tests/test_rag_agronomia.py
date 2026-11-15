"""Base agronomica (src/rag/agronomia.py): sem rede, sem DeepSeek. Embeddings reais so se o modelo ja estiver em cache."""
import json
import re
from pathlib import Path

import pytest

from src.rag import agronomia as A

RAIZ = A.RAIZ
IDX = A.DIR_INDICE
PROIB_TESTE = ["docker", "deepseek", "prompt", "agente", "subagente", ".env", "pytest", "commit", "endpoint", "streamlit", "senha",
               "api_key", "src/", "tests/", "pipeline", "parquet", "deploy"]

pytestmark = pytest.mark.skipif(not (IDX / "trechos.jsonl").exists(), reason="indice_agronomia/ nao gerado (python -m src.rag.agronomia)")


@pytest.fixture(scope="module")
def trechos():
    return [json.loads(l) for l in (IDX / "trechos.jsonl").read_text(encoding="utf-8").splitlines() if l]


def _modelo_em_cache() -> bool:
    return any(Path.home().glob(".cache/huggingface/hub/models--intfloat--multilingual-e5-small"))


def test_sem_segredos_nem_termos_de_projeto(trechos):
    for t in trechos:
        low = t["texto"].lower()
        assert not A._SEGREDO_RE.search(t["texto"]), t["id"]
        for p in PROIB_TESTE:
            assert p not in low, (t["id"], p)
        assert not A.bloco_proibido(t["texto"]), t["id"]


def test_sem_latlon(trechos):
    for t in trechos:
        assert not A._COORD_RE.search(t["texto"]), t["id"]
    assert not any(k in t for t in trechos for k in ("lat", "lon") if k in t)  # nenhum campo de coordenada nos metadados


def test_metadados_e_tipos(trechos):
    tipos = {"pesquisa_interna", "tabela_com_fonte", "dado_minerado", "estudo_publicado", "lacuna"}
    confs = {"alta", "media", "baixa", "lacuna"}
    ids = [t["id"] for t in trechos]
    assert len(ids) == len(set(ids))
    for t in trechos:
        assert t["tipo"] in tipos and t["confianca"] in confs and t["data"]
        assert t["fonte"] and t["arquivo"] and "pode_citar_ao_agricultor" in t


def test_so_lista_branca(trechos):
    permitidas = set(A.DOCS_BRANCOS) | set(A.TABELAS) | {"conab_precos_uf", "conab_precos_municipio", "conab_custos", "sigef",
                                                        "zarc", "pam", "solo", "diagnostico", "lacunas"}
    assert {t["fonte"] for t in trechos} <= permitidas
    for proibido in ("docs/00_STATUS.md", "docs/15_PENDENCIAS.md", "docs/18_ARQUITETURA_TECNICA.md", "docs/26_PESQUISA_AGENTE_HUMANO.md",
                     "docs/28_PESQUISA_VOZ_HUMANA.md", "docs/09_PESQUISA_PREVISAO_NDVI.md", "docs/17_PITCH.md"):
        assert proibido not in {t["fonte"] for t in trechos}


def test_tamanho_dos_trechos_de_documento(trechos):
    docs = [len(t["texto"].split()) for t in trechos if t["fonte"].startswith("docs/") and t["tipo"] != "lacuna"]
    assert docs and max(docs) <= 330  # ~150-250 palavras + titulo; tabelas indivisiveis podem passar um pouco


def test_busca_com_fonte_confianca_e_formato_chat():
    r = A.buscar_agronomia("qual a faixa de LER da mamona com caupi", k=5)
    assert not r["sem_evidencia"]
    t = r["trechos"][0]
    for c in ("n", "id", "arquivo", "pagina", "texto", "fonte", "confianca", "aviso", "tipo", "data", "pode_citar_ao_agricultor"):
        assert c in t
    assert t["fonte"] and t["confianca"] in ("alta", "media", "baixa", "lacuna")


def test_lacunas_recuperadas_top3():
    for q, kw in [("tem dado de preço?", "preço"), ("qual a produtividade do milho aqui?", "produtividade"), ("qual semente devo usar?", "cultivar|semente"),
                  ("quanto custa plantar?", "custo"), ("vai chover mês que vem?", "previs"), ("quais pragas dão no milho", "praga"),
                  ("que veneno uso", "defensiv|agrotóx"), ("quanto de adubo coloco", "adub"), ("preciso de calcário", "calc")]:
        r = A.buscar_agronomia(q, k=3)
        assert any(t["tipo"] == "lacuna" and re.search(kw, t["texto"], re.I) for t in r["trechos"]), q


def test_filtro_municipio_e_cultura():
    r = A.buscar_agronomia("quando plantar milho", k=5, municipio="Quixadá")
    assert r["trechos"]
    for t in r["trechos"]:
        assert t["municipio"] in (None, "Quixadá")
    r = A.buscar_agronomia("ciclo e temperatura", k=8, cultura="sorgo")
    for t in r["trechos"]:
        assert not t["culturas"] or "sorgo" in t["culturas"]


@pytest.mark.parametrize("q", ["como foi feito o app", "quanto custou a API", "qual o PIN", "quais agentes trabalharam",
                               "como funciona o Docker", "qual a senha do servidor", "como é feito o deploy", "qual o prompt do chat"])
def test_pergunta_sobre_o_projeto_nao_recupera_nada(q):
    r = A.buscar_agronomia(q, k=5)
    assert r["sem_evidencia"] or all(not A.bloco_proibido(t["texto"]) for t in r["trechos"])
    assert r["sem_evidencia"], [t["texto"][:80] for t in r["trechos"]]


def test_trecho_interno_bloqueado_pelo_filtro(tmp_path):
    reg = [{"texto": "A cultura do milho precisa de chuva regular no semiárido durante o ciclo.", "tipo": "pesquisa_interna", "arquivo": "x",
            "secao": "s", "fonte": "x", "url": "", "data": "2026-11-14", "confianca": "media", "municipio": None, "culturas": ["milho"],
            "pode_citar_ao_agricultor": True, "aviso": ""},
           {"texto": "O milho interno de engenharia tem chuva regular no ciclo para a equipe.", "tipo": "pesquisa_interna", "arquivo": "y",
            "secao": "s", "fonte": "y", "url": "", "data": "2026-11-14", "confianca": "media", "municipio": None, "culturas": ["milho"],
            "pode_citar_ao_agricultor": False, "aviso": ""}]
    for i, r in enumerate(reg):
        r["id"], r["hash"] = f"t{i}", A._hash_texto(r["texto"])
    A.construir(dir_indice=tmp_path, registros=reg, com_embeddings=False, verbose=False)
    ix = A.IndiceAgronomia(tmp_path, usar_embeddings=False)
    ag = ix.buscar("milho chuva regular ciclo", k=5)
    assert [t["id"] for t in ag["trechos"]] == ["t0"]
    todos = ix.buscar("milho chuva regular ciclo", k=5, so_agricultor=False)
    assert {t["id"] for t in todos["trechos"]} == {"t0", "t1"}


def test_bloqueios_de_conteudo():
    for s in ["Rodar o Docker no servidor", "chave DEEPSEEK_API_KEY=abc", "o PIN: 1234", "arquivo src/llm/chat.py", "lat: -5.1 lon: -39.7",
              "-5.1789, -39.2954", "sk-abcdefghijklmnopqrstuvwxyz"]:
        assert A.bloco_proibido(s), s
    for s in ["O milho precisa de 400 mm de chuva", "ciclo de 90 dias no semiárido"]:
        assert not A.bloco_proibido(s), s


def test_idempotencia_manifesto_e_so_o_que_mudou():
    r = A.construir(com_embeddings=True, verbose=False)   # nada mudou desde a construcao
    assert r["reconstruido"] is False
    man = json.loads(A.MANIFESTO.read_text(encoding="utf-8"))
    assert all(len(v["sha256"]) == 64 and v["data"] for v in man["fontes"].values())
    assert A.LACUNAS_DOC in man["fontes"] and "docs/00_STATUS.md" not in man["fontes"]


def test_busca_sem_embeddings_bm25():
    ix = A.IndiceAgronomia(IDX, usar_embeddings=False)
    assert ix.modo == "bm25"
    assert not ix.buscar("ciclo FAO do sorgo", k=3)["sem_evidencia"]


@pytest.mark.skipif(not _modelo_em_cache(), reason="modelo e5 nao esta em cache")
def test_busca_hibrida_com_embeddings():
    r = A.buscar_agronomia("qual o ciclo da FAO para o sorgo", k=5)
    assert r["modo"] == "hibrido"
    assert any(t["fonte"] == "fao_staging" and "sorgo" in t["texto"].lower() for t in r["trechos"])
