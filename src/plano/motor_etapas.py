"""Etapas 2 (Recomendação) e 3 (Clima e Época) do plano: reaproveitam o motor e o calendário que já existem (nada novo é calculado aqui).

Cada função recebe (ponto_id, cultura_id) e devolve {"itens": [...], "lacunas": [...]}. Os imports pesados ficam DENTRO das funções (a rota só
os usa quando alguém pede o plano). Qualquer falha vira lacuna visível em `montar.py`, nunca um número inventado.
Itens daqui têm status "calculado" (vêm do motor, não de uma publicação).
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache

from src.plano.texto_simples import datas_decendios, datas_quinzenas, quantos_anos

_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
FONTE_MOTOR = "Sulco: clima do local (NASA, 2001–2024) e zoneamento do Ministério da Agricultura"
FONTE_DIAG = "Sulco: clima do local (NASA, 2001–2024)"
_VIAB = {"viavel": "Os dados do clima do local indicam que a cultura é viável."}
_VIAB_CURTO = {"viavel": "viável", "inviavel": "inviável"}


def _item(atributo: str, rotulo: str, valor: str, fonte: str, contexto: str = "", unidade: str = "") -> dict:
    return {"atributo": atributo, "rotulo": rotulo, "valor": valor, "unidade": unidade, "status": "calculado",
            "fonte": {"nome": fonte, "pagina": None, "url": None}, "trecho": None, "contexto": contexto, "requer_tecnico": False,
            "referencia_da_fonte": False, "experimento": False}


def _fonte_limpa(texto: str) -> str:
    """Fonte sem caminho interno do projeto: 'FAO-56 (...), cap. 6, Tabela 11, via data/culturas/x.csv' -> 'FAO-56 (...), cap. 6, Tabela 11'."""
    return texto.split(" via ")[0].strip()


# Adubos verdes não são para colher grão: nunca viram "cultura de exemplo" do plano.
ADUBOS_VERDES = frozenset({"crotalaria_juncea", "mucuna", "feijao_de_porco"})


SOLOS = ("qualquer", "arenoso", "medio", "argiloso")


@lru_cache(maxsize=256)
def culturas_viaveis(ponto_id: str, solo: str = "qualquer") -> tuple[dict, ...]:
    """Plantas indicadas para o local e o solo informado, da mais para a menos indicada: dentro do zoneamento para esse solo, depois mais anos
    em que o clima comportou o ciclo, depois mais decêndios de janela. Usa clima (NASA POWER 2001–2024) e ZARC; não considera preço nem mercado."""
    from src.api import main as A
    from src.app import mvp as M
    from src.culturas.motor import gerar_cenarios
    from src.culturas.parametros import Parametros
    from src.plano import dados

    from src.culturas import calendario_plantio as CP
    from src.culturas import zarc as Z

    tab = A.tabela()
    geo = Z.geocodigo_do_ponto(ponto_id)
    out = []
    for cid in sorted({c for c, _ in dados.carregar()}):
        if cid not in tab or cid in ADUBOS_VERDES:
            continue
        # n_sorteios mínimo: aqui só interessa a viabilidade climática (determinística), não a faixa de incerteza do ranking.
        cens = gerar_cenarios({"local": ponto_id}, cid, tab, clima=A.clima_ponto(ponto_id), params=Parametros(usar_zarc=M.ZARC_PADRAO, n_sorteios=100))
        atual = next((c for c in cens if c["rotacao"][1] == cid), None)
        if atual is None or atual.get("viabilidade") != "viavel":
            continue
        frac = (atual.get("janela_plantio") or {}).get("fracao_anos_viaveis")
        jz = Z.janela(geo, cid, 30, solo)
        perm = jz.get("permitido")
        janela = CP.faixas_decendios(perm) if perm is not None else None
        janela_datas = datas_decendios(perm) if perm is not None and any(perm) else None
        n_dec = int(jz.get("n_decendios") or 0) if perm is not None else 0
        out.append({"cultura": cid, "nome": tab[cid]["cultura_pt"], "fracao": float(frac) if isinstance(frac, (int, float)) else 0.0, "janela": janela, "janela_datas": janela_datas,
                    "n_decendios": n_dec, "no_zoneamento": perm is not None and n_dec > 0})
    return tuple(sorted(out, key=lambda x: (not x["no_zoneamento"], -x["fracao"], -x["n_decendios"], x["nome"])))


def cultura_exemplo(ponto_id: str, solo: str = "qualquer") -> str | None:
    """A planta mais indicada para o local e o solo (o plano segue por ela)."""
    return next((c["cultura"] for c in culturas_viaveis(ponto_id, solo) if c["cultura"] not in ADUBOS_VERDES), None)


def _quinzena(q: int) -> str:
    return f"{'1ª' if q % 2 == 1 else '2ª'} quinzena de {_MESES[(q - 1) // 2]}"


def _faixas_quinzenas(qs: list[int]) -> str:
    qs = sorted(set(qs))
    if not qs:
        return ""
    blocos, ini, ant = [], qs[0], qs[0]
    for q in qs[1:] + [None]:
        if q is not None and q == ant + 1:
            ant = q
            continue
        blocos.append(_quinzena(ini) if ini == ant else f"{_quinzena(ini)} até a {_quinzena(ant)}")
        if q is not None:
            ini = ant = q
    return "; ".join(blocos)


def recomendacao(ponto_id: str, cultura_id: str, solo: str = "qualquer") -> dict:
    """Etapa 2 (o que plantar): as plantas mais indicadas para o local e o solo informado, com a janela de plantio do zoneamento. Base: clima e zoneamento, sem preço."""
    from src.api import main as A
    from src.app import mvp as M
    from src.culturas.motor import gerar_cenarios
    from src.culturas.parametros import Parametros

    tab = A.tabela()
    nome = lambda cid: tab[cid]["cultura_pt"] if cid in tab else cid   # noqa: E731
    cens = gerar_cenarios({"local": ponto_id}, cultura_id, tab, clima=A.clima_ponto(ponto_id), params=Parametros(usar_zarc=M.ZARC_PADRAO))
    atual = next((c for c in cens if c["rotacao"][1] == cultura_id), None)
    itens, lacunas = [], []
    if atual is None:
        return {"itens": [], "lacunas": ["o motor não devolveu a cultura escolhida para este local"]}
    viaveis = list(culturas_viaveis(ponto_id, solo))
    linhas = viaveis[:6]
    if cultura_id not in {c["cultura"] for c in linhas}:   # cultura pedida fora do top: aparece primeiro, com o que o motor diz dela
        j = atual.get("janela_plantio") or {}
        frac = j.get("fracao_anos_viaveis")
        linhas = [{"cultura": cultura_id, "nome": nome(cultura_id), "fracao": frac if isinstance(frac, (int, float)) else None, "janela": None,
                   "viavel": atual.get("viabilidade") == "viavel"}] + linhas[:5]
    for n, c in enumerate(linhas, 1):
        if c.get("viavel") is False:
            valor = "O clima daqui não ajuda muito esta planta. Converse com o técnico."
        else:
            frases = []
            if isinstance(c.get("fracao"), (int, float)):
                frases.append(quantos_anos(c["fracao"]))
            if c.get("janela_datas"):
                frases.append(f"Época de plantio{'' if solo == 'qualquer' else ' (solo ' + solo.replace('medio', 'médio') + ')'}: {c['janela_datas']}")
            valor = (". ".join(frases) + ".") if frases else "Pode ser plantada aqui."
        itens.append(_item(f"cultura_recomendada_{n}", c["nome"], valor, FONTE_MOTOR,
                           "Pelo clima daqui nos últimos anos e pelo zoneamento do Ministério da Agricultura. Confirme com o técnico."))
    lacunas.append("Não há preço, custo nem mercado: a comparação não considera renda.")
    return {"itens": itens, "lacunas": lacunas}


def clima_epoca(ponto_id: str, cultura_id: str, hoje: date | None = None) -> dict:
    """Etapa 3: janela do zoneamento (ZARC), ciclo da cultura, chuva e período seco do local."""
    from src.api import main as A
    from src.culturas import calendario_plantio as CP
    from src.culturas import zarc as Z

    hoje = hoje or date.today()
    itens, lacunas = [], []
    geo = Z.geocodigo_do_ponto(ponto_id)
    j = Z.janela(geo, cultura_id, 30, "qualquer")
    if j.get("permitido") is None:
        lacunas.append(f"Zoneamento de risco climático: {j.get('motivo') or 'sem janela para esta cultura e local'}.")
    else:
        itens.append(_item("janela_zarc", "Época para plantar", datas_decendios(j["permitido"]) if any(j["permitido"]) else "fora do período indicado",
                           "Ministério da Agricultura, zoneamento de risco climático (sequeiro)",
                           "São as datas com menos risco de perder a lavoura por causa da chuva."))
    try:
        calc = CP.calcular(ponto_id, [{"cultura": cultura_id, "quando": {"data": hoje.isoformat()}, "manejo": "sequeiro"}], hoje, blocos=set())
        ciclo = calc["plantios"][0].get("ciclo") or {}
        if ciclo.get("disponivel"):
            itens.append(_item("ciclo_cultura", "Da semente até a colheita", f"cerca de {ciclo['dias_ref']} dias (entre {ciclo['dias_min']} e {ciclo['dias_max']}, conforme a semente)",
                               _fonte_limpa(ciclo.get("origem") or "FAO-56"), "Valor de referência; a sua semente pode levar mais ou menos tempo."))
        else:
            lacunas.append("Duração do ciclo: sem dado para esta cultura.")
    except Exception:   # noqa: BLE001 - o cálculo falhou: vira lacuna, nunca número inventado
        lacunas.append("Duração do ciclo: o cálculo não está disponível neste momento.")
    d = A.diagnosticos().get(ponto_id) or {}
    ver = d.get("veranicos") or {}
    qs = ver.get("quinzenas_estacao_chuvosa") or []
    if qs:
        itens.append(_item("estacao_chuvosa", "Quando costuma chover mais", datas_quinzenas(qs), FONTE_DIAG, "Na média dos últimos anos; cada ano é diferente."))
    dist = ver.get("distribuicao") or {}
    if dist.get("mediana") is not None:
        itens.append(_item("periodo_seco", "Veranico (dias seguidos sem chuva no meio das águas)",
                           f"Costuma ficar uns {round(dist['mediana'])} dias sem chuva; em 1 de cada 10 anos passa de {round(dist['p90'])} dias; o maior foi {round(dist['max'])} dias.",
                           FONTE_DIAG, "Conta como dia sem chuva o que teve menos de 1 mm."))
    else:
        lacunas.append("Período seco: sem dado para este local.")
    lacunas.append("Não há previsão de chuva: o plano mostra o que costuma acontecer, não o que vai acontecer.")
    return {"itens": itens, "lacunas": lacunas}
