"""CALENDÁRIO DE PLANTIO: o que os dados mostram sobre uma lavoura que o agricultor diz ter plantado (ou pensa em plantar).

Módulo PURO e testável: sem Streamlit, sem rede, sem LLM. Toda conta é daqui; o chat só reescreve os fatos que `src/llm/fatos.py`
monta a partir deste resultado. Nada aqui diz o que fazer: devolve datas, faixas, contagens e lacunas, cada uma com a sua ORIGEM.

Entrada: `ponto_id` e uma lista de plantios `[{cultura, quando, ciclo_dias?, manejo?}]`, mais a data de hoje (injetável).
`quando` (3 formas, validadas por `validar_plantios`):
  {"data": "2026-02-10"}                                   data exata
  {"mes": 2, "ano": 2026 | null, "parte": null|"comeco"|"meio"|"fim"}   mês (+ano, + começo=dias 1-10, meio=11-20, fim=21 em diante).
                                                           Mês SEM ano = o mais recente que já começou (nunca no futuro).
  {"de": "2026-03-01", "ate": "2026-03-07", "precisao": "semana"|"relativo"|"quinzena"|"faixa"}   faixa concreta
Para cada plantio devolve (cada bloco traz `disponivel` e, se faltar dado, o `motivo`: lacuna visível, nunca preenchida):
  quando         início (faixa quando só se sabe o mês), data de referência (meio da faixa) e precisão;
  ciclo          dias do ciclo e FONTE: o que o agricultor informou > FAO-56 (Tabela 11, estágios ini/dev/mid/late; referência de OUTRAS
                 regiões) > EcoCrop (faixa mín-máx da tabela de culturas);
  fase           estágio FAO (ini/dev/mid/late) ou fração do ciclo, e dias desde o plantio;
  colheita       janela esperada (ciclo mín até máx);
  zarc           plantio dentro/fora/parcial/sem zoneamento (decêndio, risco 20/30/40, solo);
  chuva          mm desde o plantio (até o fim do ciclo de referência ou do dado) e posição entre os mesmos períodos dos anos anteriores (n anos);
  veranico       maior sequência de dias secos (< limiar do projeto) em dias da época de chuva, contra o que é comum no local;
  verde          anomalia do verde da REGIÃO (satélite) desde o plantio: não é a lavoura;
  solo_nu        época em que o solo costuma ficar nu no local (diagnóstico) e quanto falta depois da colheita;
  proximas       culturas que a matriz de rotação (fonte: acervo local) mostra como favoráveis depois desta, filtradas pela viabilidade no
                 local e pelas regras duras; sem ranking entre elas (empate declarado).
Situações: `em_andamento`, `ciclo_concluido` (pelos dias de referência), `planejamento` (data futura) ou `esclarecimento`
(cultura fora da lista, data futura distante ou antiga demais): neste caso o chat PERGUNTA, não calcula.
Suposições (declaradas): decêndio = dias 1-10, 11-20, 21-fim de cada mês (como o ZARC); mês sem dia = referência no meio da faixa;
'posição' (abaixo/perto/acima) usa terços dos anos anteriores só para a REDAÇÃO.
"""
from __future__ import annotations

import calendar
import functools
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
VERSAO = "calendario-v1"
MAX_PLANTIOS = 12
MANEJOS = ("sequeiro", "irrigado")
PARTES = ("comeco", "meio", "fim")
PRECISOES_FAIXA = ("semana", "relativo", "quinzena", "faixa", "estacao")
FUTURO_MAX_DIAS = 365               # plantio futuro até 1 ano vira 'planejamento'; além disso, esclarecimento
PASSADO_MAX_DIAS = 730              # plantio de mais de 2 anos atrás: pede esclarecimento (provável engano)
CICLO_MIN, CICLO_MAX = 30, 800      # faixa plausível do ciclo informado (dias), a mesma do staging da FAO
RISCOS_ZARC = (20, 30, 40)
RISCO_ZARC_PADRAO = 30
MIN_ANOS_CHUVA = 10                 # anos mínimos para comparar a chuva com o histórico (a mesma ideia de `risco_solo.MIN_ANOS_CHUVA`)
COBERTURA_MIN = 0.9                 # fração mínima de dias com dado (config.yaml: cobertura_minima_dados)
MIN_ANOS_VERDE = 8                  # anos mínimos para o 'normal' do verde numa época (config.yaml: confianca.anos_media)
CONFIAB_VERDE = (0, 1)              # confiabilidade do pixel aceita (config.yaml: ndvi.confiabilidade_aceita)
LIM_VERDE_PARECIDO, LIM_VERDE_BEM = 0.02, 0.06     # só REDAÇÃO ('parecido', 'um pouco', 'bem'), os mesmos de fatos.py
QUADRA = ((2, 1), (5, 31))          # 'quadra chuvosa' do Ceará (fev-mai), a mesma do painel da quadra do app

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
FASES = ("ini", "dev", "mid", "late")
ROTULO_FASE = {"ini": "fase inicial (a planta nasce e cobre pouco a terra)",
               "dev": "fase de crescimento (a planta vai cobrindo a terra)",
               "mid": "fase do meio do ciclo (a terra já está bem coberta, até a planta começar a amadurecer)",
               "late": "fase final (a planta amadurece, até a colheita)"}
FONTE_FAO = "FAO-56 (Allen et al., 1998), cap. 6, Tabela 11, via data/culturas/fao_staging.csv"
FONTE_ECOCROP = "EcoCrop (FAO), faixa de ciclo em data/culturas/tabela_culturas.csv"
_NAO_DADO = object()
_NAO_PEDIDO = {"disponivel": False, "nao_pedido": True, "motivo": "não consultado nesta resposta"}


# ------------------------------------------------------------------------------------------------ datas e 'quando'
def _iso(d: date) -> str:
    return d.isoformat()


def _data(s) -> date:
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def ultimo_dia_do_mes(ano: int, mes: int) -> int:
    return calendar.monthrange(ano, mes)[1]


def _somar_meses(d: date, n: int) -> date:
    m = d.month - 1 + n
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, ultimo_dia_do_mes(ano, mes)))


def decendio_de(d: date) -> int:
    """Decêndio 0 a 35 do ano (3 por mês: dias 1-10, 11-20, 21-fim), como as colunas dec1..dec36 do ZARC."""
    return (d.month - 1) * 3 + min((d.day - 1) // 10, 2)


def quinzena_de(d: date) -> int:
    """Quinzena 1 a 24 (definição do projeto: dias 1-15 e 16-fim), a mesma de `balanco_hidrico.quinzena_id`."""
    return (d.month - 1) * 2 + 1 + (1 if d.day > 15 else 0)


def inicio_da_quinzena(q: int, ano: int) -> date:
    return date(ano, (q - 1) // 2 + 1, 1 if q % 2 == 1 else 16)


def _dias(ini: date, fim: date):
    d = ini
    while d <= fim:
        yield d
        d += timedelta(days=1)


def decendios_no_periodo(ini: date, fim: date) -> list[int]:
    return sorted({decendio_de(d) for d in _dias(ini, min(fim, ini + timedelta(days=62)))})


def nome_do_decendio(i: int) -> str:
    return f"{i % 3 + 1}º decêndio de {MESES[i // 3]}"


def faixas_decendios(perm) -> str:
    """Decêndios permitidos (36) em faixas legíveis: 'do 2º decêndio de março ao 1º decêndio de maio'. Só formata."""
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
    return "; ".join(nome_do_decendio(a) if a == b else f"do {nome_do_decendio(a)} ao {nome_do_decendio(b)}" for a, b in runs)


def _erro_quando(q) -> str | None:
    """None se `q` é um 'quando' válido; senão a mensagem em português simples."""
    if isinstance(q, str):
        q = {"data": q}
    if not isinstance(q, dict):
        return "'quando' deve ser uma data, um mês ou uma faixa de datas"
    chaves = set(q)
    if "data" in q:
        if chaves != {"data"}:
            return "'quando' com 'data' não aceita outros campos"
        try:
            d = _data(q["data"])
        except (ValueError, TypeError):
            return "data de plantio ilegível (use AAAA-MM-DD)"
        return None if 2000 <= d.year <= 2100 else "ano do plantio fora de 2000 a 2100"
    if "mes" in q:
        extra = chaves - {"mes", "ano", "parte"}
        if extra:
            return "campo desconhecido em 'quando': " + ", ".join(sorted(map(str, extra)))
        m, a, p = q.get("mes"), q.get("ano"), q.get("parte")
        if not (isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 12):
            return "o mês do plantio deve ser um número de 1 a 12"
        if a is not None and not (isinstance(a, int) and not isinstance(a, bool) and 2000 <= a <= 2100):
            return "o ano do plantio deve estar entre 2000 e 2100"
        if p is not None and p not in PARTES:
            return "a parte do mês deve ser começo, meio ou fim"
        return None
    if "de" in q:
        extra = chaves - {"de", "ate", "precisao"}
        if extra:
            return "campo desconhecido em 'quando': " + ", ".join(sorted(map(str, extra)))
        try:
            a, b = _data(q["de"]), _data(q.get("ate"))
        except (ValueError, TypeError):
            return "faixa de datas ilegível (use AAAA-MM-DD)"
        if b < a or (b - a).days > 130:
            return "a faixa de datas do plantio é inválida ou longa demais"
        if not (2000 <= a.year <= 2100 and 2000 <= b.year <= 2100):
            return "ano do plantio fora de 2000 a 2100"
        if q.get("precisao", "faixa") not in PRECISOES_FAIXA:
            return "precisão da faixa desconhecida"
        return None
    return "'quando' deve ter 'data', 'mes' ou 'de'/'ate'"


def resolver_quando(q, hoje: date) -> dict:
    """{'ini','fim','ref' (datas), 'precisao' ('dia'|'decendio'|'mes'|faixa), 'ano_inferido', 'texto'}. Levanta ValueError se inválido.
    Mês sem ano = o mais recente que já começou; mês sem ano é cortado em `hoje` (plantei = já aconteceu)."""
    erro = _erro_quando(q)
    if erro:
        raise ValueError(erro)
    if isinstance(q, str):
        q = {"data": q}
    if "data" in q:
        d = _data(q["data"])
        return {"ini": d, "fim": d, "ref": d, "precisao": "dia", "ano_inferido": False, "texto": d.strftime("%d/%m/%Y")}
    if "de" in q:
        a, b = _data(q["de"]), _data(q["ate"])
        return {"ini": a, "fim": b, "ref": a + timedelta(days=(b - a).days // 2), "precisao": q.get("precisao", "faixa"), "ano_inferido": False,
                "texto": f"entre {a.strftime('%d/%m/%Y')} e {b.strftime('%d/%m/%Y')}"}
    m, a, p = q["mes"], q.get("ano"), q.get("parte")
    inferido = a is None
    if inferido:
        a = hoje.year if date(hoje.year, m, 1) <= hoje else hoje.year - 1
    ult = ultimo_dia_do_mes(a, m)
    d1, d2 = {None: (1, ult), "comeco": (1, 10), "meio": (11, 20), "fim": (21, ult)}[p]
    ini, fim = date(a, m, d1), date(a, m, d2)
    if inferido and fim > hoje >= ini:
        fim = hoje
    if inferido and ini > hoje:                    # 'fim de novembro' dito no dia 14: ainda não chegou; vale o mesmo mês do ano anterior
        a -= 1
        ult = ultimo_dia_do_mes(a, m)
        ini, fim = date(a, m, d1), date(a, m, {None: ult, "comeco": 10, "meio": 20, "fim": ult}[p])
    ref = ini + timedelta(days=(fim - ini).days // 2)
    pt = {None: "", "comeco": "começo de ", "meio": "meio de ", "fim": "fim de "}[p]
    return {"ini": ini, "fim": fim, "ref": ref, "precisao": "decendio" if p else "mes", "ano_inferido": inferido, "texto": f"{pt}{MESES[m - 1]} de {a}"}


def validar_plantios(lista, culturas, max_n: int = MAX_PLANTIOS) -> list[dict]:
    """Lista de plantios validada e normalizada (schema estrito). Levanta ValueError com TODAS as mensagens (separadas por '; ').
    Chaves aceitas: cultura, quando, ciclo_dias, manejo. Nada de identificador: não há campo para nome, local nem texto livre."""
    if lista is None:
        return []
    if not isinstance(lista, list):
        raise ValueError("'plantios' deve ser uma lista")
    erros, out = [], []
    if len(lista) > max_n:
        raise ValueError(f"no máximo {max_n} plantios")
    cult = set(culturas)
    for i, p in enumerate(lista, 1):
        rot = f"plantio {i}"
        if not isinstance(p, dict):
            erros.append(f"{rot}: deve ser um objeto")
            continue
        extra = set(p) - {"cultura", "quando", "ciclo_dias", "manejo"}
        if extra:
            erros.append(f"{rot}: campo(s) desconhecido(s): {', '.join(sorted(map(str, extra)))}")
        c = p.get("cultura")
        if not isinstance(c, str) or c not in cult:
            erros.append(f"{rot}: cultura fora da lista")
        q = p.get("quando")
        if isinstance(q, str):
            q = {"data": q}
        e = _erro_quando(q)
        if e:
            erros.append(f"{rot}: {e}")
        cd = p.get("ciclo_dias")
        if cd is not None and not (isinstance(cd, int) and not isinstance(cd, bool) and CICLO_MIN <= cd <= CICLO_MAX):
            erros.append(f"{rot}: 'ciclo_dias' deve ser um número inteiro de {CICLO_MIN} a {CICLO_MAX}")
        mj = p.get("manejo", "sequeiro")
        if mj is None:
            mj = "sequeiro"
        if mj not in MANEJOS:
            erros.append(f"{rot}: manejo deve ser sequeiro ou irrigado")
        if not e and isinstance(c, str) and c in cult:
            out.append({"cultura": c, "quando": json.loads(json.dumps(q)), "ciclo_dias": cd, "manejo": mj})
    if erros:
        raise ValueError("; ".join(erros))
    return out


# ------------------------------------------------------------------------------------------------ dados (injetáveis)
@functools.lru_cache(maxsize=1)
def _config() -> dict:
    try:
        import yaml
        return yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - sem config.yaml valem os padrões declarados acima
        return {}


def limiar_veranico_mm() -> float:
    v = (_config().get("veranico") or {}).get("limiar_chuva_mm")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 1.0


@functools.lru_cache(maxsize=8)
def _clima_do_ponto(ponto_id: str) -> pd.DataFrame | None:
    """Chuva diária do ponto, do arquivo 'atual' (2001 até o último dia coletado); sem ele, o histórico até 2024."""
    for nome in ("clima_diario_atual.parquet", "clima_diario.parquet"):
        p = RAIZ / "data/processed" / nome
        if p.exists():
            d = pd.read_parquet(p, columns=["ponto_id", "data", "chuva_mm"], filters=[("ponto_id", "==", ponto_id)])
            if len(d):
                return d
    return None


@functools.lru_cache(maxsize=8)
def _ndvi_do_ponto(ponto_id: str) -> pd.DataFrame | None:
    for nome in ("ndvi_16d_atual.parquet", "ndvi_16d.parquet"):
        p = RAIZ / "data/processed" / nome
        if p.exists():
            d = pd.read_parquet(p, columns=["ponto_id", "data", "ndvi", "confiabilidade"], filters=[("ponto_id", "==", ponto_id)])
            if len(d):
                return d
    return None


@functools.lru_cache(maxsize=1)
def _diagnosticos() -> dict:
    p = RAIZ / "data/processed/diagnostico/diagnostico.json"
    if not p.is_file():
        return {}
    return {str(r["ponto_id"]): r for r in json.loads(p.read_text(encoding="utf-8")) if isinstance(r, dict)}


@functools.lru_cache(maxsize=1)
def _tabela_padrao() -> dict:
    from . import tabela_culturas
    return tabela_culturas.carregar()


def pontos_validos() -> set[str]:
    p = RAIZ / "data/processed/pontos.csv"
    return set(pd.read_csv(p)["ponto_id"]) if p.exists() else set()


class Contexto:
    """Dados do ponto, carregados só quando preciso. Todo argumento injetado (inclusive `None` = 'sem esse dado') vale no lugar do arquivo."""

    def __init__(self, ponto_id: str, clima=_NAO_DADO, ndvi=_NAO_DADO, diagnostico=_NAO_DADO, geocodigo=_NAO_DADO, tabela=None, fao=_NAO_DADO,
                 zarc_fn=None, proximas_fn=None, solo: str = "qualquer", proibidas=()):
        self.ponto_id = ponto_id
        self._clima, self._ndvi, self._diag, self._geo, self._fao = clima, ndvi, diagnostico, geocodigo, fao
        self._tabela = tabela
        self.zarc_fn, self.proximas_fn, self.solo, self.proibidas = zarc_fn, proximas_fn, solo, tuple(proibidas or ())

    @property
    def tabela(self) -> dict:
        if self._tabela is None:
            self._tabela = _tabela_padrao()
        return self._tabela

    @property
    def clima(self):
        return _clima_do_ponto(self.ponto_id) if self._clima is _NAO_DADO else self._clima

    @property
    def ndvi(self):
        return _ndvi_do_ponto(self.ponto_id) if self._ndvi is _NAO_DADO else self._ndvi

    @property
    def diagnostico(self):
        return _diagnosticos().get(self.ponto_id) if self._diag is _NAO_DADO else self._diag

    @property
    def geocodigo(self):
        if self._geo is _NAO_DADO:
            from . import zarc
            return zarc.geocodigo_do_ponto(self.ponto_id)
        return self._geo

    @property
    def fao(self) -> dict:
        if self._fao is _NAO_DADO:
            try:
                from . import ciclo_fao
                self._fao = ciclo_fao.ciclos_fao()
            except Exception:  # noqa: BLE001 - staging inválido ou ausente: o ciclo cai no EcoCrop, com a lacuna dita
                self._fao = {}
        return self._fao or {}

    def janela_zarc(self, cid: str, risco: int) -> dict:
        if self.zarc_fn is not None:
            return self.zarc_fn(self.geocodigo, cid, risco, self.solo)
        from . import zarc
        return zarc.janela(self.geocodigo, cid, risco, self.solo)


# ------------------------------------------------------------------------------------------------ ciclo e fase
def ciclo_de(cid: str, ctx: Contexto, ciclo_dias: int | None = None) -> dict:
    """Ciclo usado: o do agricultor > FAO-56 > EcoCrop. `disponivel` False = lacuna. Sempre diz a fonte."""
    if ciclo_dias:
        return {"disponivel": True, "fonte": "informado", "dias_ref": int(ciclo_dias), "dias_min": int(ciclo_dias), "dias_max": int(ciclo_dias),
                "estagios": None, "origem": "ciclo informado pelo agricultor", "regiao": None}
    f = ctx.fao.get(cid)
    if f:
        return {"disponivel": True, "fonte": "fao", "dias_ref": int(f["dias"]), "dias_min": int(f["dias_min"]), "dias_max": int(f["dias_max"]),
                "estagios": [int(x) for x in f["estagios"]], "origem": FONTE_FAO, "regiao": f.get("regiao"), "n_linhas": f.get("n_linhas"),
                "url": f.get("url")}
    atr = (ctx.tabela.get(cid) or {}).get("atributos", {})
    a, b = atr.get("ciclo_min_dias"), atr.get("ciclo_max_dias")
    if a and b and 0 < float(a["valor"]) <= float(b["valor"]):
        lo, hi = int(round(float(a["valor"]))), int(round(float(b["valor"])))
        return {"disponivel": True, "fonte": "ecocrop", "dias_ref": int(round((lo + hi) / 2)), "dias_min": lo, "dias_max": hi, "estagios": None,
                "origem": FONTE_ECOCROP, "regiao": None, "url": a.get("url")}
    return {"disponivel": False, "fonte": None, "motivo": "sem ciclo da FAO nem do EcoCrop para esta cultura (lacuna)"}


def _fase_fao(estagios: list[int], d: int) -> str:
    acum = np.cumsum(estagios)
    for nome, c in zip(FASES, acum):
        if d < c:
            return nome
    return "depois"


def calcular_fase(ciclo: dict, dmin: int, dmax: int) -> dict:
    """Fase em que a lavoura deve estar hoje (por referência), dados os dias desde o plantio (faixa quando só se sabe o mês)."""
    if not ciclo.get("disponivel"):
        return {"disponivel": False, "motivo": ciclo.get("motivo", "sem ciclo")}
    ref = int(round((dmin + dmax) / 2))
    out = {"disponivel": True, "dias_min": dmin, "dias_max": dmax, "dias_ref": ref}
    if ciclo["fonte"] == "fao":
        a, b = _fase_fao(ciclo["estagios"], max(dmin, 0)), _fase_fao(ciclo["estagios"], max(dmax, 0))
        todas = [] if a == "depois" else list(FASES[FASES.index(a):FASES.index(b if b != "depois" else "late") + 1])
        out.update({"tipo": "fao", "fase_min": a, "fase_max": b, "fases": todas, "depois_do_ciclo": a == "depois",
                    "parte_depois": b == "depois" and a != "depois", "estagios": ciclo["estagios"]})
        return out
    tot = ciclo["dias_ref"]
    fr_min, fr_max = max(dmin, 0) / tot, max(dmax, 0) / tot
    out.update({"tipo": "fracao", "fracao_min": min(fr_min, 1.0), "fracao_max": min(fr_max, 1.0), "depois_do_ciclo": fr_min >= 1.0,
                "parte_depois": fr_max >= 1.0 > fr_min, "ciclo_total": tot})
    return out


def janela_colheita(ciclo: dict, ini: date, fim: date) -> dict:
    if not ciclo.get("disponivel"):
        return {"disponivel": False, "motivo": ciclo.get("motivo", "sem ciclo")}
    de, ate = ini + timedelta(days=ciclo["dias_min"]), fim + timedelta(days=ciclo["dias_max"])
    return {"disponivel": True, "de": _iso(de), "ate": _iso(ate), "dias_min": ciclo["dias_min"], "dias_max": ciclo["dias_max"], "fonte": ciclo["fonte"],
            "origem": ciclo["origem"], "unica": ciclo["dias_min"] == ciclo["dias_max"] and ini == fim}


# ------------------------------------------------------------------------------------------------ ZARC
def datas_dos_decendios(perm, ano: int) -> list[list[str]]:
    """Faixas de DATAS (ISO) dos decêndios permitidos no `ano`: [[ini, fim], ...] (decêndios seguidos juntos). Para o gráfico."""
    idx = [i for i, ok in enumerate(perm) if ok]
    out: list[list[str]] = []
    for i in idx:
        m = i // 3 + 1
        a = date(ano, m, 1 + 10 * (i % 3))
        b = date(ano, m, ultimo_dia_do_mes(ano, m) if i % 3 == 2 else 10 * (i % 3 + 1))
        if out and (a - date.fromisoformat(out[-1][1])).days == 1:
            out[-1][1] = _iso(b)
        else:
            out.append([_iso(a), _iso(b)])
    return out


def checar_zarc(ctx: Contexto, cid: str, ini: date, fim: date, manejo: str) -> dict:
    """Decêndios do plantio contra a janela de semeadura do ZARC (sequeiro), nos riscos 20, 30 e 40. Sem zoneamento = lacuna dita."""
    if manejo == "irrigado":
        return {"disponivel": False, "situacao": "nao_se_aplica", "motivo": "o zoneamento (ZARC) usado aqui é só de sequeiro; plantio irrigado não é conferido"}
    janelas = {}
    for r in RISCOS_ZARC:
        try:
            j = ctx.janela_zarc(cid, r)
        except Exception as e:  # noqa: BLE001
            return {"disponivel": False, "situacao": "sem_zoneamento", "motivo": f"zoneamento não pôde ser lido ({type(e).__name__})"}
        if j.get("permitido") is None:
            return {"disponivel": False, "situacao": "sem_zoneamento", "motivo": j.get("motivo") or "sem zoneamento para esta cultura neste município"}
        janelas[r] = j
    decs = decendios_no_periodo(ini, fim)
    por_dec = {}
    for dc in decs:
        niv = [r for r in RISCOS_ZARC if bool(janelas[r]["permitido"][dc])]
        por_dec[dc] = min(niv) if niv else None
    dentro = [dc for dc in decs if por_dec[dc] is not None]
    situacao = "dentro" if len(dentro) == len(decs) else "fora" if not dentro else "parcial"
    risco = max(por_dec[dc] for dc in dentro) if dentro else None
    j0 = janelas[RISCO_ZARC_PADRAO]
    return {"disponivel": True, "situacao": situacao, "decendios": [nome_do_decendio(d) for d in decs], "risco_ate": risco,
            "por_decendio": {nome_do_decendio(d): por_dec[d] for d in decs}, "solo": j0.get("solo", ctx.solo), "recurso": j0.get("recurso"),
            "aviso_solo": j0.get("aviso"), "janela_30": faixas_decendios(j0["permitido"]), "janela_20": faixas_decendios(janelas[20]["permitido"]),
            "janela_40": faixas_decendios(janelas[40]["permitido"]), "datas_30": datas_dos_decendios(j0["permitido"], ini.year),
            "origem": "src.culturas.zarc.janela (data/processed/zarc_ce.parquet; ZARC do MAPA, sequeiro)"}


# ------------------------------------------------------------------------------------------------ chuva, veranico
def _serie_chuva(df) -> pd.Series | None:
    if df is None or len(df) == 0 or "chuva_mm" not in df or "data" not in df:
        return None
    d = df[["data", "chuva_mm"]].dropna(subset=["data"]).drop_duplicates("data")
    s = pd.Series(d["chuva_mm"].to_numpy(float), index=pd.DatetimeIndex(pd.to_datetime(d["data"]))).sort_index()
    return s


def _deslocar_ano(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:                                # 29/fev em ano não bissexto
        return d.replace(year=d.year + n, day=28)


def chuva_desde_plantio(serie: pd.Series | None, ini: date, fim: date) -> dict:
    """Chuva acumulada (mm) de `ini` até `fim` (cortado no último dia com dado) e a posição entre os mesmos períodos dos ANOS ANTERIORES."""
    if serie is None or len(serie) == 0:
        return {"disponivel": False, "motivo": "sem série diária de chuva para este local"}
    ultimo = serie.index.max().date()
    fim_ef = min(fim, ultimo)
    if fim_ef < ini:
        return {"disponivel": False, "motivo": f"o dado de chuva só vai até {ultimo.strftime('%d/%m/%Y')}, antes do plantio"}
    n_dias = (fim_ef - ini).days + 1
    obs = serie.loc[pd.Timestamp(ini):pd.Timestamp(fim_ef)]
    n_ok = int(obs.notna().sum())
    if n_ok < COBERTURA_MIN * n_dias:
        return {"disponivel": False, "motivo": f"faltam dias de chuva no período ({n_ok} de {n_dias})"}
    total = float(obs.sum())
    primeiro = serie.index.min().date()
    hist = []
    for y in range(primeiro.year, ini.year):
        d = y - ini.year
        a, b = _deslocar_ano(ini, d), _deslocar_ano(fim_ef, d)
        if a < primeiro or b > ultimo:
            continue
        h = serie.loc[pd.Timestamp(a):pd.Timestamp(b)]
        if int(h.notna().sum()) >= COBERTURA_MIN * n_dias:
            hist.append(float(h.sum()))
    out = {"disponivel": True, "ini": _iso(ini), "fim": _iso(fim_ef), "dias": n_dias, "mm": round(total, 1), "dados_ate": _iso(ultimo),
           "cortado_no_dado": fim_ef < fim, "n_anos": len(hist)}
    if len(hist) < MIN_ANOS_CHUVA:
        out.update({"historico": False, "motivo_historico": f"só {len(hist)} anos anteriores com o período completo (mínimo {MIN_ANOS_CHUVA})"})
        return out
    h = np.array(hist)
    k = int((h < total).sum())
    fr = k / len(h)
    out.update({"historico": True, "mediana_mm": round(float(np.median(h)), 1), "min_mm": round(float(h.min()), 1), "max_mm": round(float(h.max()), 1),
                "anos_com_menos": k, "posicao": "abaixo" if fr <= 1 / 3 else "acima" if fr >= 2 / 3 else "perto",
                "origem": "clima observado (NASA POWER, célula de ~50 km) em data/processed/clima_diario_atual.parquet"})
    return out


def _quinzenas_chuvosas(diag: dict | None) -> set[int] | None:
    v = (diag or {}).get("veranicos") or {}
    q = v.get("quinzenas_estacao_chuvosa")
    return {int(x) for x in q} if q else None


def veranico_desde_plantio(serie: pd.Series | None, ini: date, fim: date, diag: dict | None) -> dict:
    """Maior sequência de dias secos (chuva < limiar do projeto) em dias da ÉPOCA DE CHUVA do local, desde o plantio, contra o que é comum."""
    lim = limiar_veranico_mm()
    if serie is None or len(serie) == 0:
        return {"disponivel": False, "motivo": "sem série diária de chuva para este local"}
    fim_ef = min(fim, serie.index.max().date())
    if fim_ef < ini:
        return {"disponivel": False, "motivo": "o dado de chuva termina antes do plantio"}
    chuvosas = _quinzenas_chuvosas(diag)
    ver = (diag or {}).get("veranicos") or {}
    dist = ver.get("distribuicao") or {}
    maior, atual, fim_maior = 0, 0, None
    dias_na_epoca = 0
    for ts, v in serie.loc[pd.Timestamp(ini):pd.Timestamp(fim_ef)].items():
        d = ts.date()
        na_epoca = chuvosas is None or quinzena_de(d) in chuvosas
        if na_epoca:
            dias_na_epoca += 1
        if na_epoca and pd.notna(v) and v < lim:
            atual += 1
            if atual > maior:
                maior, fim_maior = atual, d
        else:
            atual = 0
    if chuvosas is not None and dias_na_epoca == 0:
        return {"disponivel": False, "fora_da_epoca": True, "motivo": "nenhum dia do período cai na época de chuva do local"}
    out = {"disponivel": True, "limiar_mm": lim, "maior_dias": maior, "termina_em": _iso(fim_maior) if fim_maior else None, "dias_na_epoca": dias_na_epoca,
           "so_epoca_de_chuva": chuvosas is not None, "ini": _iso(ini), "fim": _iso(fim_ef)}
    if dist.get("mediana") is not None and dist.get("p90") is not None:
        out.update({"mediana_local": float(dist["mediana"]), "p90_local": float(dist["p90"]), "max_local": float(dist.get("max", dist["p90"])),
                    "n_estacoes": ver.get("n_estacoes"), "passou_do_comum": maior > dist["mediana"], "passou_de_1_em_10": maior > dist["p90"],
                    "origem": "data/processed/diagnostico/diagnostico.json: veranicos"})
    else:
        out["motivo_comparacao"] = "sem o que é comum no local (diagnóstico de veranicos ausente)"
    return out


# ------------------------------------------------------------------------------------------------ verde da região
def _slot_verde(d: pd.Timestamp) -> int:
    return (d.day_of_year - 1) // 16


def verde_desde_plantio(ndvi, ini: date, fim: date) -> dict:
    """Anomalia do verde da REGIÃO (composto de 16 dias do satélite menos a média do mesmo composto nos anos anteriores). Não é a lavoura."""
    if ndvi is None or len(ndvi) == 0:
        return {"disponivel": False, "motivo": "sem dado de satélite para este local"}
    d = ndvi.copy()
    d["data"] = pd.to_datetime(d["data"])
    if "confiabilidade" in d:
        d = d[d["confiabilidade"].isin(CONFIAB_VERDE)]
    d = d.dropna(subset=["ndvi"]).sort_values("data")
    if d.empty:
        return {"disponivel": False, "motivo": "sem composto de satélite confiável para este local"}
    d["slot"] = d["data"].map(_slot_verde)
    d["ano"] = d["data"].dt.year
    ultimo_dado = d["data"].max()
    janela = d[(d["data"] >= pd.Timestamp(ini)) & (d["data"] <= pd.Timestamp(fim))]
    if janela.empty:
        return {"disponivel": False, "motivo": f"sem composto de satélite entre o plantio e {min(fim, ultimo_dado.date()).strftime('%d/%m/%Y')} (o último é de {ultimo_dado.strftime('%d/%m/%Y')})"}
    ano_ini = ini.year
    base = d[d["ano"] < ano_ini]
    linhas = []
    for _, r in janela.iterrows():
        ref = base[base["slot"] == r["slot"]]
        if ref["ano"].nunique() < MIN_ANOS_VERDE:
            continue
        linhas.append({"data": r["data"], "anomalia": float(r["ndvi"] - ref["ndvi"].mean()), "n_anos": int(ref["ano"].nunique())})
    if not linhas:
        return {"disponivel": False, "motivo": f"menos de {MIN_ANOS_VERDE} anos anteriores para saber o normal desta época"}
    an = [x["anomalia"] for x in linhas]
    ult = linhas[-1]
    dif = an[-1] - an[0] if len(an) >= 2 else 0.0
    return {"disponivel": True, "n_compostos": len(linhas), "ultimo_composto": _iso(ult["data"].date()), "anomalia_ultimo": round(an[-1], 3),
            "anomalia_media": round(float(np.mean(an)), 3), "n_anos": min(x["n_anos"] for x in linhas), "ultimo_dado_do_satelite": _iso(ultimo_dado.date()),
            "evolucao": "melhorando" if dif > LIM_VERDE_PARECIDO else "piorando" if dif < -LIM_VERDE_PARECIDO else "estavel",
            "origem": "data/processed/ndvi_16d_atual.parquet (satélite MODIS, pixel de ~250 m; é a região, não a sua lavoura)"}


def nivel_verde(a: float) -> str:
    if abs(a) < LIM_VERDE_PARECIDO:
        return "parecido com o normal"
    return f"{'um pouco' if abs(a) < LIM_VERDE_BEM else 'bem'} {'mais forte' if a > 0 else 'mais fraco'} do que o normal"


# ------------------------------------------------------------------------------------------------ solo nu
def solo_nu_depois(diag: dict | None, colheita: dict) -> dict:
    """Quinzenas em que o solo do local costuma ficar nu (diagnóstico, 20% menos verdes do próprio local) e a distância da colheita esperada."""
    nu = (diag or {}).get("solo_nu")
    if not nu:
        return {"disponivel": False, "motivo": "o diagnóstico do local não traz a época de solo nu"}
    q = [int(x) for x in nu.get("quinzenas_tipicas") or []]
    out = {"disponivel": True, "quinzenas": q, "meses": sorted({(x - 1) // 2 + 1 for x in q}), "limiar_ndvi": nu.get("limiar_ndvi"),
           "origem": "data/processed/diagnostico/diagnostico.json: solo_nu (relativo ao próprio local)"}
    if not q:
        out["nenhuma_epoca"] = True
        return out
    if colheita.get("disponivel"):
        c0 = _data(colheita["de"])
        cand = []
        for ano in (c0.year, c0.year + 1):
            for x in q:
                cand.append(inicio_da_quinzena(x, ano))
        # a quinzena em curso também conta (quem colhe dentro da época de solo nu já está nela)
        dentro = quinzena_de(c0) in q
        fut = sorted(d for d in cand if d >= c0)
        out["colheita_dentro_da_epoca"] = dentro
        out["dias_ate_comecar"] = 0 if dentro else (fut[0] - c0).days if fut else None
        out["comeca_em"] = _iso(c0 if dentro else fut[0]) if (dentro or fut) else None
    return out


# ------------------------------------------------------------------------------------------------ próximas culturas
def proximas_padrao(cid: str, ctx: Contexto) -> dict:
    """Depois desta cultura, o que a MATRIZ DE ROTAÇÃO (acervo local) mostra, filtrado por regras duras (não quero) e pela viabilidade no local.
    Sem ranking: as favoráveis ficam empatadas (declarado)."""
    from . import matriz_rotacao as MR
    tab = ctx.tabela
    graus: dict[str, dict] = {}
    for b in tab:
        if b == cid:
            continue
        try:
            c = MR.consulta(cid, b)
        except KeyError:
            continue
        graus[b] = {"grau": c["grau"], "divergente": bool(c["divergente"]), "tipo": c.get("tipo_evidencia_mais_forte")}
    viaveis, lac = None, []
    try:
        from . import avaliar_sequencia as AS
        av = AS.avaliacao_local(ctx.ponto_id, tabela=ctx.tabela) if ctx._tabela is not None else AS.avaliacao_local(ctx.ponto_id)
        viaveis = {c for c, v in av["culturas"].items() if v["estado"] == "viavel"}
    except Exception as e:  # noqa: BLE001
        lac.append(f"a viabilidade no local não foi calculada agora ({type(e).__name__}); a lista abaixo não foi filtrada por ela")
    return organizar_proximas(cid, graus, viaveis, ctx.proibidas, lac)


def organizar_proximas(cid: str, graus: dict[str, dict], viaveis: set[str] | None, proibidas=(), lacunas: list[str] | None = None) -> dict:
    prib = set(proibidas or ())
    fav, neu, des, sem = [], [], [], []
    inviaveis = []
    for b, g in graus.items():
        if b in prib:
            continue
        if viaveis is not None and b not in viaveis:
            inviaveis.append(b)
            continue
        (fav if g["grau"] == "favoravel" else neu if g["grau"] == "neutro" else des if g["grau"] == "desfavoravel" else sem).append(b)
    return {"disponivel": True, "de": cid, "favoraveis": sorted(fav), "neutras": sorted(neu), "desfavoraveis": sorted(des), "sem_dado": sorted(sem),
            "inviaveis_no_local": sorted(inviaveis), "nao_quer": sorted(prib & set(graus)), "viabilidade_conferida": viaveis is not None, "empate_entre_favoraveis": len(fav) > 1,
            "lacunas": list(lacunas or []), "origem": "src.culturas.matriz_rotacao.consulta (data/culturas/matriz_rotacao.csv) + viabilidade do motor"}


# ------------------------------------------------------------------------------------------------ um plantio
def _esclarecimento(p: dict, nome: str | None, ctx: Contexto, hoje: date) -> tuple[dict | None, str | None]:
    """(quando resolvido, texto de esclarecimento). Esclarecimento = o chat pergunta; nada é calculado."""
    if p["cultura"] not in ctx.tabela:
        return None, f"a cultura '{p['cultura']}' não está na lista do Sulco"
    try:
        q = resolver_quando(p["quando"], hoje)
    except ValueError as e:
        return None, str(e)
    if (q["ini"] - hoje).days > FUTURO_MAX_DIAS:
        return q, "a data do plantio está muito longe no futuro"
    if (hoje - q["fim"]).days > PASSADO_MAX_DIAS:
        return q, "a data do plantio é de mais de 2 anos atrás"
    return q, None


def calcular_plantio(p: dict, ctx: Contexto, hoje: date, serie=_NAO_DADO, blocos: set | None = None) -> dict:
    cid = p["cultura"]
    quer = (lambda b: True) if blocos is None else (lambda b: b in blocos)
    nome = (ctx.tabela.get(cid) or {}).get("cultura_pt", cid)
    q, esclarece = _esclarecimento(p, nome, ctx, hoje)
    base = {"cultura": cid, "cultura_nome": nome, "manejo": p.get("manejo") or "sequeiro", "ciclo_informado": p.get("ciclo_dias"),
            "spec": json.loads(json.dumps(p["quando"] if isinstance(p["quando"], dict) else {"data": p["quando"]}))}
    if esclarece:
        return {**base, "status": "esclarecimento", "esclarecimento": esclarece, "quando": None if q is None else _quando_json(q), "lacunas": []}
    ciclo = ciclo_de(cid, ctx, p.get("ciclo_dias"))
    ini, fim, ref = q["ini"], q["fim"], q["ref"]
    out = {**base, "status": None, "esclarecimento": None, "quando": _quando_json(q), "ciclo": ciclo, "lacunas": []}
    colheita = janela_colheita(ciclo, ini, fim)
    out["colheita"] = colheita
    out["zarc"] = checar_zarc(ctx, cid, ini, fim, base["manejo"])
    if ini > hoje:                                   # data futura: PLANEJAMENTO (só o que não depende de ter acontecido)
        out.update({"status": "planejamento", "dias_para_plantar": (ini - hoje).days, "fase": {"disponivel": False, "motivo": "ainda não foi plantado"}})
        out["proximas"] = _proximas(cid, ctx) if quer("proximas") else _NAO_PEDIDO
        out["solo_nu"] = solo_nu_depois(ctx.diagnostico, colheita)
        out["lacunas"] = _lacunas(out)
        return out
    dmin, dmax = (hoje - min(fim, hoje)).days, (hoje - ini).days
    out["dias_desde"] = {"min": dmin, "ref": (hoje - ref).days, "max": dmax}
    out["fase"] = calcular_fase(ciclo, dmin, dmax)
    concluido = ciclo.get("disponivel") and dmin > ciclo["dias_max"]
    out["status"] = "ciclo_concluido" if concluido else "em_andamento"
    fim_per = hoje
    if ciclo.get("disponivel"):
        fim_per = min(hoje, ref + timedelta(days=ciclo["dias_ref"] - 1))
    s = _serie_chuva(ctx.clima) if serie is _NAO_DADO else serie
    out["periodo"] = {"ini": _iso(ref), "fim": _iso(fim_per), "ate_o_fim_do_ciclo": bool(ciclo.get("disponivel") and fim_per < hoje)}
    out["chuva"] = chuva_desde_plantio(s, ref, fim_per)
    out["veranico"] = veranico_desde_plantio(s, ref, fim_per, ctx.diagnostico)
    out["verde"] = verde_desde_plantio(ctx.ndvi, ref, fim_per)
    out["solo_nu"] = solo_nu_depois(ctx.diagnostico, colheita)
    out["proximas"] = _proximas(cid, ctx) if quer("proximas") else _NAO_PEDIDO
    out["lacunas"] = _lacunas(out)
    return out


def _proximas(cid: str, ctx: Contexto) -> dict:
    try:
        return ctx.proximas_fn(cid, ctx) if ctx.proximas_fn else proximas_padrao(cid, ctx)
    except Exception as e:  # noqa: BLE001
        return {"disponivel": False, "motivo": f"a rotação não pôde ser consultada ({type(e).__name__})"}


def _lacunas(r: dict) -> list[str]:
    rot = {"colheita": "colheita esperada", "fase": "fase da lavoura", "zarc": "zoneamento (ZARC)", "chuva": "chuva desde o plantio", "veranico": "período seco",
           "verde": "verde da região", "solo_nu": "época de solo nu", "proximas": "próxima cultura"}
    out = []
    for k, n in rot.items():
        b = r.get(k)
        if isinstance(b, dict) and not b.get("disponivel", True) and not b.get("nao_pedido") and not b.get("fora_da_epoca"):
            out.append(f"{n}: {b.get('motivo', 'sem dado')}")
    return out


def _quando_json(q: dict) -> dict:
    return {"ini": _iso(q["ini"]), "fim": _iso(q["fim"]), "ref": _iso(q["ref"]), "precisao": q["precisao"], "ano_inferido": q["ano_inferido"], "texto": q["texto"]}


# ------------------------------------------------------------------------------------------------ função pública
def calcular(ponto_id: str, plantios: list[dict], hoje: date | str | None = None, *, contexto: Contexto | None = None, blocos: set | None = None,
             **dados) -> dict:
    """Calendário de cada plantio. `hoje` injetável. `dados` (clima, ndvi, diagnostico, geocodigo, tabela, fao, zarc_fn, proximas_fn, solo, proibidas)
    substituem os arquivos (testes). `blocos` = conjunto de blocos pesados pedidos (hoje só 'proximas'; None = todos). Levanta ValueError se `plantios` não passa no schema; nunca devolve número sem origem."""
    hoje_d = _data(hoje) if hoje is not None else date.today()
    ctx = contexto or Contexto(ponto_id, **dados)
    tab_ids = list(ctx.tabela)
    lista = validar_plantios(plantios, tab_ids)
    serie = _serie_chuva(ctx.clima)
    resultado = [{**calcular_plantio(p, ctx, hoje_d, serie, blocos), "indice": i} for i, p in enumerate(lista)]
    return {"versao": VERSAO, "hoje": _iso(hoje_d), "plantios": resultado,
            "limites": ["O clima vem de uma célula de cerca de 50 km e o satélite de pixels de cerca de 250 m: nenhum enxerga a sua roça.",
                        "Ciclo e fases são de referência (FAO-56, outras regiões) ou da tabela do EcoCrop; a sua semente pode ser diferente.",
                        "O Sulco não prevê o tempo nem a colheita: mostra o que já aconteceu e o que os documentos dizem."]}
