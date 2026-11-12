"""Leitura e VALIDAÇÃO da tabela de culturas (data/culturas/tabela_culturas.csv).

Formato longo: uma linha por (cultura, atributo). Cada valor tem fonte, URL, página e trecho.
O validador falha se um valor 'verificado' não tiver fonte+URL+página+trecho, ou se o número
não aparecer no trecho citado. Valor ausente é 'lacuna' (com motivo), nunca estimado.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "data" / "culturas" / "tabela_culturas.csv"

COLUNAS = ["cultura_id", "cultura_pt", "nome_cientifico", "ecoport_code", "atributo", "valor", "unidade",
           "status", "fonte", "url", "pagina", "trecho", "contexto", "data_consulta"]

ATRIBUTOS_NUMERICOS = [
    "temp_min_abs_c", "temp_otima_min_c", "temp_otima_max_c", "temp_max_abs_c",
    "chuva_min_abs_mm", "chuva_otima_min_mm", "chuva_otima_max_mm", "chuva_max_abs_mm",
    "ciclo_min_dias", "ciclo_max_dias",
    "palha_ms_kg_ha", "n_acumulado_parte_aerea_kg_ha", "n_fixado_kg_ha", "demanda_hidrica_mm_ciclo",
]
ATRIBUTOS_TEXTO = ["familia_botanica"]
ATRIBUTOS = ATRIBUTOS_NUMERICOS + ATRIBUTOS_TEXTO


class TabelaInvalida(ValueError):
    """Tabela de culturas com valor sem fonte ou inconsistente."""


def carregar_linhas(caminho: Path | str = CAMINHO_PADRAO) -> list[dict]:
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def validar(linhas: list[dict]) -> list[str]:
    """Devolve a lista de erros (vazia = tabela válida)."""
    erros: list[str] = []
    vistos: set[tuple[str, str]] = set()
    culturas: dict[str, set[str]] = {}
    for i, r in enumerate(linhas, start=2):  # linha 1 = cabeçalho
        loc = f"linha {i} ({r.get('cultura_id')}/{r.get('atributo')})"
        chave = (r.get("cultura_id", ""), r.get("atributo", ""))
        if chave in vistos:
            erros.append(f"{loc}: duplicada")
        vistos.add(chave)
        culturas.setdefault(chave[0], set()).add(chave[1])
        if r.get("atributo") not in ATRIBUTOS:
            erros.append(f"{loc}: atributo desconhecido")
        st = r.get("status")
        if st == "lacuna":
            if (r.get("valor") or "").strip():
                erros.append(f"{loc}: lacuna não pode ter valor")
            if not (r.get("contexto") or "").strip():
                erros.append(f"{loc}: lacuna sem motivo em 'contexto'")
        elif st == "verificado":
            for c in ("valor", "unidade", "fonte", "url", "pagina", "trecho", "data_consulta"):
                if not (r.get(c) or "").strip():
                    erros.append(f"{loc}: verificado sem '{c}'")
            if not (r.get("url") or "").startswith("http"):
                erros.append(f"{loc}: url inválida")
            if r.get("atributo") in ATRIBUTOS_NUMERICOS and (r.get("valor") or "").strip():
                try:
                    float(r["valor"])
                except ValueError:
                    erros.append(f"{loc}: valor não numérico {r['valor']!r}")
                else:
                    if _digitos(r["valor"]) not in _digitos(r.get("trecho", "")):
                        erros.append(f"{loc}: valor {r['valor']} não aparece no trecho citado")
        else:
            erros.append(f"{loc}: status deve ser 'verificado' ou 'lacuna'")
    for cid, atrs in culturas.items():
        falta = set(ATRIBUTOS) - atrs
        if falta:
            erros.append(f"{cid}: atributos sem linha (nem lacuna): {sorted(falta)}")
    # coerência das faixas EcoCrop
    for cid in culturas:
        v = {r["atributo"]: float(r["valor"]) for r in linhas
             if r["cultura_id"] == cid and r["status"] == "verificado" and r["atributo"] in ATRIBUTOS_NUMERICOS}
        for ordem in (["temp_min_abs_c", "temp_otima_min_c", "temp_otima_max_c", "temp_max_abs_c"],
                      ["chuva_min_abs_mm", "chuva_otima_min_mm", "chuva_otima_max_mm", "chuva_max_abs_mm"]):
            if all(a in v for a in ordem):
                seq = [v[a] for a in ordem]
                if seq != sorted(seq):
                    erros.append(f"{cid}: faixa fora de ordem {ordem} = {seq}")
    return erros


def carregar(caminho: Path | str = CAMINHO_PADRAO, validar_antes: bool = True) -> dict[str, dict]:
    """Devolve {cultura_id: {cultura_pt, nome_cientifico, atributos: {atrib: {...}}}}. Lança TabelaInvalida."""
    linhas = carregar_linhas(caminho)
    if validar_antes:
        erros = validar(linhas)
        if erros:
            raise TabelaInvalida("; ".join(erros[:10]) + (f" (+{len(erros) - 10})" if len(erros) > 10 else ""))
    out: dict[str, dict] = {}
    for r in linhas:
        c = out.setdefault(r["cultura_id"], {"cultura_pt": r["cultura_pt"], "nome_cientifico": r["nome_cientifico"],
                                             "atributos": {}})
        if r["status"] == "verificado":
            val = float(r["valor"]) if r["atributo"] in ATRIBUTOS_NUMERICOS else r["valor"]
            c["atributos"][r["atributo"]] = {"valor": val, "unidade": r["unidade"], "fonte": r["fonte"],
                                             "url": r["url"], "pagina": r["pagina"], "trecho": r["trecho"],
                                             "contexto": r["contexto"]}
        else:
            c["atributos"][r["atributo"]] = None
    return out


def lacunas(tabela: dict[str, dict]) -> list[str]:
    return [f"{cid}: {a}" for cid, c in tabela.items() for a, v in c["atributos"].items() if v is None]


def main() -> int:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else CAMINHO_PADRAO
    linhas = carregar_linhas(caminho)
    erros = validar(linhas)
    if erros:
        print(f"INVALIDA: {len(erros)} erro(s)")
        for e in erros:
            print(" -", e)
        return 1
    print(f"OK: {len(linhas)} linhas, {sum(r['status'] == 'lacuna' for r in linhas)} lacunas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
