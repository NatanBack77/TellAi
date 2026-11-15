"""Gerente de diálogo DETERMINÍSTICO da conversa consultiva (sem LLM): estado, próxima ação, perguntas, chips e textos de acolhida.

Estado da conversa = JSON simples mantido pelo CHAMADOR (o servidor não guarda nada). Só guarda ENTIDADES extraídas das mensagens (culturas, ordem,
foco, regras, ponto, manejo); o histórico em texto NUNCA é guardado nem usado como fonte de fato. Chaves:
  culturas[], ordem_dita, n_safras, foco, proibidas[], ponto_id, manejo, tipo, confirmado, pendente, fora_da_lista[], ja_perguntou_foco, turnos.
`pendente` = o que o assistente perguntou por último: 'confirmar' | 'foco' | 'ordem' | 'municipio' | 'culturas' | 'refazer' | None.

Ações: 'responder' (há o que dizer com os dados), 'perguntar' (UMA coisa por vez), 'confirmar' (o entendimento, quando a extração tem baixa
confiança), 'recusar' (lucro, produtividade, previsão do tempo, tentativa de mudar as regras).
"""
from __future__ import annotations

import json
from typing import Any

from .intencao import FOCOS, ROTULO_FOCO

VERSAO_ESTADO = 1
PENDENTES = ("confirmar", "foco", "ordem", "municipio", "culturas", "refazer", "ordem_texto",
             # calendário de plantio (um por vez): cultura, mês, começo/meio/fim, ciclo da semente, confirmação, município
             "plantio_cultura", "plantio_mes", "plantio_parte", "plantio_ciclo", "plantio_confirmar", "plantio_refazer", "plantio_municipio", "plantio_oferta")
PENDENTES_PLANTIO = tuple(p for p in PENDENTES if p.startswith("plantio_"))
MAX_PLANTIOS_ESTADO = 8
MAX_FILA = 3
TEMAS_CALENDARIO = ("resumo", "chuva", "verde", "solo", "proximas", "zarc", "colheita")
MAX_CULTURAS = 4
TIPOS = ("avaliar", "sugerir", "viabilidade", "explicar", "previsao", "duvida_geral")
MANEJOS = ("sequeiro", "irrigado")


def estado_inicial() -> dict:
    return {"v": VERSAO_ESTADO, "culturas": [], "ordem_dita": False, "n_safras": None, "foco": None, "proibidas": [], "ponto_id": None,
            "manejo": None, "tipo": None, "confirmado": False, "pendente": None, "fora_da_lista": [], "ja_perguntou_foco": False, "turnos": 0,
            "plantios": [], "rascunho": None, "fila": [], "cal_idx": None, "cal_vistos": [], "cal_oferta": None,
            "ult_cultura": [], "numeros_permitidos": False, "ult_resposta": "", "aviso_limite_dito": False, "pergunta_pendente": ""}      # ult_cultura: culturas da última pergunta livre (para "e quantos dias ele demora?"); não entra no ciclo


def normalizar_estado(e: Any, ids_validos: set[str] | None = None, pontos_validos: set[str] | None = None) -> dict:
    """Estado vindo do chamador (JSON, possivelmente adulterado) => estado válido. Chave/valor desconhecido é descartado, nunca executado."""
    base = estado_inicial()
    if isinstance(e, str):
        try:
            e = json.loads(e)
        except ValueError:
            e = {}
    if not isinstance(e, dict):
        return base

    def ids(x):
        if not isinstance(x, list):
            return []
        out = [c for c in x if isinstance(c, str) and (ids_validos is None or c in ids_validos)]
        return list(dict.fromkeys(out))
    base["culturas"] = ids(e.get("culturas"))[:MAX_CULTURAS * 2]
    base["proibidas"] = ids(e.get("proibidas"))
    base["ult_cultura"] = ids(e.get("ult_cultura"))[:2]
    base["numeros_permitidos"] = bool(e.get("numeros_permitidos"))      # só do último turno
    base["aviso_limite_dito"] = bool(e.get("aviso_limite_dito"))        # o aviso 'solo, semente e preço eu ainda não tenho' sai UMA vez por conversa
    ur = e.get("ult_resposta")                                          # resumo curto da última resposta (para 'não entendi'); só é repetido ao usuário, nunca vai à IA
    base["ult_resposta"] = " ".join(ur.split())[:300] if isinstance(ur, str) else ""
    pp = e.get("pergunta_pendente")                                     # pergunta feita ANTES de eu pedir o município: respondo a ela quando o município chegar
    base["pergunta_pendente"] = " ".join(pp.split())[:300] if isinstance(pp, str) else ""
    base["ordem_dita"] = bool(e.get("ordem_dita")) and len(base["culturas"]) >= 2
    ns = e.get("n_safras")
    base["n_safras"] = ns if isinstance(ns, int) and not isinstance(ns, bool) and 1 <= ns <= MAX_CULTURAS else None
    base["foco"] = e.get("foco") if e.get("foco") in FOCOS else None
    pid = e.get("ponto_id")
    base["ponto_id"] = pid if isinstance(pid, str) and len(pid) < 60 and (pontos_validos is None or pid in pontos_validos) else None
    base["manejo"] = e.get("manejo") if e.get("manejo") in MANEJOS else None
    base["tipo"] = e.get("tipo") if e.get("tipo") in TIPOS else None
    base["confirmado"] = bool(e.get("confirmado"))
    base["ja_perguntou_foco"] = bool(e.get("ja_perguntou_foco"))
    base["pendente"] = e.get("pendente") if e.get("pendente") in PENDENTES else None
    fl = e.get("fora_da_lista")
    base["fora_da_lista"] = [x[:40] for x in fl if isinstance(x, str)][:6] if isinstance(fl, list) else []
    t = e.get("turnos")
    base["turnos"] = t if isinstance(t, int) and not isinstance(t, bool) and 0 <= t < 10_000 else 0
    _normalizar_calendario(base, e, ids_validos)
    return base


def rascunho_vazio() -> dict:
    """Plantio em construção (a conversa pergunta o que falta, uma coisa por vez). `ambiguo` = alternativas de um termo como 'feijão'."""
    return {"cultura": None, "ambiguo": None, "fora": None, "quando": None, "ciclo_dias": None, "ciclo_perguntado": 0, "parte_perguntada": False, "tentativas": 0}


def normalizar_rascunho(r: Any, ids_validos: set[str] | None = None) -> dict | None:
    """Rascunho vindo do chamador => rascunho válido (campo desconhecido ou inválido é descartado, nunca executado) ou None."""
    from src.culturas import calendario_plantio as CP
    if not isinstance(r, dict):
        return None
    out = rascunho_vazio()
    c = r.get("cultura")
    out["cultura"] = c if isinstance(c, str) and (ids_validos is None or c in ids_validos) else None
    amb = r.get("ambiguo")
    out["ambiguo"] = [x for x in amb if isinstance(x, str) and (ids_validos is None or x in ids_validos)][:3] if isinstance(amb, list) else None
    out["ambiguo"] = out["ambiguo"] or None
    f = r.get("fora")
    out["fora"] = f[:40] if isinstance(f, str) else None
    q = r.get("quando")
    out["quando"] = json.loads(json.dumps(q)) if isinstance(q, dict) and CP._erro_quando(q) is None else None
    cd = r.get("ciclo_dias")
    out["ciclo_dias"] = cd if isinstance(cd, int) and not isinstance(cd, bool) and CP.CICLO_MIN <= cd <= CP.CICLO_MAX else None
    cp, tt = r.get("ciclo_perguntado"), r.get("tentativas")
    out["ciclo_perguntado"] = cp if isinstance(cp, int) and not isinstance(cp, bool) and 0 <= cp <= 2 else int(bool(cp))
    out["tentativas"] = tt if isinstance(tt, int) and not isinstance(tt, bool) and 0 <= tt <= 3 else 0
    out["parte_perguntada"] = bool(r.get("parte_perguntada"))
    return out


def _normalizar_calendario(base: dict, e: dict, ids_validos: set[str] | None) -> None:
    from src.culturas import calendario_plantio as CP
    pl = e.get("plantios")
    if isinstance(pl, list):
        try:
            base["plantios"] = CP.validar_plantios(pl[:MAX_PLANTIOS_ESTADO], ids_validos if ids_validos is not None else _todas(pl))
        except ValueError:
            base["plantios"] = []
    base["rascunho"] = normalizar_rascunho(e.get("rascunho"), ids_validos)
    fila = e.get("fila")
    base["fila"] = [r for r in (normalizar_rascunho(x, ids_validos) for x in fila[:MAX_FILA]) if r] if isinstance(fila, list) else []
    i = e.get("cal_idx")
    base["cal_idx"] = i if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(base["plantios"]) else None
    v = e.get("cal_vistos")
    base["cal_vistos"] = [x for x in dict.fromkeys(v) if x in TEMAS_CALENDARIO] if isinstance(v, list) else []
    base["cal_oferta"] = e.get("cal_oferta") if e.get("cal_oferta") in TEMAS_CALENDARIO else None


def _todas(pl: list) -> set[str]:
    return {p.get("cultura") for p in pl if isinstance(p, dict) and isinstance(p.get("cultura"), str)}


def atualizar(estado: dict, ext: dict, ponto_id: str | None = None, perfil: dict | None = None, ids_validos: set[str] | None = None) -> dict:
    """Junta o que a mensagem trouxe ao estado. Cultura nova SUBSTITUI a lista (a não ser com 'também/além de'); foco novo substitui o antigo.
    Cultura proibida sai da lista. Mudou a lista de culturas => o entendimento volta a ser não confirmado."""
    e = json.loads(json.dumps(estado))
    antes = list(e["culturas"])
    novas = [c for c in ext["culturas"] if c not in ext["proibidas"]]
    if novas:
        if ext.get("adicionar") and e["culturas"]:
            e["culturas"] = list(dict.fromkeys(e["culturas"] + novas))
            e["ordem_dita"] = False
        else:
            e["culturas"] = novas
            e["ordem_dita"] = bool(ext["ordem_dita"])
    e["culturas"] = [c for c in e["culturas"] if c not in ext["proibidas"]][:MAX_CULTURAS * 2]
    if ext["proibidas"]:
        e["proibidas"] = list(dict.fromkeys(e["proibidas"] + ext["proibidas"]))
    if ext.get("n_safras"):
        e["n_safras"] = ext["n_safras"]
    if ext.get("foco"):
        e["foco"] = ext["foco"]
    if ext.get("manejo"):
        e["manejo"] = ext["manejo"]
    if ext.get("tipo") and ext["tipo"] != "duvida_geral":
        e["tipo"] = ext["tipo"]
    elif not e.get("tipo") and ext.get("tipo"):
        e["tipo"] = ext["tipo"]
    e["fora_da_lista"] = list(dict.fromkeys(ext["fora_da_lista"]))[:6]       # só vale para esta rodada
    pid = ponto_id or ext.get("ponto_id") or e.get("ponto_id")
    e["ponto_id"] = pid
    perfil = perfil if isinstance(perfil, dict) else {}
    if not e["manejo"] and perfil.get("manejo") in MANEJOS:
        e["manejo"] = perfil["manejo"]
    if e["culturas"] != antes:
        e["confirmado"] = False
    e["turnos"] += 1
    return e


def foco_efetivo(estado: dict, perfil: dict | None) -> tuple[str | None, bool]:
    """(foco, veio_do_perfil). A prioridade marcada no app só vale quando a conversa ainda não trouxe foco."""
    if estado.get("foco"):
        return estado["foco"], False
    p = (perfil or {}).get("prioridade")
    return ({"agua": "agua", "solo": "solo", "renda": "renda"}.get(p), True) if p in ("agua", "solo", "renda") else (None, False)


def proibidas_efetivas(estado: dict, perfil: dict | None, ids_validos: set[str] | None = None) -> list[str]:
    regras = (perfil or {}).get("regras") if isinstance((perfil or {}).get("regras"), dict) else {}
    extra = [c for c in (regras.get("proibidas") or []) if isinstance(c, str) and (ids_validos is None or c in ids_validos)]
    return list(dict.fromkeys(list(estado.get("proibidas") or []) + extra))


# ------------------------------------------------------------------------------------------------ textos
def chip(rotulo: str, texto: str | None = None) -> dict:
    return {"rotulo": rotulo, "texto": texto or rotulo}


CHIPS_FOCO = [chip("Economizar água", "Quero economizar água"), chip("Proteger o solo", "Quero proteger o solo"),
              chip("Uma renda extra", "Quero uma renda extra"), chip("Adubar com planta", "Quero adubar a terra com planta")]
CHIPS_CONFIRMA = [chip("Sim, está certo"), chip("Não, quero mudar", "Não, quero mudar")]
CHIPS_ORDEM = [chip("Ver a melhor ordem", "Ver a melhor ordem"), chip("Só ver se dão aí", "Só ver se dão certo aqui"), chip("Já tenho uma ordem", "Já tenho uma ordem")]
CHIPS_INICIO = [chip("O que dá para plantar aqui?"), chip("Quero economizar água"), chip("Quero montar um ciclo")]

PERGUNTA_FOCO = "Me diz uma coisa: o que pesa mais na sua roça, gastar menos água, cuidar da terra ou ganhar um dinheiro a mais?"
PERGUNTA_MUNICIPIO = "Para olhar os dados do seu local, preciso saber o município. Em que município fica a sua roça?"
PERGUNTA_ORDEM = "Você quer que eu veja a melhor ordem para essas culturas, ou só se elas dão certo no seu local?"
PERGUNTA_CULTURAS = "Quais culturas você pensa em colocar no ciclo? Pode dizer na ordem, por exemplo: primeiro milho, depois feijão."
PERGUNTA_ORDEM_TEXTO = "Qual é a ordem que você pensou? Por exemplo: primeiro milho, depois feijão-caupi."
TEXTO_REFAZER = "Sem problema. Me conta de novo: quais culturas você quer olhar, e em que ordem?"
TEXTO_VAZIA = "Pode escrever o que você quer saber. Por exemplo: \"o que dá para plantar aqui?\" ou \"se eu plantar milho e feijão, em que ordem é melhor?\""
TEXTO_LONGA = "Sua mensagem ficou grande para eu ler direito. Pode escrever de novo, mais curta, só com o que você quer plantar ou o que pesa mais para você?"
TEXTO_INJECAO = ("Eu só consigo ajudar com a escolha do que plantar, usando os dados do Sulco. As regras da ferramenta eu não posso mudar. "
                 "Quer me contar o que você pensa em plantar?")
TEXTO_LUCRO = ("Entendo que a renda pesa. O Sulco não tem dado de preço nem de custo, então não consigo dizer qual plantio paga mais, nem prever lucro. "
               "O que dá para ver com os dados é a água, o solo e se a cultura combina com o clima do seu local. Por onde você quer começar?")
TEXTO_PRODUTIVIDADE = ("Entendo a dúvida. Quanto vai colher eu não sei dizer: o Sulco não prevê colheita nem produtividade. "
                       "Posso mostrar o que os dados dizem de clima, água e solo para o que você quer plantar. Quer ver?")
TEXTO_CLIMA = ("Entendo a preocupação com a chuva. O Sulco não prevê o tempo: ele só mostra o que já aconteceu no seu local nos últimos anos. "
               "Quer ver o que os dados dizem sobre as épocas de plantio?")
CHIPS_RECUSA = [chip("Economizar água", "Quero economizar água"), chip("Proteger o solo", "Quero proteger o solo"), chip("O que dá para plantar aqui?")]
TEXTO_FRANQUEZA_SO_FORA = ("De {lista} ainda não temos dados: {verbo} na lista do Sulco. Posso olhar as culturas que o Sulco conhece, como milho, "
                           "feijão-caupi, sorgo, mandioca ou amendoim.")
FECHO = "Converse com o técnico."

ACOLHIDA_FOCO = {
    "agua": "Entendi, você quer gastar menos água.", "solo": "Entendi, você quer cuidar bem do solo.", "renda": "Entendi, a renda pesa para você.",
    "nitrogenio": "Entendi, você quer adubar a terra com a própria planta.", "palhada": "Entendi, você quer deixar o solo coberto com palha.",
    "pragas": "Entendi, você quer ter menos praga e doença.", "forragem": "Entendi, você precisa de comida para os animais.",
}


def lista_ptbr(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1] if itens else ""


def texto_ordem_simples(nomes: dict, ids: list[str]) -> str:
    ls = [str(nomes.get(c, c)).lower() for c in ids]
    if len(ls) == 1:
        return ls[0]
    return "primeiro " + ls[0] + ", depois " + ls[1] + "".join(f" e depois {x}" if i == len(ls) - 3 else f", depois {x}" for i, x in enumerate(ls[2:]))


def texto_entendido(estado: dict, nomes: dict, foco: str | None = None) -> str:
    """'Entendi: primeiro milho, depois feijão-caupi e depois crotalária juncea, pensando em economizar água.' (sem ponto final extra)"""
    partes = []
    cult = estado.get("culturas") or []
    if cult:
        partes.append(texto_ordem_simples(nomes, cult) if estado.get("ordem_dita") and len(cult) >= 2 else lista_ptbr([str(nomes.get(c, c)).lower() for c in cult]))
    s = "Entendi: " + (partes[0] if partes else "você quer ver o que dá para plantar")
    f = foco or estado.get("foco")
    if f:
        s += f", pensando em {ROTULO_FOCO[f].split(' (')[0]}"
    if estado.get("proibidas"):
        s += f", sem {lista_ptbr([str(nomes.get(c, c)).lower() for c in estado['proibidas']])}"
    return s


def acolhida(estado: dict, ext: dict, nomes: dict, foco: str | None) -> str:
    """Antes era uma frase que repetia o pedido ('Entendi, você quer olhar...'). Repetir o que a pessoa acabou de dizer soa robótico lido em voz alta:
    a resposta começa direto pela informação. Mantida (vazia) porque o texto padrão e os testes ainda a chamam."""
    return ""


# ================================================================================================ CALENDÁRIO DE PLANTIO (perguntas, uma por vez)
FEMININAS = {"mandioca", "palma_forrageira", "crotalaria_juncea", "mucuna", "mamona"}
MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def artigo(cid: str, tipo: str = "o") -> str:
    """'o'/'a', 'do'/'da' ou 'no'/'na' conforme a cultura."""
    fem = cid in FEMININAS
    return {"o": "a" if fem else "o", "do": "da" if fem else "do", "no": "na" if fem else "no"}[tipo]


def nome_com_artigo(cid: str, nomes: dict, tipo: str = "o") -> str:
    return f"{artigo(cid, tipo)} {str(nomes.get(cid, cid)).lower()}"


PERGUNTA_CULTURA_PLANTIO = "Qual cultura você plantou?"
PERGUNTA_FEIJAO = "Esse feijão é o feijão de corda (caupi) ou o feijão comum?"
PERGUNTA_PARTE = "Foi no começo, no meio ou no fim do mês?"
PERGUNTA_CICLO = "Você sabe quantos dias a sua semente leva até a colheita? Se não souber, tudo bem."
TEXTO_REFAZER_PLANTIO = "Sem problema. Me conta de novo: o que você plantou e quando?"
TEXTO_SEM_MES = ("Sem o mês eu não consigo olhar o calendário. Se lembrar, me diga o mês, ou a época: por exemplo, no inverno, que aqui é a época de chuva. "
                 "Em que mês foi?")
TEXTO_FALTA_DADO_CULTURA = ("De {nome} ainda não temos dados: essa cultura não está na lista do Sulco, então não consigo olhar o calendário dela. "
                            "Posso olhar milho, feijão-caupi, sorgo, mandioca ou amendoim. Qual você plantou?")
OFERTAS_CALENDARIO = {"chuva": ("Quer ver como choveu desde o plantio?", "Como choveu?"),
                      "solo": ("Quer ver quando a terra costuma ficar descoberta depois da colheita?", "E depois da colheita?"),
                      "proximas": ("Quer ver o que os documentos dizem sobre o que pode vir depois, na rotação?", "O que vem depois?")}
CHIPS_PARTE = [chip("No começo"), chip("No meio"), chip("No fim"), chip("Não lembro")]
CHIPS_CICLO = [chip("Não sei")]
CHIPS_FEIJAO = [chip("Feijão de corda", "Feijão de corda (caupi)"), chip("Feijão comum", "Feijão comum")]
CHIPS_ESTACAO = [chip("Fevereiro"), chip("Março"), chip("Abril"), chip("Maio")]
FRASE_TECNICO = "Converse com o técnico."


def pergunta_mes(cid: str, nomes: dict, estacao: bool = False) -> str:
    base = f"Em que mês você plantou {nome_com_artigo(cid, nomes)}?"
    return ("Entendi que foi na época de chuva, de fevereiro a maio. " + base) if estacao else base


def frase_quando(spec: dict, hoje) -> str:
    """'em fevereiro', 'no começo de fevereiro', 'no dia 10 de fevereiro', 'ontem', 'por volta de 14 de setembro': o que entendi do tempo, em palavras."""
    from datetime import date, timedelta
    from src.culturas import calendario_plantio as CP
    q = CP.resolver_quando(spec, hoje)
    ini, ref = q["ini"], q["ref"]
    ano_txt = f" de {ini.year}" if ini.year != hoje.year or spec.get("ano") else ""
    if "data" in spec:
        if ini == hoje:
            return "hoje"
        if ini == hoje - timedelta(days=1):
            return "ontem"
        return f"no dia {ini.day} de {MESES_PT[ini.month - 1]}{ano_txt}"
    if "mes" in spec:
        pt = {None: "em ", "comeco": "no começo de ", "meio": "no meio de ", "fim": "no fim de "}[spec.get("parte")]
        return f"{pt}{MESES_PT[ini.month - 1]}{ano_txt}"
    prec = spec.get("precisao")
    if prec == "estacao":
        return "na época de chuva (fevereiro a maio)"
    if prec == "semana":
        return f"na semana de {ini.day}/{ini.month} a {q['fim'].day}/{q['fim'].month}"
    return f"por volta de {ref.day} de {MESES_PT[ref.month - 1]}{ano_txt}"


def texto_plantio_entendido(r: dict, nomes: dict, hoje) -> str:
    """'Entendi: milho plantado no começo de fevereiro' (sem ponto final)."""
    cid = r.get("cultura")
    nome = str(nomes.get(cid, cid)).lower() if cid else "a cultura"
    pl = "plantada" if cid in FEMININAS else "plantado"
    q = f" {frase_quando(r['quando'], hoje)}" if r.get("quando") else ""
    c = f", ciclo de {r['ciclo_dias']} dias" if r.get("ciclo_dias") else ""
    return f"Entendi: {nome} {pl}{q}{c}"


def proxima_pergunta_plantio(r: dict, nomes: dict) -> tuple[str, str, list] | None:
    """(pendente, pergunta, chips) do que falta saber do plantio; None = completo, só falta confirmar. UMA coisa por vez: cultura, mês, parte, ciclo."""
    if not r.get("cultura"):
        if r.get("ambiguo"):
            return "plantio_cultura", PERGUNTA_FEIJAO, CHIPS_FEIJAO
        if r.get("fora"):
            return "plantio_cultura", TEXTO_FALTA_DADO_CULTURA.format(nome=r["fora"]), list(CHIPS_INICIO)
        return "plantio_cultura", PERGUNTA_CULTURA_PLANTIO, []
    q = r.get("quando")
    if not q or (q.get("precisao") == "estacao"):
        return "plantio_mes", pergunta_mes(r["cultura"], nomes, estacao=bool(q)), (CHIPS_ESTACAO if q else [])
    if "mes" in q and q.get("parte") is None and not r.get("parte_perguntada"):
        return "plantio_parte", PERGUNTA_PARTE, CHIPS_PARTE
    if not r.get("ciclo_dias") and not r.get("ciclo_perguntado"):
        return "plantio_ciclo", PERGUNTA_CICLO, CHIPS_CICLO
    return None
