"""'O que separa as alternativas': comparação par a par por dominância de Pareto, só nos critérios COM DADO nos dois lados.

Função pura (sem sorteio, sem I/O): mesma entrada, mesma saída, qualquer ordem de entrada. Notas: maior é melhor (as notas de `rotacao.py` e do
motor já vêm orientadas assim; água é 1 - demanda). Critério em lacuna (None, NaN ou {'lacuna': True}) nunca vira vantagem nem desvantagem: se
falta em um lado, o critério não é comparado e aparece em `lacuna_em_um`; se falta nos dois, aparece em `lacuna_nos_dois`.

Dominância: A domina B se, nos critérios com dado nos dois, A >= B em todos e A > B em ao menos um (diferença <= `tol` conta como empate).
Sem critério em comum com dado: relação `sem_criterio_comum` (nada a dizer). Dominar NÃO é provar que A é melhor na roça: é só que, nos critérios
medidos, B não ganha de A em nenhum. Pesos não entram.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

TOL_PADRAO = 1e-9
REL = ("a_domina", "b_domina", "empate_total", "sem_dominancia", "sem_criterio_comum")


def _nota(v: Any) -> float | None:
    """Nota numérica ou None (lacuna). Aceita número, ou dict com 'nota_media'/'nota' (formatos de rotacao.py e do motor)."""
    if isinstance(v, dict):
        if v.get("lacuna"):
            return None
        v = v.get("nota_media", v.get("nota"))
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def _notas(alt: dict, criterios: list[str]) -> dict[str, float | None]:
    c = alt.get("criterios") or {}
    return {k: _nota(c.get(k)) for k in criterios}


def _id(alt: dict) -> str:
    if alt.get("id") is not None:
        return str(alt["id"])
    seq = alt.get("sequencia") or alt.get("rotacao")
    if seq:
        return " > ".join(seq)
    raise ValueError("alternativa sem 'id', 'sequencia' ou 'rotacao'")


def comparar_par(a: dict[str, float | None], b: dict[str, float | None], criterios: list[str], tol: float = TOL_PADRAO) -> dict:
    """Compara duas alternativas já reduzidas a {critério: nota|None}. Listas de critérios saem em ordem alfabética."""
    a_melhor, b_melhor, empatam, lac2, lac_a, lac_b = [], [], [], [], [], []
    for k in sorted(criterios):
        x, y = a.get(k), b.get(k)
        if x is None and y is None:
            lac2.append(k)
        elif x is None:
            lac_a.append(k)
        elif y is None:
            lac_b.append(k)
        elif x - y > tol:
            a_melhor.append(k)
        elif y - x > tol:
            b_melhor.append(k)
        else:
            empatam.append(k)
    if not (a_melhor or b_melhor or empatam):
        rel = "sem_criterio_comum"
    elif a_melhor and not b_melhor:
        rel = "a_domina"
    elif b_melhor and not a_melhor:
        rel = "b_domina"
    elif not a_melhor and not b_melhor:
        rel = "empate_total"
    else:
        rel = "sem_dominancia"
    return {"relacao": rel, "a_melhor_em": a_melhor, "b_melhor_em": b_melhor, "empatam_em": empatam,
            "lacuna_nos_dois": lac2, "lacuna_so_em_a": lac_a, "lacuna_so_em_b": lac_b,
            "comparacao_incompleta": bool(lac_a or lac_b)}   # há critério com dado num lado só: a dominância vale só para os comparados


def _frases(ra: str, rb: str, p: dict, nome: dict[str, str]) -> list[str]:
    """Frases curtas e literais; sem adjetivo de venda. `nome` traduz id de critério para rótulo."""
    n = lambda ks: ", ".join(nome.get(k, k) for k in ks)
    f = []
    rel = p["relacao"]
    if rel == "a_domina":
        f.append(f"{ra} é melhor ou igual a {rb} em todos os critérios comparáveis e melhor em: {n(p['a_melhor_em'])}.")
    elif rel == "b_domina":
        f.append(f"{rb} é melhor ou igual a {ra} em todos os critérios comparáveis e melhor em: {n(p['b_melhor_em'])}.")
    elif rel == "empate_total":
        f.append(f"{ra} e {rb} empatam em todos os critérios comparáveis: {n(p['empatam_em'])}.")
    elif rel == "sem_dominancia":
        f.append(f"{ra} é melhor em: {n(p['a_melhor_em'])}. {rb} é melhor em: {n(p['b_melhor_em'])}. Nenhuma das duas domina a outra.")
    else:
        f.append(f"{ra} e {rb} não têm critério com dado nos dois; não dá para comparar.")
    if rel in ("a_domina", "b_domina", "sem_dominancia") and p["empatam_em"]:
        f.append(f"Empatam em: {n(p['empatam_em'])}.")
    if p["lacuna_nos_dois"]:
        f.append(f"Sem dado nas duas: {n(p['lacuna_nos_dois'])}.")
    if p["lacuna_so_em_a"]:
        f.append(f"Sem dado só em {ra} (não comparado): {n(p['lacuna_so_em_a'])}.")
    if p["lacuna_so_em_b"]:
        f.append(f"Sem dado só em {rb} (não comparado): {n(p['lacuna_so_em_b'])}.")
    if p["comparacao_incompleta"] and rel in ("a_domina", "b_domina"):
        f.append("A comparação vale só para os critérios com dado nos dois; os demais podem mudar o quadro.")
    return f


def separar_alternativas(alternativas: list[dict], criterios: list[str] | None = None, rotulos: dict[str, str] | None = None,
                         tol: float = TOL_PADRAO) -> dict:
    """Estrutura pronta para a tela.

    `alternativas`: lista de dicts com 'id' (ou 'sequencia'/'rotacao') e 'criterios' {nome: nota | {'nota_media'|'nota', 'lacuna'}}.
    `criterios`: quais comparar (padrão: união dos criterios das alternativas). `rotulos`: id do critério -> nome na tela.
    Saída (ordem canônica por id, não pela ordem de entrada):
      pares[]            {a, b, relacao, a_melhor_em, b_melhor_em, empatam_em, lacuna_nos_dois, lacuna_so_em_a, lacuna_so_em_b,
                         comparacao_incompleta, frases}
      posicao_pareto{id} {dominada_por: [ids], domina: [ids], na_fronteira: bool}
      fronteira[]        ids que nenhuma outra domina
      criterios_sem_dado_em_todas[]  critérios em lacuna em todas as alternativas
    """
    ids = [_id(a) for a in alternativas]
    if len(set(ids)) != len(ids):
        raise ValueError("ids de alternativas repetidos")
    crit = sorted(criterios) if criterios is not None else sorted({k for a in alternativas for k in (a.get("criterios") or {})})
    rot = rotulos or {}
    por_id = {i: _notas(a, crit) for i, a in zip(ids, alternativas)}
    ordem = sorted(ids)
    pares = []
    dom_por: dict[str, list[str]] = {i: [] for i in ordem}
    domina: dict[str, list[str]] = {i: [] for i in ordem}
    for ia in range(len(ordem)):
        for ib in range(ia + 1, len(ordem)):
            ra, rb = ordem[ia], ordem[ib]
            p = comparar_par(por_id[ra], por_id[rb], crit, tol)
            if p["relacao"] == "a_domina":
                dom_por[rb].append(ra); domina[ra].append(rb)
            elif p["relacao"] == "b_domina":
                dom_por[ra].append(rb); domina[rb].append(ra)
            pares.append({"a": ra, "b": rb, **p, "frases": _frases(ra, rb, p, rot)})
    pos = {i: {"dominada_por": dom_por[i], "domina": domina[i], "na_fronteira": not dom_por[i]} for i in ordem}
    return {"criterios": crit, "pares": pares, "posicao_pareto": pos, "fronteira": [i for i in ordem if not dom_por[i]],
            "criterios_sem_dado_em_todas": [k for k in crit if all(por_id[i][k] is None for i in ordem)],
            "leitura": "Dominância só nos critérios com dado nos dois lados. Lacuna não é nota e nunca conta a favor. Não usa pesos e não prova "
                       "que uma alternativa é melhor na roça."}


def de_estrategias(estrategias: Iterable[dict], rotulos: dict[str, str] | None = None) -> dict:
    """Atalho para a saída de `rotacao.gerar_rotacoes()['estrategias']` (critérios em `nota_media`/`lacuna`)."""
    return separar_alternativas(list(estrategias), rotulos=rotulos)


def de_cenarios(cenarios: Iterable[dict], rotulos: dict[str, str] | None = None) -> dict:
    """Atalho para a saída de `motor.gerar_cenarios()` (3 caminhos). Usa `criterios[k]['nota']`; critério sem nota entra como lacuna."""
    alts = [{"id": " > ".join(c["rotacao"]),
             "criterios": c.get("criterios") or {}} for c in cenarios]
    return separar_alternativas(alts, rotulos=rotulos)
