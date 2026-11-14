"""Adiciona a coluna `nome` (nome oficial com acento) a data/processed/pontos.csv, SEM alterar as outras colunas (D4).

Fonte: API pública do IBGE, localidades v1, UF 23 (Ceará): https://servicodados.ibge.gov.br/api/v1/localidades/estados/23/municipios
Regra: o nome oficial só é usado quando o ponto tem código `ibge` do Ceará (23xxxxx) que existe na API E o nome oficial, sem acento,
bate com o id do ponto (confere código x id). Qualquer outra situação (fora do CE, sem código, código ausente da API, nome que não bate)
mantém o nome derivado do id (sem acento) e é listada no relatório impresso. Nada é inventado.
Uso: python -m src.coleta.nomes_ibge [--dry-run]
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.coleta.ibge_codigos import _get, slug

RAIZ = Path(__file__).resolve().parents[2]
PONTOS = RAIZ / "data" / "processed" / "pontos.csv"
UF_CE = 23
URL_MUN = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
_MIUDAS = {"do", "da", "de", "dos", "das"}


def nome_derivado(ponto_id: str) -> str:
    """Nome derivado do identificador (sem acentos), ex.: varzea_alegre_ce -> 'Varzea Alegre (CE)'."""
    base, uf = ponto_id.rsplit("_", 1)
    palavras = [p if p in _MIUDAS else p.capitalize() for p in base.split("_")]
    return " ".join(palavras) + f" ({uf.upper()})"


def atribuir_nomes(pontos: pd.DataFrame, municipios_ce: dict[int, str]) -> tuple[pd.Series, list[str]]:
    """Devolve (coluna `nome`, avisos). `municipios_ce`: {código IBGE de 7 dígitos: nome oficial}."""
    nomes, avisos = [], []
    for _, r in pontos.iterrows():
        pid = r["ponto_id"]
        padrao = nome_derivado(pid)
        cod = r.get("ibge")
        if cod is None or pd.isna(cod) or str(cod).strip() == "":
            nomes.append(padrao)
            avisos.append(f"{pid}: sem código IBGE, mantém o nome derivado")
            continue
        cod = int(float(cod))
        if cod // 100000 != UF_CE:
            nomes.append(padrao)                      # fora do CE: a API consultada é só da UF 23
            continue
        oficial = municipios_ce.get(cod)
        if oficial is None:
            nomes.append(padrao)
            avisos.append(f"{pid}: código {cod} não existe na API do CE, mantém o nome derivado")
        elif slug(oficial) != pid.rsplit("_", 1)[0]:
            nomes.append(padrao)
            avisos.append(f"{pid}: código {cod} é '{oficial}' na API (nome não bate com o id), mantém o nome derivado")
        else:
            nomes.append(f"{oficial} ({pid.rsplit('_', 1)[1].upper()})")
    return pd.Series(nomes, index=pontos.index, name="nome"), avisos


def baixar_municipios_ce() -> dict[int, str]:
    return {int(m["id"]): m["nome"] for m in _get(URL_MUN.format(uf=UF_CE))}


def main(dry: bool = False, destino: Path = PONTOS) -> int:
    pontos = pd.read_csv(destino, dtype=str)         # tudo como texto: nenhuma coluna existente é reformatada
    nomes, avisos = atribuir_nomes(pontos.drop(columns=["nome"], errors="ignore"), baixar_municipios_ce())
    oficiais = int((nomes != pontos["ponto_id"].map(nome_derivado)).sum())
    print(f"{len(pontos)} pontos; {oficiais} com nome oficial diferente do derivado (acento); {len(pontos) - oficiais} iguais ao derivado")
    for a in avisos:
        print(" ", a)
    if not dry:
        out = pontos.drop(columns=["nome"], errors="ignore").copy()
        out["nome"] = nomes
        out.to_csv(destino, index=False)
        print("gravado", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
