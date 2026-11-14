"""Integracao LLM -> app (src/llm/integracao.py), pregerar e avaliar_l4. Sem rede, sem chave, sem reranker."""
import json

from src.llm import avaliar_l4, integracao, pregerar, servico
from src.llm.cache import Cache
from src.llm.provedores import DeepSeek, Provedor, Stub
from tests.test_llm import AV, Fake, cenario


def test_padrao_e_template_sem_chamar_nada(monkeypatch):
    monkeypatch.delenv("SULCO_LLM_MODO", raising=False)
    f = Fake("qualquer [1]" + AV)
    r = integracao.explicar_cenario(cenario(), provedor=f)
    assert r["origem"] == "template" and f.chamadas == 0 and "Por que:" in r["texto"]


def test_stub_nao_vira_texto_da_tela_por_padrao(tmp_path):
    r = integracao.explicar_cenario(cenario(), modo="online", provedor=Stub(), cache=Cache(tmp_path))
    assert r["origem"] == "template" and "stub" in r["motivos"][0]


def test_online_sem_chave_cai_no_template(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    prov = DeepSeek(chave="", caminho_env=tmp_path / "nao_existe.env",
                    transporte=lambda *a, **k: (_ for _ in ()).throw(AssertionError("nao deveria chamar a rede")))
    assert not integracao.tem_chave(prov)
    r = integracao.explicar_cenario(cenario(), modo="online", provedor=prov, cache=Cache(tmp_path))
    assert r["origem"] == "template" and "sem chave" in r["motivos"][0]


def test_online_com_provedor_valido_grava_cache_e_offline_le(tmp_path):
    f = Fake("O feijão fixa nitrogênio [1]." + AV)
    c = Cache(tmp_path)
    r1 = integracao.explicar_cenario(cenario(), modo="online", provedor=f, cache=c)
    assert r1["origem"] == "llm" and f.chamadas == 1
    f2 = Fake("outra coisa")
    r2 = integracao.explicar_cenario(cenario(), modo="offline", provedor=f2, cache=c)
    assert r2["origem"] == "llm" and r2["em_cache"] and f2.chamadas == 0 and r2["texto"] == r1["texto"]


def test_offline_sem_cache_cai_no_template(tmp_path):
    f = Fake("x")
    r = integracao.explicar_cenario(cenario(), modo="offline", provedor=f, cache=Cache(tmp_path / "vazio"))
    assert r["origem"] == "template" and f.chamadas == 0


def test_saida_invalida_do_llm_vira_template(tmp_path):
    r = integracao.explicar_cenario(cenario(), modo="online", provedor=Fake("rende mais [1]." + AV), cache=Cache(tmp_path))
    assert r["origem"] == "template" and r["motivos"]


def test_modo_invalido_e_env(monkeypatch):
    monkeypatch.setenv("SULCO_LLM_MODO", "lixo")
    assert integracao.modo_padrao() == "template"
    monkeypatch.setenv("SULCO_LLM_MODO", "offline")
    assert integracao.modo_padrao() == "offline"


def test_responder_pergunta_sem_llm_devolve_trechos_ou_sem_evidencia():
    busca = lambda p: {"sem_evidencia": False, "trechos": [{"n": 1, "arquivo": "a.pdf", "pagina": 2, "texto": "O caupi fixa nitrogênio no solo, e vale ler isso com calma."}]}  # noqa: E731
    r = integracao.responder_pergunta("o caupi fixa nitrogênio?", buscar_fn=busca)
    assert r["origem"] == "template" and "[1]" in r["texto"]
    r = integracao.responder_pergunta("?", buscar_fn=lambda p: {"sem_evidencia": True, "trechos": []})
    assert r["origem"] == "sem_evidencia"


def test_rotulo_origem():
    assert "regras" in integracao.rotulo_origem({"origem": "template"})
    assert "verificado" in integracao.rotulo_origem({"origem": "llm"})


# ----- pregerar
def test_pregerar_sem_chave_nao_faz_nada(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SULCO_LLM", "deepseek")
    monkeypatch.setattr(integracao, "obter_provedor_real", lambda: DeepSeek(chave="", caminho_env=tmp_path / "x.env"))
    monkeypatch.setattr(pregerar, "obter_provedor_real", integracao.obter_provedor_real)
    r = pregerar.pregerar(provedor=None, cache=Cache(tmp_path / "c"))
    assert r["feito"] is False and r["n"] == 0
    assert not (tmp_path / "c").exists()


def test_pregerar_com_provedor_falso_grava_cache(tmp_path):
    pasta = tmp_path / "cen"
    pasta.mkdir()
    (pasta / "a.json").write_text(json.dumps([cenario(), cenario()]), encoding="utf-8")
    f = Fake("O feijão fixa nitrogênio [1]." + AV)
    r = pregerar.pregerar(pasta, provedor=f, cache=Cache(tmp_path / "c"))
    assert r["feito"] and r["n"] == 2 and r["por_origem"]["llm"] == 2
    assert len(list((tmp_path / "c").glob("*.json"))) == 1  # mesmo cenario => mesma chave
    # depois disso o app offline le do cache
    r2 = integracao.explicar_cenario(cenario(), modo="offline", provedor=Fake("x"), cache=Cache(tmp_path / "c"))
    assert r2["origem"] == "llm" and r2["em_cache"]


def test_pregerar_carrega_cenarios_reais():
    cs = pregerar.carregar()
    assert len(cs) >= 10 and all("rotacao" in c for c in cs)


# ----- avaliar_l4 (encanamento com stub e busca simulada)
class IndiceFalso:
    def __init__(self):
        self.t = {"arquivo": "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", "pagina": 1,
                  "texto": "O feijão caupi exige um mínimo de 300 mm de precipitação ao longo do ciclo."}

    def buscar(self, q, k=5):
        if "chuva" in q:
            return {"sem_evidencia": False, "trechos": [dict(self.t, n=1)]}
        return {"sem_evidencia": True, "trechos": []}


def test_avaliar_l4_encanamento_stub():
    perguntas = [("Quantos milímetros de chuva o caupi precisa?", "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", 1,
                  "exige um mínimo de 300 mm de precipitação"),
                 ("Qual o preço da saca?", None, None, None)]
    res = avaliar_l4.avaliar(Stub(), IndiceFalso(), perguntas)
    assert res["recuperacao_top5"] == 1.0 and res["citacao_correta"] == 1.0
    assert res["sem_evidencia_ok"] == 1.0 and res["json_valido"] == 1.0
    assert "custo_usd_faixa" not in res  # stub nao tem custo


def test_avaliar_l4_main_sem_chave_nao_chama(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(avaliar_l4, "obter", lambda n: DeepSeek(chave="", caminho_env=tmp_path / "x.env"))
    assert avaliar_l4.main(["--provedor", "deepseek"]) == 0
    assert "não executada" in capsys.readouterr().out
