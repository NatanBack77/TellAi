"""Provedores de LLM com interface unica: `gerar(sistema, usuario) -> str`.

- stub: deterministico, sem rede, sem chave (testes e app offline).
- deepseek: API compativel OpenAI. Sem DEEPSEEK_API_KEY => ProvedorIndisponivel (o servico cai no template).
A chave nunca e impressa, logada nem incluida em mensagens de erro.
Documentacao lida em 2026-11-12: https://api-docs.deepseek.com/ (base_url, modelos, endpoint),
https://api-docs.deepseek.com/quick_start/error_codes e .../api/create-chat-completion (parametros).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODELO = "deepseek-flash"  # ID da doc oficial (pagina inicial e de precos); sobrescreva com DEEPSEEK_MODEL
ERROS_HTTP = {400: "formato invalido", 401: "chave de API invalida", 402: "saldo insuficiente",
              422: "parametros invalidos", 429: "limite de taxa", 500: "erro do servidor", 503: "servidor sobrecarregado"}


class ProvedorIndisponivel(RuntimeError):
    """Sem chave/configuracao: o chamador deve usar o template."""


class ProvedorErro(RuntimeError):
    """Falha na chamada (rede/HTTP/formato)."""


class Provedor:
    nome = "base"
    modelo = ""

    def gerar(self, sistema: str, usuario: str, max_tokens: int = 900) -> str:  # pragma: no cover
        raise NotImplementedError


def ler_chave_env(caminho_env: Path | None = None) -> str | None:
    """DEEPSEEK_API_KEY do ambiente ou do .env (le so essa linha)."""
    v = os.environ.get("DEEPSEEK_API_KEY")
    if v and v.strip():
        return v.strip()
    p = caminho_env or (RAIZ / ".env")
    try:
        for ln in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*DEEPSEEK_API_KEY\s*=\s*(.*)$", ln)
            if m and m.group(1).strip().strip("'\""):
                return m.group(1).strip().strip("'\"")
    except OSError:
        pass
    return None


def _cortar(txt: str, n: int) -> str:
    if len(txt) <= n:
        return txt
    c = txt[:n].rsplit(" ", 1)[0]
    return c


class Stub(Provedor):
    """Deterministico: monta o texto SO com valores presentes no prompt (JSON do cenario / trechos)."""
    nome = "stub"
    modelo = "stub-v1"

    def gerar(self, sistema: str, usuario: str, max_tokens: int = 900) -> str:
        trechos = [(int(n), t) for n, t in re.findall(
            r"<<<TRECHO n=(\d+)[^>]*>>>\n(.*?)\n<<<FIM_TRECHO>>>", usuario, re.S)]
        m = re.search(r"<<<CENARIO_JSON>>>\n(.*?)\n<<<FIM_CENARIO_JSON>>>", usuario, re.S)
        aviso = "Isto é um cenário a avaliar com técnico local."
        if m:
            try:
                c = json.loads(m.group(1))
            except ValueError:
                c = {}
            return self._cenario(c, trechos) + " " + aviso
        if not trechos:
            return "sem evidência"
        n, t = trechos[0]
        return f"Segundo o acervo: {_cortar(t, 300)} [{n}] {aviso}"

    @staticmethod
    def _cenario(c: dict, trechos: list) -> str:
        loc = c.get("local")
        if isinstance(loc, dict):
            loc = loc.get("nome") or loc.get("ponto_id") or loc.get("id")
        ns = {n for n, _ in trechos}
        partes = [f"Para {loc}, com a cultura atual {c.get('cultura_atual')}, o cenário é {c.get('rotacao')}."
                  if isinstance(loc, str) else f"O cenário é {c.get('rotacao')}."]
        for nome, cr in (c.get("criterios") or {}).items():
            if not isinstance(cr, dict):
                continue
            cit = ""
            n = cr.get("trecho_n")
            if n in ns:
                cit = f" [{n}]"
            partes.append(f"{nome}: valor {cr.get('valor')} {cr.get('unidade') or ''}, nota {cr.get('nota')}.".replace(" .", ".")
                          .rstrip() + cit)
        for l in (c.get("lacunas") or []):
            partes.append(f"Lacuna: {l}")
        for r in (c.get("riscos_revisao_local") or []):
            partes.append(f"Risco para revisão local: {r}")
        return " ".join(str(p) for p in partes)


def _transporte_http(url: str, headers: dict, corpo: bytes, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, data=corpo, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProvedorErro(f"falha de rede: {type(e).__name__}") from None


class DeepSeek(Provedor):
    nome = "deepseek"

    def __init__(self, chave: str | None = None, modelo: str | None = None, base_url: str = DEEPSEEK_BASE_URL,
                 transporte=None, timeout: float = 60.0, caminho_env: Path | None = None):
        self._chave = chave if chave is not None else ler_chave_env(caminho_env)
        self.modelo = modelo or os.environ.get("DEEPSEEK_MODEL") or DEEPSEEK_MODELO
        self.base_url = base_url.rstrip("/")
        self._transporte = transporte or _transporte_http
        self.timeout = timeout
        self.ultimo_uso: dict | None = None  # usage da ultima resposta (prompt/completion/total_tokens), p/ medir custo

    def gerar(self, sistema: str, usuario: str, max_tokens: int = 900) -> str:
        if not self._chave:
            raise ProvedorIndisponivel("DEEPSEEK_API_KEY não configurada (defina no .env ou no ambiente). "
                                       "Usando a explicação em template.")
        corpo = json.dumps({"model": self.modelo, "messages": [{"role": "system", "content": sistema},
                                                                {"role": "user", "content": usuario}],
                            "temperature": 0, "max_tokens": max_tokens, "stream": False,
                            "thinking": {"type": "disabled"}}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._chave}"}
        status, txt = self._transporte(self.base_url + "/chat/completions", headers, corpo, self.timeout)
        if status != 200:
            raise ProvedorErro(f"DeepSeek HTTP {status}: {ERROS_HTTP.get(status, 'erro desconhecido')}")
        try:
            dados = json.loads(txt)
            out = dados["choices"][0]["message"]["content"]
            u = dados.get("usage")
            self.ultimo_uso = {k: u.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")} \
                if isinstance(u, dict) else None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProvedorErro("resposta do DeepSeek em formato inesperado") from None
        if not isinstance(out, str) or not out.strip():
            raise ProvedorErro("resposta do DeepSeek vazia")
        return out


def obter(nome: str | None = None) -> Provedor:
    nome = (nome or os.environ.get("SULCO_LLM") or "stub").lower()
    if nome == "stub":
        return Stub()
    if nome == "deepseek":
        return DeepSeek()
    raise ValueError(f"provedor desconhecido: {nome}")
