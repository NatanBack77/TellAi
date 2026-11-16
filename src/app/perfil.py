"""Perfil do agricultor: o que ele informa, o que é obrigatório e o que tem (ou não) efeito no cálculo. Sem Streamlit; testável.

Duas famílias de campo, nunca misturadas:
  COM EFEITO   cultura atual (OPCIONAL: a primeira das culturas escolhidas; sem cultura não há caminhos), prioridade, regras duras (`regras`), safras 2 e 3 da rotação, textura, matéria orgânica,
               manejo e água de irrigação (estes dois só alimentam os filtros de consulta, não a nota).
  SÓ REGISTRA  `informativos`: área, mês em que costuma plantar, declive que percebe, acesso a mercado/transporte. Não entram em nenhuma conta;
               aparecem no cartão e na conversa com o técnico. O mês só é COMPARADO com a melhor época já calculada (sem recomendar).

O JSON do perfil é lido com `json.loads` e validado campo a campo (chaves desconhecidas, tipos e valores fora da lista dão erro). Nada é executado.
Sem identificador no que vai ao chat: `para_chat` nunca leva município, ponto_id, nome, lat nem lon.
"""
from __future__ import annotations

import json
import math
from typing import Iterable

from src.app import filtros as F
from src.culturas.regras_duras import RegrasDuras

SCHEMA = "sulco.perfil.v1"
TAMANHO_MAX_BYTES = 20_000
PRIORIDADES = ("sem", "alimento", "agua", "solo", "renda")
TEXTURAS = ("não sei", "arenoso", "médio", "argiloso")
MATERIAS_ORGANICAS = ("não sei", "baixa", "média", "alta")
DECLIVES = ("plano", "suave", "forte")
ACESSOS_MERCADO = ("sim", "não", "não sei")
MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
AGUA_MAX_MM = 3000
AREA_MAX_HA = 100_000
MAX_SEGUIDAS_MAX = 8
ROTULO_SO_REGISTRA = "só registra para o técnico; não muda o resultado"
AVISO_POUSIO = "Pousio não é modelado como safra (não há dado para dar nota a ele): sua preferência fica registrada, mas não muda o resultado."

CHAVES_REGRAS = ("proibidas", "obrigatorias", "max_seguidas_cultura", "aceita_pousio")
CHAVES_INFORMATIVOS = ("area_ha", "mes_plantio", "declive", "acesso_mercado")
CHAVES_TOPO = ("schema", "municipio", "cultura_atual", "tambem_considero", "quer_conversar", "prioridade", "manejo", "agua_irrigacao_mm",
               "equipamento", "mercado", "textura", "materia_organica", "safra_2", "safra_3", "regras", "informativos", "plantios")


class PerfilErro(ValueError):
    """Perfil inválido. `.erros` lista cada problema em português simples."""

    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


def vazio() -> dict:
    return {"schema": SCHEMA, "municipio": None, "cultura_atual": None, "tambem_considero": [], "quer_conversar": False, "prioridade": "sem", "manejo": "sequeiro", "agua_irrigacao_mm": 0,
            "equipamento": F.EQUIPAMENTOS[0], "mercado": F.MERCADOS[0], "textura": "não sei", "materia_organica": "não sei",
            "safra_2": None, "safra_3": None,
            "regras": {"proibidas": [], "obrigatorias": [], "max_seguidas_cultura": None, "aceita_pousio": False},
            "informativos": {"area_ha": None, "mes_plantio": None, "declive": None, "acesso_mercado": None}, "plantios": []}


# ---------------------------------------------------------------------------------------------- validação
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _lista_culturas(v, nome: str, culturas, erros: list[str]) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        erros.append(f"'{nome}' deve ser uma lista de culturas")
        return []
    if len(v) > 100:
        erros.append(f"'{nome}' tem culturas demais")
        return []
    desc = sorted(set(v) - set(culturas))
    if desc:
        erros.append(f"'{nome}' cita cultura desconhecida: {', '.join(desc)}")
    return sorted(set(v) & set(culturas))


def _so_chaves(d, permitidas: Iterable[str], onde: str, erros: list[str]) -> bool:
    if not isinstance(d, dict):
        erros.append(f"'{onde}' deve ser um objeto")
        return False
    extra = sorted(set(d) - set(permitidas))
    if extra:
        erros.append(f"campo(s) desconhecido(s) em '{onde}': {', '.join(map(str, extra))}")
    return True


def validar(d, culturas: Iterable[str], pontos: Iterable[str] | None = None, *, como_chat: bool = False) -> dict:
    """Valida e normaliza um perfil (dict). Campo ausente = padrão (vazio). Levanta `PerfilErro` com todos os problemas.

    `como_chat=True`: perfil do /chat, que NÃO aceita município nem cultura_atual (identificam o local; a cultura vai fora do perfil)."""
    culturas = list(culturas)
    erros: list[str] = []
    if not isinstance(d, dict):
        raise PerfilErro(["o perfil deve ser um objeto JSON"])
    _so_chaves(d, CHAVES_TOPO, "perfil", erros)
    if como_chat:
        for k in ("municipio", "cultura_atual"):
            if k in d:
                erros.append(f"'{k}' não é aceito aqui (identifica o local)")
    out = vazio()
    if "schema" in d and d["schema"] != SCHEMA:
        erros.append(f"schema deve ser '{SCHEMA}'")
    if not como_chat:
        m = d.get("municipio")
        if m is not None:
            if not isinstance(m, str) or (pontos is not None and m not in set(pontos)):
                erros.append("'municipio' não é um município da lista")
            else:
                out["municipio"] = m
        c = d.get("cultura_atual")
        if c is not None:
            if not isinstance(c, str) or c not in culturas:
                erros.append("'cultura_atual' não está na tabela de culturas")
            else:
                out["cultura_atual"] = c
    if "tambem_considero" in d:
        t = _lista_culturas(d["tambem_considero"], "tambem_considero", culturas, erros)
        if d["tambem_considero"] is not None and isinstance(d["tambem_considero"], list):
            ordem = [x for x in dict.fromkeys(d["tambem_considero"]) if x in t and x != out["cultura_atual"]]
            out["tambem_considero"] = ordem
    if "quer_conversar" in d:
        if isinstance(d["quer_conversar"], bool):
            out["quer_conversar"] = d["quer_conversar"]
        else:
            erros.append("'quer_conversar' deve ser verdadeiro ou falso")
    if out["tambem_considero"] and not out["cultura_atual"] and not como_chat:
        erros.append("'tambem_considero' precisa de 'cultura_atual' (a primeira cultura é a base dos caminhos)")
    for chave, lista in (("prioridade", PRIORIDADES), ("manejo", tuple(F.MANEJOS)), ("equipamento", tuple(F.EQUIPAMENTOS)),
                         ("mercado", tuple(F.MERCADOS)), ("textura", TEXTURAS), ("materia_organica", MATERIAS_ORGANICAS)):
        if chave in d:
            if d[chave] in lista and isinstance(d[chave], str):
                out[chave] = d[chave]
            else:
                erros.append(f"'{chave}' deve ser um destes: {', '.join(lista)}")
    if "agua_irrigacao_mm" in d:
        v = d["agua_irrigacao_mm"]
        if _num(v) and 0 <= v <= AGUA_MAX_MM:
            out["agua_irrigacao_mm"] = v
        else:
            erros.append(f"'agua_irrigacao_mm' deve ser um número de 0 a {AGUA_MAX_MM}")
    for chave in ("safra_2", "safra_3"):
        v = d.get(chave)
        if v is not None:
            if isinstance(v, str) and v in culturas:
                out[chave] = v
            else:
                erros.append(f"'{chave}' não está na tabela de culturas")
    if "regras" in d:
        r = d["regras"]
        if _so_chaves(r, CHAVES_REGRAS, "regras", erros):
            nao = _lista_culturas(r.get("proibidas"), "regras.proibidas", culturas, erros)
            sim = _lista_culturas(r.get("obrigatorias"), "regras.obrigatorias", culturas, erros)
            if set(nao) & set(sim):
                erros.append("a mesma cultura não pode estar em 'não quero plantar' e em 'preciso incluir': " + ", ".join(sorted(set(nao) & set(sim))))
            mx = r.get("max_seguidas_cultura")
            if mx is not None and not (isinstance(mx, int) and not isinstance(mx, bool) and 1 <= mx <= MAX_SEGUIDAS_MAX):
                erros.append(f"'regras.max_seguidas_cultura' deve ser um inteiro de 1 a {MAX_SEGUIDAS_MAX} (ou vazio = sem regra)")
                mx = None
            pous = r.get("aceita_pousio", False)
            if not isinstance(pous, bool):
                erros.append("'regras.aceita_pousio' deve ser verdadeiro ou falso")
                pous = False
            out["regras"] = {"proibidas": nao, "obrigatorias": sim, "max_seguidas_cultura": mx, "aceita_pousio": pous}
    if "informativos" in d:
        i = d["informativos"]
        if _so_chaves(i, CHAVES_INFORMATIVOS, "informativos", erros):
            a = i.get("area_ha")
            if a is not None:
                if _num(a) and 0 < a <= AREA_MAX_HA:
                    out["informativos"]["area_ha"] = a
                else:
                    erros.append(f"'informativos.area_ha' deve ser um número maior que 0 e até {AREA_MAX_HA}")
            m = i.get("mes_plantio")
            if m is not None:
                if isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 12:
                    out["informativos"]["mes_plantio"] = m
                else:
                    erros.append("'informativos.mes_plantio' deve ser um número de 1 a 12")
            for chave, lista in (("declive", DECLIVES), ("acesso_mercado", ACESSOS_MERCADO)):
                v = i.get(chave)
                if v is not None:
                    if isinstance(v, str) and v in lista:
                        out["informativos"][chave] = v
                    else:
                        erros.append(f"'informativos.{chave}' deve ser um destes: {', '.join(lista)}")
    if "plantios" in d:
        from src.culturas import calendario_plantio as CP
        try:
            out["plantios"] = CP.validar_plantios(d["plantios"], culturas)
        except ValueError as e:
            erros.append("'plantios': " + str(e))
    if erros:
        raise PerfilErro(erros)
    if como_chat:
        out.pop("municipio"), out.pop("cultura_atual")
        out["tambem_considero"] = [] if "tambem_considero" not in d else out["tambem_considero"]
    return out


def para_json(p: dict) -> str:
    return json.dumps(p, ensure_ascii=False, indent=2, sort_keys=False)


def de_json(texto: str | bytes, culturas: Iterable[str], pontos: Iterable[str] | None = None) -> dict:
    """Lê o arquivo do perfil: tamanho limitado, só `json.loads` (nada é executado) e validação por campo."""
    bruto = texto.encode("utf-8") if isinstance(texto, str) else bytes(texto)
    if len(bruto) > TAMANHO_MAX_BYTES:
        raise PerfilErro([f"arquivo grande demais (máximo {TAMANHO_MAX_BYTES // 1000} mil bytes)"])
    try:
        d = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise PerfilErro(["o arquivo não é um perfil válido (JSON ilegível)"]) from None
    return validar(d, culturas, pontos)


# ---------------------------------------------------------------------------------------------- regras e efeito
def regras_duras(p: dict, culturas: Iterable[str] | None = None) -> RegrasDuras:
    """`RegrasDuras` do perfil. Inclui `aceita_pousio` (só registro). Pode levantar ValueError se as regras se contradizem."""
    r = p.get("regras") or {}
    rd = RegrasDuras(proibidas=r.get("proibidas") or (), obrigatorias=r.get("obrigatorias") or (),
                     max_seguidas_cultura=r.get("max_seguidas_cultura"), aceita_pousio=bool(r.get("aceita_pousio")))
    if culturas is not None:
        rd.validar_contra(culturas)
    return rd


def regras_para_motor(rd: RegrasDuras | None) -> RegrasDuras | None:
    """Passa ao motor só se há regra que filtre; sem regra o motor roda exatamente como antes (resultado idêntico)."""
    return None if rd is None or rd.vazia else rd


def chave_regras(rd: RegrasDuras | None) -> str:
    """Texto estável (para cache): igual para regras iguais."""
    return json.dumps(rd.para_dict() if rd else {}, sort_keys=True, ensure_ascii=False)


def de_chave_regras(chave: str) -> RegrasDuras | None:
    d = json.loads(chave)
    return RegrasDuras(**d) if d else None


def efeitos(p: dict) -> dict:
    """Quais campos mexem no cálculo e quais só registram (para a tela e a documentação)."""
    return {"com_efeito": ["cultura_atual", "prioridade", "regras.proibidas", "regras.obrigatorias", "regras.max_seguidas_cultura", "safra_2",
                           "safra_3", "textura", "materia_organica"],
            "so_consulta": ["manejo", "agua_irrigacao_mm", "equipamento", "mercado"],
            "so_registra": ["regras.aceita_pousio"] + [f"informativos.{k}" for k in CHAVES_INFORMATIVOS]}


# ---------------------------------------------------------------------------------------------- texto (cartão, chat)
def _g(x) -> str:
    """Número no formato brasileiro (3,5), sem zeros à toa."""
    return f"{x:g}".replace(".", ",")


def _nome(c: str | None, nomes: dict) -> str:
    return nomes.get(c, c) if c else "não informada"


def _lista(cs: list[str], nomes: dict) -> str:
    return ", ".join(_nome(c, nomes) for c in cs)


def comparar_epoca(mes: int | None, melhor_inicio: str | None) -> str | None:
    """'você costuma plantar em março; para os dados do local a melhor época é fevereiro'. Só compara; não recomenda trocar."""
    if not mes or not melhor_inicio:
        return None
    try:
        mm = int(str(melhor_inicio).split("/")[1])
        nome_mm = MESES_PT[mm - 1]
    except (IndexError, ValueError):
        return None
    base = f"Você costuma plantar em {MESES_PT[mes - 1]}; para os dados do local a melhor época é {nome_mm}"
    return base + (" (o mesmo mês)." if mm == mes else ".")


def linhas_informadas(p: dict, nomes: dict, melhor_inicio: str | None = None) -> list[str]:
    """Texto do cartão ('O que você informou'): uma linha por campo informado, dizendo se tem efeito. Sem nome nem coordenada."""
    out = []
    if p.get("cultura_atual"):
        out.append(f"Cultura base (a primeira que você escolheu): {_nome(p['cultura_atual'], nomes)}.")
    if p.get("tambem_considero"):
        out.append("Também considero plantar (só registra; os caminhos partem da cultura base): " + _lista(p["tambem_considero"], nomes) + ".")
    if p.get("quer_conversar") and not p.get("cultura_atual"):
        out.append("Ainda não sabe o que plantar e quer conversar com o técnico.")
    r = p.get("regras") or {}
    if r.get("proibidas"):
        out.append("Culturas que você não quer plantar (regra aplicada às alternativas): " + _lista(r["proibidas"], nomes) + ".")
    if r.get("obrigatorias"):
        out.append("Culturas que você precisa incluir (regra aplicada às alternativas): " + _lista(r["obrigatorias"], nomes) + ".")
    if r.get("max_seguidas_cultura"):
        out.append(f"Máximo de safras seguidas da mesma cultura (regra aplicada): {r['max_seguidas_cultura']}.")
    if r.get("aceita_pousio"):
        out.append("Aceita pousio: " + AVISO_POUSIO)
    if p.get("safra_2") and p.get("safra_3"):
        out.append("Sua rotação atual: " + " → ".join(_nome(c, nomes) for c in (p.get("cultura_atual"), p["safra_2"], p["safra_3"])) + ".")
    if p.get("manejo") == "irrigado":
        mm = p.get("agua_irrigacao_mm") or 0
        out.append("Manejo: irrigado" + (f", água que consegue aplicar por ciclo: {_g(mm)} mm" if mm else "") + " (só consulta; não muda a nota).")
    for chave, rot in (("textura", "Textura do solo (que você informou)"), ("materia_organica", "Matéria orgânica (que você informou)")):
        if p.get(chave) not in (None, "não sei"):
            out.append(f"{rot}: {p[chave]}.")
    i = p.get("informativos") or {}
    reg = f" ({ROTULO_SO_REGISTRA})"
    if i.get("area_ha") is not None:
        out.append(f"Área do talhão: {_g(i['area_ha'])} ha{reg}.")
    if i.get("mes_plantio"):
        comp = comparar_epoca(i["mes_plantio"], melhor_inicio)
        out.append((comp or f"Você costuma plantar em {MESES_PT[i['mes_plantio'] - 1]}.").rstrip(".") + reg + ".")
    if i.get("declive"):
        out.append(f"Declive que você percebe: {i['declive']}{reg}.")
    if i.get("acesso_mercado"):
        out.append(f"Acesso a mercado ou transporte: {i['acesso_mercado']}{reg}.")
    return out


def para_chat(p: dict) -> dict:
    """Perfil que pode ir ao chat: SEM município, cultura_atual (vai à parte), nome, ponto_id, lat nem lon."""
    d = {k: v for k, v in p.items() if k not in ("municipio", "cultura_atual", "schema")}
    return json.loads(json.dumps(d, ensure_ascii=False))


def frase_chat(pc: dict, nomes: dict) -> str | None:
    """Uma frase simples com o que o agricultor informou, para a folha de fatos do chat. None se não informou nada além do padrão."""
    partes = []
    r = pc.get("regras") or {}
    if pc.get("tambem_considero"):
        partes.append("também considera plantar " + _lista(pc["tambem_considero"], nomes))
    if r.get("proibidas"):
        partes.append("não quer plantar " + _lista(r["proibidas"], nomes))
    if r.get("obrigatorias"):
        partes.append("precisa incluir " + _lista(r["obrigatorias"], nomes))
    if r.get("max_seguidas_cultura"):
        partes.append(f"aceita no máximo {r['max_seguidas_cultura']} safra(s) seguida(s) da mesma cultura")
    if pc.get("safra_2") and pc.get("safra_3"):
        partes.append("sua rotação atual repete " + " e ".join(_nome(c, nomes) for c in (pc["safra_2"], pc["safra_3"])) + " depois da cultura atual")
    if pc.get("manejo") == "irrigado":
        partes.append("planta irrigado")
    for chave, rot in (("textura", "solo de textura"), ("materia_organica", "matéria orgânica")):
        if pc.get(chave) not in (None, "não sei"):
            partes.append(f"{rot} {pc[chave]}")
    i = pc.get("informativos") or {}
    if i.get("area_ha") is not None:
        partes.append(f"talhão de {_g(i['area_ha'])} hectares")
    if i.get("declive"):
        partes.append(f"declive {i['declive']}")
    if i.get("mes_plantio"):
        partes.append(f"costuma plantar em {MESES_PT[i['mes_plantio'] - 1]}")
    if i.get("acesso_mercado"):
        partes.append(f"acesso a mercado ou transporte: {i['acesso_mercado']}")
    if not partes:
        return None
    return ("O agricultor informou: " + "; ".join(partes) + ". Área, mês de plantio, declive e acesso a mercado só ficam registrados para o "
            "técnico: não mudam o cálculo dos caminhos.")


def folha_com_perfil(folha: dict | None, pc: dict | None, nomes: dict) -> dict | None:
    """Cópia da folha de fatos com UM fato a mais (tema 'caminhos') com o perfil sem identificador. Folha e perfil originais não mudam."""
    if folha is None or not pc:
        return folha
    fr = frase_chat(pc, nomes)
    if fr is None:
        return folha
    fatos = list(folha["fatos"])
    novo = {"id": f"F{len(fatos) + 1}", "tema": "caminhos", "rotulo": "o que o agricultor informou", "texto": fr, "origem": "entrada do agricultor (perfil)",
            "prio": 1, "lacuna": False, "valor": None, "texto_simples": fr}
    return {**folha, "fatos": fatos + [novo]}


def contexto_com_perfil(ctx: dict | None, pc: dict | None) -> dict | None:
    """Cópia do `contexto` do chat (caminho antigo) com o perfil sem identificador em `perfil_agricultor`."""
    if ctx is None or not pc:
        return ctx
    return {**ctx, "perfil_agricultor": pc}


# ---------------------------------------------------------------------------------------------- estado do app
CHAVES_ESTADO = ("local", "culturas", "quer_conversar", "prioridade", "manejo", "agua_irrig", "equip", "mercado", "textura", "mo", "rot2", "rot3", "regra_nao",
                 "regra_incluir", "regra_max", "regra_pousio", "inf_area", "inf_mes", "inf_declive", "inf_mercado", "plantios")


def do_estado(ss) -> dict:
    """Perfil a partir do session_state do app (chaves dos widgets). Não valida contra a tabela (os widgets já limitam as opções)."""
    p = vazio()
    cs = list(ss.get("culturas") or [])
    p["municipio"], p["cultura_atual"] = ss.get("local"), (cs[0] if cs else None)
    p["tambem_considero"], p["quer_conversar"] = cs[1:], bool(ss.get("quer_conversar", False))
    p["prioridade"] = ss.get("prioridade", "sem")
    p["manejo"] = ss.get("manejo", "sequeiro")
    p["agua_irrigacao_mm"] = (ss.get("agua_irrig") or 0) if p["manejo"] == "irrigado" else 0
    p["equipamento"], p["mercado"] = ss.get("equip", F.EQUIPAMENTOS[0]), ss.get("mercado", F.MERCADOS[0])
    p["textura"], p["materia_organica"] = ss.get("textura", "não sei"), ss.get("mo", "não sei")
    r2, r3 = ss.get("rot2", "-"), ss.get("rot3", "-")
    p["safra_2"], p["safra_3"] = (None if r2 in (None, "-") else r2), (None if r3 in (None, "-") else r3)
    p["regras"] = {"proibidas": sorted(ss.get("regra_nao") or []), "obrigatorias": sorted(ss.get("regra_incluir") or []),
                   "max_seguidas_cultura": ss.get("regra_max"), "aceita_pousio": bool(ss.get("regra_pousio", False))}
    mx = p["regras"]["max_seguidas_cultura"]
    p["regras"]["max_seguidas_cultura"] = None if mx in (None, 0) else int(mx)
    p["informativos"] = {"area_ha": ss.get("inf_area"), "mes_plantio": ss.get("inf_mes"), "declive": ss.get("inf_declive"),
                         "acesso_mercado": ss.get("inf_mercado")}
    p["plantios"] = [dict(x) for x in (ss.get("plantios") or []) if isinstance(x, dict)]
    return p


def para_estado(ss, p: dict) -> None:
    """Põe um perfil JÁ VALIDADO nas chaves dos widgets (chamar antes de os widgets existirem: callback ou início do script)."""
    ss["local"] = p["municipio"] if p["municipio"] else ss.get("local")
    ss["culturas"] = ([p["cultura_atual"]] if p["cultura_atual"] else []) + list(p["tambem_considero"])
    ss["quer_conversar"] = bool(p["quer_conversar"])
    ss["prioridade"], ss["manejo"], ss["agua_irrig"] = p["prioridade"], p["manejo"], int(p["agua_irrigacao_mm"])
    ss["equip"], ss["mercado"], ss["textura"], ss["mo"] = p["equipamento"], p["mercado"], p["textura"], p["materia_organica"]
    ss["rot2"], ss["rot3"] = p["safra_2"] or "-", p["safra_3"] or "-"
    r = p["regras"]
    ss["regra_nao"], ss["regra_incluir"], ss["regra_max"], ss["regra_pousio"] = list(r["proibidas"]), list(r["obrigatorias"]), r["max_seguidas_cultura"], r["aceita_pousio"]
    i = p["informativos"]
    ss["inf_area"], ss["inf_mes"], ss["inf_declive"], ss["inf_mercado"] = i["area_ha"], i["mes_plantio"], i["declive"], i["acesso_mercado"]
    ss["plantios"] = [dict(x) for x in (p.get("plantios") or [])]


def cultura_base(ss) -> str | None:
    """Cultura base dos três caminhos: a primeira escolhida em 'culturas que eu planto ou penso em plantar'. Sem escolha = None (sem padrão)."""
    cs = ss.get("culturas") or []
    return cs[0] if cs else None


FOCOS_PRIORIDADE = {"agua": "agua", "solo": "solo", "renda": "renda", "alimento": "alimento"}


def estado_conversa_para_perfil(estado: dict | None, culturas: Iterable[str]) -> dict:
    """Ponte com a conversa consultiva (src/llm/conversa.py, de outro dono). Recebe o ESTADO da conversa
    {'culturas_citadas': [ids], 'foco': 'agua'|'solo'|'renda'|None} e devolve o que cabe no perfil: {'culturas': [...], 'prioridade': ...}.
    Só entra o que é válido (cultura da tabela, foco conhecido); o resto é ignorado. Não executa nada."""
    culturas = set(culturas)
    est = estado if isinstance(estado, dict) else {}
    cit = est.get("culturas_citadas")
    cs = [c for c in dict.fromkeys(cit) if isinstance(c, str) and c in culturas] if isinstance(cit, list) else []
    out: dict = {"culturas": cs}
    if est.get("foco") in FOCOS_PRIORIDADE:
        out["prioridade"] = FOCOS_PRIORIDADE[est["foco"]]
    return out
