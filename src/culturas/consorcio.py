"""Consórcio com respaldo publicado (LER / UET): EVIDÊNCIA na alternativa, nunca nota nem previsão.

Fonte única: data/culturas/ler_staging.csv (STAGING; montado por experimentos/ler/construir_staging.py a partir de artigos abertos).
O staging NÃO alimenta as notas do motor. Este módulo só responde: "este par de culturas já foi estudado em consórcio no semiárido do
Nordeste, com que LER observado, em quantos experimentos, e de onde veio?".

O que um LER publicado É e NÃO é (docs/29_LER_CONSORCIO.md):
- É o resultado de UM experimento (local, ano, arranjo, densidade e cultivares do autor). Faixa de LER entre estudos NÃO é intervalo de
  confiança nem expectativa para o terreno do agricultor.
- NÃO é produtividade, NÃO prevê ganho, NÃO mede tempo de ocupação da terra (ver ATER), preço, mão de obra nem risco de quebra.
- Ausência de estudo no staging é LACUNA, não é "consórcio ruim". Nada aqui rebaixa uma alternativa.

Entram na faixa (coluna `entra_na_faixa` = 'sim'): experimento com testemunha pareada, sequeiro, semiárido (ou 'provável' declarado), 2 culturas,
LER legível. Ficam fora e aparecem em `fora_da_faixa` (com o motivo): irrigado, resumo sem número lido, citação secundária, levantamento de
agricultor sem testemunha, local não confirmado como semiárido, valor suspeito.

Pares são sem ordem: consorcios_para("milho", "feijao_caupi") == consorcios_para("feijao_caupi", "milho").
"""
from __future__ import annotations

import csv
import statistics
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_PADRAO = RAIZ / "data/culturas/ler_staging.csv"
SEMIARIDO_OK = ("sim", "provavel")

LEITURA = ("Consórcio estudado no semiárido do Nordeste; LER observado em experimentos de outros locais e anos. Não é do seu terreno, "
           "não prevê ganho e não mede tempo de ocupação da terra, preço nem risco. Ausência de estudo é lacuna, não é sinal ruim.")


def _num(v: str) -> float | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


@lru_cache(maxsize=4)
def _linhas(caminho: str) -> tuple[dict, ...]:
    p = Path(caminho)
    if not p.exists():
        return ()
    with open(p, newline="", encoding="utf-8") as f:
        return tuple(csv.DictReader(f))


def carregar(caminho: Path | str | None = None) -> list[dict]:
    """Linhas do staging (dicts de texto). Arquivo ausente = lista vazia (lacuna, nunca erro silencioso de número)."""
    return list(_linhas(str(caminho or CAMINHO_PADRAO)))


def _par(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def _linhas_do_par(a: str, b: str, caminho) -> list[dict]:
    alvo = _par(a, b)
    return [r for r in carregar(caminho) if r.get("par_a") and r.get("par_b") and _par(r["par_a"], r["par_b"]) == alvo]


def _motivo_fora(r: dict) -> str:
    m = []
    if r.get("tipo_evidencia") != "experimento_pareado":
        m.append(f"tipo de evidência '{r.get('tipo_evidencia')}'")
    if r.get("semiarido") not in SEMIARIDO_OK:
        m.append(f"semiárido '{r.get('semiarido')}'")
    if "sequeiro" not in (r.get("regime") or ""):
        m.append(f"regime '{r.get('regime')}'")
    if _num(r.get("ler_min")) is None or _num(r.get("ler_max")) is None:
        m.append("sem valor de LER lido")
    if r.get("conferencia"):
        m.append(f"conferência: {r['conferencia']}")
    return "; ".join(m) or r.get("observacao", "")


def consorcios_para(cultura_a: str, cultura_b: str, caminho: Path | str | None = None) -> list[dict]:
    """Estudos que ENTRAM na faixa para o par (um dict por estudo), ordenados por id do estudo. Lista vazia = sem estudo no staging.

    Cada item: id_estudo, par, ler_min, ler_mediana, ler_max (sobre os arranjos desse estudo; mediana sobre os extremos publicados),
    n_arranjos, n_estudos_par (total do par), local, uf, anos, regime, fonte, url, pagina, arranjos[], avisos[].
    """
    linhas = [r for r in _linhas_do_par(cultura_a, cultura_b, caminho) if r.get("entra_na_faixa") == "sim"
              and r.get("semiarido") in SEMIARIDO_OK and _num(r.get("ler_min")) is not None and _num(r.get("ler_max")) is not None]
    por_estudo: dict[str, list[dict]] = {}
    for r in linhas:
        por_estudo.setdefault(r["id_estudo"], []).append(r)
    out = []
    for ide in sorted(por_estudo):
        rs = por_estudo[ide]
        vals = []
        for r in rs:
            lo, hi = _num(r["ler_min"]), _num(r["ler_max"])
            vals += [lo] if lo == hi else [lo, hi]
        r0 = rs[0]
        avisos = [LEITURA]
        if r0.get("semiarido") == "provavel":
            avisos.append("Local provavelmente semiárido (a introdução do estudo fala em região semiárida), mas o enquadramento oficial não foi conferido.")
        if len(rs) == 1:
            avisos.append("Um único arranjo medido neste estudo.")
        if min(vals) < 1.0:
            avisos.append("Houve arranjo com LER abaixo de 1 neste estudo: o consórcio rendeu MENOS área do que o plantio separado.")
        out.append({
            "id_estudo": ide, "par": list(_par(cultura_a, cultura_b)), "ler_min": round(min(vals), 2), "ler_mediana": round(statistics.median(vals), 2),
            "ler_max": round(max(vals), 2), "n_arranjos": len(rs), "n_estudos_par": len(por_estudo), "local": f"{r0['local']} ({r0['uf']})",
            "anos": r0["anos"], "regime": r0["regime"], "fonte": r0["fonte"], "url": r0["url_aberta"], "pagina": r0["pagina_tabela"],
            "arranjos": [r["arranjo"] for r in rs], "avisos": avisos})
    return out


def fora_da_faixa(cultura_a: str, cultura_b: str, caminho: Path | str | None = None) -> list[dict]:
    """Linhas do par que NÃO entraram (com o motivo). Transparência: mostrar o que foi lido e descartado."""
    ok = {(r["id_linha"]) for r in _linhas_do_par(cultura_a, cultura_b, caminho) if r.get("entra_na_faixa") == "sim"}
    return [{"id_linha": r["id_linha"], "id_estudo": r["id_estudo"], "arranjo": r["arranjo"], "ler_min": r["ler_min"], "ler_max": r["ler_max"],
             "motivo": _motivo_fora(r) or r.get("observacao", ""), "fonte": r["fonte"], "url": r["url_aberta"]}
            for r in _linhas_do_par(cultura_a, cultura_b, caminho) if r["id_linha"] not in ok]


def resumo_par(cultura_a: str, cultura_b: str, caminho: Path | str | None = None) -> dict | None:
    """Rótulo do par ('consórcio estudado no semiárido, LER observado X-Y em N experimentos, não é do seu terreno') ou None se não há estudo."""
    est = consorcios_para(cultura_a, cultura_b, caminho)
    if not est:
        return None
    vals = []
    for e in est:
        vals += [e["ler_min"], e["ler_max"]]
    lo, hi, n = min(vals), max(vals), len(est)
    faixa = f"{lo:.2f}".replace(".", ",") + (f" a {hi:.2f}".replace(".", ",") if hi != lo else "")
    rotulo = (f"Consórcio estudado no semiárido do Nordeste: LER observado {faixa} em {n} experimento{'s' if n > 1 else ''}; "
              "não é do seu terreno e não prevê ganho.")
    return {"par": list(_par(cultura_a, cultura_b)), "ler_min": lo, "ler_max": hi, "n_estudos": n, "n_arranjos": sum(e["n_arranjos"] for e in est),
            "rotulo": rotulo, "estudos": [{k: e[k] for k in ("id_estudo", "local", "anos", "ler_min", "ler_max", "fonte", "url", "pagina")} for e in est],
            "avisos": [LEITURA] + ([f"Há arranjos com LER abaixo de 1 em {sum(1 for e in est if e['ler_min'] < 1.0)} dos {n} estudo(s)."]
                                   if any(e["ler_min"] < 1.0 for e in est) else []),
            "leitura": LEITURA}


def tem_respaldo(cultura_a: str, cultura_b: str, caminho: Path | str | None = None) -> bool:
    """True se o par tem ao menos um estudo na faixa. False = SEM ESTUDO NO STAGING (lacuna), não 'consórcio ruim'."""
    return bool(consorcios_para(cultura_a, cultura_b, caminho))


def criterio_secundario(atual: str, ids: list[str], caminho: Path | str | None = None) -> dict[str, float]:
    """Critério OPCIONAL para desempate: 1.0 se (atual, id) tem respaldo; 0.0 se não tem estudo. Uso restrito a EMPATES; não entra em score,
    pesos nem Monte Carlo. 0.0 aqui é 'sem estudo', e NÃO significa que o consórcio seja ruim."""
    return {i: (1.0 if tem_respaldo(atual, i, caminho) else 0.0) for i in ids if i != atual}


def pares_com_respaldo(caminho: Path | str | None = None) -> list[tuple[str, str]]:
    """Pares (ordenados) com ao menos um estudo na faixa."""
    vistos = {_par(r["par_a"], r["par_b"]) for r in carregar(caminho) if r.get("par_a") and r.get("par_b")}
    return sorted(p for p in vistos if tem_respaldo(*p, caminho=caminho))


def anexar(cenarios: list[dict], modo: str, caminho: Path | str | None = None) -> None:
    """Acrescenta `consorcio` a cada cenário de alternativa (rotacao = [atual, c], c != atual), IN PLACE. modo: 'rotulo' ou 'desempate'.

    Não altera score, faixa_incerteza, critérios nem `empate_tecnico`. Sem estudo -> entrada em `lacunas` (nunca nota baixa).
    """
    if modo not in ("rotulo", "desempate"):
        raise ValueError("modo deve ser 'rotulo' ou 'desempate'")
    alts = [c for c in cenarios if len(c.get("rotacao") or []) == 2 and c["rotacao"][0] != c["rotacao"][1]]
    resp = {c["rotacao"][1]: tem_respaldo(c["rotacao"][0], c["rotacao"][1], caminho) for c in alts}
    for c in alts:
        a, b = c["rotacao"]
        res = resumo_par(a, b, caminho)
        bloco = {"modo": modo, "respaldo": res, "lacuna": None, "leitura": LEITURA}
        fora = fora_da_faixa(a, b, caminho)
        if fora:
            bloco["lidos_e_fora_da_faixa"] = [{k: f[k] for k in ("id_estudo", "arranjo", "ler_min", "ler_max", "motivo")} for f in fora]
        if res is None:
            bloco["lacuna"] = f"Sem estudo de consórcio {a} + {b} (semiárido do Nordeste) no acervo lido: lacuna, não é sinal de que o consórcio seja ruim."
            c.setdefault("lacunas", []).append(bloco["lacuna"])
        if modo == "desempate":
            bloco["desempate"] = {
                "criterio": "consórcio com respaldo publicado (1) ou sem estudo no acervo (0)", "este_tem_respaldo": resp[b],
                "alternativas_com_respaldo": sorted(k for k, v in resp.items() if v), "alternativas_sem_estudo": sorted(k for k, v in resp.items() if not v),
                "separa_as_alternativas": len(set(resp.values())) > 1,
                "leitura": "Só desempata a ESCOLHA quando as alternativas empatam exatamente em P(top-N) e posição média; não altera nota nem o empate técnico. "
                           "Ter estudo de consórcio não torna a alternativa melhor, e não ter é lacuna."}
        c["consorcio"] = bloco
