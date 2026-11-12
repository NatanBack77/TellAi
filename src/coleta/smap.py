"""Coleta SMAP L4 SPL4SMGP v008 (umidade do solo, 9 km, granulos de 3 h) -> data/processed/umidade_solo.parquet.

Fonte verificada nos atributos do proprio arquivo HDF5 (2026-11-11): Geophysical_Data/sm_surface ("Top layer soil
moisture (0-5 cm)") e Geophysical_Data/sm_rootzone ("Root zone soil moisture (0-100 cm)"), m3 m-3, float32,
_FillValue -9999, valid 0..0,9. Grade EASE-Grid 2.0 global 9 km (1624 x 3856); cell_lat/cell_lon dao o centro.

Volume: cada granulo tem ~139 MB e o chunk e a grade inteira (gzip), entao baixar/ler tudo seria ~4,7 TB.
Por isso usa o servidor OpenDAP da Earthdata (subset no servidor): um pedido por granulo com a caixa
(bounding box) que cobre os pontos, ~100 KB. Mesmo login Earthdata (.env), via earthaccess.

Cada granulo vira um JSON em data/raw/smap/granulos/ (idempotente, retomavel). Valor de preenchimento -> NaN, nunca
preenchido. Dia = data UTC do granulo (8 granulos/dia, 01:30..22:30 UTC); media diaria exige `min_granulos_dia`.
Nada aqui altera src/modelos/. O parquet so e gravado se a coleta estiver completa (ou com --parcial).
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.modelos.entrada import RAIZ, DadosInvalidos, carregar_config

RE_GRANULO = re.compile(r"_gph_(\d{8}T\d{6})_")


# ---------------------------------------------------------------- parsers (testados offline)
def carimbo_do_nome(nome: str) -> datetime:
    """'SMAP_L4_SM_gph_20150331T013000_Vv8010_001.h5' -> datetime(2015, 3, 31, 1, 30)."""
    m = RE_GRANULO.search(nome)
    if not m:
        raise DadosInvalidos(f"Nome de granulo SMAP inesperado: {nome}")
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S")


def parse_csv_opendap(texto: str, variavel: str, fill: float) -> np.ndarray:
    """Le a saida `.dap.csv` do Hyrax para uma variavel 2-D. Linhas: '/.../var[i], v0, v1, ...'.

    Fill vira NaN. Levanta DadosInvalidos se vier erro do servidor ou se faltar a variavel.
    """
    if texto.startswith("Dataset: ERROR"):
        raise DadosInvalidos(f"Erro OPeNDAP: {texto[:300]}")
    linhas = {}
    for lin in texto.splitlines():
        m = re.match(rf"^/Geophysical_Data/{re.escape(variavel)}\[(\d+)\],(.*)$", lin.strip())
        if m:
            linhas[int(m.group(1))] = [float(x) for x in m.group(2).split(",")]
    if not linhas:
        raise DadosInvalidos(f"Variavel {variavel} ausente na resposta OPeNDAP.")
    if sorted(linhas) != list(range(len(linhas))):
        raise DadosInvalidos(f"Linhas nao contiguas para {variavel}.")
    arr = np.array([linhas[i] for i in range(len(linhas))], dtype=float)
    arr[arr == fill] = np.nan
    return arr


def agregar_diario(registros: pd.DataFrame, min_granulos: int) -> pd.DataFrame:
    """registros: ponto_id, carimbo (datetime), sm_superficie, sm_raiz (NaN = fill).

    Media diaria (UTC) dos granulos validos; dia com < min_granulos validos (por variavel) vira NaN.
    """
    df = registros.copy()
    df["data"] = pd.to_datetime(df["carimbo"]).dt.normalize()
    g = df.groupby(["ponto_id", "data"])
    saida = g[["sm_superficie", "sm_raiz"]].mean()
    n = g[["sm_superficie", "sm_raiz"]].count()
    saida["n_granulos_superficie"] = n["sm_superficie"].astype("int16")
    saida["n_granulos_raiz"] = n["sm_raiz"].astype("int16")
    saida.loc[n["sm_superficie"] < min_granulos, "sm_superficie"] = np.nan
    saida.loc[n["sm_raiz"] < min_granulos, "sm_raiz"] = np.nan
    return saida.reset_index()


# ---------------------------------------------------------------- autenticacao e rede
def _login():
    import earthaccess

    arq = RAIZ / ".env"
    if arq.exists():
        for lin in arq.read_text(encoding="utf-8").splitlines():
            if "=" in lin and not lin.lstrip().startswith("#"):
                k, v = lin.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))  # nunca imprime
    if not os.environ.get("EARTHDATA_USERNAME") or not os.environ.get("EARTHDATA_PASSWORD"):
        raise DadosInvalidos("Defina EARTHDATA_USERNAME e EARTHDATA_PASSWORD no .env.")
    earthaccess.login(strategy="environment")
    return earthaccess


def carregar_pontos(cfg: dict) -> list[dict]:
    """Pontos de data/processed/pontos.csv (os mesmos do clima); sem o arquivo, cai em config.yaml."""
    arq = RAIZ / Path(cfg["caminhos"]["clima"]).parent / "pontos.csv"
    if arq.exists():
        df = pd.read_csv(arq)
        return df[["ponto_id", "lat", "lon"]].to_dict("records")
    return cfg["coleta"]["pontos"]


def _pasta(cfg: dict) -> Path:
    p = RAIZ / cfg["coleta"]["smap"]["pasta_bruta"]
    (p / "granulos").mkdir(parents=True, exist_ok=True)
    return p


def indices_pontos(cfg: dict, ea) -> dict:
    """Celula EASE2 mais proxima de cada ponto (cache em indices.json). Sem vizinho alternativo: ponto em
    celula sem dado (ex.: oceano) fica NaN."""
    c = cfg["coleta"]
    pasta = _pasta(cfg)
    arq = pasta / "indices.json"
    pontos_cfg = carregar_pontos(cfg)
    ids = [p["ponto_id"] for p in pontos_cfg]
    if arq.exists():
        idx = json.loads(arq.read_text(encoding="utf-8"))
        if set(ids) == set(idx["pontos"]) and idx.get("versao") == 1:
            return idx
    import h5py

    s = c["smap"]
    g = ea.search_data(short_name=s["short_name"], version=s["versao"], count=1,
                       temporal=("2020-01-01T00:00:00", "2020-01-01T04:00:00"))
    f = ea.open(g[:1])[0]
    h = h5py.File(f, "r")
    lat, lon = h["cell_lat"][:], h["cell_lon"][:]
    pontos = {}
    for p in pontos_cfg:
        la, lo = np.radians(p["lat"]), np.radians(p["lon"])
        d = np.sin((np.radians(lat) - la) / 2) ** 2 + np.cos(la) * np.cos(np.radians(lat)) * np.sin((np.radians(lon) - lo) / 2) ** 2
        r, col = np.unravel_index(np.nanargmin(d), d.shape)
        dkm = 2 * 6371 * np.arcsin(np.sqrt(d[r, col]))
        pontos[p["ponto_id"]] = {"row": int(r), "col": int(col), "lat_celula": float(lat[r, col]),
                                 "lon_celula": float(lon[r, col]), "dist_km": round(float(dkm), 2)}
    rows = [v["row"] for v in pontos.values()]
    cols = [v["col"] for v in pontos.values()]
    idx = {"versao": 1, "bbox": [min(rows), max(rows), min(cols), max(cols)], "pontos": pontos}
    arq.write_text(json.dumps(idx, indent=1), encoding="utf-8")
    return idx


def listar_granulos(cfg: dict, ea) -> list[dict]:
    """[{nome, carimbo(iso), url}] ordenado. Cache por ano; so o ano corrente/ultimo e refeito se faltar."""
    s = cfg["coleta"]["smap"]
    pasta = _pasta(cfg)
    ini, fim = str(s["inicio"]), str(s["fim"])
    a0, a1 = int(ini[:4]), int(fim[:4])
    todos = []
    for ano in range(a0, a1 + 1):
        arq = pasta / f"lista_{ano}.json"
        if arq.exists():
            todos += json.loads(arq.read_text(encoding="utf-8"))
            continue
        t0 = f"{ano}-{ini[4:6]}-{ini[6:]}T00:00:00" if ano == a0 else f"{ano}-01-01T00:00:00"
        t1 = f"{ano}-{fim[4:6]}-{fim[6:]}T23:59:59" if ano == a1 else f"{ano}-12-31T23:59:59"
        res = ea.search_data(short_name=s["short_name"], version=s["versao"], temporal=(t0, t1))
        itens = []
        for g in res:
            urls = [u["URL"] for u in g["umm"]["RelatedUrls"] if "opendap.earthdata.nasa.gov" in u["URL"]]
            if not urls:
                raise DadosInvalidos(f"Granulo sem URL OPeNDAP: {g['meta']['concept-id']}")
            nome = urls[0].rsplit("/", 1)[-1]
            itens.append({"nome": nome, "carimbo": carimbo_do_nome(nome).isoformat(), "url": urls[0]})
        itens.sort(key=lambda x: x["carimbo"])
        arq.write_text(json.dumps(itens), encoding="utf-8")
        todos += itens
    unicos = {x["nome"]: x for x in todos}  # listas anuais podem repetir granulos de borda
    return sorted(unicos.values(), key=lambda x: x["carimbo"])


def _arq_granulo(pasta: Path, nome: str) -> Path:
    return pasta / "granulos" / (nome.replace(".h5", "") + ".json")


def _valido(arq: Path, idx: dict) -> bool:
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
        return all(i in d["pontos"] and d["pontos"][i]["row"] == v["row"] and d["pontos"][i]["col"] == v["col"]
                   for i, v in idx["pontos"].items())
    except Exception:
        return False


def baixar_granulo(sessao, item: dict, idx: dict, cfg: dict, pasta: Path, tentativas: int = 4) -> None:
    s = cfg["coleta"]["smap"]
    r0, r1, c0, c1 = idx["bbox"]
    ce = (f"/Geophysical_Data/{s['var_superficie']}[{r0}:{r1}][{c0}:{c1}];"
          f"/Geophysical_Data/{s['var_raiz']}[{r0}:{r1}][{c0}:{c1}]")
    erro = None
    for i in range(tentativas):
        try:
            x = sessao.post(item["url"] + ".dap.csv", data={"dap4.ce": ce}, timeout=180)
            if x.status_code != 200:
                raise DadosInvalidos(f"HTTP {x.status_code}: {x.text[:200]}")
            sup = parse_csv_opendap(x.text, s["var_superficie"], s["fill"])
            raiz = parse_csv_opendap(x.text, s["var_raiz"], s["fill"])
            if sup.shape != (r1 - r0 + 1, c1 - c0 + 1) or raiz.shape != sup.shape:
                raise DadosInvalidos(f"Formato inesperado {sup.shape}.")
            pts = {}
            for pid, v in idx["pontos"].items():
                a, b = v["row"] - r0, v["col"] - c0
                pts[pid] = {"row": v["row"], "col": v["col"],
                            "sup": None if np.isnan(sup[a, b]) else float(sup[a, b]),
                            "raiz": None if np.isnan(raiz[a, b]) else float(raiz[a, b])}
            arq = _arq_granulo(pasta, item["nome"])
            tmp = arq.with_suffix(".tmp")
            tmp.write_text(json.dumps({"carimbo": item["carimbo"], "pontos": pts}), encoding="utf-8")
            tmp.replace(arq)
            return
        except Exception as e:
            erro = e
            time.sleep(2 ** i)
    raise DadosInvalidos(f"Falha no granulo {item['nome']}: {erro}")


def coletar(cfg: dict | None = None, limite: int | None = None, parcial: bool = False) -> dict:
    cfg = cfg or carregar_config()
    s = cfg["coleta"]["smap"]
    ea = _login()
    pasta = _pasta(cfg)
    idx = indices_pontos(cfg, ea)
    itens = listar_granulos(cfg, ea)
    pendentes = [it for it in itens if not _valido(_arq_granulo(pasta, it["nome"]), idx)]
    if limite:
        pendentes = pendentes[:limite]
    falhas = []
    ini = time.time()
    if pendentes:
        # sessao por thread (requests.Session nao e garantidamente thread-safe)
        import threading

        local = threading.local()

        def trabalho(it):
            if not hasattr(local, "s"):
                local.s = ea.get_requests_https_session()
            baixar_granulo(local.s, it, idx, cfg, pasta)

        with ThreadPoolExecutor(max_workers=int(s["workers"])) as ex:
            futs = {ex.submit(trabalho, it): it for it in pendentes}
            for k, f in enumerate(as_completed(futs), 1):
                try:
                    f.result()
                except Exception as e:
                    falhas.append({"granulo": futs[f]["nome"], "erro": str(e)[:200]})
                if k % 200 == 0:
                    print(f"{k}/{len(pendentes)} ({time.time() - ini:.0f}s)", flush=True)
    resumo = montar(cfg, itens, idx, pasta, parcial)
    resumo.update({"granulos_listados": len(itens), "baixados_agora": len(pendentes) - len(falhas),
                   "falhas": falhas[:20], "n_falhas": len(falhas)})
    return resumo


def montar(cfg: dict, itens: list[dict], idx: dict, pasta: Path, parcial: bool) -> dict:
    s = cfg["coleta"]["smap"]
    regs = []
    faltam = 0
    for it in itens:
        arq = _arq_granulo(pasta, it["nome"])
        if not _valido(arq, idx):
            faltam += 1
            continue
        d = json.loads(arq.read_text(encoding="utf-8"))
        for pid, v in d["pontos"].items():
            if pid in idx["pontos"]:
                regs.append((pid, d["carimbo"], np.nan if v["sup"] is None else v["sup"],
                             np.nan if v["raiz"] is None else v["raiz"]))
    resumo = {"granulos_em_cache": len(itens) - faltam, "granulos_faltando": faltam}
    if not regs:
        resumo["arquivo"] = None
        return resumo
    reg = pd.DataFrame(regs, columns=["ponto_id", "carimbo", "sm_superficie", "sm_raiz"])
    dia = agregar_diario(reg, int(s["min_granulos_dia"]))
    # grade completa ponto x dia (dia sem granulo nenhum fica NaN, nunca preenchido)
    ini, fim = pd.Timestamp(str(s["inicio"])), pd.Timestamp(str(s["fim"]))
    ids = [p["ponto_id"] for p in carregar_pontos(cfg)]
    grade = pd.MultiIndex.from_product([ids, pd.date_range(ini, fim, freq="D")], names=["ponto_id", "data"])
    df = dia.set_index(["ponto_id", "data"]).reindex(grade).reset_index()
    df[["n_granulos_superficie", "n_granulos_raiz"]] = df[["n_granulos_superficie", "n_granulos_raiz"]].fillna(0).astype("int16")
    df["sm_superficie"] = df["sm_superficie"].astype("float32")
    df["sm_raiz"] = df["sm_raiz"].astype("float32")
    resumo.update({"linhas": int(len(df)), "pontos": len(ids), "dias": int(df["data"].nunique()),
                   "pct_ausente_superficie": round(100 * float(df["sm_superficie"].isna().mean()), 3),
                   "pct_ausente_raiz": round(100 * float(df["sm_raiz"].isna().mean()), 3),
                   "pontos_100pct_nan": sorted(df.groupby("ponto_id")["sm_raiz"].apply(lambda x: x.isna().all()).loc[lambda x: x].index.tolist())})
    if faltam == 0 or parcial:
        saida = RAIZ / cfg["caminhos"]["umidade_solo"]
        saida.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(saida, index=False)
        resumo["arquivo"] = str(saida)
        resumo["completo"] = faltam == 0
    else:
        resumo["arquivo"] = None
        resumo["nota"] = "coleta incompleta: parquet NAO gravado (use --parcial para forcar)"
    return resumo


if __name__ == "__main__":
    import sys

    lim = None
    if "--limite" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limite") + 1])
    print(json.dumps(coletar(limite=lim, parcial="--parcial" in sys.argv), ensure_ascii=False, indent=2))
