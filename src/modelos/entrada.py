"""Carga de configuração e validação de entradas. Falta de dado => erro explícito."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parents[2]


class DadosInvalidos(Exception):
    """Arquivo ou coluna obrigatória ausente. Não inventar nem preencher em silêncio."""


def carregar_config(caminho: str | Path | None = None) -> dict:
    caminho = Path(caminho) if caminho else RAIZ / "config.yaml"
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ler(caminho: Path, nome: str, obrigatorias: list[str]) -> pd.DataFrame:
    if not caminho.exists():
        raise DadosInvalidos(f"Arquivo ausente para '{nome}': {caminho}")
    df = pd.read_parquet(caminho)
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        raise DadosInvalidos(f"'{nome}' sem colunas obrigatórias: {faltando}")
    df["data"] = pd.to_datetime(df["data"])
    return df


def carregar_entradas(cfg: dict, base: str | Path | None = None, atual: bool = False) -> dict[str, pd.DataFrame | None]:
    """Lê clima e NDVI (obrigatórios) e umidade do solo (opcional).

    `atual=True` lê `clima_atual`/`ndvi_atual` (original + 2025plus, ver `src/coleta/unir_2025.py`): SÓ para inferência.
    Treino, validação e métricas usam sempre `atual=False` (arquivos originais, até 2024)."""
    base = Path(base) if base else RAIZ
    cols = cfg["colunas_obrigatorias"]
    cam = cfg["caminhos"]
    saida: dict[str, pd.DataFrame | None] = {
        "clima": _ler(base / cam["clima_atual" if atual else "clima"], "clima", cols["clima"]),
        "ndvi": _ler(base / cam["ndvi_atual" if atual else "ndvi"], "ndvi", cols["ndvi"]),
        "umidade_solo": None,
    }
    um = base / cam["umidade_solo"]
    if um.exists():
        saida["umidade_solo"] = _ler(um, "umidade_solo", cols["umidade_solo"])
    return saida
