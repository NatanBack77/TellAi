"""Fixtures compartilhadas. Clima aqui é SINTÉTICO: só testa lógica, nunca é resultado real."""
import os
import socket
import tempfile

import numpy as np
import pandas as pd
import pytest

# O limite de taxa da API (src/api/limite_taxa.py) fica DESLIGADO na suíte: vários testes chamam as rotas pesadas em sequência do mesmo
# cliente. O próprio limite é testado em tests/test_limite_taxa.py com instâncias próprias.
os.environ.setdefault("SULCO_RATE_LIMIT", "0")

# ---- PROTEÇÃO CONTRA GASTO (SULCO_TESTE_SEM_REDE): o .env real tem a chave do DeepSeek e o usuário só tem US$ 5. ----
# A suíte NUNCA pode chegar à chave real nem abrir conexão externa: variáveis fixadas ANTES de qualquer import, leitura do .env
# desligada e bloqueio de sockets que não sejam locais. Testes do DeepSeek usam transporte HTTP falso injetado.
os.environ["SULCO_TESTE_SEM_REDE"] = "1"
os.environ["SULCO_CARREGAR_ENV"] = "0"
# TRAVA DE GASTO DA SUÍTE (a chave real do .env tem saldo pequeno): ambiente fixado ANTES de qualquer import do projeto.
os.environ["SULCO_LLM_MODO"] = "template"
os.environ["DEEPSEEK_API_KEY"] = "sk-teste-falsa"
os.environ["SULCO_LLM_MAX_CHAMADAS_DIA"] = "1000"
os.environ["SULCO_GASTO_ARQ"] = os.path.join(tempfile.mkdtemp(prefix="sulco_gasto_"), "gasto.json")



def clima_sintetico(pid="x_ce", anos=range(2001, 2025), chuva_pico=8.0, chuva_base=0.0, meses_chuva=(1, 2, 3, 4, 5),
                    tmax=34.0, tmin=22.0, fator_ano=None) -> pd.DataFrame:
    """Chuva diária = `chuva_pico` nos meses chuvosos e `chuva_base` no resto; `fator_ano` {ano: multiplicador}."""
    datas = pd.date_range(f"{min(anos)}-01-01", f"{max(anos)}-12-31")
    chuva = np.where(datas.month.isin(meses_chuva), chuva_pico, chuva_base).astype(float)
    if fator_ano:
        chuva = chuva * np.array([fator_ano.get(a, 1.0) for a in datas.year])
    return pd.DataFrame({"ponto_id": pid, "celula_power": "-1_-1", "data": datas, "chuva_mm": chuva,
                         "tmax_c": tmax, "tmin_c": tmin, "radiacao": 20.0})


@pytest.fixture
def fabrica_clima():
    return clima_sintetico


@pytest.fixture(autouse=True)
def _sem_rede(monkeypatch):
    """Bloqueia saída de rede em todos os testes (só loopback). Chamada real ao DeepSeek na suíte vira erro, nunca gasto."""
    orig = socket.socket.connect

    def conectar(self, endereco, *a, **k):
        host = endereco[0] if isinstance(endereco, tuple) else endereco
        if self.family == socket.AF_UNIX or str(host) in ("127.0.0.1", "::1", "localhost"):
            return orig(self, endereco, *a, **k)
        raise RuntimeError(f"REDE BLOQUEADA nos testes: tentativa de conectar a {host!r}")

    def resolver(host, *a, **k):
        if str(host) in ("127.0.0.1", "::1", "localhost"):
            return orig_gai(host, *a, **k)
        raise RuntimeError(f"REDE BLOQUEADA nos testes: resolução de {host!r}")

    orig_gai = socket.getaddrinfo
    monkeypatch.setattr(socket.socket, "connect", conectar)
    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    yield
