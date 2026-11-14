"""Folha de fatos do local para o chat: tudo o que o modelo de previsão e o sistema já dizem sobre UM local, sem LLM e sem cálculo novo.

Cada fato tem id ([F1], [F2]...), tema, texto em frases simples (números em pt-BR, com unidade), ORIGEM (função/arquivo e campo de onde
veio) e marca de lacuna. Os valores vêm das MESMAS funções que o app e a API usam (`src.api.main` previsao/limites, `src.app.mvp`,
`src.app.secao_*`, `src.culturas.zarc`); aqui só se formata. Dado ausente vira fato de LACUNA com o motivo, nunca número.

Privacidade: os textos NÃO trazem nome do município, ponto_id, código IBGE, latitude nem longitude (dizem 'este local'). Esses valores
ficam em `folha['privado']`, que serve só para conferir/limpar o texto antes de qualquer envio a uma API externa.

TEXTO SIMPLES (`texto_simples`): cada fato ganha uma frase para o AGRICULTOR (português do dia a dia, sem sigla nem termo técnico),
montada por modelo de frase, sem LLM e sem número novo (só números que já estão no texto técnico). É ela que vai ao prompt e ao texto
padrão; o `texto` técnico e a `origem` ficam na resposta da API para conferência. Fato sem frase simples (detalhe técnico) não vai ao chat.

Seleção para a pergunta (`selecionar`): determinística, por tema (palavras-chave) e teto de tokens; o LLM só vê os fatos relevantes e só
os reescreve citando [F#]. Pergunta sem tema local => nenhuma fato (o chat usa o acervo e a fonte 'sobre o Sulco').
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

from .seguranca import neutralizar, trecho_suspeito
from .verificador import sem_acento

RAIZ = Path(__file__).resolve().parents[2]
ARQ_PROSPECTIVO_JSON = RAIZ / "experimentos/prospectivo_2025/resultados.json"
ARQ_PROSPECTIVO_MD = RAIZ / "experimentos/prospectivo_2025/RESULTADO.md"
ARQ_RELATORIO = RAIZ / "data/processed/modelos/relatorio_modelos.md"
MAX_FATOS_PROMPT = 16             # poucos fatos por pergunta: resposta curta e prompt barato
TETO_TOKENS_FATOS = 900           # teto dos fatos enviados por pergunta (a pergunta, o prompt do sistema e os trechos vêm à parte)
CHARS_POR_TOKEN = 3.0             # estimativa conservadora para português (não é o tokenizador da DeepSeek)
MAX_TEXTO_LACUNA = 220
ROTULO_LOCAL = "o seu município"


def tokens_aprox(texto: str) -> int:
    return math.ceil(len(texto) / CHARS_POR_TOKEN)


# ---------------------------------------------------------------------------------------------- formatação pt-BR
def br(x, nd: int = 1) -> str:
    return f"{float(x):.{nd}f}".replace(".", ",")


def milhar(x, nd: int = 0) -> str:
    return f"{float(x):,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x, nd: int = 1) -> str:
    return br(100 * float(x), nd) + "%"


def data_br(iso) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else str(iso)


def datas_br(texto: str) -> str:
    return re.sub(r"(\d{4})-(\d{2})-(\d{2})", lambda m: f"{m.group(3)}/{m.group(2)}/{m.group(1)}", texto)


def _curto(t: str, n: int = MAX_TEXTO_LACUNA) -> str:
    t = " ".join(str(t).split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def lacuna_legivel(t: str, n: int = 160) -> str:
    """Lacuna do motor em frase simples: corta a explicação técnica depois de ';' e troca o código do critério pelo nome."""
    from src.app import mvp as M
    t = " ".join(str(t).split()).split("; no complemento")[0]
    t = re.sub(r";? lacuna [A-Z]\d+", "", t)
    m = re.match(r"(\w+): ", t)
    if m and m.group(1) in M.NOME_CRITERIO:
        t = M.NOME_CRITERIO[m.group(1)] + t[len(m.group(1)):]
    return _curto(t, n)


MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_RE_QUINZ = re.compile(r"\b(" + "|".join(MESES_ABREV) + r") [12]ª")
# Limiares de REDAÇÃO (suposição de texto, NÃO são critério científico): quanto a anomalia prevista pode se afastar de zero para a frase
# dizer 'parecido com o normal', 'um pouco' ou 'bem' mais forte/fraco. Os valores da anomalia ficam no fato técnico.
LIMIAR_PARECIDO = 0.02
LIMIAR_BEM = 0.06


def meses_do_texto(t: str, depois: str = "") -> list[int]:
    """Índices (0 a 11) dos meses citados como 'out 1ª' no texto (a partir de `depois`, se dado), em ordem de calendário, sem repetir."""
    if depois and depois in t:
        t = t.split(depois, 1)[1]
    return sorted({MESES_ABREV.index(m.group(1)) for m in _RE_QUINZ.finditer(t)})


def lista_meses(idx: list[int]) -> str:
    """Com preposição: [9, 10, 11] -> 'de outubro a dezembro'; [2, 4] -> 'em março e maio'."""
    idx = sorted(set(idx))
    if not idx:
        return ""
    if len(idx) >= 3 and idx[-1] - idx[0] == len(idx) - 1:
        return f"de {MESES_NOME[idx[0]]} a {MESES_NOME[idx[-1]]}"
    nomes = [MESES_NOME[i] for i in idx]
    return "em " + (nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1])


def mes_da_data(t: str) -> str | None:
    m = re.search(r"\b(\d{2})/(\d{2})\b", str(t))
    return MESES_NOME[int(m.group(2)) - 1] if m and 1 <= int(m.group(2)) <= 12 else None


def nivel_verde(a: float) -> str:
    """Frase simples para uma anomalia do verde (positiva = mais verde que o normal da época)."""
    if abs(a) < LIMIAR_PARECIDO:
        return "parecido com o normal para esta época"
    return f"{'um pouco' if abs(a) < LIMIAR_BEM else 'bem'} mais {'forte' if a > 0 else 'fraco'} do que o normal para esta época"


def simples_limite_global(t: str) -> str | None:
    """Frase simples para os limites fixos do app (`LIMITES_FIXOS`, `metricas.json`); None se o texto não é um dos conhecidos."""
    n = sem_acento(t.lower())
    if "pixels de 250 m" in n or ("250 m" in n and "nao enxerga o talhao" in n):
        return "O satélite vê áreas grandes e pode misturar a sua roça com mato, estrada ou vizinhos."
    if "celulas de cerca de 50 km" in n:
        return "O clima vem de uma área grande, de cerca de 50 km: a chuva da sua roça pode ser bem diferente."
    if "umidade do solo (smap)" in n:
        return "O dado de umidade do solo também vem de uma área grande e não enxerga o solo da sua roça."
    if "mostra o verdor" in n:
        return "O verde das plantas visto do satélite não é colheita nem qualidade do solo."
    if "nao preve o clima" in n:
        return "O Sulco não diz se vai chover; ele mostra o que já aconteceu."
    if "associacoes historicas" in n:
        return "O que os dados mostram são relações do passado, não prova de causa e efeito."
    if "cenario a avaliar com tecnico" in n:
        return "Toda sugestão é para conversar com o técnico; não é promessa de ganho."
    if "sem dado de mercado" in n:
        return "Ainda não temos dado de preço."
    return None


def acima_abaixo(x: float) -> str:
    if abs(x) < 5e-4:
        return "praticamente igual ao normal da época"
    return f"{br(abs(x), 3)} {'acima' if x > 0 else 'abaixo'} do normal da época"


# ---------------------------------------------------------------------------------------------- construção
class _Coletor:
    def __init__(self):
        self.fatos: list[dict] = []

    def add(self, tema: str, rotulo: str, texto: str, origem: str, prio: int = 2, lacuna: bool = False, valor: str | None = None,
            simples: str | None = None):
        self.fatos.append({"tema": tema, "rotulo": rotulo, "texto": " ".join(texto.split()), "origem": origem, "prio": prio,
                           "lacuna": lacuna, "valor": valor, "texto_simples": " ".join(simples.split()) if simples else None})

    def lacuna(self, tema: str, rotulo: str, texto: str, origem: str, prio: int = 1, simples: str | None = None):
        self.add(tema, rotulo, texto, origem, prio, True, simples=simples)


def _ler_texto(p: Path) -> str | None:
    return p.read_text(encoding="utf-8") if p.is_file() else None


def _conf_simples(conf) -> str | None:
    nome = {"alta": "alta", "media": "média", "baixa": "baixa"}.get(sem_acento(str(conf).lower()))
    return f"A confiança no modelo de previsão é {nome}; é uma avaliação simples, não uma chance." if nome else None


def _skill_historico(c: _Coletor) -> None:
    """Skill do modelo: confirmação 2022-24 e holdout (metricas.json via `limites()`), prospectivo e horizonte (resultados.json/RESULTADO.md)."""
    from src.api import main as A
    try:
        m = A.limites()
    except Exception:  # noqa: BLE001 - HTTPException 404 = arquivo ausente
        c.lacuna("modelo_skill", "métricas do modelo", "As métricas do modelo de previsão não estão disponíveis (metricas.json ausente): "
                 "não dá para dizer o quanto ele acerta.", "src.api.main.limites (data/processed/modelos/metricas.json)",
                 simples="Ainda não sabemos dizer o quanto o modelo de previsão acerta: faltam os resultados dos testes.")
        return
    nome = (m.get("decisao") or {}).get("modelo") or "xgboost"
    ho = m["holdout_temporal"]
    mm = ho["modelos"].get(nome) or {}
    anos = ho["anos_teste"]
    c.add("modelo_skill", "holdout 2022-2024",
          f"Teste do modelo escolhido ({nome}) em anos que ele não viu ({anos[0]} a {anos[-1]}): o erro (RMSE) foi {br(mm['rmse'], 3)} "
          f"e o ganho sobre repetir a média histórica da época (skill) foi {br(mm['skill_vs_climatologia'], 3)}. Skill 0 = igual à média "
          "histórica; acima de 0 = melhor que ela.", "src.api.main.limites: holdout_temporal.modelos." + nome, 1,
          valor=br(mm["skill_vs_climatologia"], 3),
          simples=("Em anos que o modelo não conhecia, ele acertou mais do que usar só a média dos anos anteriores." if mm["skill_vs_climatologia"] > 0
                   else "Em anos que o modelo não conhecia, ele não acertou mais do que usar só a média dos anos anteriores."))
    conf = ho.get("conformal", {}).get(nome, {}).get("metas") or {}
    if conf.get("80") and conf.get("90"):
        c.add("modelo_skill", "cobertura no holdout",
              f"No mesmo teste de {anos[0]} a {anos[-1]}, a faixa de incerteza de 80% cobriu {pct(conf['80']['cobertura'])} dos casos e a de "
              f"90% cobriu {pct(conf['90']['cobertura'])}: ficou abaixo da meta, então a faixa não deve ser lida como garantia.",
              "src.api.main.limites: holdout_temporal.conformal." + nome + ".metas", 2,
              simples="A margem de variação que o modelo informa nem sempre se confirmou nos testes; não é garantia.")
    if m.get("confianca"):
        c.add("modelo_skill", "confiança do modelo", f"Confiança do modelo: {m['confianca']} ({m.get('confianca_nota') or 'heurística, não é probabilidade'}).",
              "data/processed/modelos/metricas.json: confianca", 3,
              simples=_conf_simples(m["confianca"]))
    # seleção 2010-2021 e confirmação selada, do quadro do RESULTADO.md do teste prospectivo
    md = _ler_texto(ARQ_PROSPECTIVO_MD) or ""
    lin = re.search(r"^\|\s*XGBoost vs climatologia\s*\|\s*([+-][\d,]+)\s*\|\s*([+-][\d,]+)\s*\|\s*\*\*([+-][\d,]+)\*\*\s*\[IC95 ([\d,]+) a ([\d,]+)\]",
                    md, flags=re.M)
    try:
        r = json.loads(ARQ_PROSPECTIVO_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        r = None
    if lin and r:
        g = r["global"]
        ic = r["bootstrap_skill"]["xgb"]["por_composto"]["ic95"]
        c.add("modelo_skill", "skill por fase",
              f"O ganho do modelo sobre a média histórica (skill) em três fases: seleção 2010 a 2021, {lin.group(1)}; confirmação selada de "
              f"2022 a 2024 (feita uma vez), {lin.group(2)}; teste prospectivo de 2025 em diante, em dados que nunca viu, "
              f"{br(g['skill_xgb'], 3)} (intervalo de 95%: {br(ic[0], 3)} a {br(ic[1], 3)}).",
              "experimentos/prospectivo_2025/RESULTADO.md (quadro da seção 3) e resultados.json: global.skill_xgb, bootstrap_skill", 1,
              valor=br(g["skill_xgb"], 3),
              simples=("Nos testes, o modelo acerta melhor que usar só a média dos anos anteriores, mas só olhando as próximas duas semanas; "
                       "quanto mais longe, menos confiável." if g["skill_xgb"] > 0 else
                       "Nos testes mais recentes, o modelo não acertou mais do que usar só a média dos anos anteriores."))
    elif r:
        g = r["global"]
        c.add("modelo_skill", "skill prospectivo", f"No teste prospectivo de 2025 em diante, em dados que o modelo nunca viu, o skill foi "
              f"{br(g['skill_xgb'], 3)} sobre a média histórica.", "experimentos/prospectivo_2025/resultados.json: global.skill_xgb", 1,
              simples=("Nos testes mais recentes, o modelo acertou melhor que usar só a média dos anos anteriores." if g["skill_xgb"] > 0 else
                       "Nos testes mais recentes, o modelo não acertou mais do que usar só a média dos anos anteriores."))
    else:
        c.lacuna("modelo_skill", "teste prospectivo", "O teste prospectivo de 2025 em diante não está disponível nos arquivos: lacuna.",
                 "experimentos/prospectivo_2025/resultados.json")
    if r:
        h = {x["h"]: x for x in r["horizonte"]}
        if 1 in h and 4 in h:
            c.add("modelo_skill", "horizonte", f"O modelo só vale para 1 composto de 16 dias à frente. Quanto mais longe, menor o ganho: no teste "
                  f"prospectivo o skill foi {br(h[1]['skill_xgboost'], 3)} para 1 composto, {br(h[2]['skill_xgboost'], 3)} para 2, "
                  f"{br(h[3]['skill_xgboost'], 3)} para 3 e {br(h[4]['skill_xgboost'], 3)} para 4 compostos (64 dias).",
                  "experimentos/prospectivo_2025/resultados.json: horizonte[h].skill_xgboost", 1,
                  simples="Quanto mais longe no futuro, menos o modelo acerta; por isso só vale para as próximas duas semanas.")
        a80, a90 = r["faixa_aci"]["xgb_80"]["global"], r["faixa_aci"]["xgb_90"]["global"]
        c.add("modelo_skill", "cobertura real da faixa", f"Cobertura real da faixa de incerteza no teste prospectivo: a faixa de 80% cobriu "
              f"{pct(a80)} dos casos e a de 90% cobriu {pct(a90)} (a faixa foi um pouco larga demais, o que é o lado seguro; em alguns meses, "
              "como fevereiro e julho, ficou abaixo da meta).", "experimentos/prospectivo_2025/resultados.json: faixa_aci.xgb_80/xgb_90.global", 1)
        c.add("modelo_skill", "locais em que ganha", f"Em {br(r['pontos']['pct_xgb_vence_clim'], 1)}% dos locais o modelo foi melhor que a "
              "média histórica; nos demais, perdeu dela.", "experimentos/prospectivo_2025/resultados.json: pontos.pct_xgb_vence_clim", 2,
              simples=("Na maioria dos locais testados, o modelo foi melhor que usar só a média dos anos anteriores; em alguns, foi pior."
                       if r["pontos"]["pct_xgb_vence_clim"] > 50 else
                       "Em poucos locais testados o modelo foi melhor que usar só a média dos anos anteriores."))
    from src.app import mvp as M
    for t in M.limites_linhas()["previsao"]:
        n = sem_acento(t.lower())
        sp = ("O modelo acerta porque o verde das plantas muda devagar: o que vem a seguir se parece com o que já foi visto." if "persistencia" in n
              else "Só com dados de chuva e temperatura, o modelo não acerta mais do que a média dos anos anteriores." if "clima sozinho" in n else None)
        c.add("modelo_skill", "persistência e clima", t, "src.app.mvp.limites_linhas()['previsao']", 1, simples=sp)
    rel = _ler_texto(ARQ_RELATORIO) or ""
    mm_ = re.search(r"^As features de persistência não mudam sob cenário[^\n]*", rel, flags=re.M)
    if mm_:
        c.add("modelo_skill", "cenários de clima", mm_.group(0).strip() + " Por isso o app não usa esta previsão para mudar as notas dos caminhos.",
              "data/processed/modelos/relatorio_modelos.md (seção de sensibilidade a cenários)", 1,
              simples="O Sulco não usa esta previsão para mudar a ordem dos caminhos.")
    for t in [x for x in (m.get("lacunas") or []) if "`" not in x][:2]:      # lacuna com nome de variável de código não é para o agricultor
        c.lacuna("modelo_skill", "lacuna do modelo", _curto(re.sub(r"(?<=\d)\.(?=\d)", ",", t), 300), "data/processed/modelos/metricas.json: lacunas", 3)


def _previsao(c: _Coletor, pid: str) -> None:
    from src.api import main as A
    try:
        p = A.previsao(pid).model_dump()
    except Exception as e:  # noqa: BLE001 - modelo ou dados indisponíveis: lacuna com o motivo da API, nunca número
        motivo = _curto(datas_br(str(getattr(e, "detail", type(e).__name__))), 300).replace("LACUNA: ", "")
        c.lacuna("previsao", "previsão do NDVI", f"A previsão do verdor (NDVI) para este local não está disponível: {motivo}. Lacuna, sem número.",
                 "src.api.main.previsao",
                 simples="Para o seu local, ainda não temos previsão do verde das plantas: faltam dados de satélite.")
        return
    org = "src.api.main.previsao (/modelo/previsao/{ponto_id})"
    lim = p.get("limites_declarados") or []
    for t in lim[:-1]:                              # o último é o aviso geral do app
        n = sem_acento(t.lower())
        sp = ("A previsão vale só para as próximas duas semanas." if "vale so 1 composto" in n
              else "O modelo se baseia mais no verde que já foi visto antes do que na chuva ou no calor." if "persistencia" in n and "contribuem pouco" in n
              else "O satélite não enxerga a sua roça, só uma área grande; isto não é previsão de colheita, de safra nem de renda."
              if "nao e previsao de produtividade" in n else None)
        c.add("previsao_limites", "limite da previsão", _curto(t, 420), org + ": limites_declarados", 1, simples=sp)
    if p.get("ultimo_composto_observado"):
        c.add("previsao", "último composto observado",
              f"O último composto de satélite com dado válido neste local é o de {data_br(p['ultimo_composto_observado'])}: o verdor ficou "
              f"{acima_abaixo(p['anomalia_observada_ultimo'])}.", org + ": ultimo_composto_observado, anomalia_observada_ultimo", 2,
              simples=f"No último dado de satélite ({data_br(p['ultimo_composto_observado'])}), o verde das plantas estava "
                      f"{nivel_verde(p['anomalia_observada_ultimo'])}.")
    if p.get("clima_ate"):
        c.add("previsao", "fim do clima observado", f"O clima observado que o modelo usa vai até {data_br(p['clima_ate'])}; não existe previsão de "
              "clima futuro entre os dados.", org + ": clima_ate", 2,
              simples=f"O clima que o Sulco usa vai até {data_br(p['clima_ate'])}; ele não sabe como vai ser o tempo daí para frente.")
    if p.get("anomalia_ndvi_prevista") is None:
        motivo = datas_br(p.get("lacuna") or "motivo não informado")
        c.lacuna("previsao", "sem previsão", f"Sem previsão do verdor (NDVI) para este local: {_curto(motivo, 300)}. Isso é uma lacuna, não um valor "
                 "baixo ou alto.", org + ": lacuna",
                 simples="Para o seu local, ainda não temos previsão do verde das plantas: faltam dados de satélite.")
        return
    a = p["anomalia_ndvi_prevista"]
    f = p.get("faixa_incerteza") or {}
    cruza = bool(f.get("80")) and f["80"][0] < 0 < f["80"][1]     # a faixa de 80% inclui o zero: o sinal não é firme
    if cruza:
        sp = ("Para as próximas duas semanas, o verde das plantas deve ficar parecido com o normal para esta época; "
              "os dados não mostram se vai ficar mais forte ou mais fraco.")
    else:
        sp = f"Para as próximas duas semanas, o verde das plantas deve ficar {nivel_verde(a)}."
    c.add("previsao", "anomalia prevista",
          f"Previsão do verdor (NDVI) para o próximo composto de satélite, de 16 dias, com data {data_br(p['composto_alvo'])}: ele deve ficar "
          f"{acima_abaixo(a)} (anomalia = NDVI previsto menos o NDVI normal da época; acima do normal = mais verde, abaixo = menos verde). "
          f"Modelo: {p['modelo']}.", org + ": anomalia_ndvi_prevista, composto_alvo, modelo", 1, valor=br(a, 3), simples=sp)
    if f.get("80") and f.get("90"):
        c.add("previsao", "faixa de incerteza",
              f"A faixa de incerteza da previsão vai de {br(f['80'][0], 3)} a {br(f['80'][1], 3)} na faixa de 80% e de {br(f['90'][0], 3)} a "
              f"{br(f['90'][1], 3)} na faixa de 90% (valores de anomalia). A faixa é larga: o sinal da anomalia pode mudar dentro dela.",
              org + ": faixa_incerteza['80'/'90']", 1,
              simples="Esta previsão pode variar para mais ou para menos; não dá para ter certeza.")
    if p.get("extrapolacao"):
        c.add("previsao", "extrapolação", "Alguma variável do clima deste local está fora do que o modelo viu no treino: a previsão extrapola e "
              "deve ser lida com mais cautela.", org + ": extrapolacao", 1, True,
              simples="O clima do seu local está fora do que o modelo conhecia; leia a previsão com mais cuidado.")
    c.add("previsao", "treino", f"O modelo foi treinado com dados de {p['anos_treino'][0]} a {p['anos_treino'][1]}.", org + ": anos_treino", 3)
    for t in (p.get("lacunas") or [])[:2]:
        c.lacuna("previsao", "lacuna da previsão", _curto(re.sub(r"(?<=\d)\.(?=\d)", ",", datas_br(t)), 300), org + ": lacunas", 3)


def _chuva_simples(df) -> str | None:
    """Meses de maior chuva média (as 4 quinzenas mais chuvosas), em palavras; só reordena o que o fato técnico já traz."""
    q = df.dropna().sort_values("media_mm", ascending=False).head(4)
    ms = meses_do_texto(" ".join(str(x) for x in q["rotulo"]))
    return f"Em média, chove mais {lista_meses(ms)}; a chuva da sua roça pode ser bem diferente." if ms else None


def _diagnostico(c: _Coletor, pid: str, d: dict | None) -> None:
    org = "src.app.mvp.diagnostico_local (data/processed/diagnostico/diagnostico.json)"
    if d is None:
        c.lacuna("diagnostico", "diagnóstico", "Não há diagnóstico pré-calculado de satélite para este local: lacuna.", org,
                 simples="Para o seu local, ainda não temos o retrato do verde das plantas ao longo do ano.")
        return
    if d.get("solo_nu"):
        ms = meses_do_texto(d["solo_nu"]["frase"], "quinzenas:")
        c.add("diagnostico", "solo nu", d["solo_nu"]["frase"], org + ": solo_nu.frase", 1,
              simples=(f"Neste local, a terra costuma ficar mais descoberta, com pouco verde, {lista_meses(ms)}." if ms else
                       "Neste local, não aparece uma época em que a terra fique descoberta na maioria dos anos."))
    else:
        c.lacuna("diagnostico", "solo nu", "O solo nu típico não foi calculado para este local: lacuna.", org + ": solo_nu",
                 simples="Ainda não sabemos em que época a terra fica descoberta no seu local.")
    me = meses_do_texto(d["estresse_frase"], "convenção do app):")
    c.add("diagnostico", "estresse", d["estresse_frase"], org + ": estresse_frase", 1, lacuna=not d.get("estresse_top"),
          simples=(f"{lista_meses(me).capitalize()}, as plantas costumam ficar mais fracas do que o normal para a época; isso não prova falta de água."
                   if me else "Não achamos uma época em que as plantas fiquem sempre mais fracas do que o normal."))
    if d.get("veranicos"):
        fr = d["veranicos"]["frase"]
        mc = meses_do_texto(fr, "cobre ")
        med = re.search(r"mediana de (\d+) dias", fr)
        sp = (f"A época de chuva costuma ser {lista_meses(mc)}." if mc else "")
        if med:
            sp += f" Mesmo nela, é comum ficar uns {med.group(1)} dias seguidos sem chuva."
        c.add("diagnostico", "estação chuvosa e veranicos", fr, org + ": veranicos.frase", 1, simples=sp or None)
    else:
        c.lacuna("diagnostico", "veranicos", "Estação chuvosa e veranicos não foram calculados para este local: lacuna.", org + ": veranicos",
                 simples="Ainda não sabemos a época de chuva nem os períodos secos do seu local.")
    tend = []
    for t in d.get("tendencias") or []:
        extra = ""
        if t["situação"] != "sem tendência clara" and t.get("inclinação por ano") is not None:
            extra = f" ({br(t['inclinação por ano'], 2)} por ano, p = {br(t['p'], 2)})"
        tend.append(f"{t['variável']} em {t['anos']} anos: {t['situação']}{extra}")
    if tend:
        c.add("diagnostico", "tendências", "Tendências no período: " + "; ".join(tend) + ". 'Sem tendência clara' quer dizer que o teste não achou "
              "mudança segura, não que nada muda.", org + ": tendencias", 2,
              simples=("Nos últimos anos, os dados não mostram mudança segura na chuva nem na temperatura daí."
                       if all(t["situação"] == "sem tendência clara" for t in d["tendencias"]) else None))
    av = d["anos_validos"]
    c.add("diagnostico", "confiança do diagnóstico", f"Confiança do diagnóstico deste local: {d['confianca'] or 'lacuna'}. {d['confianca_nota']}. "
          f"Anos válidos de dados: NDVI {av.get('ndvi', 'lacuna')}, chuva {av.get('chuva', 'lacuna')}, umidade do solo "
          f"{av.get('umidade_solo', 'lacuna')} (a umidade do solo só existe desde 2015). Período do clima: "
          f"{' a '.join(d['periodo']) if d.get('periodo') else 'lacuna'}.", org + ": confianca, confianca_nota, anos_validos, periodo", 2)
    if d.get("lacunas"):
        c.lacuna("diagnostico", "lacunas do diagnóstico", "Lacunas do diagnóstico: " + " ".join(_curto(x, 200) for x in d["lacunas"][:3]), org + ": lacunas", 3,
                 simples="Em alguns períodos faltou dado de satélite; o retrato do seu local tem pequenos buracos.")
    if "chuva_df" in d:
        lin = [f"{r.rotulo} {br(r.media_mm, 0)}" for r in d["chuva_df"].dropna().itertuples()]
        c.add("clima", "chuva média por quinzena", "Chuva média por quinzena no local, em mm (NASA POWER, célula de cerca de 50 km; o clima da sua roça "
              "pode ser bem diferente): " + "; ".join(lin) + ".", org + ": climatologia_quinzenal.chuva_mm_quinzena", 3,
              simples=_chuva_simples(d["chuva_df"]))


def _criterios_simples(i: int, criterios: list) -> str | None:
    """Chuva e temperatura do caminho em palavras (nota >= 0,7 serve bem; >= 0,4 em parte; senão pouco). Limiares de redação, não científicos."""
    cl = {}
    for x in criterios:
        if x.get("tem_dado") and x.get("criterio") in ("chuva", "temperatura") and isinstance(x.get("nota"), (int, float)):
            cl[x["criterio"]] = "serve bem" if x["nota"] >= 0.7 else "serve em parte" if x["nota"] >= 0.4 else "serve pouco"
    if len(cl) == 2 and cl["chuva"] == cl["temperatura"]:
        return f"Caminho {i}: a chuva e a temperatura {cl['chuva'].replace('serve', 'servem', 1)} para esse plantio."
    if cl:
        return f"Caminho {i}: " + "; ".join(f"a {'chuva' if k == 'chuva' else 'temperatura'} {v}" for k, v in cl.items()) + " para esse plantio."
    return None


def _nomes_lacunas(proprias: list) -> list[str]:
    """Nomes (em palavras simples) dos critérios sem dado de um caminho."""
    nomes = []
    for t in proprias:
        m = re.match(r"([^:]+): sem dado", lacuna_legivel(t))
        if m and m.group(1).strip().lower() not in nomes:
            nomes.append(m.group(1).strip().lower())
    troca = {"nitrogênio na biomassa": "nitrogênio que a planta deixa na terra", "palha / cobertura do solo": "palha sobre o solo"}
    return [troca.get(n, n) for n in nomes]


def _lista(nomes: list[str]) -> str:
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def _lacunas_simples(i: int, proprias: list) -> str:
    nomes = _nomes_lacunas(proprias)
    if not nomes:
        return f"Caminho {i}: ainda faltam alguns dados."
    return f"Caminho {i}: ainda não temos dado de {_lista(nomes)}."


def _caminhos(c: _Coletor, pid: str, cultura: str, prio: str, calc: dict, diag: dict | None) -> None:
    from src.app import mvp as M
    org = "src.app.mvp.calcular + descricao_estrategia (motor src.culturas.motor)"
    nome = M.culturas_disponiveis()

    def nm(x):
        return nome.get(x, x).lower()
    desc = []
    for i, cen in enumerate(calc["cenarios"], 1):
        d = M.descricao_estrategia(cen, prio)
        desc.append((i, cen, d))
    # lacunas comuns aos três caminhos aparecem uma vez só
    conj = [set(x[2]["lacunas"]) for x in desc]
    comuns = [t for t in desc[0][2]["lacunas"] if all(t in s for s in conj)] if desc else []
    for i, cen, d in desc:
        alvo = cen["rotacao"][1]
        if cen.get("atual"):
            titulo = f"Caminho {i} (o que você faz hoje): repetir {nome.get(alvo, alvo)}"
        else:
            titulo = f"Caminho {i} (alternativa): {nome.get(cultura, cultura)} seguida de {nome.get(alvo, alvo)}"
        inc = d["incerteza"]
        partes = [titulo + "."]
        if inc["disponivel"]:
            partes += inc["linhas"] + inc["empate"]
        sp = (f"Caminho {i}, o que você faz hoje: repetir {nm(alvo)}." if cen.get("atual")
              else f"Caminho {i}: depois de {nm(cultura)}, plantar {nm(alvo)}." + (" Os dados não mostram qual é melhor." if inc["disponivel"] and inc["empate"] else ""))
        c.add("caminhos", f"caminho {i}", " ".join(partes), org + f": cenarios[{i - 1}].faixa_incerteza", 1, valor=None, simples=sp)
        crit = [f"{M.NOME_CRITERIO[x['criterio']]} ({M.nota_txt(x['nota'])}): {x['texto']}" for x in d["criterios"] if x["tem_dado"]]
        if crit:
            c.add("caminhos", f"critérios do caminho {i}", f"Caminho {i}, critérios com dado: " + "; ".join(crit) + ".",
                  org + f": cenarios[{i - 1}].criterios", 2, simples=_criterios_simples(i, d["criterios"]))
        cob = inc["cobertura"] if inc["disponivel"] else []
        if cob:
            c.add("caminhos", f"cobertura do caminho {i}", f"Caminho {i}: " + " ".join(cob), org + f": cenarios[{i - 1}].faixa_incerteza.cobertura", 3)
        if d["epoca"]:
            c.add("janela", f"janela do caminho {i}", f"Caminho {i}: " + d["epoca"] + (" " + d["demanda"] if d.get("demanda") else ""),
                  org + f": cenarios[{i - 1}].janela_plantio", 2,
                  simples=(f"Caminho {i}: o melhor tempo para começar a plantar é por volta de {mes_da_data(d['epoca'])}."
                           if mes_da_data(d["epoca"]) else None))
        proprias = [t for t in d["lacunas"] if t not in comuns]
        riscos = [t for t in d["riscos"] if not t.startswith("Avaliar com técnico")]
        txt = []
        if proprias:
            txt.append("Lacunas: " + " ".join(lacuna_legivel(t) for t in proprias[:3]))
        if riscos:
            txt.append("Riscos para revisão local: " + " ".join(_curto(t, 160) for t in riscos[:3]))
        if txt:
            c.add("caminhos", f"lacunas e riscos do caminho {i}", f"Caminho {i}. " + " ".join(txt), org + f": cenarios[{i - 1}].lacunas, riscos_revisao_local",
                  3, lacuna=bool(proprias), simples=_lacunas_simples(i, proprias) if proprias else None)
    # resumo de UMA linha por caminho (ação + melhor época em mês + lacuna principal): é o que o texto padrão e o prompt usam dos caminhos
    empates = []
    for i, cen, d in desc:
        alvo = cen["rotacao"][1]
        atual = bool(cen.get("atual"))
        mes = mes_da_data(d["epoca"]) if d["epoca"] else None
        proprias_i = [t for t in d["lacunas"] if t not in comuns]
        nomes = _nomes_lacunas(proprias_i)
        sp = (f"Caminho {i}{' (o que você faz hoje)' if atual else ''}: " + (f"repetir {nm(alvo)}, só para comparar" if atual
              else f"depois de {nm(cultura)}, plantar {nm(alvo)}") + (f"; melhor época para começar: {mes}" if mes else "")
              + (f"; ainda não temos dado de {_lista(nomes[:2])}" if nomes else "") + ".")
        tecnico = (f"Caminho {i}" + (" (o que você faz hoje)" if atual else "") + f": {nome.get(alvo, alvo)}. " + (d["epoca"] or "")
                   + (" Lacunas: " + " ".join(lacuna_legivel(t) for t in proprias_i) if nomes else ""))
        c.add("caminhos", f"resumo do caminho {i}", tecnico, org + f": cenarios[{i - 1}] (resumo)", 1, simples=sp)
        if not atual and d["incerteza"]["disponivel"] and d["incerteza"]["empate"]:
            empates += d["incerteza"]["empate"]
    if empates:
        c.add("caminhos", "empate entre caminhos", "Empate técnico entre os caminhos: " + " ".join(dict.fromkeys(empates)),
              org + ": faixa_incerteza.empate", 1, simples="Entre os caminhos novos, os dados não mostram qual é melhor.")
    if comuns:
        c.lacuna("caminhos", "lacunas comuns", "Lacunas comuns aos três caminhos: " + " ".join(lacuna_legivel(t, 170) for t in comuns[:4]),
                 org + ": cenarios[*].lacunas", 2,
                 simples="Em alguns anos faltou dado de clima para avaliar os caminhos.")
    if prio == "renda" and M.PRIORIDADES[prio].get("lacuna"):
        c.lacuna("caminhos", "prioridade renda", "Nos três caminhos, escolher 'renda extra' não altera o ranking: " + M.PRIORIDADES[prio]["lacuna"] + ".",
                 "src.app.mvp.PRIORIDADES['renda']", 2,
                 simples="Escolher renda extra não muda a ordem dos caminhos: ainda não temos dado de preço.")
    c.add("caminhos", "prioridade escolhida", f"Prioridade escolhida pelo agricultor: {M.PRIORIDADES[prio]['rotulo']}. " + _curto(M.PRIORIDADES[prio]["regra"], 400),
          "src.app.mvp.PRIORIDADES", 3,
          simples=("Você não escolheu uma prioridade." if prio == "sem" else f"A sua prioridade é {M.PRIORIDADES[prio]['rotulo'].lower()}."))
    v = M.vulnerabilidade_cultura_atual(pid, cultura, calc, diag)
    for t in v["lacunas"]:
        c.lacuna("janela", "janela da cultura atual", _curto(t), "src.app.mvp.vulnerabilidade_cultura_atual", 2,
                 simples=f"Ainda não sabemos o melhor tempo de plantio de {nm(cultura)} no seu local.")
    if "melhor_inicio" in v:
        txt = (f"Cultura atual ({nome.get(cultura, cultura)}): melhor início de plantio nos dados de 2001 a 2024: {v['melhor_inicio']} (ciclo suposto de "
               f"{v['duracao']} dias). Inícios com menor adequação: {', '.join(v['piores_inicios'])}. Situação da cultura neste local pelo motor: "
               f"{v['viabilidade']}.")
        if "solo_nu_no_ciclo" in v:
            txt += (f" Dentro do ciclo da melhor data: campo nu típico em {M.rotulos_quinzenas(v['solo_nu_no_ciclo'])}; maior estresse do verdor em "
                    f"{M.rotulos_quinzenas(v['estresse_no_ciclo'])}; estação chuvosa em {M.rotulos_quinzenas(v['estacao_chuvosa_no_ciclo'])}.")
        mi = mes_da_data(v["melhor_inicio"])
        pior = sorted({int(x[3:5]) - 1 for x in v.get("piores_inicios") or [] if re.fullmatch(r"\d{2}/\d{2}", str(x))})
        sp = None
        if mi:
            sp = f"Para {nm(cultura)}, o melhor tempo para começar a plantar nos dados é por volta de {mi}."
            if pior:
                sp += f" Começar {lista_meses(pior)} costuma ser pior."
        c.add("janela", "vulnerabilidade da cultura atual", txt, "src.app.mvp.vulnerabilidade_cultura_atual", 1, simples=sp)


def _decendio(i: int) -> str:
    from src.app import mvp as M
    return f"{i % 3 + 1}º decêndio de {M.MESES[i // 3]}"


def faixas_decendios(perm) -> str:
    """Decêndios permitidos (36, a partir de 1º jan) em faixas: 'do 2º decêndio de mar ao 1º decêndio de mai'. Só formata."""
    idx = [i for i, ok in enumerate(perm) if ok]
    if not idx:
        return "nenhum"
    runs, ini, ant = [], idx[0], idx[0]
    for i in idx[1:]:
        if i != ant + 1:
            runs.append((ini, ant))
            ini = i
        ant = i
    runs.append((ini, ant))
    return "; ".join(_decendio(a) if a == b else f"do {_decendio(a)} ao {_decendio(b)}" for a, b in runs)


def _meses_perm(perm) -> str:
    """Meses com algum decêndio permitido (36 decêndios, 3 por mês), em palavras: 'fevereiro a abril'."""
    return lista_meses(sorted({i // 3 for i, ok in enumerate(perm) if ok}))


def _zarc(c: _Coletor, pid: str, culturas: list[str]) -> None:
    from src.app import filtros as F
    from src.app import mvp as M
    from src.culturas import zarc as zarc_mod
    geo = zarc_mod.geocodigo_do_ponto(pid)
    nome = M.culturas_disponiveis()
    for cid in culturas:
        j = zarc_mod.janela(geo, cid, F.RISCO_ZARC, "qualquer")
        perm = j.get("permitido")
        org = "src.culturas.zarc.janela (data/processed/zarc_ce.parquet)"
        if perm is None or len(perm) != 36:
            c.lacuna("zarc", f"ZARC de {cid}", f"ZARC de {nome.get(cid, cid)}: sem zoneamento para este município ({_curto(j.get('motivo') or 'sem dado')}).", org, 2,
                     simples=f"Para {nome.get(cid, cid).lower()}, não há zoneamento do Ministério da Agricultura para o seu município.")
            continue
        rec = re.sub(r"safra_(\d{4})_(\d{4})", r"safra \1/\2", str(j.get("recurso") or ""))
        c.add("zarc", f"ZARC de {cid}", f"ZARC (zoneamento do Ministério da Agricultura, sequeiro, risco até {F.RISCO_ZARC}%) de {nome.get(cid, cid)}: "
              f"{j.get('n_decendios')} decêndios com plantio permitido: {faixas_decendios(perm)}" + (f" ({rec})" if rec else "") + ". O ZARC não "
              "considera pragas e doenças.", org, 2,
              simples=f"Pelo zoneamento do Ministério da Agricultura, {nome.get(cid, cid).lower()} pode ser plantado {_meses_perm(perm)}; "
                      "ele não considera pragas e doenças.")


def _agua_simples(q: list) -> str:
    """Compara só o sinal do saldo (chuva menos ETo) de cada quinzena; sem número novo."""
    neg = sum(1 for x in q if x["saldo_mm"] < 0)
    if neg > 0.75 * len(q):
        return "Quase o ano todo, a chuva não cobre a água que o calor tira da terra; só nas épocas mais chuvosas ela chega perto."
    if neg > 0.4 * len(q):
        return "Em boa parte do ano, a chuva não cobre a água que o calor tira da terra."
    return "Na maior parte do ano, a chuva cobre a água que o calor tira da terra."


def _solo_risco_extremos_eto_renda(c: _Coletor, pid: str, culturas: list[str]) -> None:
    from src.app import mvp as M
    from src.app import secao_balanco_renda as SBR
    from src.app import secao_risco_solo as SRS
    est = M.solo_estimado(pid)
    org = "src.app.mvp.solo_estimado (data/processed/solo.parquet, SoilGrids)"
    if est:
        c.add("solo", "solo estimado", f"Solo estimado pelo mapa global SoilGrids (0 a 30 cm; mediana de cerca de 2 km em volta): argila "
              f"{br(est['argila_pct'], 0)}%, areia {br(est['areia_pct'], 0)}%, silte {br(est['silte_pct'], 0)}%, carbono orgânico "
              f"{br(est['carbono_organico_g_kg'], 0)} g/kg, pH {br(est['ph_agua'], 1)}; textura {est['textura']}. Não é análise de solo: confirme com o técnico.",
              org, 1, simples=f"Pelo mapa, o solo da sua região é de tipo {est['textura']}; é só uma estimativa, confirme com o técnico.")
        if est.get("aviso_pixels"):
            c.lacuna("solo", "aviso do solo estimado", est["aviso_pixels"], org + ": aviso_pixels", 1)
    else:
        c.lacuna("solo", "solo estimado", "Não há solo estimado (SoilGrids) para este local: lacuna.", org,
                 simples="Para o seu local, ainda não temos uma estimativa do tipo de solo.")
    s = SRS.secao_risco_solo(pid)
    org = "src.app.secao_risco_solo.secao_risco_solo"
    lim = s["limiares"]["cortes_da_soma"]
    ent = []
    for e in s["entradas"]:
        v = e["valor"]
        if isinstance(v, dict):
            v = ", ".join(f"{k.replace('_pct', '')} {br(x, 0)}%" for k, x in v.items() if x is not None)
        elif isinstance(v, (int, float)):
            v = br(v, 1)
        if v is None:
            ent.append(f"{e['componente']}: lacuna")
            continue
        extra = f"; classe {e['classe']}" if e.get("classe") else ""
        nota = f"; nota {e['nota']}" if e.get("nota") is not None else ""
        corte = e.get("corte")
        rel = (f"; corte por tercis entre os {corte['n_pontos']} pontos do projeto ({br(corte['c1'], 1)} e {br(corte['c2'], 1)}), ou seja, relativo aos outros pontos"
               if corte else "")
        ent.append(f"{e['componente']}: {v} {e.get('unidade') or ''}".strip() + extra + nota + rel)
    c.add("risco", "risco de erosão", f"Indicador relativo de erosão e escoamento neste local: {s['classe']} (soma de notas {s['soma_notas']} de "
          f"{s['soma_maxima']}; médio a partir de {lim['medio_a_partir_de']}, alto a partir de {lim['alto_a_partir_de']}; as notas e os cortes são "
          "suposição do projeto). Componentes: " + " | ".join(ent) + ".", org, 1, not s["disponivel"],
          simples=(f"O risco de a chuva levar a terra embora (erosão) aqui é {s['classe']}; é só uma indicação, confirme com o técnico."
                   if s["disponivel"] and s.get("classe") else "Ainda não dá para dizer o risco de erosão no seu local."))
    for t in s["avisos"][:1]:
        c.add("risco", "aviso do risco", _curto(t, 380), org + ": avisos", 2)
    for t in s["lacunas"][:3]:
        c.lacuna("risco", "lacuna do risco", lacuna_legivel(t, 220), org + ": lacunas", 2)
    e = SRS.secao_extremos(pid)
    org = "src.app.secao_risco_solo.secao_extremos (src.culturas.extremos)"
    if not e.get("disponivel"):
        c.lacuna("extremos", "calor e chuva extrema", "Calor e chuva extrema não foram calculados para este local (sem série diária de clima): lacuna.", org,
                 simples="Ainda não sabemos quantos dias muito quentes ou de chuva muito forte houve no seu local.")
    else:
        df = e["definicoes"]
        ult = e["tabela_por_ano"].iloc[-1]
        c.add("extremos", "definições", f"Dia quente: {df['calor']} (limiar entre {br(df['limiar_tmax_c_min'], 1)} e {br(df['limiar_tmax_c_max'], 1)} °C "
              f"ao longo do ano). Chuva extrema: {df['chuva_extrema']} (limiar {br(df['limiar_chuva_extrema_mm'], 1)} mm por dia). Período-base: "
              f"{df['periodo_base']}.", org + ": definicoes", 2)
        c.add("extremos", "último ano", f"No ano de {int(ult['ano'])} houve {int(ult['dias_quentes'])} dias quentes, {int(ult['dias_chuva_extrema'])} "
              f"dias de chuva extrema e a maior chuva em um dia foi de {br(ult['rx1day_mm'], 1)} mm.", org + ": tabela_por_ano (último ano)", 2,
              simples=f"No ano de {int(ult['ano'])}, houve {int(ult['dias_quentes'])} dias muito quentes e {int(ult['dias_chuva_extrema'])} dias de "
                      f"chuva muito forte; a maior chuva em um dia foi de {br(ult['rx1day_mm'], 1)} mm.")
        nomes = {"dias_quentes": "dias quentes", "dias_chuva_extrema": "dias de chuva extrema", "rx1day_mm": "maior chuva em 1 dia"}
        tl = []
        for k, t in e["tendencias"].items():
            if t.get("resultado") == "calculada":
                tl.append(f"{nomes.get(k, k)}: {br(0.0 if abs(t['inclinacao_por_ano']) < 0.005 else t['inclinacao_por_ano'], 2)} por ano em {t['n_anos']} anos, " +
                          ("sem tendência clara" if t["mann_kendall"] == "no trend" else "com tendência") + f" (p = {br(t['p_valor'], 2)})")
        if tl:
            c.add("extremos", "tendência dos extremos", "Tendência dos extremos: " + "; ".join(tl) + ".", org + ": tendencias", 3,
                  simples=("Nos dados, não há mudança segura no número de dias quentes nem de chuvas fortes."
                           if all("sem tendência clara" in x for x in tl) else None))
        for t in e["lacunas"][:2]:
            c.lacuna("extremos", "lacuna dos extremos", _curto(t), org + ": lacunas", 3)
    b = SBR.secao_balanco_hidrico(pid)
    org = "src.app.secao_balanco_renda.secao_balanco_hidrico (src.culturas.balanco_hidrico)"
    q = [x for x in b["quinzenas"] if x["saldo_mm"] is not None]
    c.add("eto", "aviso da ETo", _curto(b["aviso"], 520), org + ": aviso", 1)
    if q:
        c.add("eto", "chuva menos ETo", "Chuva menos evapotranspiração de referência (ETo) por quinzena, média de 2001 a 2024, em mm (saldo negativo = a "
              "atmosfera pede mais água do que a chuva traz, para uma superfície de referência): " +
              "; ".join(f"{x['rotulo']} chuva {br(x['chuva_mm'], 0)}, ETo {br(x['eto_mm'], 0)}, saldo {br(x['saldo_mm'], 0)}" for x in q) + ".", org + ": quinzenas", 2,
              simples=_agua_simples(q))
    else:
        c.lacuna("eto", "chuva menos ETo", "O saldo chuva menos ETo não foi calculado para este local: lacuna.", org, 1,
                 simples="Ainda não calculamos se a chuva dá conta da água que o calor tira, no seu local.")
    for t in b["lacunas"][:1]:
        c.lacuna("eto", "lacuna da ETo", _curto(t), org + ": lacunas", 2)
    import pandas as pd
    ibge = M.carregar_pontos().set_index("ponto_id").loc[pid].get("ibge")
    ibge = None if pd.isna(ibge) else int(ibge)
    r = SBR.secao_renda(ibge, list(M.carregar_tabela()))
    org = "src.app.secao_balanco_renda.secao_renda (src.culturas.renda, IBGE/PAM)"
    nome = M.culturas_disponiveis()
    itens = {i["cultura"]: i for i in r["itens"]}
    com, sem, com_s, sem_s = [], [], [], []
    for cid in culturas:
        i = itens.get(cid)
        if i and not i["lacuna"]:
            com_s.append(f"{nome.get(cid, cid)} R$ {milhar(i['receita_bruta_r_ha'])}")
            com.append(f"{nome.get(cid, cid)} R$ {milhar(i['receita_bruta_r_ha'])} por hectare" + (f" ({_curto(i['nota'], 110)})" if i.get("nota") else ""))
        else:
            sem.append(f"{nome.get(cid, cid)}: {lacuna_legivel((i or {}).get('motivo_lacuna') or 'sem dado', 120)}")
            sem_s.append(nome.get(cid, cid).lower())
    if com:
        c.add("renda", "receita bruta", f"{r['titulo']} neste município: " + "; ".join(com) + ". Receita bruta NÃO é lucro (sem custo, preço futuro nem mercado) "
              "e não é previsão de renda.", org, 1,
              simples="Nos dados do IBGE, a venda bruta por hectare neste município foi: " + "; ".join(com_s) +
                      ". Isso não é lucro, porque não desconta os custos.")
    if sem:
        c.lacuna("renda", "receita bruta sem dado", "Sem receita bruta (IBGE) para: " + "; ".join(sem) + ".", org, 1,
                 simples="Ainda não temos dado de venda do IBGE para: " + ", ".join(sem_s) + ".")
    if ibge is None:
        c.lacuna("renda", "receita bruta", "Este local não tem código de município do IBGE: sem receita bruta.", org, 1,
                 simples="Ainda não temos dado de venda nem de preço para o seu município.")


def _metricas_globais(c: _Coletor) -> None:
    from src.app import logica as L
    for t in L.LIMITES_FIXOS:
        c.add("limites", "limite dos dados", t, "src.app.logica.LIMITES_FIXOS", 2, simples=simples_limite_global(t))
    from src.api import main as A
    try:
        m = A.limites()
    except Exception:  # noqa: BLE001
        return
    for t in (m.get("limites_fixos") or [])[:2]:
        c.add("limites", "limite fixo da API", _curto(t, 200), "src.api.main.limites: limites_fixos", 3,
              simples=simples_limite_global(t))


def montar_folha(ponto_id: str, cultura_atual: str | None = None, prioridade: str = "sem", calc: dict | None = None) -> dict:
    """Folha de fatos DETERMINÍSTICA do local. Nunca levanta: o que falhar vira fato de lacuna.

    Devolve {'fatos': [...], 'privado': {...}, 'tem_cultura': bool}. Os fatos NÃO têm nome, ponto_id, IBGE, lat nem lon."""
    from src.app import mvp as M
    c = _Coletor()
    pts = M.carregar_pontos().set_index("ponto_id")
    if ponto_id not in pts.index:
        raise KeyError(f"ponto '{ponto_id}' não está em pontos.csv")
    linha = pts.loc[ponto_id]
    import pandas as pd
    ibge = None if pd.isna(linha.get("ibge")) else int(linha.get("ibge"))
    privado = {"ponto_id": ponto_id, "nome": str(linha["nome"]), "ibge": ibge, "lat": float(linha["lat"]), "lon": float(linha["lon"]),
               "celula_power": str(linha["celula_power"])}

    def seguro(tema, rotulo, origem, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - uma parte sem dado vira lacuna, não derruba a folha
            c.lacuna(tema, rotulo, f"Não foi possível montar este bloco para este local ({type(e).__name__}): lacuna.", origem, 2)

    seguro("previsao", "previsão", "src.api.main.previsao", lambda: _previsao(c, ponto_id))
    seguro("modelo_skill", "métricas", "src.api.main.limites", lambda: _skill_historico(c))
    diag = None
    try:
        diag = M.diagnostico_local(ponto_id)
    except Exception:  # noqa: BLE001
        pass
    seguro("diagnostico", "diagnóstico", "src.app.mvp.diagnostico_local", lambda: _diagnostico(c, ponto_id, diag))
    culturas = []
    if cultura_atual:
        if prioridade not in M.PRIORIDADES:
            prioridade = "sem"
        try:
            calc = calc or M.calcular(ponto_id, cultura_atual, prioridade, com_evidencias=False)
            seguro("caminhos", "caminhos", "src.app.mvp.calcular", lambda: _caminhos(c, ponto_id, cultura_atual, prioridade, calc, diag))
            culturas = list(dict.fromkeys(cen["rotacao"][1] for cen in calc["cenarios"]))
        except Exception as e:  # noqa: BLE001
            c.lacuna("caminhos", "caminhos", f"Os três caminhos não puderam ser calculados para este local ({type(e).__name__}): lacuna.", "src.app.mvp.calcular")
        seguro("zarc", "ZARC", "src.culturas.zarc.janela", lambda: _zarc(c, ponto_id, culturas))
    else:
        c.lacuna("caminhos", "caminhos", "A cultura atual não foi informada: os três caminhos não foram calculados (lacuna).", "entrada do usuário")
    seguro("solo", "solo, risco, extremos, ETo e renda", "src.app.secao_*", lambda: _solo_risco_extremos_eto_renda(c, ponto_id, culturas))
    seguro("limites", "limites", "src.app.logica.LIMITES_FIXOS", lambda: _metricas_globais(c))
    for i, f in enumerate(c.fatos, 1):
        f["id"] = f"F{i}"
    folha = {"fatos": c.fatos, "privado": privado, "tem_cultura": bool(cultura_atual), "prioridade": prioridade}
    for f in folha["fatos"]:                                  # defesa final: nenhum identificador no texto
        f["texto"] = anonimizar(f["texto"], privado)
        if f.get("texto_simples"):
            f["texto_simples"] = anonimizar(f["texto_simples"], privado)
    return folha


# ---------------------------------------------------------------------------------------------- anonimização
def _sa(s: str) -> str:
    return "".join(sem_acento(ch) or ch for ch in s)


def _alvos(privado: dict | None) -> list[tuple[str, str]]:
    """(valor, substituto) de tudo que identifica o local. Números só casam inteiros (sem grudar em outro número)."""
    if not privado:
        return []
    alvos = []
    nome = str(privado.get("nome") or "")
    if len(nome) >= 3:
        alvos.append((nome, ROTULO_LOCAL))
    pid = str(privado.get("ponto_id") or "")
    if pid:
        alvos.append((pid, ROTULO_LOCAL))
        base = pid.rsplit("_", 1)[0].replace("_", " ")
        if len(base) >= 4:
            alvos.append((base, ROTULO_LOCAL))
    if privado.get("ibge"):
        alvos.append((str(privado["ibge"]), "[código removido]"))
    for k in ("lat", "lon"):
        v = privado.get(k)
        if v is not None:
            for nd in (2, 3, 4, 5, 6):
                for sep in (".", ","):
                    alvos.append((f"{float(v):.{nd}f}".replace(".", sep), "[coordenada removida]"))
    return sorted(alvos, key=lambda x: -len(x[0]))


def _padrao(chave: str):
    numerico = bool(re.fullmatch(r"-?[\d.,]+", chave))
    return re.compile((r"(?<![\w.,])" if numerico else r"(?<!\w)") + re.escape(_sa(chave).lower()) + (r"(?![\d])" if numerico else r"(?!\w)"))


def anonimizar(texto: str, privado: dict | None) -> str:
    """Troca nome do município, ponto_id, código IBGE, latitude e longitude (se aparecerem) por 'o seu município' ou remove."""
    if not privado or not isinstance(texto, str):
        return texto
    saida = texto
    for chave, subst in _alvos(privado):
        n = _sa(saida).lower()
        for m in reversed(list(_padrao(chave).finditer(n))):
            saida = saida[:m.start()] + subst + saida[m.end():]
    return saida


def identificadores(privado: dict | None) -> list[str]:
    """Valores que NUNCA podem aparecer num texto enviado à API externa (usado pelos testes)."""
    return [c for c, _ in _alvos(privado)]


def vazou(texto: str, privado: dict | None) -> list[str]:
    """Identificadores que aparecem no texto (vazio = ok). Compara sem acento, sem diferença de maiúsculas e sem grudar em outros números."""
    n = _sa(texto).lower()
    return [c for c, _ in _alvos(privado) if _padrao(c).search(n)]


# ---------------------------------------------------------------------------------------------- seleção para a pergunta
TEMAS = {   # tema da PERGUNTA -> temas de FATO que ela aciona
    "previsao": ("previsao", "previsao_limites", "modelo_skill"),
    "modelo": ("modelo_skill", "previsao_limites", "limites"),
    "diagnostico": ("diagnostico",),
    "caminhos": ("caminhos", "janela"),
    "zarc": ("zarc", "janela"),
    "solo": ("solo", "risco"),
    "risco": ("risco", "solo"),
    "extremos": ("extremos", "clima"),
    "eto": ("eto", "clima"),
    "renda": ("renda",),
    "clima": ("clima", "extremos", "eto", "diagnostico"),
    "limites": ("limites", "modelo_skill"),
}
# FORTE = pergunta sobre os dados do local em qualquer frase; FRACO = palavra comum de pergunta agronômica ("quanta chuva o caupi precisa?"),
# só conta se a pergunta fala do SEU local (meu/aqui/município...). Assim as perguntas do acervo continuam indo ao RAG.
FORTES = {
    "previsao": r"previs|prever|proxim\w+ (semana|quinzena|mes|composto|dia)|nas proximas|vai ficar|ficara|futuro|amanha|daqui a|"
                r"mes que vem|anomalia|composto|\bndvi\b",
    "modelo": r"modelo|confiavel|confio|acert|\bskill\b|metrica|precisao|incerteza",
    "diagnostico": r"solo nu|campo nu|terra (nua|descoberta)|estresse|veranico|tendencia|diagnostico|estacao chuvosa",
    "caminhos": r"caminho|alternativ|sugeri|sugest|recomend|empate|lacuna|criterio|pontuacao|top ?3|por ?que (o sulco|sugeri|esse|essa|isso)",
    "risco": r"erosao|escoamento|declive|enxurrada|perda de solo",
    "solo": r"soilgrids",
    "extremos": r"rx1day|dias quentes|chuva extrema",
    "eto": r"evapotransp|\beto\b|balanco hidrico|\bsaldo\b",
    "renda": r"receita bruta|receita (do|da|por) (municipio|hectare)|\bibge\b|valor da producao|\brenda\b",
    "limites": r"limite|nao sabe|nao consegue|enxerga|resolucao|de onde vem",
}
FRACOS = {
    "previsao": r"vegetacao|verdor",
    "diagnostico": r"quinzena|epoca|chuvosa|satelite|vegetacao|verdor|sofre|sofrimento",
    "caminhos": r"rotacao|cultura|plantar|plantio|\bnota\b|risco|cenario|opcao|opcoes|janela",
    "zarc": r"zarc|zoneamento|permitid|decendio|quando plantar|epoca de plantio",
    "solo": r"\bsolo\b|argila|areia|silte|textura|\bph\b|carbono|materia organica",
    "extremos": r"calor|quente|extrem|chuva forte|temporal|temperatura",
    "eto": r"\bagua\b|seca\b",
    "clima": r"clima|chuva|chove|temperatura|pluviosidade",
}
LOCAL = (r"\b(meu|minha|meus|minhas|aqui|local|municipio|cidade|regiao|roca|sitio|propriedade|nesta|neste|nessa|desse|dessa|esse|essa|"
         r"onde (eu )?(moro|planto|vivo))\b")
GERAL = r"meu (local|municipio|terreno|lugar|sitio)|minha (cidade|regiao|terra|roca)|\baqui\b|esse local|este local|resumo|me (fale|conte|diga) (do|sobre)"
_FORTES = {k: re.compile(v) for k, v in FORTES.items()}
_FRACOS = {k: re.compile(v) for k, v in FRACOS.items()}
_LOCAL = re.compile(LOCAL)
_GERAL = re.compile(GERAL)


def temas_da_pergunta(pergunta: str) -> list[str]:
    n = sem_acento(pergunta.lower())
    ach = [k for k, r in _FORTES.items() if r.search(n)]
    if _LOCAL.search(n):
        ach += [k for k, r in _FRACOS.items() if r.search(n) and k not in ach]
    if not ach and _GERAL.search(n):
        ach = ["geral"]
    return ach


def selecionar(folha: dict | None, pergunta: str, teto_tokens: int = TETO_TOKENS_FATOS) -> list[dict]:
    """Fatos RELEVANTES à pergunta (determinístico), limpos e dentro do teto de tokens. [] = a pergunta não é sobre dados do local.

    Só entram fatos com `texto_simples` (é o que o agricultor lê e o que vai ao prompt); o teto conta o tamanho dessa frase."""
    if not folha or not folha.get("fatos"):
        return []
    temas = temas_da_pergunta(pergunta)
    if not temas:
        return []
    if "modelo" in temas:             # 'quanto o modelo de previsão acerta?' é sobre as MÉTRICAS, não sobre a previsão do local
        temas = ["modelo"] + [t for t in temas if t not in ("modelo", "previsao")]
    base = [f for f in folha["fatos"] if f.get("texto_simples")]
    if temas == ["geral"]:
        alvo = {"previsao", "diagnostico", "caminhos", "janela", "solo"}
        cand = [f for f in base if f["tema"] in alvo and f["prio"] == 1]
    else:
        # ordem de importância dos temas da pergunta = ordem em que casaram; o 1º tema manda no desempate
        ordem = {}
        for i, t in enumerate(temas):
            for ft in TEMAS.get(t, ()):
                ordem.setdefault(ft, i)
        cand = [f for f in base if f["tema"] in ordem]
        cand.sort(key=lambda f: (f["prio"], ordem[f["tema"]], int(f["id"][1:])))
        if "previsao" in temas:      # pergunta sobre o futuro: previsão e limites primeiro
            cand.sort(key=lambda f: (0 if f["tema"] in ("previsao", "previsao_limites") else 1, f["prio"], int(f["id"][1:])))
    escolhidos, gasto, vistos = [], 0, set()
    for f in cand:
        if f["texto_simples"] in vistos:
            continue                  # mesma frase simples vinda de duas fontes: uma só vez
        vistos.add(f["texto_simples"])
        if trecho_suspeito(f["texto_simples"]):
            continue                  # fato com cara de instrução (ex.: texto de lacuna adulterado) não vai ao modelo
        t = tokens_aprox(f["texto_simples"]) + 6
        if gasto + t > teto_tokens or len(escolhidos) >= MAX_FATOS_PROMPT:
            continue
        escolhidos.append(f)
        gasto += t
    resumidos = {f["rotulo"].rsplit(" ", 1)[1] for f in escolhidos if f["rotulo"].startswith("resumo do caminho ")}
    if resumidos:       # o resumo de uma linha já traz ação, época e lacuna do caminho: não repete os fatos detalhados
        sai = {r for i in resumidos for r in (f"caminho {i}", f"janela do caminho {i}", f"lacunas e riscos do caminho {i}")}
        escolhidos = [f for f in escolhidos if f["rotulo"] not in sai]
    escolhidos.sort(key=lambda f: int(f["id"][1:]))
    return [{**f, "texto": neutralizar(f["texto"]), "texto_simples": neutralizar(f["texto_simples"])} for f in escolhidos]


def bloco_fatos(fatos: list[dict]) -> str:
    """Fatos como o LLM os recebe: só a frase SIMPLES (sem origem, sem identificadores, sem o texto técnico)."""
    return "<<<FATOS_DO_LOCAL>>>\n" + "\n".join(f"[{f['id']}] {f.get('texto_simples') or f['texto']}" for f in fatos) + "\n<<<FIM_FATOS>>>"


MSG_PADRAO_VAZIA = "Ainda não temos dado para responder isso."
FECHO_PADRAO = "Converse com o técnico."
FECHO_PREVISAO = "Isso vale só para as próximas duas semanas; converse com o técnico."
MAX_LINHAS_PADRAO = 5
MAX_LINHAS_CAMINHOS = 6
# pergunta sobre o quanto o modelo acerta: resposta (ganho nos testes), onde ganha, por que acerta, margem de variação
METRICAS_ORDEM = ["skill por fase", "locais em que ganha", "persistência e clima", "cobertura no holdout"]


def template_fatos(fatos: list[dict]) -> str:
    """Texto padrão (sem IA), curto e simples: no máximo 5 linhas (até 3 fatos, 1 lacuna e o fecho 'converse com o técnico').

    Cada linha leva o id [F#] só para conferência; `chat.limpar_citacoes` tira os marcadores do texto exibido. Só `texto_simples`."""
    uteis = [f for f in fatos if f.get("texto_simples")]
    if not uteis:
        return MSG_PADRAO_VAZIA + " " + FECHO_PADRAO
    prev = any(f["tema"] in ("previsao", "previsao_limites", "modelo_skill") for f in uteis)

    resumos = sorted((f for f in uteis if f["rotulo"].startswith("resumo do caminho ")), key=lambda f: int(f["rotulo"].rsplit(" ", 1)[1]))
    if resumos and not prev:      # caminhos: Caminho 1 (hoje), 2 e 3, uma linha cada, + empate + fecho (máx. 6 linhas)
        ls = [f"{f['texto_simples']} [{f['id']}]" for f in resumos][:3]
        ls += [f"{f['texto_simples']} [{f['id']}]" for f in uteis if f["rotulo"] == "empate entre caminhos"][:1]
        return "\n".join(ls[:MAX_LINHAS_CAMINHOS - 1] + [FECHO_PADRAO])
    tem_prev = any(f["tema"] == "previsao" and f["rotulo"] in ("anomalia prevista", "previsão do NDVI", "sem previsão") for f in uteis)

    def ordem(f):      # a RESPOSTA primeiro: previsão (ou a lacuna dela) ou, numa pergunta de métricas, o skill; depois caminhos, época, resto
        r = f["rotulo"]
        if f["tema"] == "previsao" and r in ("anomalia prevista", "previsão do NDVI", "sem previsão"):
            grupo = 0
        elif not tem_prev and r in METRICAS_ORDEM:
            grupo = 0 if r == METRICAS_ORDEM[0] else 1
            return (grupo, METRICAS_ORDEM.index(r), int(f["id"][1:]))
        else:
            grupo = 1 if r.startswith("caminho ") and "hoje" not in f["texto_simples"] else \
                2 if r.startswith("janela do caminho") and r != "janela do caminho 1" else 3
        return (grupo, f["prio"], int(f["id"][1:]))
    frase_prev = "A previsão vale só para as próximas duas semanas."
    corpo, por_tema = [], {}
    for f in sorted((f for f in uteis if not f["lacuna"] or f["rotulo"] in ("previsão do NDVI", "sem previsão")), key=ordem):
        if prev and f["texto_simples"] == frase_prev:
            continue                       # o fecho já diz isso
        if not tem_prev and f["rotulo"] in ("horizonte", "holdout 2022-2024") and any(x["rotulo"] == METRICAS_ORDEM[0] for x in uteis):
            continue                       # já dito pelo 'skill por fase' (acerta mais, só duas semanas)
        if len(corpo) < 3 and f["rotulo"] != "cobertura real da faixa":
            corpo.append(f)
            por_tema[f["tema"]] = por_tema.get(f["tema"], 0) + 1
    lac = sorted((f for f in uteis if f["lacuna"] and f not in corpo),
                 key=lambda f: (0 if "ainda não temos" in f["texto_simples"] else 1, f["prio"], int(f["id"][1:])))[:1]
    escolhidos = sorted(corpo + lac, key=ordem if corpo and corpo[0]["tema"] == "previsao" else lambda f: int(f["id"][1:]))
    ls = [f"{f['texto_simples']} [{f['id']}]" for f in escolhidos][:MAX_LINHAS_PADRAO - 1]
    ls.append(FECHO_PREVISAO if prev else FECHO_PADRAO)
    return "\n".join(ls)


def fecho_para(texto: str, fatos: list[dict], previsao: bool | None = None) -> str:
    """Linha fixa que o CÓDIGO anexa à resposta da IA (a IA não precisa escrever o fecho). Fecho de previsão ('só duas semanas; converse com
    o técnico') SÓ quando o tema escolhido é previsão ou métricas do modelo; nos demais, 'Converse com o técnico.'. Não duplica o que o texto
    já diz; devolve '' se não falta nada. `previsao=None`: deduz dos temas dos fatos."""
    n = sem_acento(texto.lower())
    tem_tec = bool(re.search(r"convers\w+ com o tecnico|avaliar com tecnico local", n))
    if previsao is None:
        previsao = any(f.get("tema") in ("previsao", "previsao_limites", "modelo_skill") for f in fatos)
    if previsao and "duas semanas" not in n:
        return "Isso vale só para as próximas duas semanas." if tem_tec else FECHO_PREVISAO
    return "" if tem_tec else FECHO_PADRAO
