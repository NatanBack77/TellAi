"""Limite de taxa (rate limit) da API, sem dependência nova: janela deslizante por cliente e por grupo de rota.

Por quê: o `/cenarios`, `/rotacao`, `/plano` e `/evidencias` são pesados (Monte Carlo, reranker); sem limite, poucos clientes esgotam a CPU.
Dois grupos: GERAL (todas as rotas, exceto as isentas) e PESADO (rotas caras, limite menor). Estourou => HTTP 429 + `Retry-After`.

Configuração (variáveis de ambiente; formato "N/SEGUNDOS"):
  SULCO_RATE_LIMIT=0|1          liga/desliga (padrão 1)
  SULCO_RATE_GERAL=120/60       padrão: 120 requisições por 60 s por cliente
  SULCO_RATE_PESADO=20/60       padrão: 20 requisições por 60 s por cliente nas rotas pesadas
  SULCO_CONFIAR_PROXY=0|1       1 = usa o 1º IP de X-Forwarded-For (SÓ atrás de um proxy confiável; senão o cliente forja o IP)

Limites (declarados): o contador fica na MEMÓRIA do processo. Com vários processos/réplicas cada um conta sozinho (o limite efetivo
multiplica); para limite global use também o proxy (docker/nginx/nginx.conf). Não substitui autenticação.
"""
from __future__ import annotations

import math
import os
import threading
import time
from collections import deque

# Rotas isentas (healthcheck do orquestrador não pode tomar 429)
ISENTAS = ("/saude",)
# Prefixos de rotas caras (Monte Carlo, otimização, reranker, treino)
PESADAS = ("/cenarios", "/rotacao", "/plano", "/evidencias", "/modelo/previsao", "/chat", "/conversa", "/calendario", "/voz/transcrever", "/voz/falar")
MAX_CHAVES = 20_000


def _par(texto: str, padrao: tuple[int, float]) -> tuple[int, float]:
    """'N/SEGUNDOS' -> (N, SEGUNDOS); valor inválido cai no padrão (e é ignorado em silêncio, nunca derruba a API)."""
    try:
        n, s = texto.split("/")
        n, s = int(n), float(s)
        return (n, s) if n > 0 and s > 0 else padrao
    except Exception:
        return padrao


class LimiteTaxa:
    def __init__(self, geral: tuple[int, float] = (120, 60.0), pesado: tuple[int, float] = (20, 60.0), ligado: bool = True,
                 confiar_proxy: bool = False, relogio=time.monotonic):
        self.geral, self.pesado, self.ligado, self.confiar_proxy = geral, pesado, ligado, confiar_proxy
        self._relogio = relogio
        self._hist: dict[tuple[str, str], deque] = {}
        self._trava = threading.Lock()

    @classmethod
    def do_ambiente(cls) -> "LimiteTaxa":
        e = os.environ
        return cls(geral=_par(e.get("SULCO_RATE_GERAL", ""), (120, 60.0)), pesado=_par(e.get("SULCO_RATE_PESADO", ""), (20, 60.0)),
                   ligado=e.get("SULCO_RATE_LIMIT", "1") != "0", confiar_proxy=e.get("SULCO_CONFIAR_PROXY", "0") == "1")

    # -------- classificação
    @staticmethod
    def grupo(caminho: str) -> str | None:
        """None = isenta; 'pesado' ou 'geral'."""
        if caminho in ISENTAS:
            return None
        return "pesado" if caminho.startswith(PESADAS) else "geral"

    def cliente(self, ip: str | None, x_forwarded_for: str | None) -> str:
        if self.confiar_proxy and x_forwarded_for:
            primeiro = x_forwarded_for.split(",")[0].strip()
            if primeiro:
                return primeiro
        return ip or "desconhecido"

    # -------- decisão
    def verificar(self, cliente: str, grupo: str) -> dict:
        """Registra a requisição se couber. Devolve {ok, limite, restante, reinicia_em (s), retry_after (s)}."""
        n, janela = self.pesado if grupo == "pesado" else self.geral
        agora = self._relogio()
        chave = (cliente, grupo)
        with self._trava:
            fila = self._hist.get(chave)
            if fila is None:
                if len(self._hist) >= MAX_CHAVES:      # protege a memória: descarta os clientes sem atividade na janela
                    self._limpar(agora)
                    if len(self._hist) >= MAX_CHAVES:
                        self._hist.pop(next(iter(self._hist)))
                fila = self._hist[chave] = deque()
            while fila and agora - fila[0] >= janela:
                fila.popleft()
            if len(fila) >= n:
                espera = max(janela - (agora - fila[0]), 0.0)
                return {"ok": False, "limite": n, "restante": 0, "reinicia_em": espera, "retry_after": max(1, math.ceil(espera))}
            fila.append(agora)
            reinicia = janela - (agora - fila[0])
            return {"ok": True, "limite": n, "restante": n - len(fila), "reinicia_em": reinicia, "retry_after": 0}

    def _limpar(self, agora: float) -> None:
        for chave in [c for c, f in self._hist.items() if not f or agora - f[-1] >= max(self.geral[1], self.pesado[1])]:
            self._hist.pop(chave, None)


def cabecalhos(r: dict) -> dict[str, str]:
    h = {"X-RateLimit-Limit": str(r["limite"]), "X-RateLimit-Remaining": str(r["restante"]),
         "X-RateLimit-Reset": str(max(0, math.ceil(r["reinicia_em"])))}
    if not r["ok"]:
        h["Retry-After"] = str(r["retry_after"])
    return h
