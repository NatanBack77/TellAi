"""Rotação em SEQUÊNCIA de safras (padrão: 3 safras seguidas no mesmo local), em vez de culturas isoladas.

Cada candidata é uma sequência (c1, c2, c3) com c1 = cultura atual (já plantada neste ano). A rotação existente do agricultor é a primeira
estratégia (informada por ele, ou, sem informação, a repetição da cultura atual). As demais vêm de uma simulação estilo SMAA-2
(src/culturas/incerteza.py) sobre critérios com dado e fonte; dado ausente vira lacuna (incerteza), nunca nota inventada.

Critérios (nota 0-1):
  adeq_clima         média, entre as 3 culturas, da adequação ao clima do ciclo (temperatura e chuva do EcoCrop, motor de ciclo; ZARC opcional),
                     por ano de clima (o mesmo ano de clima vale para as 3 safras: SUPOSIÇÃO; ano real seguinte não é conhecido);
  diversidade_familia fração das transições entre safras com família botânica diferente. É só um PROXY de quebra de ciclo de pragas e doenças:
                     NÃO há dado de pragas no projeto (lacuna declarada);
  leguminosa_antes   fração das transições em que uma leguminosa (família Leguminosae) precede uma não leguminosa. Regra agronômica geral
                     (SUPOSIÇÃO, a confirmar com o acervo/técnico); o N fixado medido só existe para 3 culturas (amendoim, crotalária, mucuna; conferido em data/culturas/tabela_culturas.csv) e é mostrado à parte;
                     o N acumulado na biomassa existe para 10 das 16 culturas;
  palha              média da palha (kg MS/ha) das 3 culturas, min-max entre as candidatas; sem dado em alguma = lacuna;
  agua               1 - demanda hídrica média (mm/ciclo), min-max; sem dado em alguma = lacuna.
Renda: lacuna (não há dado de preço, custo nem mercado). Solo: o que o agricultor informa só gera avisos de risco; não altera nota.
A saída é cenário a avaliar com técnico local; apoio à decisão, não recomendação nem previsão de produtividade.
"""
from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd

from . import ciclo, incerteza
from .motor import AVISO, RISCOS_FIXOS, avaliar_local
from .parametros import Parametros

CRITERIOS = ["adeq_clima", "diversidade_familia", "leguminosa_antes", "palha", "agua"]
PRINCIPAIS_PADRAO = ["adeq_clima", "diversidade_familia", "leguminosa_antes"]
LEGUMINOSA = "Leguminosae"
HORIZONTE = 3
MAX_CANDIDATAS = 80   # pré-seleção antes da simulação (custo cresce com o quadrado do nº de candidatas)

# Ordem de importância por prioridade do agricultor (SUPOSIÇÃO a validar com técnico; ver docs/11_MVP.md).
ORDEM_PRIORIDADE = {
    "sem": None,
    "agua": ("agua", "adeq_clima", "diversidade_familia", "leguminosa_antes", "palha"),
    "solo": ("palha", "leguminosa_antes", "diversidade_familia", "adeq_clima", "agua"),
    "renda": None,   # sem dado de renda (renda_por_cultura=None) não altera o ranking; com dado, ver ORDEM_RENDA
}
# Com `renda_por_cultura` informado e prioridade 'renda': critério extra 'renda' (receita bruta/ha do IBGE/PAM, NÃO é lucro) vira o mais
# importante. SUPOSIÇÃO a validar com técnico (como as demais ordens).
ORDEM_RENDA = ("renda", "adeq_clima", "diversidade_familia", "leguminosa_antes", "palha", "agua")

# cultura da tabela -> produto do PAM/IBGE (contexto local; o PAM não separa caupi de feijão comum)
PAM_PRODUTO = {"milho": "Milho (em grão)", "feijao_caupi": "Feijão (em grão)", "feijao_comum": "Feijão (em grão)",
               "mandioca": "Mandioca", "algodao": "Algodão herbáceo (em caroço)", "amendoim": "Amendoim (em casca)",
               "girassol": "Girassol (em grão)", "gergelim": "Gergelim", "mamona": "Mamona (baga)", "sorgo": "Sorgo (em grão)"}


def _v(tab: dict, cid: str, atr: str):
    d = tab[cid]["atributos"].get(atr)
    return None if d is None else d["valor"]


def _fonte(tab: dict, cid: str, atr: str) -> dict | None:
    d = tab[cid]["atributos"].get(atr)
    return None if d is None else {"fonte": d["fonte"], "url": d["url"], "pagina": d["pagina"]}


def _minmax(x: np.ndarray, maior_melhor: bool = True) -> np.ndarray:
    ok = ~np.isnan(x)
    if ok.sum() < 2 or np.nanmax(x) == np.nanmin(x):
        return np.where(ok, np.nan, np.nan)     # sem variação entre candidatas: sem nota (lacuna)
    n = (x - np.nanmin(x)) / (np.nanmax(x) - np.nanmin(x))
    return n if maior_melhor else 1 - n


def contexto_pam(ibge: int | None, caminho: str | None = None) -> dict[str, dict]:
    """Área colhida (ha) por produto no município, último ano disponível (IBGE PAM, SIDRA 1612). Só contexto; nunca entra na nota."""
    from src.modelos.entrada import RAIZ
    arq = RAIZ / "data/processed/pam_ce.parquet" if caminho is None else caminho
    if ibge is None or not pd.io.common.file_exists(arq):
        return {}
    d = pd.read_parquet(arq)
    d = d[(d["ibge"] == int(ibge)) & (d["variavel"] == "area_colhida_ha") & d["valor"].notna()]
    if d.empty:
        return {}
    ano = int(d["ano"].max())
    d = d[d["ano"] == ano]
    return {cid: {"area_colhida_ha": float(d[d["produto"] == prod]["valor"].sum()), "ano": ano}
            for cid, prod in PAM_PRODUTO.items() if (d["produto"] == prod).any()}


def _janela(res: dict) -> dict:
    return {"inicio": res["inicio"], "adequacao_media": round(res["adeq_media"], 3), "anos_viaveis": round(res["p_ano_viavel"], 3)}


def gerar_rotacoes(perfil: dict, cultura_atual: str, tabela: dict, clima: ciclo.ClimaPonto, params: Parametros | None = None,
                   prioridade: str = "sem", rotacao_atual: list[str] | None = None, n_alternativas: int = 2,
                   solo_usuario: dict | None = None, ibge: int | None = None,
                   renda_por_cultura: dict[str, float | None] | None = None) -> dict[str, Any]:
    """Estratégia atual + `n_alternativas` sequências de 3 safras. Devolve {'estrategias': [...], 'lacunas', 'suposicoes', 'aviso', ...}."""
    p = params or Parametros()
    if cultura_atual not in tabela:
        raise KeyError(f"cultura atual '{cultura_atual}' não está na tabela")
    if prioridade not in ORDEM_PRIORIDADE:
        raise ValueError(f"prioridade deve ser uma de {list(ORDEM_PRIORIDADE)}")
    ordem = ORDEM_PRIORIDADE[prioridade]
    usa_renda = bool(prioridade == "renda" and renda_por_cultura and any(v is not None for v in renda_por_cultura.values()))
    criterios = CRITERIOS + ["renda"] if usa_renda else CRITERIOS
    principais = PRINCIPAIS_PADRAO + ["renda"] if usa_renda else PRINCIPAIS_PADRAO
    if usa_renda:
        ordem = ORDEM_RENDA
    bloco = "completo" if prioridade == "solo" else "principal"
    import dataclasses
    p = dataclasses.replace(p, ordem_pesos=ordem, bloco_ranking=bloco)
    av = avaliar_local(tabela, clima, p)
    cs = av["culturas"]
    viaveis = [c for c in tabela if cs[c]["estado"] == "viavel" or (c == cultura_atual and cs[c]["res"] is not None)]
    lacunas = list(clima.lacunas)
    if cultura_atual not in viaveis:
        lacunas.append(f"cultura atual '{cultura_atual}' sem avaliação climática neste local; a sequência parte dela, sem nota de clima própria.")
    if av["anos"][2] == 0 or not viaveis:
        return {"estrategias": [], "lacunas": lacunas + ["sem culturas viáveis avaliáveis neste local: nenhuma sequência calculada."],
                "suposicoes": p.suposicoes(), "aviso": AVISO, "horizonte_safras": HORIZONTE}
    if rotacao_atual is not None:
        if len(rotacao_atual) != HORIZONTE or rotacao_atual[0] != cultura_atual or any(c not in tabela for c in rotacao_atual):
            raise ValueError(f"rotacao_atual deve ter {HORIZONTE} culturas da tabela, começando pela cultura atual")
        base = tuple(rotacao_atual)
    else:
        base = (cultura_atual,) * HORIZONTE
    resto = [c for c in viaveis if c in tabela]
    cand = [base] + [s for s in itertools.product([cultura_atual], resto, resto) if s != base and len(set(s)) > 1]
    n_anos = av["anos"][2]
    adq = {c: np.asarray(cs[c]["res"]["adeq_por_ano"], float) for c in set(itertools.chain(*cand)) if cs[c]["res"] is not None}
    C, K = len(cand), len(criterios)
    T = np.full((C, K, n_anos), np.nan)
    fam = {c: _v(tabela, c, "familia_botanica") for c in tabela}
    palha = {c: _v(tabela, c, "palha_ms_kg_ha") for c in tabela}
    agua = {c: _v(tabela, c, "demanda_hidrica_mm_ciclo") for c in tabela}
    pal_m, agu_m, ren_m = np.full(C, np.nan), np.full(C, np.nan), np.full(C, np.nan)
    rend = renda_por_cultura or {}
    for i, s in enumerate(cand):
        if all(c in adq for c in s):
            T[i, 0, :] = np.mean([adq[c] for c in s], axis=0)
        trans = list(zip(s[:-1], s[1:]))
        if all(fam[a] is not None and fam[b] is not None for a, b in trans):
            T[i, 1, :] = np.mean([fam[a] != fam[b] for a, b in trans])
            T[i, 2, :] = np.mean([(fam[a] == LEGUMINOSA and fam[b] != LEGUMINOSA) for a, b in trans])
        if all(palha[c] is not None for c in s):
            pal_m[i] = np.mean([palha[c] for c in s])
        if all(agua[c] is not None for c in s):
            agu_m[i] = np.mean([agua[c] for c in s])
        if usa_renda and all(rend.get(c) is not None for c in s):
            ren_m[i] = np.mean([rend[c] for c in s])
    T[:, 3, :] = _minmax(pal_m)[:, None]
    T[:, 4, :] = _minmax(agu_m, maior_melhor=False)[:, None]
    if usa_renda:
        T[:, 5, :] = _minmax(ren_m)[:, None]
    n_total = C
    if C > MAX_CANDIDATAS + 1:          # pré-seleção determinística: pesos iguais nos critérios com dado; a base (índice 0) fica sempre
        por_crit = np.where(np.isnan(T).all(axis=2), np.nan, np.nansum(T, axis=2) / np.maximum((~np.isnan(T)).sum(axis=2), 1))
        tem = ~np.isnan(por_crit)
        pre = np.where(tem.any(axis=1), np.where(tem, por_crit, 0.0).sum(axis=1) / np.maximum(tem.sum(axis=1), 1), -1.0)
        manter = [0] + [int(i) for i in np.argsort(-pre[1:], kind="stable")[:MAX_CANDIDATAS] + 1]
        manter.sort()
        cand, T = [cand[i] for i in manter], T[manter]
        C = len(cand)
    ranqueia = np.array([i > 0 for i in range(C)])
    sim = incerteza.simular(T, criterios, principais, ranqueia, p)[bloco]
    rk, r_idx = sim["ranking"], sim["r_idx"]
    rng = np.random.default_rng(p.semente)
    ordem_idx = sorted(range(len(r_idx)), key=lambda j: (-round(rk["p_topo"][j], 9), round(rk["pos_media"][j], 9), rng.random()))
    esc: list[int] = []
    for j in ordem_idx:                      # alternativas distintas (outro conjunto de culturas e outra 2ª safra; evita a mesma combinação em ordem trocada)
        i = int(r_idx[j])
        if len(esc) >= n_alternativas:
            break
        if all(frozenset(cand[i][1:]) != frozenset(cand[e][1:]) and cand[i][1] != cand[e][1] for e in esc):
            esc.append(i)
    for j in ordem_idx:                      # se não houver distintas o bastante, completa pelas melhores restantes
        i = int(r_idx[j])
        if len(esc) >= n_alternativas:
            break
        if i not in esc:
            esc.append(i)
    ctx = contexto_pam(ibge)
    estrategias = []
    for papel, i in [("atual", 0)] + [("alternativa", i) for i in esc]:
        s = cand[i]
        k_lo, k_hi = sim["score_lo"][i], sim["score_hi"][i]
        pos = {int(r): j for j, r in enumerate(r_idx)}.get(i)
        emp = [] if pos is None else [[cand[int(r_idx[o])] for o in sim["empates"][pos]]]
        crit = {}
        for k, nome in enumerate(criterios):
            v = T[i, k, :]
            crit[nome] = {"nota_media": None if np.isnan(v).all() else round(float(np.nanmean(v)), 3), "lacuna": bool(np.isnan(v).all())}
        det = [{"cultura": c, "nome": tabela[c]["cultura_pt"], "familia": fam[c],
                "palha_ms_kg_ha": palha[c], "fonte_palha": _fonte(tabela, c, "palha_ms_kg_ha"),
                "demanda_hidrica_mm": agua[c], "fonte_demanda": _fonte(tabela, c, "demanda_hidrica_mm_ciclo"),
                "n_fixado_kg_ha": _v(tabela, c, "n_fixado_kg_ha"), "fonte_n_fixado": _fonte(tabela, c, "n_fixado_kg_ha"),
                "janela": _janela(cs[c]["res"]) if cs[c]["res"] is not None else None,
                "no_municipio": ctx.get(c)} for c in s]
        if usa_renda:
            for x in det:
                x["renda_bruta_r_ha"] = rend.get(x["cultura"])

        lac = []
        sem_dado = [k for k, v in crit.items() if v["lacuna"]]
        if sem_dado:
            lac.append("sem dado para: " + ", ".join(sem_dado) + " (entra como incerteza na simulação, não como nota)")
        for c in dict.fromkeys(s):
            faltam = [a for a, v in (("palha", palha[c]), ("demanda hídrica", agua[c])) if v is None]
            if faltam:
                lac.append(f"{tabela[c]['cultura_pt']}: sem {', '.join(faltam)} na tabela de culturas")
        lac += ["pragas e doenças: sem dado; a diversidade de famílias é só um proxy de quebra de ciclo"]
        if usa_renda:
            lac.append("renda: só receita BRUTA por hectare (IBGE/PAM, valores correntes); NÃO é lucro; sem custo, preço futuro nem mercado")
            lac += [f"{tabela[c]['cultura_pt']}: sem receita bruta no PAM (lacuna visível; entra como incerteza, não como nota)"
                    for c in dict.fromkeys(s) if rend.get(c) is None]
        else:
            lac.append("renda e mercado: sem dado de preço, custo ou demanda")
        riscos = list(RISCOS_FIXOS) + ["Cada safra usa o mesmo ano de clima da simulação; o clima real de cada ano seguinte não é conhecido.",
                                       "Culturas fora da prática local ou sem semente/mercado podem não ser viáveis na prática."]
        if solo_usuario:
            tex = str(solo_usuario.get("textura", "")).lower()
            org = solo_usuario.get("origem", "informado")
            if tex.startswith("aren"):
                riscos.append(f"Solo arenoso {org}: baixa retenção de água e de matéria orgânica; palha e cobertura pesam mais, e a seca é mais crítica. Avaliar com técnico.")
            if tex.startswith("argil"):
                riscos.append(f"Solo argiloso {org}: risco de encharcamento e compactação em chuva forte; avaliar drenagem com técnico.")
            if str(solo_usuario.get("materia_organica", "")).lower().startswith("baix"):
                riscos.append("Matéria orgânica baixa informada pelo agricultor: favorece sequências com mais palha e leguminosa, mas o app não mede o efeito.")
        estrategias.append({
            "papel": papel, "sequencia": list(s), "nomes": [tabela[c]["cultura_pt"] for c in s],
            "rotacao_informada_pelo_usuario": bool(papel == "atual" and rotacao_atual is not None),
            "score_mediana": round(float(sim["score_mediana"][i]), 1), "faixa_score": [round(float(k_lo), 1), round(float(k_hi), 1)],
            "p_top": None if pos is None else round(float(rk["p_topo"][pos]), 3),
            "posicao_p10_p90": None if pos is None else [int(rk["pos_p_baixo"][pos]), int(rk["pos_p_alto"][pos])],
            "empate_tecnico_com": [list(x) for x in emp[0]] if emp else [],
            "criterios": crit, "culturas": det, "lacunas": lac, "riscos_revisao_local": riscos})
    sup = p.suposicoes() + [
        f"SUPOSIÇÃO: horizonte de {HORIZONTE} safras, uma por ano (uma estação chuvosa por ano no semiárido); a primeira é a cultura atual.",
        "SUPOSIÇÃO: leguminosa antes de não leguminosa é benéfica (regra agronômica geral); a diversidade de famílias é proxy de quebra de ciclo de pragas.",
        f"SUPOSIÇÃO: prioridade '{prioridade}' vira ordem de critérios (a validar com técnico)." + (" 'renda' sem dado de receita: não altera nada." if prioridade == "renda" and not usa_renda else "")
        + (" Com 'renda': critério extra = receita bruta/ha média das culturas da sequência (PAM, correntes, NÃO é lucro); sequência com cultura sem dado = lacuna." if usa_renda else ""),
        "O mesmo ano de clima vale para as 3 safras de cada sorteio.",
        f"Para limitar o tempo de cálculo, só as {MAX_CANDIDATAS} sequências de maior nota média (pesos iguais, critérios com dado) entram na "
        "simulação de incerteza; as demais ficam de fora.",
    ]
    return {"estrategias": estrategias, "lacunas": lacunas, "suposicoes": sup, "aviso": AVISO, "horizonte_safras": HORIZONTE,
            "n_candidatas": n_total, "n_simuladas": C, "prioridade": prioridade, "bloco": bloco, "criterios": criterios, "usa_renda": usa_renda, "anos_clima": av["anos"],
            "empate_tecnico_todos": bool(all(len(e["empate_tecnico_com"]) > 0 for e in estrategias[1:])) if len(estrategias) > 1 else False}
