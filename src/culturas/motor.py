"""Motor de rotação: filtro de viabilidade (faixas EcoCrop) -> pontuação ponderada -> seleção.

Princípios (docs/01 seção 3): nenhum número inventado; critério sem dado vira lacuna visível e fica
FORA da pontuação (pontuação renormalizada, declarada); o motor apoia, não decide.

Suposições do motor (NÃO são dado de fonte; revisar com o usuário):
- M1 pesos dos critérios (PESOS) são uma proposta de projeto, não vêm de literatura.
- M2 nota climática: 0 fora da faixa absoluta, 1 na faixa ótima, linear entre as duas (mesma forma
  trapezoidal do modelo EcoCrop descrito no README do OpenCLIM). Aplicada à temperatura MÉDIA do período.
- M3 a chuva do perfil é comparada à faixa de chuva do EcoCrop como chuva acumulada no ciclo (leitura do
  código OpenCLIM); a definição oficial da FAO (anual vs. ciclo) não foi verificada.
- M4 notas de N e palha: min-max entre as candidatas com dado; valores vêm de estudos diferentes
  (locais e idades de corte diferentes), logo a comparação é só indicativa.
- M5 'familia_diferente': 1 se a família botânica (EcoCrop) difere da cultura atual, 0 se igual.
"""
from __future__ import annotations

from typing import Any

from .tabela_culturas import carregar

AVISO = "Cenário a avaliar com técnico local. Apoio à decisão; não é recomendação nem previsão."

PESOS = {"temperatura": 0.25, "chuva": 0.25, "n_na_biomassa": 0.20, "palha": 0.15, "familia_diferente": 0.15}

UNID = {"temperatura": "°C", "chuva": "mm", "n_na_biomassa": "kg/ha", "palha": "kg/ha", "familia_diferente": "texto"}

SUPOSICOES = [
    "Pesos dos critérios são proposta de projeto (não vêm de fonte).",
    "Nota climática trapezoidal (0 fora da faixa absoluta, 1 na ótima), aplicada à temperatura média do período.",
    "Chuva do perfil comparada à faixa EcoCrop como chuva acumulada no ciclo (definição oficial FAO não verificada).",
    "Notas de N e palha vêm de estudos distintos (local e idade de corte diferentes): comparação só indicativa.",
]

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


def gerar_cenarios(perfil: dict, cultura_atual: str, tabela: dict | None = None, n_alternativas: int = 2) -> list[dict]:
    """Devolve [cenário da cultura atual] + as `n_alternativas` melhores viáveis (contrato JSON, seção 7).

    perfil: {"local": str, "temp_media_c": float|None, "chuva_ciclo_mm": float|None}
    """
    tab = tabela if tabela is not None else carregar()
    if cultura_atual not in tab:
        raise KeyError(f"cultura atual '{cultura_atual}' não está na tabela")
    via = {c: viabilidade(tab, c, perfil) for c in tab}
    cand = [c for c in tab if c != cultura_atual and via[c]["estado"] == "viavel"]
    ids = [cultura_atual] + cand
    pont = pontuar(tab, perfil, cultura_atual, ids)
    ranque = sorted(cand, key=lambda c: (-(pont[c]["score"] if pont[c]["score"] is not None else -1), c))
    escolhidas = ranque[:n_alternativas]
    lacunas_gerais = []
    if len(escolhidas) < n_alternativas:
        lacunas_gerais.append(f"Só {len(escolhidas)} alternativa(s) viável(is) com os dados disponíveis (pedido: {n_alternativas}).")
    excl_ind = [c for c in tab if c != cultura_atual and via[c]["estado"] == "indeterminada"]
    if excl_ind:
        lacunas_gerais.append("Não avaliáveis por falta de dado/perfil (fora do ranking): " + ", ".join(sorted(excl_ind)))
    cenarios = []
    for c in [cultura_atual] + escolhidas:
        p = pont[c]
        lac = list(lacunas_gerais) + [f"{k}: critério sem nota (dado ausente ou sem comparação); fora do score" for k in p["criterios_sem_nota"]]
        lac += via[c]["lacunas"]
        lac.append("faixa_incerteza: não calculada (nenhum modelo de incerteza ligado a este motor).")
        lac.append("trechos: sem evidência recuperada (RAG não ligado a este motor).")
        riscos = list(RISCOS_FIXOS)
        if via[c]["estado"] != "viavel":
            riscos.insert(0, f"Viabilidade da cultura atual: {via[c]['estado']} ({'; '.join(via[c]['motivos'] + via[c]['lacunas'])}).")
        cenarios.append({
            "local": perfil.get("local"),
            "cultura_atual": cultura_atual,
            "rotacao": [cultura_atual, c],
            "score": p["score"],
            "faixa_incerteza": None,
            "criterios": _criterios_json(tab, c, p["notas"], perfil, cultura_atual),
            "lacunas": lac,
            "riscos_revisao_local": riscos,
            "trechos": [],
            "viabilidade": via[c]["estado"],
            "pesos_usados": p["pesos_usados"],
            "suposicoes": SUPOSICOES,
            "aviso": AVISO,
        })
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
