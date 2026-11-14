"""Carrega o `.env` da raiz para `os.environ`, SO com prefixos permitidos.

Permitidos: SULCO_*, DEEPSEEK_*, API_*, APP_*. Qualquer outra chave (EARTHDATA_*, etc.) e ignorada.
Nunca sobrescreve variavel ja definida; ignora comentarios (linha e fim de linha), linhas invalidas e valores vazios.
Nunca imprime nem devolve valores: `carregar_env()` devolve so os NOMES carregados.
`SULCO_CARREGAR_ENV=0` (no ambiente) desliga (usado na suite de testes).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PREFIXOS = ("SULCO_", "DEEPSEEK_", "API_", "APP_")
_LINHA = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def _valor(bruto: str) -> str:
    v = bruto.strip()
    if v[:1] in ("'", '"'):
        fim = v.find(v[0], 1)
        if fim != -1:
            return v[1:fim]            # entre aspas: '#' dentro das aspas faz parte do valor
        return v[1:].strip()           # aspa sem fechamento: tolera
    m = re.search(r"\s#", v)           # comentario no fim da linha (precisa de espaco antes do '#')
    if m:
        v = v[:m.start()]
    return v.strip()


def carregar_env(caminho: Path | str | None = None, prefixos: tuple[str, ...] = PREFIXOS) -> list[str]:
    if os.environ.get("SULCO_CARREGAR_ENV", "1") == "0":
        return []
    p = Path(caminho) if caminho else RAIZ / ".env"
    try:
        linhas = p.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    carregadas: list[str] = []
    for ln in linhas:
        if ln.lstrip().startswith("#"):
            continue
        m = _LINHA.match(ln)
        if not m:
            continue
        chave, val = m.group(1), _valor(m.group(2))
        if not chave.startswith(prefixos) or not val or os.environ.get(chave):
            continue
        os.environ[chave] = val
        carregadas.append(chave)
    return carregadas
