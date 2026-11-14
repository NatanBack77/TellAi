"""Carrega e VALIDA data/culturas/fao_staging.csv (dados de cultura lidos de publicações FAO; área de preparo).

Este arquivo NÃO alimenta tabela_culturas.csv nem o motor de produção. Regras (cada linha de dado):
  - fonte e URL obrigatórias (URL http/https);
  - valor numérico e PRESENTE no trecho copiado (aceita '9.153' como 9153 e, havendo `conversao`, valor/1000 no trecho);
  - atributo conhecido, valor dentro de faixa física plausível;
  - linha de lacuna (atributo 'ciclo/kc/estagios/raiz/ky') não tem valor e traz o motivo em `observacao`.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "data/culturas/fao_staging.csv"
COLUNAS = ["cultura_id", "atributo", "valor", "unidade", "regiao_da_fonte", "fonte", "url", "pagina_tabela", "trecho",
           "mapeamento_fao", "conversao", "observacao"]
ATRIBUTO_LACUNA = "ciclo/kc/estagios/raiz/ky"
FAIXAS = {  # (mín, máx) plausíveis; fora disso a linha é rejeitada
    "estagio_ini_dias": (1, 400), "estagio_dev_dias": (1, 400), "estagio_mid_dias": (1, 400), "estagio_late_dias": (0, 400),
    "ciclo_dias_total": (30, 800),
    "kc_ini": (0.0, 1.5), "kc_mid": (0.0, 1.5), "kc_mid_min": (0.0, 1.5), "kc_mid_max": (0.0, 1.5),
    "kc_end": (0.0, 1.5), "kc_end_min": (0.0, 1.5), "kc_end_max": (0.0, 1.5),
    "altura_max_m": (0.05, 6), "profundidade_raiz_m_min": (0.1, 5), "profundidade_raiz_m_max": (0.1, 5),
    "fracao_deplecao_p": (0.05, 0.95), "ky_total": (0.2, 2.0),
    "demanda_hidrica_mm_ciclo_min": (100, 3000), "demanda_hidrica_mm_ciclo_max": (100, 3000),
    "n_fixado_kg_ha_min": (0, 500), "n_fixado_kg_ha_max": (0, 500),
    "palha_ms_kg_ha": (100, 40000), "palha_ms_kg_ha_min": (100, 40000), "palha_ms_kg_ha_max": (100, 40000),
    "n_acumulado_parte_aerea_kg_ha": (1, 1000),
}


class StagingInvalido(ValueError):
    pass


def _tokens_numericos(texto: str) -> set[float]:
    """Todos os números do trecho: '9.153' vira 9.153 E 9153 (ponto de milhar); '9-125' vira 9 e 125; ',' como decimal."""
    out: set[float] = set()
    for t in re.findall(r"\d+(?:[.,]\d+)*", texto):
        t2 = t.replace(",", ".")
        try:
            out.add(float(t2))
        except ValueError:
            pass
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", t):
            out.add(float(re.sub(r"[.,]", "", t)))
    return out


def valor_no_trecho(valor: float, trecho: str, conversao: str = "") -> bool:
    toks = _tokens_numericos(trecho)
    if any(abs(valor - t) < 1e-9 for t in toks):
        return True
    if conversao and any(abs(valor - t * 1000) < 1e-6 for t in toks):    # t/ha -> kg/ha (declarado em `conversao`)
        return True
    return False


def carregar_linhas(caminho: Path | str = CAMINHO_PADRAO) -> list[dict]:
    with open(caminho, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        faltam = [c for c in COLUNAS if c not in (r.fieldnames or [])]
        if faltam:
            raise StagingInvalido(f"colunas ausentes: {faltam}")
        return list(r)


def validar(linhas: list[dict]) -> list[str]:
    erros = []
    for i, l in enumerate(linhas, start=2):
        ref = f"linha {i} ({l.get('cultura_id')}/{l.get('atributo')})"
        if not l.get("cultura_id"):
            erros.append(f"{ref}: cultura_id vazio")
        if l["atributo"] == ATRIBUTO_LACUNA:
            if l["valor"] or not l["observacao"]:
                erros.append(f"{ref}: lacuna deve ter valor vazio e motivo em observacao")
            continue
        if l["atributo"] not in FAIXAS:
            erros.append(f"{ref}: atributo desconhecido")
            continue
        if not l["fonte"].strip():
            erros.append(f"{ref}: fonte obrigatória")
        if not re.match(r"^https?://\S+$", l["url"] or ""):
            erros.append(f"{ref}: URL obrigatória (http/https)")
        if not l["trecho"].strip() or not l["pagina_tabela"].strip():
            erros.append(f"{ref}: trecho e pagina_tabela obrigatórios")
        try:
            v = float(l["valor"])
        except ValueError:
            erros.append(f"{ref}: valor não numérico: {l['valor']!r}")
            continue
        lo, hi = FAIXAS[l["atributo"]]
        if not lo <= v <= hi:
            erros.append(f"{ref}: valor {v} fora da faixa plausível [{lo}, {hi}]")
        if l["trecho"].strip() and not valor_no_trecho(v, l["trecho"], l.get("conversao", "")):
            erros.append(f"{ref}: valor {l['valor']} não aparece no trecho")
    return erros


def carregar(caminho: Path | str = CAMINHO_PADRAO, validar_antes: bool = True) -> list[dict]:
    linhas = carregar_linhas(caminho)
    if validar_antes:
        e = validar(linhas)
        if e:
            raise StagingInvalido("; ".join(e[:10]) + (f" (+{len(e) - 10})" if len(e) > 10 else ""))
    for l in linhas:
        if l["atributo"] != ATRIBUTO_LACUNA:
            l["valor"] = float(l["valor"])
    return linhas


def valores(linhas: list[dict], cultura_id: str, atributo: str) -> list[float]:
    return [l["valor"] for l in linhas if l["cultura_id"] == cultura_id and l["atributo"] == atributo]


def culturas_sem_dado(linhas: list[dict]) -> dict[str, str]:
    return {l["cultura_id"]: l["observacao"] for l in linhas if l["atributo"] == ATRIBUTO_LACUNA}


def main() -> int:
    linhas = carregar_linhas()
    e = validar(linhas)
    print(f"{len(linhas)} linhas; {len(e)} erro(s)")
    for x in e:
        print(" -", x)
    return 1 if e else 0


if __name__ == "__main__":
    raise SystemExit(main())
