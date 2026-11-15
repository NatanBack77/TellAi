"""Avalia um CICLO MONTADO PELO AGRICULTOR (1 a 4 culturas, na ordem que ele disse) e as outras ORDENS das mesmas culturas.

Usa o mesmo motor do app (`motor.avaliar_local`: viabilidade e adequação ao clima por cultura, mesmo ciclo/ZARC/ano de clima) e os mesmos
critérios de `rotacao.py` (adeq_clima, diversidade_familia, leguminosa_antes, palha, agua). Não edita `rotacao.py` nem `motor.py`; só os importa.

O que a ORDEM muda (e o que não muda), com as mesmas definições de `rotacao.py`:
  - diversidade_familia: fração das trocas entre safras com família botânica diferente (só um proxy de quebra de ciclo de pragas; sem dado de pragas);
  - leguminosa_antes: fração das trocas em que uma leguminosa vem antes de uma não leguminosa (regra agronômica geral, SUPOSIÇÃO do projeto);
  - adeq_clima, palha e agua são médias das MESMAS culturas: não mudam com a ordem (aparecem à parte, como 'igual em todas as ordens').
Palha, água e N fixado vêm da tabela de culturas só onde há dado; sem dado é LACUNA (nunca nota).

Comparação entre ordens: dominância de Pareto (`pareto.py`), sem pesos. Ordens com as MESMAS notas nos critérios com dado ficam EMPATADAS
('com os dados que temos, A e B ficam empatadas'); nunca se escolhe uma só por desempate. Dominar não prova que uma ordem rende mais: só que,
nos critérios medidos, a outra não ganha em nenhum.
Suposição de horizonte (a mesma de `rotacao.py`): uma safra por ano; cada safra usa o clima de anos já observados, nunca clima futuro.
"""
from __future__ import annotations

import itertools
from typing import Any

import numpy as np

from . import pareto, regras_duras as rd
from .motor import AVISO, avaliar_local
from .rotacao import LEGUMINOSA, ORDEM_PRIORIDADE
from .tabela_culturas import carregar as _carregar_tabela

MAX_CULTURAS = 4
MAX_PERMUTACOES = 24            # 4! ; acima disso a lista é cortada (a ordem dita fica sempre)
CRITERIOS_ORDEM = ["adeq_clima", "diversidade_familia", "leguminosa_antes"]
ROTULOS = {"adeq_clima": "adequação ao clima", "diversidade_familia": "família diferente entre safras",
           "leguminosa_antes": "leguminosa antes de outra planta", "palha": "palha", "agua": "água que a planta pede"}
TOL = 1e-9
_CACHE_AV: dict[str, dict] = {}


class SequenciaErro(ValueError):
    """Pedido inválido (cultura fora da tabela, quantidade fora de 1 a 4...)."""


def limpar_cache() -> None:
    _CACHE_AV.clear()


def avaliacao_local(ponto_id: str, tabela: dict | None = None, clima=None, params=None) -> dict:
    """`motor.avaliar_local` do ponto (3 a 4 s), guardado em memória por ponto: viabilidade não depende da prioridade nem da ordem."""
    if ponto_id in _CACHE_AV and tabela is None and clima is None and params is None:
        return _CACHE_AV[ponto_id]
    from src.app import mvp as M            # só aqui: a camada de culturas não depende do app para calcular com `av` injetado
    tab = tabela or M.carregar_tabela()
    av = avaliar_local(tab, clima if clima is not None else M.clima_ponto(ponto_id), params or M.parametros("sem", 1000))
    if tabela is None and clima is None and params is None:
        _CACHE_AV[ponto_id] = av
    return av


def _v(tab: dict, cid: str, atr: str):
    d = tab[cid]["atributos"].get(atr)
    return None if d is None else d["valor"]


def _fonte(tab: dict, cid: str, atr: str):
    d = tab[cid]["atributos"].get(atr)
    return None if d is None else {"fonte": d.get("fonte"), "url": d.get("url"), "pagina": d.get("pagina")}


def _por_cultura(tab: dict, av: dict, cid: str) -> dict:
    c = av["culturas"][cid]
    res = c["res"]
    return {"id": cid, "nome": tab[cid]["cultura_pt"], "familia": _v(tab, cid, "familia_botanica"), "estado": c["estado"],
            "motivos": list(c["motivos"]), "lacunas": list(c["lacunas"]),
            "p_ano_viavel": None if res is None else round(float(res["p_ano_viavel"]), 3),
            "melhor_inicio": None if res is None else res["inicio"],
            "adeq_media": None if res is None else round(float(res["adeq_media"]), 3),
            "palha_ms_kg_ha": _v(tab, cid, "palha_ms_kg_ha"), "fonte_palha": _fonte(tab, cid, "palha_ms_kg_ha"),
            "demanda_hidrica_mm": _v(tab, cid, "demanda_hidrica_mm_ciclo"), "fonte_demanda": _fonte(tab, cid, "demanda_hidrica_mm_ciclo"),
            "n_fixado_kg_ha": _v(tab, cid, "n_fixado_kg_ha"), "fonte_n_fixado": _fonte(tab, cid, "n_fixado_kg_ha"),
            "n_na_biomassa_kg_ha": _v(tab, cid, "n_acumulado_parte_aerea_kg_ha")}


def _criterios_ordem(seq: tuple, fam: dict, adq: dict) -> dict:
    """Notas da ordem `seq`, com as definições de rotacao.py. None = lacuna."""
    trans = list(zip(seq[:-1], seq[1:]))
    out: dict[str, float | None] = {}
    out["adeq_clima"] = (float(np.nanmean(np.mean([adq[c] for c in seq], axis=0))) if all(c in adq for c in seq) else None)
    if trans and all(fam.get(a) is not None and fam.get(b) is not None for a, b in trans):
        out["diversidade_familia"] = float(np.mean([fam[a] != fam[b] for a, b in trans]))
        out["leguminosa_antes"] = float(np.mean([(fam[a] == LEGUMINOSA and fam[b] != LEGUMINOSA) for a, b in trans]))
    else:
        out["diversidade_familia"] = out["leguminosa_antes"] = None       # 1 cultura (sem troca) ou família sem dado: não há nota
    return out


def _vetor(crit: dict) -> tuple:
    return tuple(None if crit[k] is None else round(crit[k], 9) for k in CRITERIOS_ORDEM)


def avaliar(ponto_id: str, culturas: list[str], regras=None, prioridade: str = "sem", av: dict | None = None, tabela: dict | None = None,
            max_permutacoes: int = MAX_PERMUTACOES) -> dict[str, Any]:
    """Avalia o ciclo `culturas` (na ordem dita, a primeira safra primeiro) e as ordens alternativas das mesmas culturas.

    `regras`: RegrasDuras ou dict (regras_duras.py). Aqui `proibidas` vale para TODAS as posições (o agricultor está montando o ciclo, nenhuma
    safra já foi plantada). `av`: resultado de `motor.avaliar_local` (injetável em teste); sem ele, calcula e guarda em memória."""
    if prioridade not in ORDEM_PRIORIDADE:
        raise SequenciaErro(f"prioridade deve ser uma de {list(ORDEM_PRIORIDADE)}")
    cult = list(culturas or [])
    if not 1 <= len(cult) <= MAX_CULTURAS:
        raise SequenciaErro(f"informe de 1 a {MAX_CULTURAS} culturas (recebi {len(cult)})")
    tab = tabela or _carregar_tabela()
    desc = [c for c in cult if c not in tab]
    if desc:
        raise SequenciaErro("cultura fora da tabela: " + ", ".join(desc))
    if regras is not None:
        rd.validar(regras, tab)
    av = av or avaliacao_local(ponto_id, tabela=tabela)
    fam = {c: _v(tab, c, "familia_botanica") for c in tab}
    pc = {c: _por_cultura(tab, av, c) for c in dict.fromkeys(cult)}
    adq = {c: np.asarray(av["culturas"][c]["res"]["adeq_por_ano"], float) for c in pc if av["culturas"][c]["res"] is not None}

    dita = tuple(cult)
    perms = list(dict.fromkeys(itertools.permutations(cult)))      # sem repetidas (multiconjunto); a 1ª é a ordem dita
    cortou = len(perms) > max_permutacoes
    perms = perms[:max_permutacoes]
    ordens, ids = [], []
    for s in perms:
        crit = _criterios_ordem(s, fam, adq)
        viola = rd.verificar(("__inicio__",) + s, {**fam, "__inicio__": None}, regras) if regras is not None else []
        ordens.append({"sequencia": list(s), "nomes": [tab[c]["cultura_pt"] for c in s], "dita": s == dita,
                       "criterios": {k: {"nota_media": None if v is None else round(v, 3), "lacuna": v is None} for k, v in crit.items()},
                       "viola_regras": viola, "_vetor": _vetor(crit),
                       "trocas": [{"de": a, "para": b, "familia_diferente": None if fam[a] is None or fam[b] is None else fam[a] != fam[b],
                                   "leguminosa_antes": None if fam[a] is None or fam[b] is None else (fam[a] == LEGUMINOSA and fam[b] != LEGUMINOSA)}
                                  for a, b in zip(s[:-1], s[1:])]})
        ids.append(" > ".join(s))
    comparaveis = [o for o in ordens if o["dita"] or not o["viola_regras"]]
    descartadas = [{"sequencia": o["sequencia"], "motivos": o["viola_regras"]} for o in ordens if o["viola_regras"] and not o["dita"]]
    pt = pareto.separar_alternativas([{"id": " > ".join(o["sequencia"]), "criterios": o["criterios"]} for o in comparaveis],
                                     criterios=[k for k in CRITERIOS_ORDEM], rotulos=ROTULOS)
    topo = pt["fronteira"]
    por_id = {" > ".join(o["sequencia"]): o for o in comparaveis}
    vetores_topo = {por_id[i]["_vetor"] for i in topo}
    vetores_todos = {o["_vetor"] for o in comparaveis}
    if len(comparaveis) == 1:
        veredito = "uma_ordem"
    elif len(vetores_todos) == 1:
        veredito = "todas_iguais"                       # a ordem não muda nada nos critérios com dado: todas empatadas
    elif len(vetores_topo) == 1:
        veredito = "topo_unico" if len(topo) == 1 else "topo_empatado"
    else:
        veredito = "sem_dominancia"                     # ganha em um critério, perde em outro
    dita_id = " > ".join(dita)
    dominada_por = pt["posicao_pareto"].get(dita_id, {}).get("dominada_por", []) if dita_id in pt["posicao_pareto"] else []
    # critérios que NÃO variam com a ordem (iguais em todas) e os que variam
    var = [k for k in CRITERIOS_ORDEM if len({o["_vetor"][CRITERIOS_ORDEM.index(k)] for o in comparaveis}) > 1]
    # prioridade do agricultor: quais critérios dela variam com a ordem; quem lidera neles (lexicográfico, só informação)
    ordem_p = ORDEM_PRIORIDADE.get(prioridade) or ()
    crit_prior = [k for k in ordem_p if k in CRITERIOS_ORDEM or k in ("palha", "agua")]
    var_prior = [k for k in crit_prior if k in var]
    lider = None
    if var_prior and veredito == "sem_dominancia":
        def chave(i):
            v = por_id[i]["_vetor"]
            return tuple(-(v[CRITERIOS_ORDEM.index(k)] or 0) for k in var_prior)
        melhor = min(chave(i) for i in topo)
        lider = [i for i in topo if chave(i) == melhor]
    # médias do ciclo que não mudam com a ordem
    def media(attr):
        vals = [pc[c][attr] for c in cult]
        return (float(np.mean(vals)) if all(v is not None for v in vals) else None,
                [pc[c]["id"] for c in dict.fromkeys(cult) if pc[c][attr] is None])
    palha_m, falta_palha = media("palha_ms_kg_ha")
    agua_m, falta_agua = media("demanda_hidrica_mm")
    n_fix = {c: pc[c]["n_fixado_kg_ha"] for c in pc if pc[c]["n_fixado_kg_ha"] is not None}
    lacunas = ["pragas e doenças: sem dado no projeto; trocar de família só indica quebra do ciclo das pragas, não prova",
               "renda e mercado: sem dado de preço, custo ou demanda"]
    for c in pc:
        faltam = [n for n, a in (("palha", "palha_ms_kg_ha"), ("água que a planta pede", "demanda_hidrica_mm"), ("nitrogênio fixado", "n_fixado_kg_ha"))
                  if pc[c][a] is None]
        if faltam:
            lacunas.append(f"{pc[c]['nome']}: sem dado de {', '.join(faltam)} na tabela de culturas")
    inviaveis = [c for c in pc if pc[c]["estado"] == "inviavel"]
    indeterminadas = [c for c in pc if pc[c]["estado"] == "indeterminada"]
    for c in inviaveis:
        lacunas.append(f"{pc[c]['nome']}: pelo clima deste local, não ficou dentro das faixas da planta em anos suficientes")
    for c in indeterminadas:
        lacunas.append(f"{pc[c]['nome']}: sem avaliação de clima neste local ({'; '.join(pc[c]['lacunas'][:1]) or 'faltou dado'})")
    if cortou:
        lacunas.append(f"só as primeiras {max_permutacoes} ordens foram comparadas")
    riscos = ["Cada safra usa o clima de anos já observados; o clima dos próximos anos não é conhecido.",
              "Cultura fora da prática local, sem semente ou sem mercado pode não ser viável na prática. Avaliar com técnico local."]
    for o in ordens:
        o.pop("_vetor")
    return {"ponto_id": ponto_id, "culturas": cult, "ordem_dita": list(dita), "n_safras": len(cult), "prioridade": prioridade,
            "per_cultura": pc, "ordens": ordens, "n_ordens": len(ordens),
            "pareto": pt, "fronteira": topo, "veredito": veredito, "dita_na_fronteira": dita_id in topo, "dominada_por": dominada_por,
            "criterios_que_variam": var, "criterios_iguais": [k for k in CRITERIOS_ORDEM if k not in var],
            "prioridade_efeito": {"prioridade": prioridade, "criterios": crit_prior, "variam_com_a_ordem": var_prior,
                                  "lideres": lider},
            "agregados": {"palha_media_kg_ha": palha_m, "falta_palha": falta_palha, "agua_media_mm": agua_m, "falta_agua": falta_agua,
                          "n_fixado_kg_ha": n_fix},
            "inviaveis": inviaveis, "indeterminadas": indeterminadas, "descartadas_por_regra": descartadas,
            "regras_duras": None if regras is None else rd.descrever(regras, descartadas, None),
            "anos_clima": av["anos"], "lacunas": lacunas, "riscos_revisao_local": riscos,
            "suposicoes": ["uma safra por ano (uma estação chuvosa por ano no semiárido); cada safra usa clima de anos já vistos",
                           "leguminosa antes de não leguminosa é benéfica (regra agronômica geral, a confirmar com técnico)",
                           "a troca de família é só um sinal de quebra de ciclo de pragas e doenças (sem dado de pragas)"],
            "aviso": AVISO}


# ------------------------------------------------------------------------------------------------ sugestão por foco (quando ele não montou o ciclo)
FOCO_ATRIBUTO = {   # foco -> (atributo da tabela de culturas, maior é melhor?, unidade em palavras)
    "agua": ("demanda_hidrica_mm_ciclo", False, "mm por ciclo"),
    "solo": ("palha_ms_kg_ha", True, "kg de palha por hectare"),
    "palhada": ("palha_ms_kg_ha", True, "kg de palha por hectare"),
    "nitrogenio": ("n_fixado_kg_ha", True, "kg de nitrogênio fixado por hectare"),
}
LACUNA_FOCO = {
    "renda": "sem dado de preço, custo nem mercado: o Sulco não consegue dizer o que dá mais renda",
    "pragas": "sem dado de pragas e doenças: só dá para ver se a família da planta é diferente da que veio antes",
    "forragem": "sem valor numérico de forragem: os documentos do acervo trazem a produção só em gráfico, sem números",
}


def criterios_aplicados(av: dict) -> dict:
    """O QUE a viabilidade de `av` (motor.avaliar_local) de fato considerou, lido das próprias avaliações (não de um texto fixo).

    clima: sempre (temperatura média e chuva dentro do ciclo). zarc: 'sim' (janela do zoneamento do MAPA em todas as culturas avaliadas),
    'parcial' (só em parte; as sem ZARC usam janela aproximada das anuais) ou 'nao'. solo_zarc: o tipo de solo entrou na escolha da janela do ZARC.
    solo_ecocrop: pH/textura contra o EcoCrop (Parametros.solo_modo='ecocrop'). semente, mercado, municipio_planta (PAM): o motor NÃO usa (sem dado ligado)."""
    avs = [(c.get("av") or {}) for c in av.get("culturas", {}).values()]
    zs = [a.get("zarc") for a in avs if a.get("zarc") and a["zarc"].get("aplicado")]
    exatas = [z for z in zs if not z.get("aproximada")]
    n = len([a for a in avs if a.get("estado") == "avaliavel"])
    zarc = "nao" if not exatas else ("sim" if len(exatas) == n else "parcial")
    solos = [a.get("solo") for a in avs if a.get("solo") and a["solo"].get("aplicado")]
    return {"clima": True, "zarc": zarc, "zarc_risco": exatas[0]["risco"] if exatas else None,
            "zarc_solo": exatas[0]["solo"] if exatas else None, "solo_zarc": bool(exatas) and exatas[0]["solo"] in ("arenoso", "medio", "argiloso"),
            "solo_ecocrop": bool(solos), "semente": False, "mercado": False, "municipio_planta": False}


def sugerir_por_foco(ponto_id: str, foco: str | None, excluir: list[str] | None = None, atual: str | None = None, av: dict | None = None,
                     tabela: dict | None = None, k: int = 3) -> dict[str, Any]:
    """Quais culturas dão certo no local (motor) e, com `foco`, quais ficam na frente no dado da tabela de culturas.

    Ordena só pelo ATRIBUTO da tabela (valores de estudos diferentes: leitura indicativa); empate = mesmo valor. Sem dado = lacuna (fora do
    ranking, nunca nota). `excluir`: culturas que o agricultor não quer (ficam fora)."""
    tab = tabela or _carregar_tabela()
    av = av or avaliacao_local(ponto_id, tabela=tabela)
    ex = set(excluir or [])
    viaveis = [c for c in tab if av["culturas"][c]["estado"] == "viavel" and c not in ex]
    inviaveis = [c for c in tab if av["culturas"][c]["estado"] == "inviavel" and c not in ex]
    indet = [c for c in tab if av["culturas"][c]["estado"] == "indeterminada" and c not in ex]
    out: dict[str, Any] = {"ponto_id": ponto_id, "foco": foco, "viaveis": viaveis, "inviaveis": inviaveis, "indeterminadas": indet,
                           "excluidas": sorted(ex), "ranking": [], "topo": [], "empate_no_topo": False, "sem_dado": [], "atributo": None,
                           "unidade": None, "criterios": criterios_aplicados(av), "lacuna_foco": None, "diferentes_da_atual": None, "anos_clima": av["anos"]}
    if foco in FOCO_ATRIBUTO:
        atr, maior, un = FOCO_ATRIBUTO[foco]
        out["atributo"], out["unidade"], out["maior_melhor"] = atr, un, maior
        com = [(c, _v(tab, c, atr)) for c in viaveis if _v(tab, c, atr) is not None]
        com.sort(key=lambda x: (-x[1] if maior else x[1]))
        out["ranking"] = [{"id": c, "valor": v, "fonte": _fonte(tab, c, atr)} for c, v in com]
        out["sem_dado"] = [c for c in viaveis if _v(tab, c, atr) is None]
        if com:
            best = com[0][1]
            out["topo"] = [c for c, v in com if abs(v - best) <= TOL]
            out["empate_no_topo"] = len(out["topo"]) > 1
        out["top_k"] = [r["id"] for r in out["ranking"][:k]]
    elif foco in LACUNA_FOCO:
        out["lacuna_foco"] = LACUNA_FOCO[foco]
        if foco == "pragas" and atual and atual in tab:
            fa = _v(tab, atual, "familia_botanica")
            out["diferentes_da_atual"] = [c for c in viaveis if fa is not None and _v(tab, c, "familia_botanica") not in (None, fa)]
    return out
