"""Limite de taxa da API: lógica (relógio falso) e integração com a rota (TestClient)."""
import pytest
from fastapi.testclient import TestClient

from src.api import main as api
from src.api.limite_taxa import LimiteTaxa, _par, cabecalhos


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _lim(geral=(3, 10.0), pesado=(2, 10.0), **kw):
    r = Relogio()
    return LimiteTaxa(geral=geral, pesado=pesado, relogio=r, **kw), r


def test_permite_ate_o_limite_e_bloqueia_depois():
    lim, _ = _lim()
    ok = [lim.verificar("1.1.1.1", "geral")["ok"] for _ in range(4)]
    assert ok == [True, True, True, False]


def test_restante_diminui_e_retry_after_positivo():
    lim, r = _lim()
    assert lim.verificar("a", "geral")["restante"] == 2
    lim.verificar("a", "geral"); lim.verificar("a", "geral")
    bloq = lim.verificar("a", "geral")
    assert not bloq["ok"] and bloq["restante"] == 0 and bloq["retry_after"] >= 1


def test_janela_desliza_e_libera_depois_do_tempo():
    lim, r = _lim()
    for _ in range(3):
        lim.verificar("a", "geral")
    assert not lim.verificar("a", "geral")["ok"]
    r.t += 10.1                      # a janela de 10 s passou
    assert lim.verificar("a", "geral")["ok"]


def test_clientes_e_grupos_sao_independentes():
    lim, _ = _lim()
    for _ in range(2):
        lim.verificar("a", "pesado")
    assert not lim.verificar("a", "pesado")["ok"]
    assert lim.verificar("b", "pesado")["ok"]          # outro cliente
    assert lim.verificar("a", "geral")["ok"]           # outro grupo do mesmo cliente


def test_grupos_de_rota():
    g = LimiteTaxa.grupo
    assert g("/saude") is None
    assert g("/municipios") == "geral" and g("/diagnostico/quixada_ce") == "geral"
    for rota in ("/cenarios", "/cenarios/clima", "/rotacao", "/plano", "/evidencias", "/modelo/previsao/quixada_ce"):
        assert g(rota) == "pesado", rota


def test_proxy_so_confiado_quando_configurado():
    lim, _ = _lim(confiar_proxy=False)
    assert lim.cliente("9.9.9.9", "1.2.3.4, 5.6.7.8") == "9.9.9.9"     # forjar o cabeçalho não ajuda
    lim2, _ = _lim(confiar_proxy=True)
    assert lim2.cliente("9.9.9.9", "1.2.3.4, 5.6.7.8") == "1.2.3.4"
    assert lim2.cliente("9.9.9.9", None) == "9.9.9.9" and lim2.cliente(None, None) == "desconhecido"


def test_configuracao_invalida_cai_no_padrao():
    assert _par("abc", (120, 60.0)) == (120, 60.0)
    assert _par("0/60", (120, 60.0)) == (120, 60.0)
    assert _par("10/-5", (120, 60.0)) == (120, 60.0)
    assert _par("10/30", (120, 60.0)) == (10, 30.0)


def test_ambiente(monkeypatch):
    monkeypatch.setenv("SULCO_RATE_LIMIT", "0")
    assert LimiteTaxa.do_ambiente().ligado is False
    monkeypatch.setenv("SULCO_RATE_LIMIT", "1")
    monkeypatch.setenv("SULCO_RATE_GERAL", "5/30")
    monkeypatch.setenv("SULCO_RATE_PESADO", "2/30")
    monkeypatch.setenv("SULCO_CONFIAR_PROXY", "1")
    lim = LimiteTaxa.do_ambiente()
    assert lim.ligado and lim.geral == (5, 30.0) and lim.pesado == (2, 30.0) and lim.confiar_proxy


def test_memoria_limitada(monkeypatch):
    import src.api.limite_taxa as m
    monkeypatch.setattr(m, "MAX_CHAVES", 50)
    lim, _ = _lim()
    for i in range(500):
        lim.verificar(f"c{i}", "geral")
    assert len(lim._hist) <= 50


def test_cabecalhos():
    h = cabecalhos({"ok": False, "limite": 3, "restante": 0, "reinicia_em": 4.2, "retry_after": 5})
    assert h["Retry-After"] == "5" and h["X-RateLimit-Limit"] == "3" and h["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" not in cabecalhos({"ok": True, "limite": 3, "restante": 2, "reinicia_em": 4.2, "retry_after": 0})


# ------------------------------------------------------------------ integração com a API
@pytest.fixture
def cliente_limitado(monkeypatch):
    lim, relogio = _lim(geral=(4, 60.0), pesado=(2, 60.0))
    monkeypatch.setattr(api, "LIMITE", lim)
    return TestClient(api.app), relogio


def test_api_devolve_429_com_retry_after_nas_rotas_pesadas(cliente_limitado):
    c, _ = cliente_limitado
    r1 = c.get("/evidencias", params={"q": ""})              # conta no grupo pesado (a resposta pode ser 4xx/5xx; o que vale é o limite)
    r2 = c.get("/evidencias", params={"q": ""})
    assert r1.status_code != 429 and r2.status_code != 429
    r3 = c.get("/evidencias", params={"q": ""})
    assert r3.status_code == 429
    assert int(r3.headers["Retry-After"]) >= 1 and r3.headers["X-RateLimit-Remaining"] == "0"
    corpo = r3.json()
    assert corpo["grupo"] == "pesado" and "lacuna" in corpo


def test_api_saude_nunca_toma_429(cliente_limitado):
    c, _ = cliente_limitado
    assert all(c.get("/saude").status_code == 200 for _ in range(30))


def test_api_rota_leve_tem_limite_proprio_e_cabecalhos(cliente_limitado):
    c, _ = cliente_limitado
    r = c.get("/municipios")
    assert r.status_code == 200 and r.headers["X-RateLimit-Limit"] == "4" and r.headers["X-RateLimit-Remaining"] == "3"
    for _ in range(3):
        c.get("/municipios")
    assert c.get("/municipios").status_code == 429


def test_api_libera_depois_da_janela(cliente_limitado):
    c, relogio = cliente_limitado
    for _ in range(4):
        c.get("/municipios")
    assert c.get("/municipios").status_code == 429
    relogio.t += 61
    assert c.get("/municipios").status_code == 200


def test_api_desligada_nao_limita(monkeypatch):
    lim, _ = _lim(geral=(1, 60.0), ligado=False)
    monkeypatch.setattr(api, "LIMITE", lim)
    c = TestClient(api.app)
    assert all(c.get("/municipios").status_code == 200 for _ in range(5))
