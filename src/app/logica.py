"""Lógica do app SULCO, sem Streamlit (testável).

Regras: só lê arquivos locais; nenhum número vem do código; dado ausente vira lacuna.

Consumo dos outros módulos (contrato JSON, docs/01_VISAO_GERAL.md seção 7):
- Cenários: arquivos `*.json` em `data/processed/cenarios/` (ou env SULCO_CENARIOS_DIR).
  Cada arquivo: lista de cenários, ou {"cenarios": [...]}, ou um cenário só.
  Cenário: local, cultura_atual, rotacao, score, faixa_incerteza, criterios{nome:
  {valor, unidade, nota, fonte, pagina}}, lacunas[], riscos_revisao_local[],
  trechos[{n, arquivo, pagina, texto}]. Campos opcionais: "atual" (bool), "sintetico" (bool).
  `local` pode ser texto (id) ou {"ponto_id"|"id", "nome", ...}.
- Perfil: diagnostico.json do módulo de modelos (lista de pontos com `ponto_id`).
- Limites: relatorio_modelos.md (tabelas lidas do texto).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LACUNA = "LACUNA (dado não disponível)"
CAMPOS_CRITERIO = ("valor", "unidade", "nota", "fonte", "pagina")
CAMPOS_CENARIO = ("local", "cultura_atual", "rotacao", "score", "faixa_incerteza",
                  "criterios", "lacunas", "riscos_revisao_local", "trechos")
ROTULO_SINTETICO = "SINTÉTICO — só teste de formato"


def pasta_cenarios() -> Path:
    return Path(os.environ.get("SULCO_CENARIOS_DIR", RAIZ / "data/processed/cenarios"))


def caminhos_diagnostico() -> list[Path]:
    if "SULCO_DIAGNOSTICO" in os.environ:
        return [Path(os.environ["SULCO_DIAGNOSTICO"])]
    return [RAIZ / "data/processed/diagnostico/diagnostico.json",
            RAIZ / "data/processed/modelos/diagnostico.json"]


def caminho_relatorio() -> Path:
    return Path(os.environ.get("SULCO_RELATORIO", RAIZ / "data/processed/modelos/relatorio_modelos.md"))


# ---------- cenários ----------
def local_id(local) -> str | None:
    if isinstance(local, dict):
        v = local.get("ponto_id") or local.get("id") or local.get("nome")
        return str(v) if v else None
    return str(local) if local not in (None, "") else None


def local_nome(local) -> str:
    if isinstance(local, dict) and local.get("nome"):
        return str(local["nome"])
    return local_id(local) or LACUNA


def texto_rotacao(rotacao) -> str:
    if isinstance(rotacao, (list, tuple)):
        return " → ".join(str(x) for x in rotacao) if rotacao else LACUNA
    return str(rotacao) if rotacao not in (None, "") else LACUNA


def e_sintetico(cenario: dict, arquivo: str = "") -> bool:
    return bool(cenario.get("sintetico")) or Path(arquivo).name.upper().startswith("SINTETICO")


def e_atual(cenario: dict) -> bool:
    if "atual" in cenario:
        return bool(cenario["atual"])
    rot, cult = cenario.get("rotacao"), cenario.get("cultura_atual")
    if isinstance(rot, str) and isinstance(cult, str):
        return rot.strip().lower() == cult.strip().lower()
    return False


def carregar_cenarios(pasta: Path | None = None) -> tuple[list[dict], list[str]]:
    """Lê todos os JSON da pasta. Devolve (cenarios, erros). Nunca levanta por arquivo ruim."""
    pasta = pasta or pasta_cenarios()
    cenarios, erros = [], []
    if not pasta.is_dir():
        return [], []
    for arq in sorted(pasta.glob("*.json")):
        try:
            dado = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            erros.append(f"{arq.name}: não foi possível ler ({e.__class__.__name__}).")
            continue
        if isinstance(dado, dict) and isinstance(dado.get("cenarios"), list):
            itens = dado["cenarios"]
        elif isinstance(dado, list):
            itens = dado
        elif isinstance(dado, dict):
            itens = [dado]
        else:
            erros.append(f"{arq.name}: formato inesperado.")
            continue
        for c in itens:
            if isinstance(c, dict):
                c = dict(c)
                c["_arquivo"] = arq.name
                cenarios.append(c)
            else:
                erros.append(f"{arq.name}: item de cenário inválido.")
    return cenarios, erros


def locais_disponiveis(cenarios: list[dict]) -> dict[str, str]:
    """id -> nome, só de locais com cenário."""
    out: dict[str, str] = {}
    for c in cenarios:
        lid = local_id(c.get("local"))
        if lid and lid not in out:
            out[lid] = local_nome(c.get("local"))
    return out


def culturas_do_local(cenarios: list[dict], lid: str) -> list[str]:
    vistas: list[str] = []
    for c in cenarios:
        if local_id(c.get("local")) == lid and c.get("cultura_atual") and c["cultura_atual"] not in vistas:
            vistas.append(str(c["cultura_atual"]))
    return vistas


def selecionar(cenarios: list[dict], lid: str, cultura: str) -> list[dict]:
    sel = [c for c in cenarios if local_id(c.get("local")) == lid and str(c.get("cultura_atual")) == cultura]
    # a estratégia atual primeiro, depois a ordem do arquivo (não reordenamos por nota: quem escolhe é o técnico)
    return sorted(sel, key=lambda c: 0 if e_atual(c) else 1)


def problemas_cenario(c: dict) -> list[str]:
    """Campos do contrato ausentes ou vazios (viram lacunas visíveis)."""
    p = [f"Campo ausente no cenário: {k}." for k in CAMPOS_CENARIO if k not in c]
    crit = c.get("criterios")
    if isinstance(crit, dict):
        for nome, v in crit.items():
            if not isinstance(v, dict):
                p.append(f"Critério '{nome}' em formato inválido.")
                continue
            falta = [k for k in CAMPOS_CRITERIO if v.get(k) in (None, "")]
            if falta:
                p.append(f"Critério '{nome}' sem: {', '.join(falta)}.")
    return p


def faixa(c: dict) -> tuple[float, float] | None:
    f = c.get("faixa_incerteza")
    try:
        if isinstance(f, (list, tuple)) and len(f) == 2:
            lo, hi = float(f[0]), float(f[1])
        elif isinstance(f, dict):
            lo = float(next(f[k] for k in ("min", "inferior", "baixo", "lo") if k in f))
            hi = float(next(f[k] for k in ("max", "superior", "alto", "hi") if k in f))
        else:
            return None
    except (StopIteration, TypeError, ValueError):
        return None
    return (lo, hi)


def _num_ou_none(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _pct(x) -> str:
    x = _num_ou_none(x)
    return LACUNA if x is None else f"{x * 100:.0f}%"


def resumo_incerteza(c: dict) -> dict:
    """Frases simples sobre a faixa de incerteza, P(top-N), cobertura, empate e janela (só com o que está no JSON).

    Funciona só quando `faixa_incerteza` é um dict do Monte Carlo do motor (tem `p_topN` ou `cobertura`);
    nos outros formatos devolve {'disponivel': False} e o app mantém a exibição antiga.
    """
    f = c.get("faixa_incerteza")
    if not isinstance(f, dict):
        return {"disponivel": False}
    chave_top = next((k for k in f if re.fullmatch(r"p_top\d+", k)), None)
    if chave_top is None and "cobertura" not in f:
        return {"disponivel": False}
    lo, hi = _num_ou_none(f.get("score_p10", f.get("min"))), _num_ou_none(f.get("score_p90", f.get("max")))
    pcs = f.get("percentis") if isinstance(f.get("percentis"), list) and len(f.get("percentis")) == 2 else None
    nome_pc = f"{fmt_num(pcs[0])}% a {fmt_num(pcs[1])}%" if pcs else "faixa central"
    linhas = []
    if lo is not None and hi is not None:
        linhas.append(f"Faixa da pontuação nos sorteios ({nome_pc}): de {fmt_num(lo)} a {fmt_num(hi)}.")
    else:
        linhas.append(f"Faixa da pontuação: {LACUNA}.")
    out = {"disponivel": True, "faixa": (lo, hi), "linhas": linhas, "empate": [], "cobertura": [], "janela": []}
    if chave_top:
        n = chave_top[len("p_top"):]
        p3 = f.get(chave_top)
        p10, p90 = f.get("posicao_p10"), f.get("posicao_p90")
        linhas.append(f"Ficou entre as {n} primeiras em {_pct(p3)} dos sorteios; posição típica entre {fmt_num(p10)}º e "
                      f"{fmt_num(p90)}º lugar (quanto menor a faixa de posições, mais firme).")
    else:
        linhas.append("Estratégia atual: serve de comparação e não entra no ranking das alternativas.")
    emp = f.get("empate_tecnico_com")
    if isinstance(emp, list) and emp:
        out["empate"].append(f"Empate técnico com {len(emp)} outras culturas candidatas (as faixas de pontuação se "
                             "sobrepõem): os dados não separam estas opções. Quem decide entre elas é o técnico local.")
    cob = f.get("cobertura") if isinstance(f.get("cobertura"), dict) else {}
    rp, cp = cob.get("ranking_principal"), cob.get("completa")
    if isinstance(rp, dict):
        crit = ", ".join(str(x) for x in rp.get("criterios", [])) or LACUNA
        ptot = _num_ou_none(rp.get("peso_total")) or 0
        frac = (_num_ou_none(rp.get("peso_coberto")) or 0) / ptot if ptot else None
        out["cobertura"].append(f"Ranking feito só com os critérios que todas as culturas têm ({crit}), cobrindo "
                                f"{_pct(frac)} do peso total.")
    if isinstance(cp, dict):
        ptot = _num_ou_none(cp.get("peso_total")) or 0
        frac = (_num_ou_none(cp.get("peso_coberto")) or 0) / ptot if ptot else None
        sem = cp.get("criterios_sem_dado") or []
        txt = f"Dados disponíveis para esta cultura: {_pct(frac)} do peso total."
        if sem:
            txt += " Sem dado (lacuna, mostrada à parte): " + ", ".join(str(x) for x in sem) + "."
        out["cobertura"].append(txt)
    j = c.get("janela_plantio")
    if isinstance(j, dict):
        anos = j.get("anos") or [None, None, None]
        ae = j.get("adequacao_entre_anos") or {}
        out["janela"].append(
            f"Melhor época de plantio no clima de {fmt_num(anos[0])} a {fmt_num(anos[1])}: início por volta de "
            f"{fmt_num(j.get('melhor_inicio'))}, ciclo de {fmt_num(j.get('duracao_dias'))} dias (duração suposta: o ciclo real "
            f"precisa ser confirmado). Adequação entre anos: típica {fmt_num(ae.get('p50'))}, em anos ruins "
            f"{fmt_num(ae.get('p10'))} (0 a 1).")
    return out


def fmt_num(x) -> str:
    if isinstance(x, bool) or x is None or x == "":
        return LACUNA
    if isinstance(x, (int, float)):
        return f"{x:g}" if abs(x) >= 1e-3 or x == 0 else f"{x:.3g}"
    return str(x)


def numero_citacao(c: dict, crit: dict) -> int | None:
    """[n] do trecho que sustenta o critério (campo `trecho_n` ou arquivo+página iguais)."""
    trechos = [t for t in (c.get("trechos") or []) if isinstance(t, dict)]
    n = crit.get("trecho_n")
    if n is not None and any(t.get("n") == n for t in trechos):
        return n
    for t in trechos:
        if t.get("arquivo") == crit.get("fonte") and str(t.get("pagina")) == str(crit.get("pagina")) \
                and t.get("n") is not None:
            return t["n"]
    return None


def linha_criterio(c: dict, nome: str, crit) -> str:
    """Frase em template, só com valores do JSON."""
    if not isinstance(crit, dict):
        return f"{nome}: {LACUNA}."
    valor = fmt_num(crit.get("valor"))
    un = crit.get("unidade") or ""
    nota = fmt_num(crit.get("nota"))
    fonte = crit.get("fonte") or LACUNA
    pag = crit.get("pagina")
    n = numero_citacao(c, crit)
    cit = f" [{n}]" if n is not None else " [sem trecho citado: lacuna]"
    pag_txt = f", p. {pag}" if pag not in (None, "") else ", página: LACUNA"
    return f"{nome}: valor {valor} {un}".rstrip() + f" (nota {nota}; fonte: {fonte}{pag_txt}){cit}"


def _nota_num(crit) -> float | None:
    if isinstance(crit, dict) and isinstance(crit.get("nota"), (int, float)) and not isinstance(crit["nota"], bool):
        return float(crit["nota"])
    return None


def explicar(c: dict) -> dict:
    """Template (sem LLM). Devolve listas de frases: por_que, beneficios, lacunas, riscos."""
    crit = c.get("criterios") if isinstance(c.get("criterios"), dict) else {}
    notas = {k: _nota_num(v) for k, v in crit.items()}
    com_nota = {k: v for k, v in notas.items() if v is not None}
    por_que = [linha_criterio(c, k, v) for k, v in crit.items()]
    if com_nota:
        mx, mn = max(com_nota.values()), min(com_nota.values())
        melhores = [k for k, v in com_nota.items() if v == mx]
        piores = [k for k, v in com_nota.items() if v == mn and mn != mx]
    else:
        melhores, piores = [], []
    beneficios = [f"Maior nota entre os critérios deste cenário: {linha_criterio(c, k, crit[k])}" for k in melhores]
    if not beneficios:
        beneficios = [f"Benefícios: {LACUNA}."]
    lac = list(c.get("lacunas") or []) + problemas_cenario(c)
    lac += [f"Critério '{k}' sem nota numérica." for k in crit if k not in com_nota]
    if not (c.get("trechos") or []):
        lac.append("Sem evidência citada (nenhum trecho do acervo) para este cenário.")
    riscos = list(c.get("riscos_revisao_local") or [])
    riscos += [f"Menor nota entre os critérios: {linha_criterio(c, k, crit[k])}" for k in piores]
    if not riscos:
        riscos = [f"Riscos para revisão local: {LACUNA}."]
    return {"por_que": por_que or [f"Por quê: {LACUNA}."], "beneficios": beneficios,
            "lacunas": lac, "riscos": riscos}


# ---------- perfil (diagnóstico) ----------
def carregar_diagnostico() -> tuple[list[dict], Path | None]:
    for p in caminhos_diagnostico():
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(d, list):
                return [x for x in d if isinstance(x, dict)], p
    return [], None


def perfil_do_local(diag: list[dict], lid: str) -> dict | None:
    for r in diag:
        if str(r.get("ponto_id")) == lid:
            return r
    return None


def resumo_perfil(r: dict) -> dict:
    """Extrai do diagnóstico só o que existe; o resto vira lacuna."""
    saz = r.get("sazonalidade_ndvi") or {}
    ver = r.get("veranicos") or {}
    dias = [e.get("maior_veranico_dias") for e in ver.get("por_estacao", []) if isinstance(e, dict)
            and e.get("maior_veranico_dias") is not None]
    tend = []
    for nome, t in (r.get("tendencias") or {}).items():
        if isinstance(t, dict):
            tend.append({"variável": nome, "anos": t.get("n_anos"), "inclinação por ano": t.get("inclinacao_por_ano"),
                         "Mann-Kendall": t.get("mann_kendall"), "p": t.get("p_valor"), "situação": t.get("resultado")})
    return {"confianca": r.get("confianca"), "confianca_nota": r.get("confianca_nota"),
            "periodo": r.get("periodo"), "anos_validos": r.get("n_anos_validos"),
            "slot_pico": saz.get("slot_pico"), "slot_vale": saz.get("slot_vale"),
            "forca_sazonalidade": saz.get("forca_sazonalidade"),
            "maior_veranico_dias": max(dias) if dias else None, "n_estacoes": ver.get("n_estacoes"),
            "tendencias": tend, "lacunas": r.get("lacunas") or [], "limites": r.get("limites") or []}


# ---------- limites dos dados ----------
LIMITES_FIXOS = [
    "NDVI vem de pixels de 250 m (MODIS): pode misturar o seu talhão com mato, estrada ou vizinhos.",
    "O clima (NASA POWER) vem de células de cerca de 50 km: a chuva da sua roça pode ser bem diferente.",
    "A umidade do solo (SMAP) tem cerca de 9 km: não enxerga o solo do seu talhão.",
    "NDVI mostra o verdor da vegetação. Não é produtividade, nem qualidade do solo, nem colheita.",
    "O app não prevê o clima. Ele descreve o que aconteceu no passado.",
    "As relações mostradas são associações históricas, não prova de causa e efeito.",
    "Toda sugestão é um cenário a avaliar com técnico local. Não é promessa de que uma rotação rende mais.",
]


def _tabela_md(texto: str, titulo: str) -> list[list[str]]:
    """Linhas (células) da primeira tabela após o cabeçalho que contém `titulo`."""
    linhas = texto.splitlines()
    for i, ln in enumerate(linhas):
        if ln.startswith("#") and titulo in ln:
            tab = []
            for l2 in linhas[i + 1:]:
                if l2.startswith("#") and tab:
                    break
                if l2.strip().startswith("|"):
                    cels = [x.strip() for x in l2.strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-{2,}:?", x) for x in cels):
                        tab.append(cels)
                elif tab:
                    break
            return tab
    return []


def _num(s: str) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", s.replace("−", "-"))
    return float(m.group().replace(",", ".")) if m else None


def ler_relatorio(caminho: Path | None = None) -> dict:
    """Lê os números reais do relatório. Devolve {'disponivel': bool, ...} sem inventar nada."""
    caminho = caminho or caminho_relatorio()
    if not caminho.is_file():
        return {"disponivel": False, "motivo": f"{caminho.name} não encontrado."}
    txt = caminho.read_text(encoding="utf-8")
    hold = _tabela_md(txt, "Holdout temporal")
    cob = _tabela_md(txt, "Cobertura da faixa")
    if len(hold) < 2:
        return {"disponivel": False, "motivo": "Tabela de holdout não encontrada no relatório."}
    cab = hold[0]
    try:
        i_skill = next(i for i, c in enumerate(cab) if c.lower().startswith("skill"))
    except StopIteration:
        return {"disponivel": False, "motivo": "Coluna de skill não encontrada no relatório."}
    holdout = [{"modelo": r[0], "skill": _num(r[i_skill]), "linha": dict(zip(cab, r))} for r in hold[1:]
               if len(r) > i_skill]
    modelo = re.search(r"\*\*Modelo:\s*([^.*]+)\.?\*\*", txt)
    sintetico = bool(re.search(r"SINTETICO|SINTÉTICO", txt[:600]))
    nao_supera = [m for m in holdout if m["modelo"].lower() != "climatologia"
                  and m["skill"] is not None and m["skill"] <= 0]
    return {"disponivel": True, "holdout": holdout, "cobertura": {"cabecalho": cob[0] if cob else [], "linhas": cob[1:]},
            "modelo_escolhido": modelo.group(1).strip() if modelo else None,
            "sem_ganho_no_holdout": [m["modelo"] for m in nao_supera],
            "sintetico": sintetico, "arquivo": caminho.name}
