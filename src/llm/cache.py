"""Cache em disco por hash (entrada -> saida bruta do modelo) para o demo offline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_PADRAO = RAIZ / "data" / "processed" / "llm_cache"


def chave(provedor: str, modelo: str, versao: str, sistema: str, usuario: str) -> str:
    return hashlib.sha256(json.dumps([provedor, modelo, versao, sistema, usuario], ensure_ascii=False).encode()).hexdigest()


class Cache:
    def __init__(self, pasta: Path | None = None):
        self.pasta = Path(pasta) if pasta else PASTA_PADRAO

    def ler(self, k: str) -> str | None:
        try:
            return json.loads((self.pasta / f"{k}.json").read_text(encoding="utf-8"))["saida"]
        except (OSError, ValueError, KeyError):
            return None

    def gravar(self, k: str, saida: str, meta: dict) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / f"{k}.json").write_text(json.dumps({"meta": meta, "saida": saida}, ensure_ascii=False), encoding="utf-8")
