"""Lógica do MVP do SULCO (sem Streamlit; testável). Só lê arquivos locais, nunca chama API.

Fluxo: local (ponto) + cultura atual + prioridade -> diagnóstico do local (arquivo pré-calculado) ->
motor de culturas (src/culturas: ciclo + Monte Carlo, ~0,4 s) -> 3 estratégias (atual + 2) com evidência do acervo
(cache pré-calculado) -> cenário de clima (recalcula o motor com chuva/temperatura perturbadas).

Regras: todo número exibido vem de arquivo ou de código rodado; o que falta vira LACUNA; nada agronômico
é escrito aqui de memória. Pesos por prioridade são SUPOSIÇÃO (ver PRIORIDADES).
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.coleta.nomes_ibge import nome_derivado
from src.culturas import ciclo as ciclo_mod
from src.culturas.motor import avaliar_local, gerar_cenarios
from src.culturas.parametros import Parametros
from src.culturas.rotacao import gerar_rotacoes
from src.culturas.risco_solo import solo_de_linha
from src.culturas.rotacao_milp import otimizar_com_incerteza
from src.culturas.tabela_culturas import carregar as carregar_tabela_culturas

RAIZ = Path(__file__).resolve().parents[2]
LACUNA = "LACUNA (dado não disponível)"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
N_QUINZENAS = 24
LIMIAR_Z_ESTRESSE = -1.0   # convenção de apresentação do app: z <= -1 = "abaixo do normal" (não é limiar agronômico)
MIN_ANOS_ESTRESSE = 5      # mínimo de anos por quinzena para falar de frequência
# Limites dos controles de cenário: escolha de apresentação, NÃO é previsão de clima nem faixa de projeção.
CHUVA_FATOR_MIN, CHUVA_FATOR_MAX = 0.7, 1.3
TEMP_DELTA_MIN, TEMP_DELTA_MAX = 0.0, 3.0
N_SORTEIOS_APP = 10000
ZARC_PADRAO = True   # decisão do usuário (2026-11-13): ZARC ligado por padrão no app; só se aplica a municípios do Ceará com ZARC

AVISO = "Cenário a avaliar com técnico local. O app apoia a conversa; não decide e não promete que a rotação rende mais."

# ---------------------------------------------------------------------------------------------- prioridades
# Cada prioridade vira uma ORDEM de importância entre critérios (faixas ordinais), nunca pesos exatos.
# O motor sorteia pesos que respeitam a ordem (SMAA-O: Parametros.ordem_pesos). TUDO ISTO É SUPOSIÇÃO a validar com técnico.
PRIORIDADES: dict[str, dict] = {
    "sem": {
        "rotulo": "Sem prioridade (pesos livres)",
        "ordem": None, "bloco": "principal",
        "regra": "Nenhuma ordem de importância entre os critérios: o motor sorteia pesos livres (sem preferência).",
    },
    "alimento": {
        "rotulo": "Garantir alimento e diversificação (ODS 2)",
        "ordem": ("familia_diferente", "n_na_biomassa", "chuva", "temperatura", "palha"), "bloco": "completo",
        "consorcio_modo": "rotulo",
        "regra": ("Foco no ODS 2 (Fome Zero e Agricultura Sustentável - Meta 2.4): prioriza a quebra de monocultura "
                  "(família botânica diferente) para diversificar nutrientes (carboidrato + proteína vegetal) e reduzir o risco "
                  "de quebra de safra familiar por estiagem, valorizando espécies fixadoras de nitrogênio (n_na_biomassa) e "
                  "ativando evidências científicas de Land Equivalent Ratio (LER > 1) para consórcios no Semiárido."),
    },
    "agua": {
        "rotulo": "Economizar água",
        "ordem": ("chuva", "temperatura", "familia_diferente"), "bloco": "principal",
        "regra": ("SUPOSIÇÃO a validar com técnico: o critério chuva (quanto a chuva do ciclo cabe na faixa que a cultura "
                  "aceita) passa a valer mais que temperatura e que família botânica. A ideia é preferir culturas que se "
                  "encaixam na chuva do local e talvez precisem de menos água extra. O app NÃO mede consumo de água nem "
                  "irrigação: a demanda hídrica do ciclo aparece só onde a tabela de culturas tem o dado."),
    },
    "solo": {
        "rotulo": "Proteger o solo",
        "ordem": ("palha", "n_na_biomassa", "familia_diferente", "chuva", "temperatura"), "bloco": "completo",
        "regra": ("SUPOSIÇÃO a validar com técnico: palha (cobertura do solo), nitrogênio na biomassa e família botânica "
                  "diferente passam a valer mais que chuva e temperatura. Palha e nitrogênio têm dado só para parte das "
                  "culturas; para as demais o dado que falta entra como incerteza (nem prêmio, nem castigo) e aparece como "
                  "lacuna. O app NÃO mede erosão nem matéria orgânica."),
    },
    "renda": {
        "rotulo": "Renda extra",
        "ordem": None, "bloco": "principal",
        "regra": ("Nos três caminhos (seção 3), escolher 'renda extra' NÃO altera o ranking: o projeto não tem preço, custo nem mercado, e o "
                  "resultado é o mesmo de 'sem prioridade' (LACUNA). Só na rotação de 3 safras (3b) a prioridade usa a receita BRUTA por hectare do "
                  "IBGE (não é lucro); cultura sem esse valor vira lacuna."),
        "lacuna": "sem dado de preço/custo/mercado: o app não consegue falar de renda",
    },
}
PRIORIDADES_AUDITORIA = ("sem", "alimento", "agua", "solo")   # 'renda' = 'sem' por construção


def dir_mvp() -> Path:
    return Path(os.environ.get("SULCO_MVP_DIR", RAIZ / "data/processed/mvp"))


def dir_diagnostico() -> Path:
    return Path(os.environ.get("SULCO_DIAGNOSTICO_DIR", RAIZ / "data/processed/diagnostico"))


def dir_dados() -> Path:
    return Path(os.environ.get("SULCO_DADOS_DIR", RAIZ / "data/processed"))


def br(x, nd: int = 1) -> str:
    """Número no formato brasileiro; None/NaN vira LACUNA."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return LACUNA
    return f"{x:.{nd}f}".replace(".", ",")


def nota_txt(n) -> str:
    return "sem nota (lacuna)" if n is None else f"nota {br(n, 2)} de 1"


def pct(x, nd: int = 0) -> str:
    return LACUNA if x is None else br(100 * x, nd) + "%"


# ---------------------------------------------------------------------------------------------- carga (com cache)
@lru_cache(maxsize=4)
def _nomes_do_csv(caminho: str) -> dict[str, str]:
    """`nome` oficial (com acento, IBGE) gravado em pontos.csv por src/coleta/nomes_ibge.py; sem a coluna = vazio."""
    arq = Path(caminho)
    if not arq.exists():
        return {}
    p = pd.read_csv(arq)
    if "nome" not in p.columns:
        return {}
    return {i: n for i, n in zip(p["ponto_id"], p["nome"]) if isinstance(n, str) and n.strip()}


def nome_do_ponto(ponto_id: str) -> str:
    """Nome do ponto: o oficial de pontos.csv (coluna `nome`, IBGE) quando existe; senão o derivado do id (sem acento)."""
    return _nomes_do_csv(str(dir_dados() / "pontos.csv")).get(ponto_id) or nome_derivado(ponto_id)


@lru_cache(maxsize=1)
def carregar_pontos() -> pd.DataFrame:
    p = pd.read_csv(dir_dados() / "pontos.csv")
    p["nome"] = [nome_do_ponto(x) for x in p["ponto_id"]]
    p["uf"] = p["ponto_id"].str.rsplit("_", n=1).str[1].str.upper()
    p["_ordem"] = p["nome"].map(lambda n: unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower())
    return p.sort_values(["uf", "_ordem"]).drop(columns="_ordem").reset_index(drop=True)


@lru_cache(maxsize=1)
def carregar_tabela() -> dict:
    return carregar_tabela_culturas()


def culturas_disponiveis() -> dict[str, str]:
    t = carregar_tabela()
    return {cid: c["cultura_pt"] for cid, c in t.items()}


@lru_cache(maxsize=1)
def _clima_df() -> pd.DataFrame:
    return pd.read_parquet(dir_dados() / "clima_diario.parquet", columns=["ponto_id", "data", "chuva_mm", "tmax_c", "tmin_c"])


@lru_cache(maxsize=256)
def clima_ponto(ponto_id: str) -> ciclo_mod.ClimaPonto:
    """Série diária do ponto (NÃO modificar os arrays: use `perturbar`)."""
    return ciclo_mod.ClimaPonto.de_dataframe(_clima_df(), ponto_id)


def perturbar(c: ciclo_mod.ClimaPonto, fator_chuva: float, delta_t: float) -> ciclo_mod.ClimaPonto:
    """Cenário: chuva diária x fator e temperatura diária + delta (uniformes em todo o ano; NaN continua NaN)."""
    if fator_chuva < 0:
        raise ValueError("fator_chuva não pode ser negativo")
    return replace(c, chuva=c.chuva * fator_chuva, tmed=c.tmed + delta_t)


@lru_cache(maxsize=1)
def carregar_diagnosticos() -> dict[str, dict]:
    arq = dir_diagnostico() / "diagnostico.json"
    if not arq.is_file():
        return {}
    return {str(r["ponto_id"]): r for r in json.loads(arq.read_text(encoding="utf-8")) if isinstance(r, dict)}


@lru_cache(maxsize=1)
def _anomalias() -> pd.DataFrame | None:
    arq = dir_diagnostico() / "anomalias.parquet"
    return pd.read_parquet(arq) if arq.is_file() else None


@lru_cache(maxsize=1)
def carregar_evidencias() -> dict | None:
    arq = dir_mvp() / "evidencias_rag.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.is_file() else None


@lru_cache(maxsize=1)
def carregar_auditoria() -> dict | None:
    arq = dir_mvp() / "auditoria_alternativas.json"
    return json.loads(arq.read_text(encoding="utf-8")).get("resumo") if arq.is_file() else None


def limpar_caches() -> None:
    for f in (carregar_pontos, carregar_tabela, _clima_df, clima_ponto, carregar_diagnosticos, _anomalias,
              carregar_evidencias, carregar_auditoria):
        f.cache_clear()


# ---------------------------------------------------------------------------------------------- estratégias
def parametros(prioridade: str, n_sorteios: int = N_SORTEIOS_APP, usar_zarc: bool = ZARC_PADRAO) -> Parametros:
    cfg = PRIORIDADES[prioridade]
    consorcio_modo = cfg.get("consorcio_modo", "sem")
    return Parametros(n_sorteios=n_sorteios, ordem_pesos=cfg["ordem"], bloco_ranking=cfg["bloco"],
                      usar_zarc=usar_zarc, consorcio_modo=consorcio_modo)


def _anexar_evidencias(c: dict, alvo: str) -> None:
    from src.pipeline.gerar_cenarios import anexar_evidencias
    ev = carregar_evidencias()
    if ev is None or alvo not in ev:
        c["trechos"] = []
        c["lacunas"].append("evidências: cache do acervo (evidencias_rag.json) não encontrado; nenhum trecho citado.")
        return
    anexar_evidencias(c, ev[alvo])
    sem = [k for k, d in c["criterios"].items() if d.get("evidencia_rag", {}).get("sem_evidencia")]
    if sem:
        c["lacunas"].append("sem evidência no acervo para: " + ", ".join(sem))


def descartes_caminhos(av: dict, tab: dict, cultura_atual: str, regras) -> dict | None:
    """Quantas alternativas viáveis as regras duras do agricultor tiraram dos 3 caminhos (None = sem regra). Mesma conta do motor.

    `todas_descartadas`: havia alternativa viável e as regras tiraram todas (a tela diz isso em frase simples)."""
    if regras is None:
        return None
    from src.culturas import regras_duras as rd
    fam = {c: (tab[c]["atributos"].get("familia_botanica") or {}).get("valor") for c in tab}
    cand = [c for c in tab if c != cultura_atual and av["culturas"][c]["estado"] == "viavel"]
    ok, fora = rd.separar([(cultura_atual, c) for c in cand], fam, regras)
    return {"n_viaveis": len(cand), "n_descartadas": len(fora), "n_restantes": len(ok), "todas_descartadas": bool(cand) and not ok,
            "descartadas_por_motivo": rd.resumo_descartes(fora), "descartadas": [{"cultura": d["sequencia"][1], "motivos": d["motivos"]} for d in fora]}


def calcular(ponto_id: str, cultura_atual: str, prioridade: str = "sem", fator_chuva: float = 1.0,
             delta_t: float = 0.0, n_sorteios: int = N_SORTEIOS_APP, com_evidencias: bool = True, regras=None) -> dict:
    """Atual + 2 alternativas (motor), com local, evidências e lacunas. `av` traz a avaliação de todas as culturas.

    `regras`: RegrasDuras do agricultor (ou None). Alternativa que viola regra nunca entra; a cultura atual fica sempre."""
    t0 = time.perf_counter()
    tab = carregar_tabela()
    pts = carregar_pontos().set_index("ponto_id")
    if ponto_id not in pts.index:
        raise KeyError(f"ponto '{ponto_id}' não está em pontos.csv")
    p = parametros(prioridade, n_sorteios)
    clima = clima_ponto(ponto_id)
    if fator_chuva != 1.0 or delta_t != 0.0:
        clima = perturbar(clima, fator_chuva, delta_t)
    cens = gerar_cenarios({"local": ponto_id}, cultura_atual, tab, clima=clima, params=p, regras=regras)
    av = avaliar_local(tab, clima, p)
    linha = pts.loc[ponto_id]
    for c in cens:
        alvo = c["rotacao"][1]
        c["atual"] = alvo == cultura_atual
        c["local"] = {"ponto_id": ponto_id, "nome": linha["nome"], "lat": float(linha["lat"]), "lon": float(linha["lon"]),
                      "celula_power": str(linha["celula_power"])}
        c["prioridade"] = prioridade
        if com_evidencias:
            _anexar_evidencias(c, alvo)
        if PRIORIDADES[prioridade].get("lacuna"):
            c["lacunas"].append(PRIORIDADES[prioridade]["lacuna"])
    return {"cenarios": cens, "av": av, "params": p, "clima": clima, "prioridade": prioridade, "regras": regras,
            "descartes": descartes_caminhos(av, tab, cultura_atual, regras), "segundos": time.perf_counter() - t0}


def bloco_ranking(c: dict, prioridade: str) -> dict:
    """Campos de ranking do bloco que escolheu as alternativas (principal ou complemento com N e palha)."""
    f = c.get("faixa_incerteza") or {}
    if PRIORIDADES[prioridade]["bloco"] == "completo":
        return f.get("complemento_n_palha") or {}
    return f


CHAVES_RANKING = ("p_top3", "p_1o", "posicao_p10", "posicao_p90", "posicao_media", "aceitabilidade_posicao",
                  "empate_tecnico_com", "empate_tecnico")


def visao_faixa(c: dict, prioridade: str) -> dict:
    """Cópia do cenário cuja `faixa_incerteza` reflete o bloco usado na escolha (para `logica.resumo_incerteza`)."""
    f = c.get("faixa_incerteza")
    if not isinstance(f, dict) or PRIORIDADES[prioridade]["bloco"] != "completo":
        return c
    comp = {k: v for k, v in (f.get("complemento_n_palha") or {}).items() if k != "criterios"}
    novo = {k: v for k, v in f.items() if k not in CHAVES_RANKING}   # tira o ranking do bloco principal
    novo.update(comp)
    cc = dict(c)
    cc["faixa_incerteza"] = novo
    return cc


# ---------------------------------------------------------------------------------------------- textos das estratégias
def fonte_curta(d: dict) -> str:
    """Fonte do dado em poucas palavras (a referência completa vai em `fonte_completa`)."""
    f = d.get("fonte")
    if not f:
        return LACUNA
    f = f.split(" (")[0].strip()
    pag = d.get("pagina")
    return f"{f[:90]}{'…' if len(f) > 90 else ''}" + (f", p. {pag}" if pag not in (None, "") and len(str(pag)) <= 20 else "")


def fonte_completa(d: dict) -> str:
    return (f"{d.get('fonte') or LACUNA} | local no documento: {d.get('pagina') or LACUNA} | url: {d.get('url') or LACUNA}"
            + (f" | contexto: {d['contexto']}" if d.get("contexto") else ""))


def texto_evidencia(d: dict) -> str:
    n = d.get("trecho_n")
    return (f"trecho relacionado do acervo: [{n}] (achado por busca; pode não confirmar o valor)" if n is not None
            else "sem evidência no acervo para este critério")


def linhas_criterios(c: dict) -> list[dict]:
    """Uma linha por critério, só com valores do JSON: critério, o que significa, nota, fonte, se entrou no ranking."""
    out = []
    for nome, d in (c.get("criterios") or {}).items():
        v, nota = d.get("valor"), d.get("nota")
        if nome == "temperatura" and isinstance(v, dict):
            txt = (f"temperatura média no ciclo: {br(v.get('perfil'))} °C; a cultura aceita de {br(v.get('temp_min_abs_c'))} a "
                   f"{br(v.get('temp_max_abs_c'))} °C e rende melhor entre {br(v.get('temp_otima_min_c'))} e "
                   f"{br(v.get('temp_otima_max_c'))} °C")
        elif nome == "chuva" and isinstance(v, dict):
            txt = (f"chuva no ciclo: {br(v.get('perfil'), 0)} mm; a cultura aceita de {br(v.get('chuva_min_abs_mm'), 0)} a "
                   f"{br(v.get('chuva_max_abs_mm'), 0)} mm e rende melhor entre {br(v.get('chuva_otima_min_mm'), 0)} e "
                   f"{br(v.get('chuva_otima_max_mm'), 0)} mm")
        elif nome == "familia_diferente" and isinstance(v, dict):
            igual = v.get("familia") == v.get("familia_atual")
            txt = (f"família botânica: {v.get('familia')} (a atual é {v.get('familia_atual')}); "
                   + ("é a MESMA família da atual" if igual else "é família DIFERENTE da atual"))
        elif nome == "n_na_biomassa" and v is not None:
            txt = f"nitrogênio acumulado na parte aérea: {br(v, 0)} kg/ha (estudo pontual, não do semiárido)"
        elif nome == "palha" and v is not None:
            txt = f"palha (matéria seca): {br(v, 0)} kg/ha (estudo pontual, não do semiárido)"
        else:
            txt = None
        out.append({"criterio": nome, "texto": txt, "nota": nota, "tem_dado": txt is not None,
                    "fonte": f"fonte do dado: {fonte_curta(d)}" if txt else None,
                    "fonte_completa": fonte_completa(d) if txt else None,
                    "evidencia": texto_evidencia(d) if txt else None, "no_ranking": bool(d.get("no_ranking_principal")),
                    "lacuna": d.get("lacuna")})
    return out


NOME_CRITERIO = {"temperatura": "Temperatura", "chuva": "Chuva", "familia_diferente": "Família diferente da atual",
                 "n_na_biomassa": "Nitrogênio na biomassa", "palha": "Palha / cobertura do solo"}


def beneficios(c: dict) -> list[str]:
    """Pontos fortes = critérios com a maior nota entre os que têm dado. Cada um traz o dado e a fonte."""
    ls = [x for x in linhas_criterios(c) if x["tem_dado"] and isinstance(x["nota"], (int, float))]
    if not ls:
        return [f"Benefícios: {LACUNA}."]
    mx = max(x["nota"] for x in ls)
    return [f"{NOME_CRITERIO[x['criterio']]} (nota {br(x['nota'], 2)} de 1): {x['texto']}; {x['fonte']}; {x['evidencia']}"
            for x in ls if x["nota"] == mx]


def riscos(c: dict, prioridade: str) -> list[str]:
    out = list(c.get("riscos_revisao_local") or [])
    ls = [x for x in linhas_criterios(c) if x["tem_dado"] and isinstance(x["nota"], (int, float))]
    if ls:
        mn = min(x["nota"] for x in ls)
        mx = max(x["nota"] for x in ls)
        if mn < mx:
            out += [f"Ponto fraco pelos dados: {NOME_CRITERIO[x['criterio']]} (nota {br(x['nota'], 2)} de 1): {x['texto']}"
                    for x in ls if x["nota"] == mn]
    if PRIORIDADES[prioridade]["bloco"] == "completo":
        out.append("Nas notas de palha e nitrogênio cada cultura é comparada só com as outras que têm dado (escala mínimo-máximo), "
                   "e os valores vêm de estudos diferentes: a diferença pode refletir o estudo, não a cultura.")
    j = c.get("janela_plantio")
    if isinstance(j, dict):
        fv = j.get("fracao_anos_viaveis")
        if fv is not None and fv < 1:
            out.append(f"Na melhor época, em {pct(1 - fv)} dos anos de 2001 a 2024 o ciclo caiu fora da faixa que a cultura "
                       "aceita (chuva ou temperatura).")
    return out


def lacunas_estrategia(c: dict) -> list[str]:
    """Lacunas do cenário, sem as repetidas do clima/perfil; acrescenta critérios sem dado."""
    out = []
    for l in c.get("lacunas") or []:
        if l.startswith(("umidade do solo", "Empate técnico (intervalos")):
            continue
        out.append(l)
    for x in linhas_criterios(c):
        if not x["tem_dado"]:
            out.append(f"{NOME_CRITERIO[x['criterio']]}: sem dado com fonte para esta cultura (lacuna).")
    return list(dict.fromkeys(out))


def demanda_hidrica(c: dict) -> str:
    j = c.get("janela_plantio") or {}
    d, r = j.get("demanda_hidrica_mm_ciclo"), j.get("chuva_sobre_demanda_hidrica")
    if d is None:
        return "Demanda de água do ciclo: LACUNA (a tabela de culturas não tem este dado para esta cultura)."
    return (f"Demanda de água do ciclo na tabela: {br(d, 0)} mm. Chuva média no ciclo na melhor época: {br(j.get('chuva_ciclo_mm'), 0)} mm "
            f"(razão chuva/demanda {br(r, 2)}; informativo, não entra na nota).")


def frases_incerteza(c: dict, prioridade: str) -> dict:
    """Faixa, chance de ficar no topo, empate e cobertura de critérios, do bloco que escolheu as alternativas."""
    f = c.get("faixa_incerteza")
    if not isinstance(f, dict):
        return {"disponivel": False, "linhas": [], "cobertura": [], "empate": []}
    fx = bloco_ranking(c, prioridade)
    completo = PRIORIDADES[prioridade]["bloco"] == "completo"
    pcs = f.get("percentis") or [10, 90]
    lo, hi = fx.get("score_p10"), fx.get("score_p90")
    linhas = [f"Faixa da pontuação nos sorteios ({br(pcs[0], 0)}% a {br(pcs[1], 0)}%): de {br(lo)} a {br(hi)}."
              if lo is not None and hi is not None else f"Faixa da pontuação: {LACUNA}."]
    pt = fx.get("p_top3")
    if pt is not None:
        p10, p90 = fx.get("posicao_p10"), fx.get("posicao_p90")
        pos = f"sempre na posição {p10}º" if p10 == p90 else f"posição típica entre {p10}º e {p90}º lugar"
        linhas.append(f"Ficou entre as 3 primeiras em {pct(pt)} dos sorteios; {pos} (quanto menor a faixa de posições, mais firme).")
    else:
        linhas.append("Estratégia atual: serve de comparação e não entra no ranking das alternativas.")
    cob = f.get("cobertura") or {}
    cobertura = []
    if completo:
        cobertura.append("Ranking feito com os 5 critérios (temperatura, chuva, família, nitrogênio e palha). Onde falta dado de "
                         "nitrogênio ou palha, ele entra como incerteza, sem prêmio nem castigo.")
    else:
        rp = cob.get("ranking_principal") or {}
        if rp:
            crit = ", ".join(NOME_CRITERIO.get(x, x) for x in rp.get("criterios", []))
            cobertura.append(f"Ranking feito só com os critérios que todas as culturas têm ({crit}), cobrindo "
                             f"{pct(rp['peso_coberto'] / rp['peso_total'])} do peso total.")
    cp = cob.get("completa") or {}
    if cp.get("peso_total"):
        txt = f"Dados disponíveis para esta cultura: {pct(cp['peso_coberto'] / cp['peso_total'])} do peso total."
        if cp.get("criterios_sem_dado"):
            txt += " Sem dado (lacuna): " + ", ".join(NOME_CRITERIO.get(x, x) for x in cp["criterios_sem_dado"]) + "."
        cobertura.append(txt)
    emp = fx.get("empate_tecnico_com") or []
    empate = ([f"Empate técnico com {len(emp)} outras culturas candidatas (as faixas de pontuação se sobrepõem): os dados não "
               "separam estas opções. Quem decide entre elas é o técnico local."] if emp else [])
    return {"disponivel": True, "linhas": linhas, "cobertura": cobertura, "empate": empate}


def descricao_estrategia(c: dict, prioridade: str) -> dict:
    """Tudo o que a tela mostra de uma estratégia, em frases."""
    inc = frases_incerteza(c, prioridade)
    fx = bloco_ranking(c, prioridade)
    empatadas = fx.get("empate_tecnico_com") or []
    j = c.get("janela_plantio")
    epoca = None
    if isinstance(j, dict):
        epoca = (f"Melhor época para começar o plantio nos dados de {j['anos'][0]} a {j['anos'][1]}: por volta de "
                 f"{j['melhor_inicio']} (ciclo de {j['duracao_dias']} dias, duração suposta). Em anos típicos a adequação "
                 f"é {br(j['adequacao_entre_anos']['p50'], 2)} e em anos ruins {br(j['adequacao_entre_anos']['p10'], 2)} (0 a 1).")
    return {
        "criterios": linhas_criterios(c), "beneficios": beneficios(c), "riscos": riscos(c, prioridade),
        "lacunas": lacunas_estrategia(c), "epoca": epoca, "incerteza": inc, "empatadas": list(empatadas),
        "p_top3": fx.get("p_top3"), "faixa": (fx.get("score_p10"), fx.get("score_p90")),
        "demanda": demanda_hidrica(c) if prioridade == "agua" else None,
        "consorcio": c.get("consorcio"),
        "trechos": [t for t in (c.get("trechos") or []) if isinstance(t, dict)],
    }


# ---------------------------------------------------------------------------------------------- diagnóstico do local
def rotulo_quinzena(q: int) -> str:
    return f"{MESES[(q - 1) // 2]} {1 if q % 2 == 1 else 2}ª"


def rotulos_quinzenas(qs) -> str:
    return ", ".join(rotulo_quinzena(q) for q in qs) if qs else "nenhuma"


TENDENCIA_PT = {"no trend": "sem tendência clara", "increasing": "subindo", "decreasing": "caindo"}
VAR_PT = {"chuva_anual_mm": "chuva do ano (mm)", "temperatura_media_c": "temperatura média (°C)",
          "ndvi_pico": "pico anual de verdor (NDVI)"}


def estresse_por_quinzena(ponto_id: str, variavel: str = "ndvi") -> pd.DataFrame:
    """Por quinzena: nº de anos com dado, fração de anos 'abaixo do normal' (z <= LIMIAR_Z_ESTRESSE) e z médio."""
    a = _anomalias()
    if a is None:
        return pd.DataFrame(columns=["quinzena", "n_anos", "frac_abaixo", "z_medio"])
    d = a[(a["ponto_id"] == ponto_id) & (a["variavel"] == variavel)].dropna(subset=["z"])
    g = d.groupby("quinzena")["z"]
    out = pd.DataFrame({"n_anos": g.count(), "frac_abaixo": g.apply(lambda s: float((s <= LIMIAR_Z_ESTRESSE).mean())),
                        "z_medio": g.mean()}).reindex(range(1, N_QUINZENAS + 1))
    out.index.name = "quinzena"
    return out.reset_index()


def quinzenas_do_ciclo(inicio_dias: int, duracao: int) -> list[int]:
    """Quinzenas tocadas por um ciclo que começa `inicio_dias` após 1º/jan (ano de referência não bissexto)."""
    if duracao >= 365:
        return list(range(1, N_QUINZENAS + 1))
    base = pd.Timestamp("2001-01-01")
    qs = []
    for d in range(duracao):
        t = base + pd.Timedelta(days=(inicio_dias + d) % 365)
        q = (t.month - 1) * 2 + (1 if t.day <= 15 else 2)
        if q not in qs:
            qs.append(q)
    return qs


def diagnostico_local(ponto_id: str) -> dict | None:
    """Diagnóstico REAL do ponto (lido de data/processed/diagnostico) já em frases e tabelas. None = lacuna."""
    r = carregar_diagnosticos().get(ponto_id)
    if r is None:
        return None
    out: dict = {"confianca": r.get("confianca"), "confianca_nota": r.get("confianca_nota"), "periodo": r.get("periodo"),
                 "anos_validos": r.get("n_anos_validos") or {}, "lacunas": r.get("lacunas") or [], "bruto": r}
    nu = r.get("solo_nu")
    if nu:
        freq = {int(k): v for k, v in nu["frequencia_por_quinzena"].items()}
        out["solo_nu"] = {"limiar": nu["limiar_ndvi"], "tipicas": nu["quinzenas_tipicas"],
                          "df": pd.DataFrame({"quinzena": list(freq), "frac_anos_solo_nu": list(freq.values()),
                                              "rotulo": [rotulo_quinzena(q) for q in freq]}),
                          "criterio": nu["criterio_tipica"]}
        out["solo_nu"]["frase"] = (
            f"Neste local o NDVI (verdor visto do satélite) fica abaixo de {br(nu['limiar_ndvi'], 2)} (o percentil 20 do próprio "
            f"local) em pelo menos metade dos anos nas quinzenas: {rotulos_quinzenas(nu['quinzenas_tipicas'])}. "
            if nu["quinzenas_tipicas"] else
            f"Nenhuma quinzena teve NDVI abaixo de {br(nu['limiar_ndvi'], 2)} (o percentil 20 do próprio local) em pelo menos "
            "metade dos anos: não há época típica de campo nu por esta regra. ")
        out["solo_nu"]["frase"] += ("'Solo nu' aqui é RELATIVO ao local (as 20% quinzenas menos verdes dele), não um valor "
                                    "agronômico absoluto; o satélite não vê o seu talhão.")
    else:
        out["solo_nu"] = None
    clim = r.get("climatologia_quinzenal") or {}
    nd = clim.get("ndvi")
    if nd:
        out["ndvi_df"] = pd.DataFrame([{"quinzena": int(q), "rotulo": rotulo_quinzena(int(q)), "media": v["media"],
                                        "inf": None if v["media"] is None or v["desvio"] is None else v["media"] - v["desvio"],
                                        "sup": None if v["media"] is None or v["desvio"] is None else v["media"] + v["desvio"]}
                                       for q, v in nd.items()])
    ch = clim.get("chuva_mm_quinzena")
    if ch:
        out["chuva_df"] = pd.DataFrame([{"quinzena": int(q), "rotulo": rotulo_quinzena(int(q)), "media_mm": v["media"]}
                                        for q, v in ch.items()])
    ver = r.get("veranicos")
    if ver:
        out["veranicos"] = {"quinzenas_chuvosas": ver["quinzenas_estacao_chuvosa"], "limiar": ver["limiar_chuva_mm"],
                            "n_estacoes": ver["n_estacoes"], **ver["distribuicao"]}
        out["veranicos"]["frase"] = (
            f"A estação chuvosa típica deste local (as {len(ver['quinzenas_estacao_chuvosa'])} quinzenas mais chuvosas na média) "
            f"cobre {rotulos_quinzenas(ver['quinzenas_estacao_chuvosa'])}. Dentro dela, o maior período seguido sem chuva "
            f"(menos de {br(ver['limiar_chuva_mm'], 0)} mm por dia) teve mediana de {br(ver['distribuicao']['mediana'], 0)} dias, "
            f"foi de até {br(ver['distribuicao']['p90'], 0)} dias em 1 de cada 10 anos e chegou a {br(ver['distribuicao']['max'], 0)} dias "
            f"({ver['n_estacoes']} estações analisadas).")
    est = estresse_por_quinzena(ponto_id, "ndvi")
    elig = est[est["n_anos"] >= MIN_ANOS_ESTRESSE].sort_values(["frac_abaixo", "z_medio"], ascending=[False, True])
    top = elig.head(3)
    out["estresse_df"] = est
    out["estresse_top"] = [int(q) for q in top["quinzena"]] if len(top) and top["frac_abaixo"].max() > 0 else []
    out["estresse_frase"] = (
        f"Quinzenas em que o verdor mais vezes ficou abaixo do normal dessa quinzena (mais de 1 desvio-padrão abaixo da média "
        f"do local; convenção do app): " + "; ".join(f"{rotulo_quinzena(int(q))} ({pct(f)} dos {int(n)} anos)"
                                                       for q, f, n in zip(top["quinzena"], top["frac_abaixo"], top["n_anos"]))
        + ". É anomalia em relação ao próprio local, não prova de falta de água." if out["estresse_top"] else
        "Não há quinzena com ao menos 5 anos de dados e verdor abaixo do normal: LACUNA ou local sem épocas de estresse marcadas.")
    out["tendencias"] = [{"variável": VAR_PT.get(k, k), "anos": t.get("n_anos"),
                          "situação": TENDENCIA_PT.get(t.get("mann_kendall"), LACUNA) if t.get("resultado") else LACUNA,
                          "inclinação por ano": t.get("inclinacao_por_ano"), "p": t.get("p_valor")}
                         for k, t in (r.get("tendencias") or {}).items()]
    return out


def vulnerabilidade_cultura_atual(ponto_id: str, cultura: str, calc: dict, diag: dict | None) -> dict:
    """Quando a cultura atual é mais vulnerável: adequação por início de plantio, e sobreposição do ciclo com solo nu/estresse."""
    ca = calc["av"]["culturas"].get(cultura)
    out = {"cultura": cultura, "lacunas": []}
    if ca is None or ca.get("res") is None:
        out["lacunas"].append(f"cultura atual não avaliável neste local: {'; '.join(ca['lacunas']) if ca else 'sem dado'}.")
        return out
    p, res, dur = calc["params"], ca["res"], ca["av"]["dur"]
    passo = p.passo_inicio_dias
    inicios = [ciclo_mod.data_do_inicio(k, passo) for k in range(len(res["media_por_inicio"]))]
    out["df"] = pd.DataFrame({"inicio": inicios, "ordem": range(len(inicios)),
                              "adequacao_media": [float(x) for x in res["media_por_inicio"]],
                              "frac_anos_viaveis": [float(x) for x in res["p_viavel_por_inicio"]]})
    out["melhor_inicio"], out["duracao"], out["viabilidade"] = res["inicio"], dur, ca["estado"]
    pior = out["df"].sort_values(["adequacao_media", "ordem"]).head(3)
    out["piores_inicios"] = list(pior["inicio"])
    qs = quinzenas_do_ciclo(res["k"] * passo, dur)
    out["quinzenas_ciclo"] = qs
    if diag:
        nu = (diag.get("solo_nu") or {}).get("tipicas") or []
        out["solo_nu_no_ciclo"] = [q for q in qs if q in nu]
        out["estresse_no_ciclo"] = [q for q in qs if q in diag.get("estresse_top", [])]
        ver = (diag.get("veranicos") or {}).get("quinzenas_chuvosas") or []
        out["estacao_chuvosa_no_ciclo"] = [q for q in qs if q in ver]
    else:
        out["lacunas"].append("sem diagnóstico do local: não dá para cruzar o ciclo com solo nu e estresse.")
    return out


# ---------------------------------------------------------------------------------------------- cenário de clima
def _faixa_observada(ca: dict, ok: np.ndarray, k: int) -> dict:
    av = ca["av"]
    chuva, temp = av["chuva"][ok][:, k], av["tmedia"][ok][:, k]
    return {"chuva": (float(np.nanmin(chuva)), float(np.nanmax(chuva)), float(np.nanmean(chuva))),
            "temp": (float(np.nanmin(temp)), float(np.nanmax(temp)), float(np.nanmean(temp)))}


def cenario_clima(ponto_id: str, cultura: str, prioridade: str, fator_chuva: float, delta_t: float,
                  base: dict | None = None, regras=None) -> dict:
    """Mesmo motor, clima perturbado. Compara as MESMAS 3 estratégias do cenário-base e diz se o clima sai do já visto."""
    base = base or calcular(ponto_id, cultura, prioridade, com_evidencias=False, regras=regras)
    regras = base.get("regras", regras)
    p = base["params"]
    clima_c = perturbar(clima_ponto(ponto_id), fator_chuva, delta_t)
    av_c = avaliar_local(carregar_tabela(), clima_c, p)
    linhas, avisos = [], []
    for c in base["cenarios"]:
        cid = c["rotacao"][1]
        b, s = base["av"]["culturas"][cid], av_c["culturas"][cid]
        lin = {"cultura": cid, "atual": bool(c.get("atual")), "estado_base": b["estado"], "estado_cenario": s["estado"]}
        if b["res"] is not None:
            lin.update(adeq_base=b["res"]["adeq_media"], inicio_base=b["res"]["inicio"], anos_viaveis_base=b["res"]["p_ano_viavel"],
                       chuva_base=b["res"]["chuva_ciclo_mm"])
            ob = _faixa_observada(b, base["av"]["ok"], b["res"]["k"])
            lin["observado"] = ob
            chuva_c, temp_c = ob["chuva"][2] * fator_chuva, ob["temp"][2] + delta_t
            lin["chuva_cenario_neste_inicio"], lin["temp_cenario_neste_inicio"] = chuva_c, temp_c
            lin["fora_chuva"] = not (ob["chuva"][0] <= chuva_c <= ob["chuva"][1])
            lin["fora_temp"] = not (ob["temp"][0] <= temp_c <= ob["temp"][1])
            if lin["fora_chuva"] or lin["fora_temp"]:
                avisos.append(
                    f"{cid}: o cenário leva "
                    + ("a chuva do ciclo a " + br(chuva_c, 0) + f" mm (já visto entre {br(ob['chuva'][0], 0)} e {br(ob['chuva'][1], 0)} mm) "
                       if lin["fora_chuva"] else "")
                    + ("a temperatura média do ciclo a " + br(temp_c) + f" °C (já vista entre {br(ob['temp'][0])} e {br(ob['temp'][1])} °C)"
                       if lin["fora_temp"] else "")
                    + ": fora do que ocorreu neste local entre 2001 e 2024 (EXTRAPOLAÇÃO).")
        if s["res"] is not None:
            lin.update(adeq_cenario=s["res"]["adeq_media"], inicio_cenario=s["res"]["inicio"],
                       anos_viaveis_cenario=s["res"]["p_ano_viavel"], chuva_cenario=s["res"]["chuva_ciclo_mm"])
        linhas.append(lin)
    novo = gerar_cenarios({"local": ponto_id}, cultura, carregar_tabela(), clima=clima_c, params=p, regras=regras)
    alt_base = [c["rotacao"][1] for c in base["cenarios"] if not c.get("atual")]
    alt_nova = [c["rotacao"][1] for c in novo if c["rotacao"][1] != cultura]
    return {"linhas": linhas, "avisos": avisos, "alternativas_base": alt_base, "alternativas_cenario": alt_nova,
            "mudou_alternativas": set(alt_base) != set(alt_nova), "fator_chuva": fator_chuva, "delta_t": delta_t,
            "extrapolacao": bool(avisos)}


# ---------------------------------------------------------------------------------------------- limites e glossário
GLOSSARIO = [
    ("NDVI", "Índice de 'verdor' calculado de imagens de satélite (MODIS, pixel de 250 m, uma composição a cada 16 dias). "
             "Sobe com folhas verdes e cai com solo exposto ou vegetação seca. Não é produtividade, nem qualidade do solo."),
    ("Solo nu (neste app)", "Quinzena em que o NDVI do local fica no percentil 20 mais baixo do próprio local. É relativo: "
                            "cada local é comparado com ele mesmo, não com um valor agronômico fixo."),
    ("Anomalia", "Quanto um valor se afastou do normal daquela quinzena no próprio local, medido em desvios-padrão (z). "
                 "Anomalia negativa = mais seco/menos verde que o normal."),
    ("Umidade do solo (SMAP)", "Satélite da NASA que estima a água no solo em células de cerca de 9 km (superfície e zona "
                               "da raiz). Mostra a tendência da região, não o seu talhão. No MVP é só informativa."),
    ("Evapotranspiração", "Água que sai do solo e das plantas para o ar. O MVP NÃO calcula evapotranspiração nem balanço "
                          "hídrico: é uma lacuna declarada."),
    ("Veranico", "Período seguido de dias sem chuva (aqui, menos de 1 mm por dia) dentro da estação chuvosa."),
    ("Empate técnico", "Duas ou mais culturas cujas faixas de pontuação se sobrepõem: os dados não separam uma da outra. "
                       "Nesse caso o app NÃO mostra 1º, 2º e 3º lugar."),
    ("Faixa de incerteza", "O quanto a pontuação muda se os pesos dos critérios, os dados que faltam e o ano de chuva mudarem. "
                           "Não é chance de dar certo na roça."),
    ("Fixadoras de nitrogênio", "Plantas da família do feijão (leguminosas) que, junto com bactérias que vivem nas raízes, pegam o "
                                "nitrogênio do ar e o deixam disponível para a planta. Por isso o app dá ponto a leguminosa na "
                                "rotação. Quanto de nitrogênio cada uma deixa na sua terra varia muito: o app só usa o valor "
                                "quando a tabela de culturas tem fonte; senão é lacuna."),
    ("Adubação verde", "Plantar uma cobertura (como crotalária, feijão-de-porco ou guandu) para cortar e deixar sobre a terra ou "
                       "misturar nela, em vez de colher. Ajuda a cobrir o solo e a trazer matéria orgânica. O resultado depende "
                       "de chuva e de espécie: a avaliar com técnico local."),
    ("Raízes profundas", "Raízes que descem fundo no solo e buscam água e nutriente que as plantas de raiz rasa não alcançam; "
                         "também ajudam a soltar camadas duras. O app NÃO mede a profundidade da raiz: usa só o que a tabela de "
                         "culturas e o acervo trazem, e o que falta aparece como lacuna."),
    ("Balanço hídrico", "Conta de água do solo: o que entra (chuva e irrigação) menos o que sai (evaporação e uso pela planta). "
                        "O app ainda não faz essa conta; hoje compara a chuva do ciclo com uma demanda de referência."),
    ("Risco de erosão", "Chance de a chuva levar a terra embora. Cresce com terreno inclinado, solo descoberto e chuva forte. "
                        "No mapa, o declive e o solo nu são INDICADORES desse risco, não uma medida de quanta terra se perde."),
]

# Trechos REAIS do acervo (docs_rag/*.pdf) que sustentam cada explicação. `pagina` = página do PDF (a 1ª página do arquivo é a 1).
# O teste tests/test_mvp.py confere que o trecho aparece nessa página (quando o pdftotext existe); não escreva trecho de memória.
TRECHOS_GLOSSARIO = {
    "Fixadoras de nitrogênio": {
        "arquivo": "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", "pagina": 97,
        "trecho": "Fixação biológica do nitrogênio (FBN) é um processo natural que ocorre pela associação simbiótica entre plantas e "
                  "microrganismos do solo."},
    "Adubação verde": {
        "arquivo": "embrapa_semiarido_biomassa_leguminosas_milheto.pdf", "pagina": 1,
        "trecho": "uso de plantas, em cultivo rotacionado, sucessivo ou consorciado com outras culturas, com a finalidade de "
                  "incorporá-las ou depositá-las sobre o solo, a fim de melhorar a cobertura e suas características físicas, "
                  "químicas e biológicas, é chamado de adubação verde"},
    "Raízes profundas": {
        "arquivo": "embrapa_debiasi_diversificacao_especies.pdf", "pagina": 9,
        "trecho": "culturas caracterizadas por alta produção de fitomassa e sistema radicular profundo e vigoroso, visando melhorar "
                  "a qualidade do solo"},
    "Evapotranspiração": {
        "arquivo": "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", "pagina": 27,
        "trecho": "Evapotranspiração representa a perda de água da cultura para a atmosfera, por meio dos processos de transpiração "
                  "da planta e evaporação direta de água do solo."},
    "Balanço hídrico": {
        "arquivo": "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", "pagina": 28,
        "trecho": "Para o processamento do balanço hídrico da cultura, na escala diária, são requeridos dados de clima, de solo e "
                  "da cultura."},
    "Risco de erosão": {
        "arquivo": "embrapa_cap3_sistema_plantio_direto.pdf", "pagina": 2,
        "trecho": "A ausência de cobertura do solo, viva ou morta, aumenta a suscetibilidade do solo à erosão"},
}


# True SÓ porque a seção de ETo e "chuva menos ETo" está desenhada na tela (app.painel_balanco). Se for False, o glossário e a página
# "Limites dos dados" voltam a dizer que o app não calcula ET nem balanço hídrico.
BALANCO_NA_TELA = True


def balanco_na_tela() -> bool:
    return BALANCO_NA_TELA and _modulo_opcional("src.app.secao_balanco_renda") is not None


def _modulo_opcional(nome: str):
    import importlib
    try:
        return importlib.import_module(nome)
    except ImportError:
        return None


def glossario_atual() -> list[tuple[str, str, dict | None]]:
    """(termo, texto, trecho do acervo). O texto de ET/balanço hídrico só diz que o app calcula se o módulo de balanço existir."""
    tem_balanco = balanco_na_tela()
    out = []
    for termo, texto in GLOSSARIO:
        if tem_balanco and termo == "Evapotranspiração":
            texto = ("Água que sai do solo e das plantas para o ar. O app estima só a evapotranspiração de REFERÊNCIA (ETo, equação de "
                     "Hargreaves-Samani, com temperatura do satélite): NÃO é o quanto a sua cultura gasta, porque falta o coeficiente da "
                     "cultura (Kc), que é lacuna. Estimativa para a região, a avaliar com técnico local.")
        if tem_balanco and termo == "Balanço hídrico":
            texto = ("Conta de água do solo: o que entra (chuva e irrigação) menos o que sai (evaporação e uso pela planta). O app mostra só "
                     "'chuva menos ETo' por quinzena: NÃO é o balanço do solo (sem armazenamento, escoamento nem irrigação).")
        out.append((termo, texto, TRECHOS_GLOSSARIO.get(termo)))
    return out


def _ler(caminho: Path) -> str | None:
    return caminho.read_text(encoding="utf-8") if caminho.is_file() else None


def numeros_avaliacao_195() -> dict:
    """Números REAIS lidos de experimentos/avaliacao_195/RESULTADO.md (tabelas e linhas citadas literalmente)."""
    from src.app import logica as L
    txt = _ler(RAIZ / "experimentos/avaliacao_195/RESULTADO.md")
    if txt is None:
        return {"disponivel": False}
    linhas_ler = [l.strip() for l in txt.splitlines()
                  if l.startswith(("Holdout 2022-2024", "Cobertura conformal holdout", "Esta CLI NAO usa persistencia"))]
    def tab(titulo):
        t = L._tabela_md(txt, titulo)
        return pd.DataFrame(t[1:], columns=t[0]) if len(t) > 1 else None
    conf = tab("Confirmacao selada")
    sel = tab("Selecao 2010-2021")
    pers = None
    if conf is not None:
        for _, r in conf.iterrows():
            if str(r.iloc[0]).strip() == "persistencia":
                pers = L._num(r.iloc[1])
    return {"disponivel": True, "confirmacao": conf, "selecao": sel, "linhas": linhas_ler, "persistencia_confirmacao_ridge": pers,
            "arquivo": "experimentos/avaliacao_195/RESULTADO.md"}


def acerto_rag() -> str | None:
    txt = _ler(RAIZ / "docs/04_RETOMADA.md")
    m = re.search(r"acerto top-5 de \*\*(\d+)%\*\*[^.]*?\((\d+)% só nos docs em PT\)[^.]*?(\d+) perguntas[^.]*?meta era (\d+)%", txt or "")
    return (f"acerto top-5 de {m.group(1)}% ({m.group(2)}% só nos documentos em português) numa avaliação de {m.group(3)} "
            f"perguntas; a meta do projeto era {m.group(4)}% (fonte: docs/04_RETOMADA.md)") if m else None


def contagens_dados() -> dict:
    p = carregar_pontos()
    d = carregar_diagnosticos()
    conf = pd.Series([r.get("confianca") for r in d.values()]).value_counts().to_dict() if d else {}
    tab = carregar_tabela()
    com_n = sum(1 for c in tab.values() if c["atributos"].get("n_acumulado_parte_aerea_kg_ha") is not None)
    com_palha = sum(1 for c in tab.values() if c["atributos"].get("palha_ms_kg_ha") is not None)
    com_dem = sum(1 for c in tab.values() if c["atributos"].get("demanda_hidrica_mm_ciclo") is not None)
    return {"pontos": len(p), "pontos_ce": int((p["uf"] == "CE").sum()), "celulas_power": int(p["celula_power"].nunique()),
            "confianca": conf, "culturas": len(tab), "com_n": com_n, "com_palha": com_palha, "com_demanda": com_dem}


def limites_linhas() -> dict[str, list[str]]:
    """Frases da página 'Limites dos dados' (números lidos de arquivo). A página do app e a fonte 'sobre o Sulco' do chat usam esta função.

    Chaves: `visao_geral` (o que o satélite e o clima veem), `previsao` (o que a previsão de NDVI consegue; vazia se o RESULTADO.md da
    avaliação não existir) e `motor` (o que o motor de estratégias não sabe). Linha que começa com 'LACUNA' é lacuna declarada.
    """
    from src.app import filtros as F
    from src.app import logica as L
    n = contagens_dados()
    visao = list(L.LIMITES_FIXOS)
    visao.append(f"São {n['pontos']} locais ({n['pontos_ce']} municípios do Ceará), mas só {n['celulas_power']} células de clima "
                 "distintas: locais na mesma célula têm exatamente o mesmo clima. O NDVI é novo em cada local; a chuva não.")
    visao.append("Confiança do diagnóstico por local (heurística de cobertura de dados, não é probabilidade): "
                 f"{', '.join(f'{k} = {v}' for k, v in n['confianca'].items())}.")
    prev = []
    a = numeros_avaliacao_195()
    if a["disponivel"]:
        if a["persistencia_confirmacao_ridge"] is not None:
            prev.append(f"Com 195 pontos, o ganho vem da persistência (o verdor da quinzena anterior): skill de "
                        f"{br(a['persistencia_confirmacao_ridge'], 2)} sobre a média histórica na confirmação selada de 2022-2024. "
                        "'Skill' acima de 0 = melhor que repetir a média histórica.")
        prev.append("O clima sozinho não supera a média histórica fora da amostra. O app, por isso, não usa previsão de NDVI para dar nota.")
    motor = [f"Faixas de temperatura e chuva vêm do EcoCrop (genéricas por espécie, não por cultivar nem por solo). "
             f"Só {n['com_n']} de {n['culturas']} culturas têm nitrogênio e palha na tabela, e esses valores vêm de estudos pontuais; "
             f"só {n['com_demanda']} têm demanda de água do ciclo.",
             "A duração do ciclo é SUPOSIÇÃO (ponto médio do EcoCrop); o ciclo real depende da cultivar. Pesos e prioridades "
             "são proposta do projeto, ainda sem validação com técnico."]
    pts = carregar_pontos()
    est_ok = solo_estimado(pts["ponto_id"].iloc[0]) is not None
    motor.append("Solo: " + ("só uma ESTIMATIVA do mapa SoilGrids (250 m, camadas 0 a 30 cm), não análise do seu talhão; se você informar a "
                             "textura, a sua prevalece." if est_ok else "LACUNA, o arquivo de solo estimado não foi encontrado."))
    motor.append(f"ZARC (zoneamento do MAPA): só o Ceará; entra como filtro das datas de plantio de sequeiro (risco até {F.RISCO_ZARC}%); "
                 "culturas sem ZARC usam uma janela aproximada declarada; o manejo irrigado do ZARC só é consultado nos filtros da tela 1, "
                 "sem efeito na pontuação.")
    if balanco_na_tela():
        motor.append("Evapotranspiração, balanço hídrico, preço e renda: veja a seção própria em 'Meu local' e as lacunas dela; são estimativas "
                     "a avaliar com técnico local. Custo, mercado, pragas e doenças continuam sem dado.")
    else:
        motor.append("Não há dado de preço, custo, mercado, pragas, doenças nem evapotranspiração (o app ainda não calcula balanço hídrico). "
                     "'Renda extra' é uma lacuna: não altera o ranking.")
    motor.append("Equipamento e preferência de mercado (tela 1) não têm dado por trás: viram lacuna, não filtro.")
    aud = carregar_auditoria()
    if aud:
        for prio, r in aud["por_prioridade"].items():
            motor.append(f"Auditoria (cultura atual = {aud['cultura_atual']}, {aud['n_pontos']} locais, prioridade "
                         f"'{PRIORIDADES[prio]['rotulo']}'): {r['com_empate_tecnico']} de {r['alternativas_mostradas']} alternativas "
                         f"mostradas ({pct(r['frac_com_empate_tecnico'])}) estão em empate técnico; mediana de "
                         f"{br(r['mediana_n_empatadas'], 0)} candidatas empatadas; chance de ficar entre as 3 primeiras de "
                         f"{pct(r['p_top3_min'])} a {pct(r['p_top3_max'])}.")
    else:
        motor.append("LACUNA: auditoria das alternativas não gerada (python -m src.app.precalculo auditoria).")
    rag = acerto_rag()
    motor.append(f"Evidência do acervo (RAG): {rag if rag else 'LACUNA (número de acerto não encontrado)'}. Muitos critérios ficam "
                 "'sem evidência'; o app mostra isso em vez de inventar fonte.")
    motor.append("O diagnóstico descreve o passado. O app não prevê chuva, não prevê colheita e não prova que uma rotação rende mais.")
    return {"visao_geral": visao, "previsao": prev, "motor": motor}


# ------------------------------------------------------------------------------------------ rotação em 3 safras
OPCOES_TEXTURA = ["não sei", "arenoso", "médio", "argiloso"]
OPCOES_MO = ["não sei", "baixa", "média", "alta"]


def calcular_rotacao(ponto_id: str, cultura_atual: str, prioridade: str = "sem", rotacao_atual: list[str] | None = None,
                     textura: str = "não sei", materia_organica: str = "não sei", usar_zarc: bool = ZARC_PADRAO,
                     n_sorteios: int = 3000, renda_por_cultura: dict | None = None, regras=None) -> dict:
    """Rotação de 3 safras (atual + 2 alternativas) para o local. `rotacao_atual`: 3 culturas começando pela atual, ou None (repete a atual).

    Solo informado pelo usuário só gera avisos de risco (não altera nota). ZARC (opcional) restringe os inícios de plantio.
    """
    t0 = time.perf_counter()
    tab = carregar_tabela()
    pts = carregar_pontos().set_index("ponto_id")
    if ponto_id not in pts.index:
        raise KeyError(f"ponto '{ponto_id}' não está em pontos.csv")
    p = parametros(prioridade, n_sorteios, usar_zarc)
    solo = {k: v for k, v in (("textura", textura), ("materia_organica", materia_organica)) if v not in (None, "não sei")} or None
    est = solo_estimado(ponto_id)
    if solo is not None and "textura" in solo:
        solo["origem"] = "informado"
    elif est is not None:                                  # agricultor não informou a textura: usa a estimada (rotulada)
        solo = {**(solo or {}), "textura": est["textura"], "origem": "estimado pelo mapa SoilGrids (~2 km)"}
    if solo and solo.get("textura") in ("arenoso", "argiloso", "médio"):
        p = replace(p, zarc_solo={"arenoso": "arenoso", "argiloso": "argiloso", "médio": "medio"}[solo["textura"]])
    ibge = pts.loc[ponto_id].get("ibge")
    ibge = None if pd.isna(ibge) else int(ibge)
    if prioridade == "renda" and renda_por_cultura is None:        # receita bruta/ha (IBGE/PAM): módulo opcional, sem ele = lacuna
        try:
            from src.app.secao_balanco_renda import secao_renda
            renda_por_cultura = secao_renda(ibge, list(tab))["renda_por_cultura"]
        except ImportError:
            renda_por_cultura = None
    r = gerar_rotacoes({"local": ponto_id}, cultura_atual, tab, clima_ponto(ponto_id), p, prioridade, rotacao_atual, 2, solo,
                       ibge, renda_por_cultura, regras=regras)
    r["usar_zarc"], r["solo_informado"], r["solo_estimado"], r["segundos"] = usar_zarc, solo, est, time.perf_counter() - t0
    r["local"] = {"ponto_id": ponto_id, "nome": pts.loc[ponto_id]["nome"]}
    return r


# ------------------------------------------------------------------------------------------ plano de várias safras (MILP)
ORDEM_MILP = {
    "sem": None,
    "renda": None,
    "agua": ("adeq", "div", "leg", "palha"),
    "solo": ("palha", "leg", "div", "adeq"),
    "alimento": ("div", "leg", "adeq", "palha"),
}


def calcular_plano(ponto_id: str, cultura_atual: str, prioridade: str = "sem", horizonte: int = 5, nunca_repetir_seguida: bool = True,
                   min_leguminosas: int = 2, usar_zarc: bool = ZARC_PADRAO, n_sorteios: int = 150, regras_agricultor=None) -> dict:
    """Plano de `horizonte` safras por MILP com regras duras, repetido com pesos/ano de clima/lacunas sorteados (frequência de cada sequência ser a ótima).

    PROPOSTA, não decisão: o MILP devolve um ótimo por sorteio; a frequência mostra que nenhuma sequência domina (empate técnico).
    """
    t0 = time.perf_counter()
    tab = carregar_tabela()
    if ponto_id not in carregar_pontos().set_index("ponto_id").index:
        raise KeyError(f"ponto '{ponto_id}' não está em pontos.csv")
    p = parametros(prioridade, 1000, usar_zarc)
    av = avaliar_local(tab, clima_ponto(ponto_id), p)
    cult = [c for c in tab if av["culturas"][c]["res"] is not None and (av["culturas"][c]["estado"] == "viavel" or c == cultura_atual)]
    if cultura_atual not in cult:
        return {"lacuna": f"cultura atual '{cultura_atual}' sem avaliação climática neste local; plano não calculado.", "top": []}
    adeq = {c: np.asarray(av["culturas"][c]["res"]["adeq_por_ano"], float) for c in cult}
    fam = {c: (tab[c]["atributos"].get("familia_botanica") or {}).get("valor") for c in cult}
    pal = {c: (tab[c]["atributos"].get("palha_ms_kg_ha") or {}).get("valor") for c in cult}
    regras = {}
    if nunca_repetir_seguida:
        regras["sem_repetir_seguida"] = True
    if min_leguminosas:
        regras["min_leguminosas"] = int(min_leguminosas)
    if regras_agricultor is not None:                      # regras duras do agricultor (perfil): só entram culturas viáveis aqui
        d = regras_agricultor.para_dict()
        falta = sorted(c for c in d["obrigatorias"] if c not in cult)
        if falta:
            return {"lacuna": "você pediu para incluir " + ", ".join(tab[c]["cultura_pt"] if c in tab else c for c in falta)
                    + ", mas o clima do local não permite essa cultura: nenhum plano atende. Converse com o técnico.", "top": []}
        regras["proibidas"] = [c for c in d["proibidas"] if c in cult]
        regras["obrigatorias"] = d["obrigatorias"]
        if d["max_seguidas_cultura"]:
            regras["max_seguidas_cultura"] = d["max_seguidas_cultura"]
    r = otimizar_com_incerteza(cult, cultura_atual, adeq, fam, pal, T=horizonte, regras=regras, n=n_sorteios, ordem_pesos=ORDEM_MILP[prioridade])
    r["top"] = [{**x, "nomes": [tab[c]["cultura_pt"] for c in x["sequencia"]]} for x in r["top"]]
    r["segundos"], r["usar_zarc"], r["prioridade"], r["n_culturas"] = time.perf_counter() - t0, usar_zarc, prioridade, len(cult)
    if not r["top"]:
        r["lacuna"] = "nenhuma sequência atende às regras escolhidas; afrouxe as regras (ex.: menos leguminosas)."
    return r


# ------------------------------------------------------------------------------------------ solo estimado (SoilGrids)
@lru_cache(maxsize=1)
def _solo_df() -> pd.DataFrame | None:
    arq = RAIZ / "data/processed/solo.parquet"
    return pd.read_parquet(arq).set_index("ponto_id") if arq.exists() else None


LIMITE_FRACAO_PIXELS = 0.5   # abaixo disso, menos da metade da janela de ~2 km tem dado válido (critério da auditoria do SoilGrids)


def solo_estimado(ponto_id: str) -> dict | None:
    """Solo do ponto estimado pelo SoilGrids (mapa global de 250 m; mediana de ~2 km; média 0-30 cm PONDERADA pela espessura das camadas). NÃO é análise de solo.

    Classe de textura pelo teor de argila (agrupamento simples: < 15% arenoso, 15 a 35% médio, > 35% argiloso). Sem dado: None (lacuna).
    `aviso_pixels`: texto próprio quando o pixel central é inválido ou menos da metade da janela tem dado (None quando a cobertura é boa).
    """
    d = _solo_df()
    if d is None or ponto_id not in d.index or pd.isna(d.loc[ponto_id].get("clay_0-5cm")):
        return None
    s = solo_de_linha(d.loc[ponto_id])
    argila = s["argila_pct"]
    classe = "arenoso" if argila < 15 else ("argiloso" if argila > 35 else "médio")
    fr, central = s["fracao_pixels_validos"], s["pixel_central_valido"]
    aviso_pixels = None
    if fr is not None and fr < LIMITE_FRACAO_PIXELS:
        aviso_pixels = (f"Poucos pixels do mapa de solo têm dado em volta deste ponto ({pct(fr)} da janela de ~2 km"
                        + ("; o pixel central não tem dado" if not central else "") + "): estimativa de baixa confiança, confirme com o técnico.")
    elif not central:
        aviso_pixels = "O pixel central do mapa de solo não tem dado; o valor vem dos pixels vizinhos. Confirme com o técnico."
    return {"argila_pct": argila, "areia_pct": s["areia_pct"], "silte_pct": s["silte_pct"], "carbono_organico_g_kg": s["carbono_g_kg"],
            "ph_agua": s["ph_agua"], "textura": classe, "pixel_central_valido": central, "fracao_pixels_validos": fr, "aviso_pixels": aviso_pixels,
            "aviso": "Estimativa de um mapa global (250 m; mediana de ~2 km em volta do ponto), camadas 0-30 cm (média ponderada pela espessura). Não é análise de solo; confirme com o técnico."}
