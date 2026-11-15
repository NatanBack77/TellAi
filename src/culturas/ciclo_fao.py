"""Ciclo de referência da FAO-56 (Allen et al. 1998, cap. 6, Tabela 11) lido de data/culturas/fao_staging.csv.

Uso no motor (decisão do usuário 2026-11-14, `Parametros.ciclo_fonte="fao"`): as 11 culturas que a FAO cobre usam a duração
da Tabela 11; as 5 sem dado FAO (guandu, palma, crotalária juncea, feijão-de-porco, mucuna) mantêm o ciclo do EcoCrop.
O ciclo FAO é de OUTRAS REGIÕES (Califórnia, Mediterrâneo, Nigéria, Índia...): nenhuma linha é do semiárido brasileiro.

REGRA ÚNICA de escolha da linha (fixada antes de olhar qualquer ranking; só usa o RÓTULO de região impresso pela FAO):
  1. Mandioca: só a linha do "ano 1" (210 d); o "ano 2" é cultivo de 2 anos e não entra (decisão declarada).
  2. Se alguma linha da cultura tem no rótulo da região a palavra "arid" (a FAO escreve "Arid Climate", "Arid Region",
     "(Semi) Arid Climates"), vale essa linha (a mais próxima do semiárido segundo a própria classificação da FAO).
     Havendo mais de uma, a mediana inferior entre elas.
  3. Sem rótulo árido: mediana inferior das linhas ordenadas pela soma dos 4 estágios (empate: ordem do rótulo).
     Com uma só linha, é essa.
A duração é a SOMA dos 4 estágios (ini+dev+mid+late); a FAO imprime também um "Total" que em 3 culturas difere da soma
(sorgo, caupi, gergelim); o aviso mostra os dois quando divergem. A faixa mín–máx das linhas (mesmo filtro da regra 1) vai
sempre no aviso; é ela que `ciclo_modo` 'min'/'max' usa nas culturas FAO.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from . import fao_staging as fs

EST = ("estagio_ini_dias", "estagio_dev_dias", "estagio_mid_dias", "estagio_late_dias")
REGRA_TEXTO = ("linha da Tabela 11 do FAO-56 escolhida por regra única: (1) mandioca só ano 1; (2) se a FAO rotula alguma linha "
               "da cultura como 'Arid', vale ela; (3) senão, mediana inferior das linhas pela soma dos 4 estágios. "
               "Duração = soma dos 4 estágios.")


def _grupos(linhas: list[dict]) -> dict[str, list[dict]]:
    g: dict = defaultdict(dict)
    meta: dict = {}
    for l in linhas:
        if l["atributo"] in EST + ("ciclo_dias_total",):
            k = (l["cultura_id"], l["pagina_tabela"])
            g[k][l["atributo"]] = l["valor"]
            meta[k] = {"regiao": l["regiao_da_fonte"], "pagina": l["pagina_tabela"], "url": l["url"], "fonte": l["fonte"],
                       "trecho": l["trecho"] if l["atributo"] == "ciclo_dias_total" else meta.get(k, {}).get("trecho", l["trecho"])}
    out: dict[str, list[dict]] = defaultdict(list)
    for (cid, tag), d in g.items():
        faltam = [a for a in EST if a not in d]
        if faltam:
            raise fs.StagingInvalido(f"{cid} / {tag}: estágios ausentes {faltam}")
        est = [int(d[a]) for a in EST]
        out[cid].append({**meta[(cid, tag)], "estagios": est, "soma": sum(est),
                         "total_impresso": int(d["ciclo_dias_total"]) if "ciclo_dias_total" in d else None})
    for cid in out:
        out[cid].sort(key=lambda r: (r["soma"], r["pagina"]))
    return dict(out)


def escolher_linha(cid: str, linhas: list[dict]) -> tuple[dict, str, list[dict]]:
    """(linha escolhida, regra aplicada, linhas consideradas) conforme a REGRA ÚNICA do módulo."""
    if cid == "mandioca":
        linhas = [r for r in linhas if "year 1" in r["pagina"]]
    if not linhas:
        raise fs.StagingInvalido(f"{cid}: sem linha da Tabela 11")
    aridas = [r for r in linhas if "arid" in r["regiao"].lower()]
    if aridas:
        return aridas[(len(aridas) - 1) // 2], "rotulo_arido", linhas
    if len(linhas) == 1:
        return linhas[0], "linha_unica", linhas
    return linhas[(len(linhas) - 1) // 2], "mediana_inferior", linhas


@lru_cache(maxsize=4)
def _ciclos(caminho: str) -> dict:
    lin = fs.carregar(caminho)                  # valida: fonte, URL, trecho e valor no trecho
    out = {}
    for cid, rows in _grupos(lin).items():
        r, regra, cons = escolher_linha(cid, rows)
        somas = [x["soma"] for x in cons]
        out[cid] = {"dias": r["soma"], "dias_min": min(somas), "dias_max": max(somas), "n_linhas": len(cons), "regra": regra,
                    "regiao": r["regiao"], "pagina": r["pagina"], "url": r["url"], "fonte": r["fonte"], "trecho": r["trecho"],
                    "estagios": r["estagios"], "total_impresso": r["total_impresso"],
                    "soma_confere_total": r["total_impresso"] == r["soma"],
                    "linhas": [{"regiao": x["regiao"], "soma": x["soma"]} for x in cons]}
    return out


def ciclos_fao(caminho: Path | str = fs.CAMINHO_PADRAO) -> dict[str, dict]:
    """{cultura_id: info do ciclo FAO} das culturas com Tabela 11 (as demais ficam ausentes: lacuna declarada)."""
    return _ciclos(str(caminho))


def sem_fao(caminho: Path | str = fs.CAMINHO_PADRAO) -> list[str]:
    return sorted(c for c in fs.culturas_sem_dado(fs.carregar_linhas(caminho)) if c not in ciclos_fao(caminho))


def dias_por_modo(info: dict, modo: str) -> int:
    """'medio' = linha escolhida pela regra; 'min'/'max' = menor/maior soma entre as linhas consideradas."""
    return {"medio": info["dias"], "min": info["dias_min"], "max": info["dias_max"]}[modo]


def aviso_fao(info: dict, cultura_pt: str, ecocrop: tuple[float, float] | None = None) -> str:
    """Texto do aviso 'ciclo de referência de outras regiões' (vai em `lacunas` e `suposicoes` do cenário)."""
    t = (f"Ciclo de {cultura_pt}: {info['dias']} dias = soma dos estágios da Tabela 11 do FAO-56, linha '{info['regiao']}' "
         f"({info['n_linhas']} linha(s) na tabela, {info['dias_min']}–{info['dias_max']} dias; regra: {info['regra']}). "
         "É ciclo de referência de outras regiões, NÃO medido no semiárido brasileiro; a cultivar local pode diferir.")
    if not info["soma_confere_total"] and info["total_impresso"] is not None:
        t += f" A FAO imprime total {info['total_impresso']} d, diferente da soma dos estágios ({info['dias']} d); usada a soma."
    if ecocrop and not (ecocrop[0] <= info["dias"] <= ecocrop[1]):
        t += f" Fora do intervalo do EcoCrop ({ecocrop[0]:.0f}–{ecocrop[1]:.0f} d)."
    return t


def aviso_ecocrop(cultura_pt: str, dias: int, lo: float, hi: float, motivo: str) -> str:
    return (f"Ciclo de {cultura_pt}: {dias} dias ({motivo}; intervalo EcoCrop {lo:.0f}–{hi:.0f} d). "
            "Não é medido no semiárido; a cultivar local pode diferir.")
