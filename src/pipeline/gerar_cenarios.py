"""Pipeline: perfil do local (dados reais) -> motor de culturas -> evidências do RAG -> JSON do contrato.

Saída: data/processed/cenarios/<ponto_id>.json (lista de cenários; contrato em docs/01 seção 7), lida pelo app.

Regras anti-alucinação:
- todo número vem de arquivo (clima_diario.parquet, umidade_solo.parquet, tabela_culturas.csv) ou de código;
- sem dado => campo None + texto em `lacunas` (nunca estimativa);
- trecho do RAG só entra se a busca o devolver; busca vazia => `sem_evidencia` no critério;
- `faixa_incerteza` vem do Monte Carlo do motor (src/culturas/incerteza.py; o que representa está em `leitura`);
- a cultura atual é ENTRADA explícita (--cultura-atual ou --culturas-arquivo); nunca inferida;
- sem LLM.

Suposições deste módulo (declaradas em cada cenário em `suposicoes`):
- P1 o motor recebe a SÉRIE DIÁRIA do ponto (clima_diario.parquet) e avalia chuva acumulada e temperatura média DENTRO do
  ciclo, para cada início de plantio e cada ano (src/culturas/ciclo.py). `perfil` (médias 2001–2024) é só informativo.
- P2 temperatura diária = (Tmax+Tmin)/2 (aproximação da média diária; não é a média horária).
- P3 consultas ao RAG são modelos de frase fixos (ver CONSULTAS); um trecho só é mantido se citar a cultura.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src.culturas.ciclo import ClimaPonto
from src.culturas.motor import AVISO, gerar_cenarios, validar_cenario
from src.culturas.parametros import CHUVA_MODOS, CICLO_FONTES, CICLO_MODOS, EPOCA_MODOS, Parametros
from src.culturas.tabela_culturas import carregar
from src.rag import busca as rag
from src.rag.busca import radical, tokenizar

RAIZ = Path(__file__).resolve().parents[2]
PROC = RAIZ / "data/processed"
SAIDA = PROC / "cenarios"
ANO_INI, ANO_FIM = 2001, 2024
K_RAG = 2

CONSULTAS = {
    "temperatura": "{c} temperatura exigência clima",
    "chuva": "{c} precipitação chuva exigência hídrica",
    "n_na_biomassa": "{c} nitrogênio biomassa adubo verde",
    "palha": "{c} palhada cobertura do solo",
    "familia_diferente": "rotação de culturas {c} família",
}
# Termos que o trecho deve conter além do nome da cultura (filtro de precisão; P3)
TERMOS_CRITERIO = {
    "temperatura": ["temperatura", "clima", "termic"],
    "chuva": ["chuva", "precipitacao", "pluviometric", "hidric"],
    "n_na_biomassa": ["nitrogenio"],
    "palha": ["palha", "palhada", "cobertura"],
    "familia_diferente": ["rotacao", "familia", "sucessao"],
}
SUPOSICOES_PIPELINE = [
    "Chuva e temperatura do motor = valores DENTRO do ciclo (início de plantio x ano), do clima diário NASA POWER 2001–2024 (célula de ~50 km: pontos da mesma célula têm o mesmo clima).",
    "Temperatura diária = (Tmax+Tmin)/2.",
    "Cultura atual é informada pelo usuário; não é inferida por satélite nem por palpite.",
    "Trechos do acervo são recuperados por busca (BM25 + embeddings); só entram se citarem a cultura e um termo do critério. Podem não ser do semiárido.",
]


# ---------------------------------------------------------------- perfil
def perfil_local(ponto: dict, clima: pd.DataFrame, solo: pd.DataFrame | None) -> tuple[dict, list[str]]:
    """Perfil do ponto a partir dos parquets. Devolve (perfil, lacunas). Sem dado => None + lacuna."""
    pid, lac = ponto["ponto_id"], []
    perfil = {"local": pid, "temp_media_c": None, "chuva_anual_media_mm": None,
              "tmax_media_c": None, "tmin_media_c": None, "anos_chuva": None,
              "sm_superficie_media": None, "sm_raiz_media": None, "sm_periodo": None,
              "fontes": ["data/processed/clima_diario.parquet (NASA POWER)"]}
    d = clima[(clima["ponto_id"] == pid) & (clima["data"].dt.year.between(ANO_INI, ANO_FIM))]
    if d.empty:
        lac.append(f"clima: sem linhas de clima_diario.parquet para {pid}; perfil climático indisponível.")
    else:
        tem = d.dropna(subset=["tmax_c", "tmin_c"])
        if tem.empty:
            lac.append("temperatura: sem Tmax/Tmin válidos.")
        else:
            perfil["tmax_media_c"] = round(float(tem["tmax_c"].mean()), 2)
            perfil["tmin_media_c"] = round(float(tem["tmin_c"].mean()), 2)
            perfil["temp_media_c"] = round(float(((tem["tmax_c"] + tem["tmin_c"]) / 2).mean()), 2)
        ch = d.dropna(subset=["chuva_mm"])
        por_ano = ch.groupby(ch["data"].dt.year)["chuva_mm"].agg(["sum", "count"])
        compl = por_ano[por_ano["count"] >= 365]  # anos civis completos (365 ou 366 dias)
        if compl.empty:
            lac.append("chuva: nenhum ano civil completo; média anual indisponível.")
        else:
            perfil["chuva_anual_media_mm"] = round(float(compl["sum"].mean()), 1)
            perfil["anos_chuva"] = [int(compl.index.min()), int(compl.index.max()), int(len(compl))]
            if len(compl) < ANO_FIM - ANO_INI + 1:
                lac.append(f"chuva: só {len(compl)} de {ANO_FIM - ANO_INI + 1} anos completos entraram na média.")
    s = None if solo is None else solo[solo["ponto_id"] == pid]
    if s is None or s.empty or s[["sm_superficie", "sm_raiz"]].dropna(how="all").empty:
        lac.append("umidade do solo (SMAP): sem dado para este ponto; não entra no perfil.")
    else:
        perfil["sm_superficie_media"] = round(float(s["sm_superficie"].mean()), 4)
        perfil["sm_raiz_media"] = round(float(s["sm_raiz"].mean()), 4)
        perfil["sm_periodo"] = [str(s["data"].min().date()), str(s["data"].max().date())]
        perfil["fontes"].append("data/processed/umidade_solo.parquet (SMAP SPL4SMGP; m3/m3; só 2015+)")
    lac.append("umidade do solo: informativa; o motor de culturas não tem critério de solo (não influencia o score).")
    return perfil, lac


# ---------------------------------------------------------------- RAG
def _contem_cultura(texto: str, nome_pt: str) -> bool:
    ts = set(tokenizar(texto))
    return any(t in ts for t in tokenizar(nome_pt))


def evidencias(cultura_id: str, nome_pt: str, atual_pt: str | None = None, dir_indice: Path | None = None,
               busca=None) -> dict[str, dict]:
    """Por critério: {'sem_evidencia': bool, 'trechos': [...]} (só o que a busca devolveu e que cita a cultura)."""
    busca = busca or (lambda q, k: rag.buscar(q, k=k, **({"dir_indice": dir_indice} if dir_indice else {})))
    out = {}
    for crit, modelo in CONSULTAS.items():
        r = busca(modelo.format(c=nome_pt), K_RAG)
        termos = {radical(x) for x in TERMOS_CRITERIO[crit]}
        ts = [t for t in r.get("trechos", []) if _contem_cultura(t.get("texto", ""), nome_pt)
              and termos & set(tokenizar(t.get("texto", "")))]
        out[crit] = {"sem_evidencia": not ts, "trechos": ts}
    return out


def anexar_evidencias(cenario: dict, ev: dict[str, dict]) -> None:
    """Junta trechos (dedup por arquivo+página+texto), renumera `n` e liga cada critério a `trecho_n(s)`."""
    trechos, idx = [], {}
    for crit, e in ev.items():
        ns = []
        for t in e["trechos"]:
            chave = (t["arquivo"], t["pagina"], t["texto"])
            if chave not in idx:
                idx[chave] = len(trechos) + 1
                trechos.append({"n": idx[chave], "arquivo": t["arquivo"], "pagina": t["pagina"], "texto": t["texto"]})
            ns.append(idx[chave])
        c = cenario["criterios"].get(crit)
        if c is None:
            continue
        c["evidencia_rag"] = {"sem_evidencia": e["sem_evidencia"], "trechos_n": ns}
        if ns:
            c["trecho_n"] = ns[0]
        else:
            c["trecho_n"] = None
            c.setdefault("lacuna_evidencia", "sem evidência no acervo para este critério")
    cenario["trechos"] = trechos


# ---------------------------------------------------------------- pipeline
def montar_cenarios(ponto: dict, cultura_atual: str, clima, solo, tabela: dict, busca=None,
                    dir_indice: Path | None = None, params: Parametros | None = None) -> list[dict]:
    perfil, lac_perfil = perfil_local(ponto, clima, solo)
    p = params or Parametros(ano_ini=ANO_INI, ano_fim=ANO_FIM)
    serie = ClimaPonto.de_dataframe(clima, ponto["ponto_id"], p.ano_ini, p.ano_fim)
    cens = gerar_cenarios(perfil, cultura_atual, tabela, clima=serie, params=p)
    for c in cens:
        alvo = c["rotacao"][1]
        ev = evidencias(alvo, tabela[alvo]["cultura_pt"], tabela[cultura_atual]["cultura_pt"], dir_indice, busca)
        anexar_evidencias(c, ev)
        c["local"] = {"ponto_id": ponto["ponto_id"], "lat": ponto.get("lat"), "lon": ponto.get("lon"),
                      "celula_power": ponto.get("celula_power")}
        c["atual"] = alvo == cultura_atual
        c["perfil"] = {k: v for k, v in perfil.items() if k != "local"}
        c["lacunas"] = [l for l in c["lacunas"] if not l.startswith(("trechos:", "faixa_incerteza:"))]
        c["lacunas"] += lac_perfil
        sem = [k for k, d in c["criterios"].items() if d.get("evidencia_rag", {}).get("sem_evidencia")]
        if sem:
            c["lacunas"].append("sem evidência no acervo para: " + ", ".join(sem))
        if not c["trechos"]:
            c["lacunas"].append("trechos: nenhum trecho do acervo recuperado para este cenário.")
        c["suposicoes"] = list(c["suposicoes"]) + SUPOSICOES_PIPELINE
        c["aviso"] = AVISO
        c["pesos_nota"] = "pesos do motor são proposta de projeto, sem aprovação"
        e = validar_cenario(c)
        if e:
            raise ValueError(f"cenário inválido para {ponto['ponto_id']}: {e}")
    return cens


def escolher_pontos(pontos: pd.DataFrame, ids: list[str] | None, n: int) -> list[dict]:
    if ids:
        faltam = [i for i in ids if i not in set(pontos["ponto_id"])]
        if faltam:
            raise SystemExit(f"ponto_id não existe em pontos.csv: {faltam}")
        sel = pontos[pontos["ponto_id"].isin(ids)]
    else:  # n pontos do CE, espaçados de forma determinística pela lista (não escolhidos por resultado)
        ce = pontos[pontos["ponto_id"].str.endswith("_ce")].reset_index(drop=True)
        passo = max(len(ce) // n, 1)
        sel = ce.iloc[::passo].head(n)
    return sel.to_dict("records")


def rodar(pontos_ids: list[str] | None, n: int, cultura_atual: str | None, culturas_arquivo: Path | None,
          saida: Path = SAIDA, proc: Path = PROC, busca=None, params: Parametros | None = None) -> list[Path]:
    mapa = {}
    if culturas_arquivo:
        mapa = json.loads(Path(culturas_arquivo).read_text(encoding="utf-8"))
    elif not cultura_atual:
        raise SystemExit("Informe a cultura atual: --cultura-atual <id> ou --culturas-arquivo <json {ponto_id: cultura}>.")
    pontos = pd.read_csv(proc / "pontos.csv")
    clima = pd.read_parquet(proc / "clima_diario.parquet")
    sp = proc / "umidade_solo.parquet"
    solo = pd.read_parquet(sp) if sp.is_file() else None
    tab = carregar()
    saida.mkdir(parents=True, exist_ok=True)
    escritos = []
    for p in escolher_pontos(pontos, pontos_ids or (list(mapa) if mapa else None), n):
        cult = mapa.get(p["ponto_id"], cultura_atual) if mapa else cultura_atual
        if not cult:
            print(f"pulado {p['ponto_id']}: sem cultura atual informada", file=sys.stderr)
            continue
        if cult not in tab:
            raise SystemExit(f"cultura '{cult}' não está na tabela: {sorted(tab)}")
        cens = montar_cenarios(p, cult, clima, solo, tab, busca, params=params)
        arq = saida / f"{p['ponto_id']}.json"
        arq.write_text(json.dumps(cens, ensure_ascii=False, indent=2), encoding="utf-8")
        escritos.append(arq)
        print(f"{arq.name}: {len(cens)} cenários; rotações: {[c['rotacao'][1] for c in cens]}")
    return escritos


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pontos", nargs="*", help="ponto_id(s); padrão: --n pontos do CE espaçados")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--cultura-atual", help="id da cultura atual (aplicada a todos os pontos)")
    ap.add_argument("--culturas-arquivo", type=Path, help="JSON {ponto_id: cultura_id}")
    ap.add_argument("--saida", type=Path, default=SAIDA)
    ap.add_argument("--ciclo-modo", choices=CICLO_MODOS, default="medio", help="duração do ciclo (SUPOSIÇÃO): min, medio ou max")
    ap.add_argument("--chuva-modo", choices=CHUVA_MODOS, default=Parametros.chuva_modo,
                    help="chuva de 365 dias desde o início (anual, padrão) ou do ciclo (opção anterior) (SUPOSIÇÃO)")
    ap.add_argument("--ciclo-fonte", choices=CICLO_FONTES, default=Parametros.ciclo_fonte,
                    help="ciclo da Tabela 11 do FAO-56 (fao, padrão) ou do EcoCrop (ecocrop, opção anterior) (SUPOSIÇÃO)")
    ap.add_argument("--epoca-modo", choices=EPOCA_MODOS, default=Parametros.epoca_modo,
                    help="época de plantio: ZARC ou ciclo aproximado (zarc_ou_ciclo, padrão) ou modo anterior (anual_legado) (SUPOSIÇÃO)")
    ap.add_argument("--risco-max", type=float, default=0.30, help="fração de anos que pode falhar (SUPOSIÇÃO)")
    ap.add_argument("--passo-inicio", type=int, default=10, help="dias entre inícios de plantio")
    ap.add_argument("--n-sorteios", type=int, default=10000)
    ap.add_argument("--semente", type=int, default=Parametros.semente)
    a = ap.parse_args(argv)
    params = Parametros(ciclo_modo=a.ciclo_modo, ciclo_fonte=a.ciclo_fonte, epoca_modo=a.epoca_modo, chuva_modo=a.chuva_modo, risco_max=a.risco_max,
                        passo_inicio_dias=a.passo_inicio, n_sorteios=a.n_sorteios, semente=a.semente)
    rodar(a.pontos, a.n, a.cultura_atual, a.culturas_arquivo, a.saida, params=params)


if __name__ == "__main__":
    main()
