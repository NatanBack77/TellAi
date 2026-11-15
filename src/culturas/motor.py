"""Motor de rotação: avaliação do ciclo (temperatura e chuva por início de plantio) -> filtro de viabilidade ->
pontuação -> ranking com incerteza (Monte Carlo estilo SMAA-2).

Princípios (docs/01 seção 3): nenhum número inventado; critério sem dado vira lacuna visível; o motor apoia, não decide.
Detalhes e limites: docs/10_MOTOR_CICLO_E_INCERTEZA.md. Parâmetros de decisão do usuário: parametros.py.

Suposições do motor (NÃO são dado de fonte; revisar com o usuário):
- M1 pesos dos critérios (PESOS) são uma proposta de projeto, não vêm de literatura (o Monte Carlo os sorteia).
- M2 nota climática: 0 fora da faixa absoluta, 1 na ótima, linear entre as duas (forma trapezoidal do EcoCrop descrita
  no README do OpenCLIM), aplicada à temperatura MÉDIA e à chuva ACUMULADA no ciclo de cada início/ano (ciclo.py).
- M3 a chuva é comparada à faixa EcoCrop como chuva dos 365 dias desde o início (`chuva_modo="anual"`, padrão desde
  2026-11-14: a descrição oficial do EcoCrop diz "annual precipitation"; a ficha da espécie não foi aberta) ou do ciclo
  (`chuva_modo="ciclo"`, opção anterior). O atendimento hídrico do ciclo (chuva/demanda) é só informação, fora do ranking.
- M7 duração do ciclo: Tabela 11 do FAO-56 nas culturas que a FAO cobre (`ciclo_fonte="fao"`, ciclo_fao.py); EcoCrop nas demais.
- M4 notas de N e palha: min-max entre as candidatas com dado; valores vêm de estudos diferentes
  (locais e idades de corte diferentes), logo a comparação é só indicativa.
- M5 'familia_diferente': 1 se a família botânica (EcoCrop) difere da cultura atual, 0 se igual.
- M6 ranking principal só com critérios que todas as candidatas têm; N/palha à parte (lacuna = incerteza, não prêmio).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from . import ciclo, ciclo_fao, incerteza
from .parametros import Parametros
from .tabela_culturas import carregar

AVISO = "Cenário a avaliar com técnico local. Apoio à decisão; não é recomendação nem previsão."

PESOS = {"temperatura": 0.25, "chuva": 0.25, "n_na_biomassa": 0.20, "palha": 0.15, "familia_diferente": 0.15}

UNID = {"temperatura": "°C", "chuva": "mm", "n_na_biomassa": "kg/ha", "palha": "kg/ha", "familia_diferente": "texto"}

def _suposicoes_base(p: Parametros) -> list[str]:
    anual = p.chuva_modo == "anual"
    return [
        "Pesos dos critérios são proposta de projeto (não vêm de fonte).",
        "Nota climática trapezoidal (0 fora da faixa absoluta, 1 na ótima), aplicada à temperatura média do ciclo e à chuva "
        + ("dos 365 dias desde o início do plantio." if anual else "acumulada no ciclo."),
        ("Faixa de chuva do EcoCrop comparada à chuva ANUAL (365 dias desde o início): a descrição oficial do EcoCrop na FAO diz "
         "'annual precipitation'. O atendimento hídrico do ciclo (chuva sobre a demanda) é só informação, não entra no ranking."
         if anual else
         "Faixa de chuva do EcoCrop comparada à chuva do ciclo (opção anterior; a descrição oficial fala em chuva anual)."),
    ] + _SUPOSICOES_FIXAS


_SUPOSICOES_FIXAS = [
    "Ranking principal usa só os critérios que todas as candidatas têm; N e palha são mostrados à parte, e lacuna vale incerteza, não nota.",
    "Notas de N e palha vêm de estudos distintos (local e idade de corte diferentes): comparação só indicativa.",
]
SUPOSICOES = _suposicoes_base(Parametros())      # padrão atual (compatibilidade); o cenário usa _suposicoes_base(p)

RISCOS_FIXOS = [
    "Dados de satélite têm resolução de km; o talhão pode diferir do pixel.",
    "Faixas EcoCrop são genéricas por espécie, não por cultivar nem por solo.",
    "Valores de palha e N vêm de estudos pontuais fora do semiárido; avaliar com técnico local.",
    "Não considera preço, mercado, pragas, doenças, solo nem disponibilidade de semente.",
]


def _v(tab: dict, cid: str, atrib: str):
    d = tab[cid]["atributos"].get(atrib)
    return None if d is None else d["valor"]


def _nota_trapezio(x: float, mn: float, omn: float, omx: float, mx: float) -> float:
    if x <= mn or x >= mx:
        return 0.0
    if omn <= x <= omx:
        return 1.0
    return (x - mn) / (omn - mn) if x < omn else (mx - x) / (mx - omx)


def _faixa(tab: dict, cid: str, pref: str, unidade: str) -> tuple | None:
    chaves = [f"{pref}_min_abs_{unidade}", f"{pref}_otima_min_{unidade}", f"{pref}_otima_max_{unidade}",
              f"{pref}_max_abs_{unidade}"]
    vals = [_v(tab, cid, k) for k in chaves]
    return None if any(v is None for v in vals) else tuple(vals)


def viabilidade(tab: dict, cid: str, perfil: dict) -> dict:
    """Filtro por faixa ABSOLUTA do EcoCrop. Estados: viavel | inviavel | indeterminada (falta dado)."""
    motivos, indet = [], []
    for nome, pref, un, chave in (("temperatura", "temp", "c", "temp_media_c"), ("chuva", "chuva", "mm", "chuva_ciclo_mm")):
        faixa = _faixa(tab, cid, pref, un)
        x = perfil.get(chave)
        if x is None:
            indet.append(f"perfil sem '{chave}': {nome} não avaliada")
        elif faixa is None:
            indet.append(f"EcoCrop sem faixa completa de {nome} para {cid}: lacuna")
        elif not (faixa[0] < x < faixa[3]):
            motivos.append(f"{nome} {x} fora da faixa absoluta {faixa[0]}–{faixa[3]}")
    estado = "inviavel" if motivos else ("indeterminada" if indet else "viavel")
    return {"estado": estado, "motivos": motivos, "lacunas": indet}


def _normalizar(valores: dict[str, float]) -> dict[str, float | None]:
    """min-max entre as candidatas com dado; <2 candidatas ou todas iguais => sem nota (None)."""
    if len(valores) < 2:
        return {k: None for k in valores}
    lo, hi = min(valores.values()), max(valores.values())
    if hi == lo:
        return {k: None for k in valores}
    return {k: (v - lo) / (hi - lo) for k, v in valores.items()}


def pontuar(tab: dict, perfil: dict, atual: str, ids: list[str]) -> dict[str, dict]:
    """Nota por critério e score 0-100 para cada cultura de `ids` (renormalizado pelos critérios com dado)."""
    notas: dict[str, dict[str, float | None]] = {c: {} for c in ids}
    for crit in PESOS:
        if crit in ("temperatura", "chuva"):
            pref, un, chave = ("temp", "c", "temp_media_c") if crit == "temperatura" else ("chuva", "mm", "chuva_ciclo_mm")
            for c in ids:
                f, x = _faixa(tab, c, pref, un), perfil.get(chave)
                notas[c][crit] = None if f is None or x is None else _nota_trapezio(x, *f)
        elif crit == "familia_diferente":
            fa = _v(tab, atual, "familia_botanica")
            for c in ids:
                fc = _v(tab, c, "familia_botanica")
                notas[c][crit] = None if fa is None or fc is None else float(fc != fa)
        else:
            atr = "n_acumulado_parte_aerea_kg_ha" if crit == "n_na_biomassa" else "palha_ms_kg_ha"
            com_dado = {c: _v(tab, c, atr) for c in ids if _v(tab, c, atr) is not None}
            nn = _normalizar(com_dado)
            for c in ids:
                notas[c][crit] = nn.get(c)
    out = {}
    for c in ids:
        usados = {k: n for k, n in notas[c].items() if n is not None}
        pw = sum(PESOS[k] for k in usados)
        score = None if pw == 0 else round(100 * sum(PESOS[k] * n for k, n in usados.items()) / pw, 1)
        out[c] = {"notas": notas[c], "score": score, "pesos_usados": {k: PESOS[k] for k in usados},
                  "criterios_sem_nota": [k for k in PESOS if k not in usados]}
    return out


def _criterios_json(tab: dict, cid: str, notas: dict, perfil: dict, atual: str) -> dict:
    """Bloco `criterios{valor, unidade, nota, fonte, pagina, url}` do contrato (docs/01 seção 7)."""
    atrs = {"temperatura": ["temp_min_abs_c", "temp_otima_min_c", "temp_otima_max_c", "temp_max_abs_c"],
            "chuva": ["chuva_min_abs_mm", "chuva_otima_min_mm", "chuva_otima_max_mm", "chuva_max_abs_mm"],
            "n_na_biomassa": ["n_acumulado_parte_aerea_kg_ha"], "palha": ["palha_ms_kg_ha"],
            "familia_diferente": ["familia_botanica"]}
    out = {}
    for crit, lista in atrs.items():
        fontes = [tab[cid]["atributos"].get(a) for a in lista]
        if any(f is None for f in fontes):
            out[crit] = {"valor": None, "unidade": UNID[crit], "nota": None, "fonte": None, "pagina": None,
                         "url": None, "lacuna": "sem dado com fonte para este critério"}
            continue
        if crit in ("temperatura", "chuva"):
            valor = {a: f["valor"] for a, f in zip(lista, fontes)}
            valor["perfil"] = perfil.get("temp_media_c" if crit == "temperatura" else "chuva_ciclo_mm")
        elif crit == "familia_diferente":
            valor = {"familia": fontes[0]["valor"], "familia_atual": _v(tab, atual, "familia_botanica")}
        else:
            valor = fontes[0]["valor"]
        f0 = fontes[0]
        out[crit] = {"valor": valor, "unidade": UNID[crit], "nota": notas.get(crit), "fonte": f0["fonte"],
                     "pagina": f0["pagina"], "url": f0["url"], "contexto": f0["contexto"]}
        if notas.get(crit) is None:
            out[crit]["lacuna"] = "dado existe mas sem base de comparação (nota não calculada)"
    return out


def _avisos_ciclo(tab: dict, cid: str, av: dict) -> list[str]:
    """Aviso sobre a duração do ciclo da cultura: 'ciclo de referência de outras regiões' (FAO) ou ciclo EcoCrop (ponto médio)."""
    info = av.get("ciclo_info") or {}
    nome = tab[cid]["cultura_pt"]
    if info.get("fonte") == "fao":
        return [ciclo_fao.aviso_fao(info, nome, info.get("ecocrop_min_max"))]
    if info.get("fonte") == "override":
        return [f"Ciclo de {nome}: {info['dias']} dias informado manualmente (ciclo_override)."]
    eco = info.get("ecocrop_min_max")
    if eco is None:
        return []
    motivo = info.get("motivo") or "ciclo do EcoCrop escolhido pelo modo configurado"
    return [ciclo_fao.aviso_ecocrop(nome, info["dias"], eco[0], eco[1], motivo)]


def _suposicoes_ciclo(tab: dict, cid: str, r: dict, p: Parametros) -> list[str]:
    return ["SUPOSIÇÃO (ciclo): " + a for a in _avisos_ciclo(tab, cid, r["av"])] if r.get("av") else []


CRITERIOS = list(PESOS)  # ordem fixa dos 5 critérios (eixo do tensor de notas)
LEITURA_RANKING = ("Ranking principal só pelos critérios que TODAS as candidatas têm; N na biomassa e palha ficam à parte "
                   "(informação), sem prêmio nem castigo por lacuna.")


def avaliar_local(tab: dict, clima: ciclo.ClimaPonto, p: Parametros) -> dict:
    """Viabilidade e adequação dentro do ciclo de TODAS as culturas da tabela, num ponto.

    Devolve {'ok': máscara de anos usados, 'anos': [ini, fim, n], 'culturas': {cid: {estado, motivos, lacunas, res, av}}}.
    """
    avs = {c: ciclo.notas_ciclo(tab, c, clima, p) for c in tab}
    ok = ciclo.anos_comuns(list(avs.values()), clima)
    n = int(ok.sum())
    anos_usados = [int(a) for a, o in zip(clima.anos, ok) if o]
    out = {}
    for c, av in avs.items():
        if av["estado"] != "avaliavel":
            out[c] = {"estado": "indeterminada", "motivos": [], "lacunas": av["lacunas"], "res": None, "av": av}
        elif n < p.min_anos:
            out[c] = {"estado": "indeterminada", "motivos": [], "av": av, "res": None,
                      "lacunas": [f"clima: só {n} anos com ciclo completo (mínimo {p.min_anos}); cultura não avaliada"]}
        else:
            res = ciclo.resumir(av, ok, p)
            est = "viavel" if res["viavel_no_risco"] else "inviavel"
            mot = [] if est == "viavel" else [
                f"em nenhum início de plantio a cultura ficou dentro das faixas absolutas em ao menos "
                f"{1 - p.risco_max:.0%} dos {n} anos (melhor início: {res['p_ano_viavel']:.0%} dos anos)"]
            out[c] = {"estado": est, "motivos": mot, "lacunas": [], "res": res, "av": av}
    return {"ok": ok, "anos": [anos_usados[0], anos_usados[-1], n] if anos_usados else [None, None, 0],
            "anos_lista": anos_usados, "culturas": out}


def _notas_estaticas(tab: dict, atual: str, ids: list[str]) -> dict[str, dict[str, float | None]]:
    """Notas que não dependem do ano: família (vs. atual) e N/palha (min-max entre as candidatas com dado, M4)."""
    notas: dict[str, dict] = {c: {} for c in ids}
    fa = _v(tab, atual, "familia_botanica")
    for c in ids:
        fc = _v(tab, c, "familia_botanica")
        notas[c]["familia_diferente"] = None if fa is None or fc is None else float(fc != fa)
    for crit, atr in (("n_na_biomassa", "n_acumulado_parte_aerea_kg_ha"), ("palha", "palha_ms_kg_ha")):
        nn = _normalizar({c: _v(tab, c, atr) for c in ids if _v(tab, c, atr) is not None})
        for c in ids:
            notas[c][crit] = nn.get(c)
    return notas


def _criterios_ranking(nota: np.ndarray) -> list[int]:
    """Índices dos critérios que TODAS as culturas simuladas têm (sem NaN)."""
    return [k for k in range(nota.shape[1]) if not np.isnan(nota[:, k, :]).any()]


def _score_base(pesos: dict, crit: list[str], notas: dict) -> float | None:
    """Score 0-100 com os pesos-base RENORMALIZADOS só entre `crit` (o mesmo conjunto para todas as culturas)."""
    if not crit or any(notas.get(k) is None for k in crit):
        return None
    pw = sum(pesos[k] for k in crit)
    return round(100 * sum(pesos[k] * notas[k] for k in crit) / pw, 1)


ROTULO_CICLO_APROXIMADO = "janela aproximada, sem zoneamento oficial"


def _origem_epoca(av: dict, p: Parametros) -> dict:
    """De ONDE vem a época de plantio: 'zarc' (decêndios indicados pelo zoneamento oficial) ou 'ciclo_aproximado' (adequação do ciclo)."""
    z = av.get("zarc")
    if z and z.get("aplicado") and not z.get("aproximada") and z.get("decendios_permitidos") == 0:
        return {"epoca_fonte": "zarc", "epoca_sem_indicacao": True,
                "epoca_rotulo": f"ZARC (MAPA) não indica nenhum decêndio ao risco {z['risco']} neste município: sem época de plantio válida (a data mostrada é apenas formal)",
                "epoca_detalhe": z}
    if z and z.get("aplicado") and not z.get("aproximada"):
        return {"epoca_fonte": "zarc", "epoca_rotulo": f"ZARC (MAPA), risco {z['risco']}, solo '{z['solo']}', {z['decendios_permitidos']} decêndios indicados",
                "epoca_detalhe": z}
    if p.epoca_modo == "anual_legado":
        return {"epoca_fonte": "zarc_aproximada_anuais" if z and z.get("aproximada") else "anual_legado_sem_zarc",
                "epoca_rotulo": "modo anterior (anual_legado): época sem valor informativo" if not z or not z.get("aproximada") else
                                "janela aproximada pelas anuais com ZARC, sem zoneamento oficial da cultura",
                "epoca_detalhe": z}
    motivo = ("ZARC desligado" if not p.usar_zarc else (z or {}).get("motivo") or "sem ZARC")
    return {"epoca_fonte": "ciclo_aproximado", "epoca_rotulo": ROTULO_CICLO_APROXIMADO + f" ({motivo})",
            "epoca_motivo": motivo, "epoca_agua": av.get("epoca_agua"),
            "epoca_criterio": "mínimo(temperatura do ciclo, chuva anual, chuva do ciclo / demanda); não é recomendação agronômica"}


def _janela_json(tab: dict, cid: str, clima, av_local: dict, p: Parametros) -> dict:
    res = av_local["culturas"][cid]["res"]
    av = av_local["culturas"][cid]["av"]
    j = {"definicao": "adequação = mínimo(nota de temperatura, nota de chuva) por início de plantio e ano",
         "melhor_inicio": res["inicio"], "decendio": res["decendio"], "duracao_dias": av["dur"],
         "ciclo_modo": p.ciclo_modo, "chuva_modo": p.chuva_modo,
         "inicios_equivalentes": [ciclo.data_do_inicio(k, p.passo_inicio_dias) for k in res["plato"]],
         "adequacao_media": round(res["adeq_media"], 3),
         "adequacao_entre_anos": {"p10": round(res["adeq_p10"], 3), "p50": round(res["adeq_p50"], 3),
                                  "p90": round(res["adeq_p90"], 3)},
         "fracao_anos_viaveis": round(res["p_ano_viavel"], 3),
         "temp_media_ciclo_c": round(res["tmedia_ciclo"], 2), "chuva_ciclo_mm": round(res["chuva_ciclo_mm"], 1),
         "chuva_comparada_mm": round(res["chuva_comparada_mm"], 1),
         "chuva_comparada_janela_dias": av["dur_chuva"],
         "ciclo_fonte": p.ciclo_fonte, "ciclo_referencia": {k: v for k, v in av["ciclo_info"].items() if k != "ecocrop_min_max"},
         "ciclo_ecocrop_min_max": av["ciclo_info"].get("ecocrop_min_max"),
         "anos": av_local["anos"]}
    j.update(_origem_epoca(av, p))
    sens = {}
    for m in ("min", "max"):
        if m == p.ciclo_modo:
            continue
        p2 = replace(p, ciclo_modo=m)
        a2 = ciclo.notas_ciclo(tab, cid, clima, p2)
        if a2["estado"] != "avaliavel":
            continue
        mask = av_local["ok"] & a2["valido"].all(axis=1)
        if mask.sum() < p.min_anos:
            sens[m] = None
            continue
        r2 = ciclo.resumir(a2, mask, p2)
        sens[m] = {"duracao_dias": a2["dur"], "melhor_inicio": r2["inicio"], "adequacao_media": round(r2["adeq_media"], 3)}
    j["sensibilidade_ciclo"] = sens
    dem = _v(tab, cid, "demanda_hidrica_mm_ciclo")
    j["chuva_sobre_demanda_hidrica"] = (None if dem is None else round(res["chuva_ciclo_mm"] / dem, 2))
    j["atendimento_hidrico_nota"] = ("INFORMAÇÃO (decisão do usuário): chuva do ciclo sobre a demanda da tabela; não entra no "
                                     "ranking nem na nota de chuva. ETc = Kc x ETo não está no motor (só no experimento).")
    j["demanda_hidrica_mm_ciclo"] = dem
    return j


def _faixa_json(i_sim: int, cid: str, sim: dict, ids_sim: list[str], cobertura: dict, p: Parametros,
                anos: list, nome_rank: list[str]) -> dict:
    """Bloco `faixa_incerteza` (contrato): principal (critérios comuns) + complemento com N/palha."""
    pr, co = sim["principal"], sim["completo"]
    out = {"min": round(float(pr["score_lo"][i_sim]), 1), "max": round(float(pr["score_hi"][i_sim]), 1),
           "score_p10": None, "score_p90": None}
    out["score_p10"], out["score_p90"] = out["min"], out["max"]
    out["score_p50"] = round(float(pr["score_mediana"][i_sim]), 1)
    out["percentis"] = [p.percentil_baixo, p.percentil_alto]
    out["criterios_ranking"] = pr["criterios"]
    out["cobertura"] = cobertura
    for rot, bloco in (("principal", pr), ("completo", co)):
        d = {}
        if cid in nome_rank and bloco["ranking"] is not None:
            j = list(bloco["r_idx"]).index(i_sim)
            rk = bloco["ranking"]
            d = {"posicao_p10": int(rk["pos_p_baixo"][j]), "posicao_p90": int(rk["pos_p_alto"][j]),
                 f"p_top{p.top_n}": round(float(rk["p_topo"][j]), 3), "p_1o": round(float(rk["p_1o"][j]), 3),
                 "posicao_media": round(float(rk["pos_media"][j]), 2),
                 "aceitabilidade_posicao": [round(float(x), 3) for x in rk["aceit"][j]],
                 "empate_tecnico_com": [ids_sim[bloco["r_idx"][q]] for q in bloco["empates"][j]]}
            d["empate_tecnico"] = bool(d["empate_tecnico_com"])
        if rot == "principal":
            out.update(d)
        else:
            d.update({"criterios": bloco["criterios"], "score_p10": round(float(bloco["score_lo"][i_sim]), 1),
                      "score_p90": round(float(bloco["score_hi"][i_sim]), 1),
                      "score_p50": round(float(bloco["score_mediana"][i_sim]), 1)})
            out["complemento_n_palha"] = d
    out.update({"metodo": "Monte Carlo estilo SMAA-2: pesos (Dirichlet) + lacunas ~ U[0,1] + ano do clima",
                "n_sorteios": p.n_sorteios, "semente": p.semente, "anos_clima": anos, "leitura": incerteza.LEITURA})
    return out


def gerar_cenarios(perfil: dict, cultura_atual: str, tabela: dict | None = None, n_alternativas: int = 2,
                   clima: ciclo.ClimaPonto | None = None, params: Parametros | None = None, regras=None) -> list[dict]:
    """[cenário da cultura atual] + as `n_alternativas` melhores viáveis (contrato JSON, seção 7).

    perfil: {"local": str, ...} (informativo). clima: série diária do ponto (obrigatória): chuva e temperatura são
    avaliadas DENTRO do ciclo, para cada início de plantio e cada ano (ver ciclo.py). params: ver parametros.py.
    """
    if clima is None:
        raise ValueError("gerar_cenarios exige `clima` (série diária do ponto): o motor avalia o ciclo, não a média anual")
    p = params or Parametros()
    tab = tabela if tabela is not None else carregar()
    if cultura_atual not in tab:
        raise KeyError(f"cultura atual '{cultura_atual}' não está na tabela")
    loc = perfil.get("local")
    av = avaliar_local(tab, clima, p)
    cs = av["culturas"]
    cand = [c for c in tab if c != cultura_atual and cs[c]["estado"] == "viavel"]
    lac_regras: list[str] = []
    if regras is not None:       # regras duras do agricultor (src/culturas/regras_duras.py): o caminho [atual, c] precisa respeitá-las
        from . import regras_duras as rd
        fam = {c: _v(tab, c, "familia_botanica") for c in tab}
        rd.validar(regras, tab)
        ok_, fora_ = rd.separar([(cultura_atual, c) for c in cand], fam, regras)
        cand = [s[1] for s in ok_]
        if fora_:
            lac_regras.append("Regras do agricultor (duras) tiraram %d caminho(s): %s" % (
                len(fora_), "; ".join(f"{d['sequencia'][1]} ({', '.join(d['motivos'])})" for d in fora_)))
    atual_ok = cs[cultura_atual]["res"] is not None
    ids_sim = ([cultura_atual] if atual_ok else []) + cand
    lacunas_gerais = list(clima.lacunas) + lac_regras
    excl_ind = [c for c in tab if c != cultura_atual and cs[c]["estado"] == "indeterminada"]
    if excl_ind:
        lacunas_gerais.append("Não avaliáveis por falta de dado/clima (fora do ranking, visíveis como indeterminadas): "
                              + ", ".join(sorted(excl_ind)))
    if av["anos"][2] < clima.ano_fim - clima.ano_ini + 1:
        lacunas_gerais.append(f"clima: {av['anos'][2]} de {clima.ano_fim - clima.ano_ini + 1} anos entraram "
                              "(só anos em que todos os ciclos avaliados estão completos).")
    # ---- notas por critério e simulação
    notas = {}
    sim = None
    pr_crit: list[str] = []
    if ids_sim:
        est = _notas_estaticas(tab, cultura_atual, ids_sim)
        n_a = av["anos"][2]
        T = np.full((len(ids_sim), len(CRITERIOS), n_a), np.nan)
        for i, c in enumerate(ids_sim):
            r = cs[c]["res"]
            T[i, CRITERIOS.index("temperatura"), :] = r["nt_por_ano"]
            T[i, CRITERIOS.index("chuva"), :] = r["nr_por_ano"]
            notas[c] = {"temperatura": float(np.mean(r["nt_por_ano"])), "chuva": float(np.mean(r["nr_por_ano"])), **est[c]}
            for k in ("familia_diferente", "n_na_biomassa", "palha"):
                if est[c][k] is not None:
                    T[i, CRITERIOS.index(k), :] = est[c][k]
        k_pr = _criterios_ranking(T)
        pr_crit = [CRITERIOS[k] for k in k_pr]
        ranqueia = np.array([c != cultura_atual for c in ids_sim])
        sim = incerteza.simular(T, CRITERIOS, pr_crit, ranqueia, p)
    # ---- escolha das alternativas: P(top-N), posição média, e (empate exato) sorteio com semente fixa; nunca alfabético
    escolhidas, corte_empatado, corte_por_consorcio = [], False, False
    if sim is not None and cand and sim[p.bloco_ranking]["ranking"] is not None:
        rk = sim[p.bloco_ranking]["ranking"]
        perm = np.random.default_rng(p.semente + 1).permutation(len(cand))
        if p.consorcio_modo == "desempate":      # critério secundário OPCIONAL (docs/29): só quebra EMPATE EXATO; padrão 'sem' não passa por aqui
            from . import consorcio as _cons
            resp = [0 if _cons.tem_respaldo(cultura_atual, c) else 1 for c in cand]
        else:
            resp = [0] * len(cand)
        chave = [(-round(float(rk["p_topo"][j]), 9), round(float(rk["pos_media"][j]), 9), resp[j], int(perm[j])) for j in range(len(cand))]
        ordem = sorted(range(len(cand)), key=lambda j: chave[j])
        escolhidas = [cand[j] for j in ordem[:n_alternativas]]
        if len(ordem) > n_alternativas:
            a, b = chave[ordem[n_alternativas - 1]], chave[ordem[n_alternativas]]
            corte_empatado = a[:2] == b[:2]
            corte_por_consorcio = corte_empatado and a[2] != b[2]
    if len(escolhidas) < n_alternativas:
        lacunas_gerais.append(f"Só {len(escolhidas)} alternativa(s) viável(is) com os dados disponíveis (pedido: {n_alternativas}).")
    cobertura_pr = None
    if pr_crit:
        cobertura_pr = {"ranking_principal": {"criterios": pr_crit, "peso_coberto": round(sum(PESOS[k] for k in pr_crit), 3),
                                              "peso_total": round(sum(PESOS.values()), 3)}}
    cenarios = []
    for c in [cultura_atual] + escolhidas:
        r = cs[c]
        lac = list(lacunas_gerais) + list(r["lacunas"])
        lac += _avisos_ciclo(tab, c, r["av"])
        riscos = list(RISCOS_FIXOS)
        if r["estado"] != "viavel":
            riscos.insert(0, f"Viabilidade da cultura atual: {r['estado']} ({'; '.join(r['motivos'] + r['lacunas'])}).")
        if r["res"] is None:
            cenarios.append({"local": loc, "cultura_atual": cultura_atual, "rotacao": [cultura_atual, c], "score": None,
                             "faixa_incerteza": None, "criterios": {}, "lacunas": lac + ["cultura não avaliada: sem faixa/ciclo/clima"],
                             "riscos_revisao_local": riscos, "trechos": [], "viabilidade": r["estado"], "pesos_usados": {},
                             "suposicoes": _suposicoes_base(p) + p.suposicoes() + _suposicoes_ciclo(tab, c, r, p), "aviso": AVISO})
            continue
        i = ids_sim.index(c)
        nt = notas[c]
        usados = {k: PESOS[k] for k in pr_crit}
        sem_nota = [k for k in CRITERIOS if nt.get(k) is None]
        cob_c = {"peso_coberto": round(sum(PESOS[k] for k in CRITERIOS if nt.get(k) is not None), 3),
                 "peso_total": round(sum(PESOS.values()), 3), "criterios_sem_dado": sem_nota}
        cobertura = dict(cobertura_pr or {}, completa=cob_c)
        # `chuva_ciclo_mm` do perfil = a chuva efetivamente comparada à faixa (anual no modo 'anual'; ver janela_plantio)
        perfil_ciclo = {"temp_media_c": r["res"]["tmedia_ciclo"], "chuva_ciclo_mm": r["res"]["chuva_comparada_mm"]}
        crit_json = _criterios_json(tab, c, nt, perfil_ciclo, cultura_atual)
        for k, d in crit_json.items():
            d["no_ranking_principal"] = k in pr_crit
            if k in ("temperatura", "chuva") and d.get("valor") is not None:
                dj = r["av"]["dur"] if (k == "temperatura" or p.chuva_modo == "ciclo") else r["av"]["dur_chuva"]
                d["janela"] = f"início {r['res']['inicio']}, {dj} dias, média de {av['anos'][2]} anos"
        lac += [f"{k}: sem dado (lacuna); no complemento do Monte Carlo vale como incerteza U[0,1], fora do ranking principal"
                for k in sem_nota if k not in pr_crit]
        fx = _faixa_json(i, c, sim, ids_sim, cobertura, p, av["anos"], [x for x in ids_sim if x != cultura_atual])
        if fx.get("empate_tecnico"):
            lac.append("Empate técnico (intervalos de score p%g-p%g se sobrepõem) com: %s. A ordem entre elas não tem base nos dados."
                       % (p.percentil_baixo, p.percentil_alto, ", ".join(fx["empate_tecnico_com"])))
        if c in escolhidas and corte_por_consorcio:
            lac.append("Corte das alternativas em empate exato (mesmo P(top-N) e posição média): desempatado pelo critério opcional 'consórcio com "
                       "respaldo publicado' (consorcio_modo='desempate'). Isso não significa que a escolhida seja melhor.")
        elif c in escolhidas and corte_empatado:
            lac.append("Corte das alternativas em empate exato (mesmo P(top-N) e posição média): escolha por sorteio com "
                       "semente fixa, não por ordem alfabética nem por critério agronômico.")
        riscos_c = riscos
        cenarios.append({
            "local": loc, "cultura_atual": cultura_atual, "rotacao": [cultura_atual, c],
            "score": _score_base(PESOS, pr_crit, nt), "faixa_incerteza": fx, "criterios": crit_json,
            "lacunas": lac, "riscos_revisao_local": riscos_c, "trechos": [], "viabilidade": r["estado"],
            "pesos_usados": usados, "janela_plantio": _janela_json(tab, c, clima, av, p),
            "ranking_nota": LEITURA_RANKING, "suposicoes": _suposicoes_base(p) + p.suposicoes() + _suposicoes_ciclo(tab, c, r, p),
            "aviso": AVISO})
    if p.consorcio_modo != "sem":                # evidência de consórcio (docs/29); não altera nota, faixa nem ordem; padrão 'sem' não passa por aqui
        from . import consorcio as _cons
        _cons.anexar(cenarios, p.consorcio_modo)
    return cenarios


CAMPOS_CONTRATO = ["local", "cultura_atual", "rotacao", "score", "faixa_incerteza", "criterios", "lacunas",
                   "riscos_revisao_local", "trechos"]


def validar_cenario(c: dict[str, Any]) -> list[str]:
    """Erros do cenário: campos do contrato, aviso e nota sem fonte+URL+página."""
    erros = [f"campo ausente: {k}" for k in CAMPOS_CONTRATO if k not in c]
    if c.get("aviso") != AVISO:
        erros.append("aviso 'a avaliar com técnico local' ausente")
    for nome, d in (c.get("criterios") or {}).items():
        if d.get("nota") is not None and not (d.get("fonte") and d.get("url") and d.get("pagina")):
            erros.append(f"critério {nome}: nota sem fonte/url/página")
        if d.get("valor") is None and d.get("nota") is not None:
            erros.append(f"critério {nome}: nota sem valor bruto")
    return erros
