"""AP1: cartão de uma folha por município (HTML imprimível; PDF se `fpdf2` estiver instalado). Sem Streamlit.

Todo o texto sai dos MESMOS dados e funções do app (diagnóstico, janela da cultura atual, rotação de 3 safras, risco de solo, solo estimado).
Nenhum número novo: o que não existe vira LACUNA. Não promete rendimento nem lucro; termina com "a avaliar com técnico local".
Uso: `d = montar_cartao(ponto_id, cultura, prioridade)`; `cartao_html(d)`; `cartao_pdf(d)` (bytes ou None se faltar a lib).
"""
from __future__ import annotations

import html
import re

from src.app import mvp as M

AVISO_FINAL = "A avaliar com técnico local."
AVISO_ESCOPO = ("Apoio à conversa com o técnico; não é recomendação, nem previsão de produtividade ou de lucro. O satélite enxerga áreas de "
                "cerca de 250 m a 50 km, não o seu talhão.")
LEVAR_AO_TECNICO_FIXO = [
    "A textura e a matéria orgânica medidas na sua área (o mapa de solo usado aqui é global e não substitui análise).",
    "O ciclo real da cultivar que você usa e a data em que costuma plantar (o app supõe o ponto médio do ciclo da espécie).",
    "Quais culturas têm semente, mercado e máquina disponíveis perto de você (o app não tem dado de preço, custo nem equipamento).",
    "Se a época de campo nu e a de maior estresse dos satélites batem com o que você vê na roça.",
]
MAX_LACUNAS = 5


def _lac(msg: str) -> str:
    return f"LACUNA: {msg}"


def _bloco_local(ponto_id: str, cultura: str, prio: str) -> dict:
    nome = M.nome_do_ponto(ponto_id)
    cult = M.culturas_disponiveis().get(cultura, cultura)
    p = M.carregar_pontos().set_index("ponto_id").loc[ponto_id]
    return {"titulo": "Local", "itens": [
        f"{nome}. Coordenadas do ponto de referência: {M.br(float(p['lat']), 2)}, {M.br(float(p['lon']), 2)}.",
        f"Cultura atual: {cult}. O que importa mais: {M.PRIORIDADES[prio]['rotulo']}."]}


def _bloco_diagnostico(ponto_id: str, d: dict | None) -> dict:
    if d is None:
        return {"titulo": "O que os satélites mostram (época típica de solo nu e de estresse)", "itens": [_lac("diagnóstico do local não encontrado.")]}
    itens = [f"Solo nu: {d['solo_nu']['frase']}" if d.get("solo_nu") else _lac("solo nu não calculado para este local."),
             f"Estresse: {d['estresse_frase']}"]
    itens.append(f"Confiança do diagnóstico: {d['confianca'] or M.LACUNA}. {d['confianca_nota']}.")
    return {"titulo": "O que os satélites mostram (época típica de solo nu e de estresse)", "itens": itens}


def _bloco_janela(ponto_id: str, cultura: str, calc: dict | None, d: dict | None) -> dict:
    tit = "Melhor janela de plantio da cultura atual"
    if calc is None or d is None:
        return {"titulo": tit, "itens": [_lac("janela não calculada (faltam cenários ou diagnóstico).")]}
    v = M.vulnerabilidade_cultura_atual(ponto_id, cultura, calc, d)
    itens = [_lac(t) for t in v["lacunas"]]
    if "melhor_inicio" in v:
        itens.append(f"Melhor início de plantio nos dados históricos: {v['melhor_inicio']} (ciclo suposto de {v['duracao']} dias). "
                     f"Inícios com menor adequação: {', '.join(v['piores_inicios'])}. Situação da cultura neste local pelo motor: {v['viabilidade']}.")
        if "solo_nu_no_ciclo" in v:
            itens.append(f"Dentro do ciclo da melhor data, campo nu típico: {M.rotulos_quinzenas(v['solo_nu_no_ciclo'])}; "
                         f"maior estresse do verdor: {M.rotulos_quinzenas(v['estresse_no_ciclo'])}.")
    return {"titulo": tit, "itens": itens or [_lac("janela não calculada.")]}


def _bloco_caminhos(rot: dict | None) -> dict:
    tit = "Três caminhos para conversar (rotação atual + 2 alternativas)"
    if rot is None or not rot.get("estrategias"):
        lac = (rot or {}).get("lacunas") or ["rotações não calculadas para este local."]
        return {"titulo": tit, "itens": [_lac(t) for t in lac]}
    linhas, vistas, lac_proprias = [], set(rot.get("lacunas") or []), []
    for i, e in enumerate(rot["estrategias"]):
        p_top = M.pct(e["p_top"]) if e.get("p_top") is not None else "(não entra no ranking)"
        n_emp = len(e.get("empate_tecnico_com") or [])
        proprias = [t for t in e["lacunas"] if t not in vistas]
        linhas.append([("Atual" if e["papel"] == "atual" else f"Alternativa {i}"), " > ".join(e["nomes"]),
                       f"{M.br(e['score_mediana'], 1)} (faixa {M.br(e['faixa_score'][0], 1)} a {M.br(e['faixa_score'][1], 1)})",
                       p_top, f"empate técnico com {n_emp} outras sequências" if n_emp else "sem empate técnico detectado"])
        rot_i = "Atual" if e["papel"] == "atual" else f"Alternativa {i}"
        lac_proprias += [_lac(f"{rot_i}: {t}") for t in proprias[:3]]
    itens = []
    if rot.get("empate_tecnico_todos"):
        itens.append("As alternativas estão em EMPATE TÉCNICO com muitas outras sequências: os dados deste app não dizem qual é melhor. "
                     "Quem escolhe entre elas é o agricultor com o técnico.")
    itens.append("Pontuação de 0 a 100 é uma régua do projeto (pesos-base, suposições a validar); não é produtividade nem lucro.")
    comuns = list(rot.get("lacunas") or [])
    itens += [_lac(t) for t in comuns[:MAX_LACUNAS]] + lac_proprias
    if not comuns and not lac_proprias:
        itens.append("Lacunas dos três caminhos: nenhuma informada pelo motor.")
    return {"titulo": tit, "tabela": {"cabecalho": ["Caminho", "Sequência (3 safras)", "Pontuação (mediana)", "Entre as 3 melhores", "Empate"],
                                      "linhas": linhas}, "itens": itens}


def _bloco_solo(ponto_id: str, rot: dict | None) -> dict:
    tit = "Risco de solo e solo estimado"
    itens = []
    try:
        from src.app import secao_risco_solo as SRS
        s = SRS.secao_risco_solo(ponto_id)
        itens.append(f"Indicador relativo de erosão e escoamento: {s['classe']} (soma de notas {s['soma_notas']} de {s['soma_maxima']}). "
                     "É relativo aos outros pontos do projeto, não é perda de solo medida.")
        itens += [_lac(t) for t in s["lacunas"]]
    except Exception as e:  # noqa: BLE001 - uma parte sem dado vira lacuna, não derruba o cartão
        itens.append(_lac(f"risco de solo não calculado ({e.__class__.__name__})."))
    est = M.solo_estimado(ponto_id)
    if est:
        itens.append(f"Solo estimado pelo mapa SoilGrids (0 a 30 cm): argila {M.br(est['argila_pct'], 0)}%, areia {M.br(est['areia_pct'], 0)}%, "
                     f"carbono orgânico {M.br(est['carbono_organico_g_kg'], 0)} g/kg, pH {M.br(est['ph_agua'], 1)}. {est['aviso']}")
        if est.get("aviso_pixels"):
            itens.append("ATENÇÃO: " + est["aviso_pixels"])
    else:
        itens.append(_lac("solo estimado indisponível para este local."))
    return {"titulo": tit, "itens": itens}


def _bloco_informado(perfil: dict, calc: dict | None, ponto_id: str, cultura: str, d: dict | None) -> dict | None:
    """'O que você informou': o perfil sem identificador (o nome e as coordenadas já estão no bloco Local). Diz o que tem efeito e o que só registra."""
    from src.app import perfil as P
    melhor = None
    if calc is not None and d is not None:
        try:
            melhor = M.vulnerabilidade_cultura_atual(ponto_id, cultura, calc, d).get("melhor_inicio")
        except Exception:  # noqa: BLE001
            melhor = None
    linhas = P.linhas_informadas(perfil, M.culturas_disponiveis(), melhor)
    if not linhas:
        return None
    return {"titulo": "O que você informou", "itens": linhas + ["Campos marcados 'só registra' não entram em nenhuma conta; servem para a conversa com o técnico."]}


def _bloco_levar(rot: dict | None) -> dict:
    itens = list(LEVAR_AO_TECNICO_FIXO)
    ests = (rot or {}).get("estrategias") or [{}]
    itens += list(ests[0].get("riscos_revisao_local") or [])[:3]
    return {"titulo": "O que levar ao técnico", "itens": itens}


def montar_cartao(ponto_id: str, cultura: str, prioridade: str = "sem", calc: dict | None = None, rotacao: dict | None = None,
                  perfil: dict | None = None) -> dict:
    """Monta o cartão (estrutura de dados). `calc`/`rotacao` opcionais: o app passa os resultados já em cache; sem eles o cartão calcula."""
    if calc is None:
        try:
            calc = M.calcular(ponto_id, cultura, prioridade)
        except Exception:  # noqa: BLE001
            calc = None
    if rotacao is None:
        try:
            rotacao = M.calcular_rotacao(ponto_id, cultura, prioridade)
        except Exception:  # noqa: BLE001
            rotacao = None
    d = M.diagnostico_local(ponto_id)
    blocos = [_bloco_local(ponto_id, cultura, prioridade), _bloco_diagnostico(ponto_id, d), _bloco_janela(ponto_id, cultura, calc, d),
              _bloco_caminhos(rotacao), _bloco_solo(ponto_id, rotacao), _bloco_levar(rotacao)]
    if perfil:
        bi = _bloco_informado(perfil, calc, ponto_id, cultura, d)
        if bi:
            blocos.insert(1, bi)
    return {"ponto_id": ponto_id, "titulo": f"SULCO: cartão de {M.nome_do_ponto(ponto_id)}", "escopo": AVISO_ESCOPO, "blocos": blocos,
            "aviso_final": AVISO_FINAL}


# ---------------------------------------------------------------------------------------------------------- saídas
def cartao_texto(c: dict) -> str:
    """Texto plano do cartão (base dos testes de conteúdo e do PDF)."""
    out = [c["titulo"], c["escopo"]]
    for b in c["blocos"]:
        out.append(b["titulo"])
        if b.get("tabela"):
            out += [" | ".join(l) for l in b["tabela"]["linhas"]]
        out += b["itens"]
    out.append(c["aviso_final"])
    return "\n".join(out)


def cartao_html(c: dict) -> str:
    e = html.escape
    p = [f"<h1>{e(c['titulo'])}</h1>", f"<p class='aviso'>{e(c['escopo'])}</p>"]
    for b in c["blocos"]:
        p.append(f"<h2>{e(b['titulo'])}</h2>")
        if b.get("tabela"):
            t = b["tabela"]
            p.append("<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in t["cabecalho"]) + "</tr>"
                     + "".join("<tr>" + "".join(f"<td>{e(x)}</td>" for x in l) + "</tr>" for l in t["linhas"]) + "</table>")
        p.append("<ul>" + "".join(f"<li class='{'lac' if i.startswith('LACUNA') else ''}'>{e(i)}</li>" for i in b["itens"]) + "</ul>")
    p.append(f"<p class='final'>{e(c['aviso_final'])}</p>")
    css = ("@page{size:A4;margin:10mm}body{font:9.5px/1.3 Arial,Helvetica,sans-serif;color:#222;max-width:190mm;margin:0 auto}"
           "h1{font-size:15px;margin:0 0 3px}h2{font-size:11px;margin:7px 0 2px;border-bottom:1px solid #999}ul{margin:2px 0;padding-left:14px}"
           "li{margin:0 0 1px}.lac{color:#8a4b00}.aviso{font-style:italic;margin:0}table{border-collapse:collapse;width:100%;font-size:8.5px}"
           "th,td{border:1px solid #bbb;padding:1px 3px;text-align:left;vertical-align:top}.final{font-weight:bold;border:1px solid #222;padding:3px;margin-top:6px}"
           "@media print{body{max-width:none}}")
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>{e(c['titulo'])}</title><style>{css}</style></head>"
            f"<body>{''.join(p)}</body></html>")


_SUBST = {"→": "->", "–": "-", "—": "-", "≤": "<=", "≥": ">=", "“": '"', "”": '"', "‘": "'", "’": "'", "•": "-", "≈": "~", "×": "x", "−": "-", "…": "..."}


def _latin1(s: str) -> str:
    for k, v in _SUBST.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def cartao_pdf(c: dict) -> bytes | None:
    """PDF de uma página A4 (fonte padrão Helvetica, só latin-1: acentos do português ok). None se `fpdf2` não estiver instalado."""
    try:
        from fpdf import FPDF
    except ImportError:
        return None
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(10, 8, 10)
    pdf.add_page()
    w = pdf.w - 20

    def par(txt, tam=7.5, estilo="", h=3.4, recuo=0):
        pdf.set_font("Helvetica", estilo, tam)
        pdf.set_x(10 + recuo)
        pdf.multi_cell(w - recuo, h, _latin1(txt), new_x="LMARGIN", new_y="NEXT")

    par(c["titulo"], 13, "B", 6)
    par(c["escopo"], 7, "I")
    for b in c["blocos"]:
        pdf.ln(1)
        par(b["titulo"], 9, "B", 4.2)
        if b.get("tabela"):
            for l in b["tabela"]["linhas"]:
                par(" | ".join(l), 6.8, "", 3.1, 2)
        for i in b["itens"]:
            par("- " + i, 7, "", 3.2, 2)
    pdf.ln(1.5)
    par(c["aviso_final"], 9, "B", 4.5)
    return bytes(pdf.output())


def n_paginas_pdf(dados: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", dados))
