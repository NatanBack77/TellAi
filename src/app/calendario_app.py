"""Lógica do 'Meu calendário' (sem Streamlit; testável): lista de plantios do formulário, linha do tempo de cada plantio e junção com o que a conversa guardou.

Nada aqui calcula dado novo: a linha do tempo só põe em barras o que `culturas/calendario_plantio.calcular` já devolveu (plantio, fases de referência, colheita
esperada, janela do zoneamento, época de solo nu). Todas as barras de fase e colheita são REFERÊNCIA de outras regiões (FAO/EcoCrop), não medida na roça.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from src.culturas import calendario_plantio as CP

PARTES_ROTULO = {None: "não sei", "comeco": "começo", "meio": "meio", "fim": "fim"}
ROTULO_FASE_BARRA = {"ini": "Fase inicial", "dev": "Crescimento", "mid": "Meio do ciclo", "late": "Fim do ciclo"}
ETAPAS = ["Plantio", "Fases (referência)", "Colheita esperada", "Janela do zoneamento", "Terra descoberta depois"]


def hoje() -> date:
    return date.today()


def novo_plantio(cultura: str, mes: int, parte: str | None, ano: int | None, ciclo_dias: int | None, manejo: str, culturas) -> dict:
    """Plantio do formulário já validado pelo schema (levanta ValueError em português)."""
    q: dict = {"mes": int(mes)}
    if ano:
        q["ano"] = int(ano)
    if parte in CP.PARTES:
        q["parte"] = parte
    pl = {"cultura": cultura, "quando": q, "ciclo_dias": int(ciclo_dias) if ciclo_dias else None, "manejo": manejo or "sequeiro"}
    return CP.validar_plantios([pl], culturas)[0]


def juntar_plantios(atuais: list[dict], novos: list[dict], culturas, maximo: int = CP.MAX_PLANTIOS) -> list[dict]:
    """Lista atual + os que a conversa guardou, sem repetir, no máximo `maximo`, tudo validado pelo schema."""
    vistos, out = set(), []
    for p in CP.validar_plantios(list(atuais or []), culturas) + CP.validar_plantios(list(novos or []), culturas):
        k = json.dumps(p, sort_keys=True)
        if k not in vistos:
            vistos.add(k)
            out.append(p)
    return out[-maximo:]


def titulo_plantio(p: dict, nomes: dict, hoje_: date) -> str:
    q = CP.resolver_quando(p["quando"], hoje_)
    return f"{nomes.get(p['cultura'], p['cultura'])}: plantado {q['texto']}"


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso[:10])


def linha_do_tempo(p: dict, hoje_: date) -> list[dict]:
    """Barras da linha do tempo de UM plantio calculado (item de `calcular(...)['plantios']`): [{etapa, detalhe, inicio, fim}] (datas como datetime).
    Plantio com esclarecimento não tem linha do tempo (lista vazia)."""
    if p.get("status") == "esclarecimento" or not p.get("quando"):
        return []
    q = p["quando"]
    rows = [{"etapa": "Plantio", "detalhe": "quando você plantou" + ("" if q["ini"] == q["fim"] else " (faixa: você disse só o período)"),
             "inicio": _dt(q["ini"]), "fim": _dt(q["fim"]) + timedelta(days=1)}]
    ci = p.get("ciclo") or {}
    if ci.get("disponivel"):
        ref = _dt(q["ref"])
        if ci.get("estagios"):
            ini = ref
            for nome, d in zip(CP.FASES, ci["estagios"]):
                if d:
                    rows.append({"etapa": "Fases (referência)", "detalhe": ROTULO_FASE_BARRA[nome], "inicio": ini, "fim": ini + timedelta(days=int(d))})
                    ini += timedelta(days=int(d))
        else:
            rows.append({"etapa": "Fases (referência)", "detalhe": "Ciclo todo (sem as fases)" if ci["fonte"] != "informado" else "Ciclo que você informou",
                         "inicio": ref, "fim": ref + timedelta(days=ci["dias_ref"])})
    co = p.get("colheita") or {}
    if co.get("disponivel"):
        rows.append({"etapa": "Colheita esperada", "detalhe": "pela referência" if co["fonte"] != "informado" else "pelo ciclo que você informou",
                     "inicio": _dt(co["de"]), "fim": _dt(co["ate"]) + timedelta(days=1)})
    z = p.get("zarc") or {}
    for a, b in z.get("datas_30") or []:
        rows.append({"etapa": "Janela do zoneamento", "detalhe": "plantio indicado, risco até 30%", "inicio": _dt(a), "fim": _dt(b) + timedelta(days=1)})
    sn = p.get("solo_nu") or {}
    if sn.get("disponivel") and sn.get("quinzenas") and co.get("disponivel"):
        c0 = _dt(co["de"]).date()
        for ano in (c0.year, c0.year + 1):
            grupos: list[list[int]] = []
            for qz in sorted(sn["quinzenas"]):
                if grupos and qz == grupos[-1][-1] + 1:
                    grupos[-1].append(qz)
                else:
                    grupos.append([qz])
            for g in grupos:
                a = CP.inicio_da_quinzena(g[0], ano)
                ultimo = CP.inicio_da_quinzena(g[-1], ano)
                b = date(ano, ultimo.month, 15) if ultimo.day == 1 else date(ano, ultimo.month, CP.ultimo_dia_do_mes(ano, ultimo.month))
                if b >= c0 and a <= c0 + timedelta(days=366):
                    rows.append({"etapa": "Terra descoberta depois", "detalhe": "época em que o local costuma ter pouco verde", "inicio": datetime(a.year, a.month, a.day),
                                 "fim": datetime(b.year, b.month, b.day) + timedelta(days=1)})
        # só o primeiro período que vem depois da colheita (o resto é repetição do ciclo seguinte)
        solos = [r for r in rows if r["etapa"] == "Terra descoberta depois"]
        if solos:
            primeiro = sorted(solos, key=lambda r: r["inicio"])[0]
            rows = [r for r in rows if r["etapa"] != "Terra descoberta depois"] + [primeiro]
    return rows


def resumo_fase(p: dict) -> str:
    """Uma linha: situação e fase atual (texto do cálculo, sem número novo)."""
    st_ = p.get("status")
    if st_ == "esclarecimento":
        return "Preciso de mais um dado: " + str(p.get("esclarecimento"))
    if st_ == "planejamento":
        return f"Planejamento: faltam {p['dias_para_plantar']} dias para esse plantio."
    fa = p.get("fase") or {}
    if not fa.get("disponivel"):
        return "Fase: sem o ciclo dessa cultura (lacuna)."
    if fa.get("tipo") == "fao":
        if fa["depois_do_ciclo"]:
            return "Fase: já passou do ciclo de referência (FAO, outras regiões)."
        return "Fase pela referência (FAO, outras regiões): " + " / ".join(ROTULO_FASE_BARRA[f] for f in fa["fases"]) + "."
    pct = fa["fracao_max"] * 100
    return f"Cerca de {pct:.0f}% do ciclo de referência." if not fa["depois_do_ciclo"] else "Já passou do ciclo."
