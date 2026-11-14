"""A1: indicador simples e transparente de risco de erosão/escoamento (baixo/médio/alto). Funções puras, sem Streamlit.

NÃO é RUSLE: o projeto não tem erosividade medida, erodibilidade (fator K), comprimento de rampa nem manejo.
É uma soma de 4 notas (0, 1 ou 2): declive, textura, carbono orgânico, frequência de chuva erosiva.

Faixas com FONTE LIDA:
- Classes de declive (Embrapa): plano 0-3 %, suave ondulado 3-8, mod. ondulado 8-13, ondulado 13-20, forte ondulado 20-45,
  montanhoso > 45. Fonte: Pereira & Lombardi Neto (2004), Avaliação da aptidão agrícola das terras: proposta metodológica,
  Embrapa Meio Ambiente, Documentos 43, p. 22, Tabela 10 (adaptada de Giboshi 1999; Ramalho-Filho & Beek 1995).
  https://www.infoteca.cnptia.embrapa.br/bitstream/doc/14508/1/documentos43.pdf
- Classes de textura (SiBCS, Embrapa): arenosa (areia - argila > 700 g/kg), média (< 350 g/kg argila e > 150 g/kg areia),
  argilosa (350-600 g/kg argila), muito argilosa (> 600), siltosa (< 350 argila e < 150 areia).
  https://www.embrapa.br/en/solos/sibcs/atributos-do-solo?link=sibcs
- Chuva erosiva: total >= 10 mm (ou >= 6 mm em 15 min), Wischmeier & Smith (1978) citado em Lima et al. (2023), Embrapa Solos,
  Boletim de P&D 286, "Erosividade da chuva do Brasil".
  https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1159615/1/CNPS-BPD-286-2023.pdf
  Aqui só há chuva diária: dia com >= 10 mm é aproximação (declarada). Coincide com o índice R10mm do ETCCDI.

SUPOSIÇÕES explícitas (SEM fonte lida; parâmetros abaixo, trocáveis): o mapeamento classe -> nota, os cortes de carbono e de
dias de chuva erosiva (tercis entre os pontos do projeto, ou seja, RELATIVOS), e os cortes da soma (<=2 baixo, 3-4 médio, >=5 alto).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]

# --- classes com fonte (Embrapa Documentos 43, Tabela 10) -> limite superior (%) de cada classe
CLASSES_DECLIVE = [("plano", 3.0), ("suave ondulado", 8.0), ("moderadamente ondulado", 13.0), ("ondulado", 20.0),
                   ("forte ondulado", 45.0), ("montanhoso ou escarpado", float("inf"))]
# SUPOSIÇÃO: nota por classe (0 = plano/suave; 1 = mod. ondulado/ondulado; 2 = forte ondulado ou mais). A Tabela 10 mostra grau de
# limitação crescente com a classe, mas depende do fator K (que não temos); por isso a nota é agrupada e declarada.
NOTA_DECLIVE = {"plano": 0, "suave ondulado": 0, "moderadamente ondulado": 1, "ondulado": 1, "forte ondulado": 2,
                "montanhoso ou escarpado": 2}
# SUPOSIÇÃO: nota por textura (sem fonte lida que ligue textura a erosão/infiltração neste projeto).
NOTA_TEXTURA = {"média": 0, "arenosa": 1, "argilosa": 1, "muito argilosa": 2, "siltosa": 2}
# SUPOSIÇÃO: cortes da soma 0..8
CORTE_MEDIO, CORTE_ALTO = 3, 5
LIMIAR_DIA_EROSIVO_MM = 10.0  # Wischmeier & Smith (1978) via Embrapa BPD 286 (aproximação diária)
MIN_ANOS_CHUVA = 10           # SUPOSIÇÃO: anos mínimos para contar dias de chuva erosiva por ano

AVISO = ("Indicador simples e relativo, NÃO é RUSLE nem medida de perda de solo. Declive vem de um modelo de relevo de ~30 m, solo de um "
         "mapa global de 250 m e chuva de células de ~50 km: nenhum enxerga a sua roça. A avaliar com técnico local.")


def classe_declive(declive_pct: float | None) -> str | None:
    """Classe de relevo da Embrapa; None se faltar dado. Monótona (mais declive, classe igual ou mais forte)."""
    if declive_pct is None or (isinstance(declive_pct, float) and np.isnan(declive_pct)) or declive_pct < 0:
        return None
    for nome, teto in CLASSES_DECLIVE:
        if declive_pct <= teto:
            return nome
    return CLASSES_DECLIVE[-1][0]


def classe_textura(argila_pct: float | None, areia_pct: float | None) -> str | None:
    """Grupamento textural do SiBCS (argila/areia em %, = g/100 g). Aproximação: a classe 'areia/areia franca' do SiBCS
    vem do triângulo textural; aqui usa-se o critério areia - argila > 70 pontos percentuais (700 g/kg) lido na fonte."""
    if argila_pct is None or areia_pct is None or np.isnan(argila_pct) or np.isnan(areia_pct):
        return None
    if areia_pct - argila_pct > 70:
        return "arenosa"
    if argila_pct > 60:
        return "muito argilosa"
    if argila_pct >= 35:
        return "argilosa"
    if areia_pct < 15:
        return "siltosa"
    return "média"


def _terco(valor: float | None, c1: float, c2: float, invertido: bool = False) -> int | None:
    if valor is None or np.isnan(valor):
        return None
    n = 0 if valor <= c1 else (1 if valor <= c2 else 2)
    return 2 - n if invertido else n


def dias_chuva_erosiva_por_ano(clima: pd.DataFrame | None) -> tuple[float | None, int, str | None]:
    """Média de dias/ano com chuva diária >= 10 mm (anos completos). Devolve (média, n_anos, lacuna)."""
    if clima is None or len(clima) == 0 or not {"data", "chuva_mm"} <= set(clima.columns):
        return None, 0, "Sem chuva diária do local: frequência de chuva erosiva não calculada."
    d = clima.dropna(subset=["chuva_mm"]).copy()
    d["ano"] = pd.to_datetime(d["data"]).dt.year
    cont = d.groupby("ano")["chuva_mm"].agg(n="size", ero=lambda s: int((s >= LIMIAR_DIA_EROSIVO_MM).sum()))
    cont = cont[cont["n"] >= 360]
    if len(cont) < MIN_ANOS_CHUVA:
        return None, int(len(cont)), f"Só {len(cont)} anos completos de chuva (mínimo {MIN_ANOS_CHUVA}): frequência de chuva erosiva não calculada."
    return float(cont["ero"].mean()), int(len(cont)), None


def referencia_pontos(tab: pd.DataFrame) -> dict:
    """Cortes (tercis) entre os pontos do projeto. `tab` precisa das colunas carbono_g_kg e dias_chuva_erosiva_ano."""
    ref = {}
    for col in ("carbono_g_kg", "dias_chuva_erosiva_ano"):
        v = tab[col].dropna() if col in tab else pd.Series(dtype=float)
        ref[col] = None if len(v) < 10 else {"c1": float(np.percentile(v, 100 / 3)), "c2": float(np.percentile(v, 200 / 3)), "n_pontos": int(len(v))}
    return ref


def avaliar_risco(declive_pct: float | None, argila_pct: float | None, areia_pct: float | None, carbono_g_kg: float | None,
                  dias_chuva_erosiva_ano: float | None, referencia: dict | None) -> dict:
    """Indicador baixo/médio/alto. Se faltar QUALQUER componente: classe None (lacuna visível) e a soma parcial é só informativa."""
    lac, comp = [], {}
    cd = classe_declive(declive_pct)
    comp["declive"] = {"valor": declive_pct, "unidade": "%", "classe": cd, "nota": NOTA_DECLIVE.get(cd) if cd else None,
                       "fonte_faixa": "Embrapa Documentos 43, Tabela 10", "nota_e_suposicao": True}
    ct = classe_textura(argila_pct, areia_pct)
    comp["textura"] = {"valor": {"argila_pct": argila_pct, "areia_pct": areia_pct}, "classe": ct,
                       "nota": NOTA_TEXTURA.get(ct) if ct else None, "fonte_faixa": "SiBCS (Embrapa), atributos do solo",
                       "nota_e_suposicao": True}
    refc = (referencia or {}).get("carbono_g_kg")
    nc = _terco(carbono_g_kg, refc["c1"], refc["c2"], invertido=True) if refc else None  # menos carbono = mais risco
    comp["carbono_organico"] = {"valor": carbono_g_kg, "unidade": "g/kg (SoilGrids, 0-30 cm)", "nota": nc,
                                "corte": refc, "regra": "tercis entre os pontos do projeto; menos carbono = nota maior",
                                "fonte_faixa": None, "nota_e_suposicao": True}
    refr = (referencia or {}).get("dias_chuva_erosiva_ano")
    nr = _terco(dias_chuva_erosiva_ano, refr["c1"], refr["c2"]) if refr else None
    comp["chuva_erosiva"] = {"valor": dias_chuva_erosiva_ano, "unidade": f"dias/ano com chuva >= {LIMIAR_DIA_EROSIVO_MM:g} mm", "nota": nr,
                             "corte": refr, "regra": "tercis entre os pontos do projeto; mais dias = nota maior",
                             "fonte_faixa": "limiar 10 mm: Wischmeier & Smith (1978) via Embrapa BPD 286", "nota_e_suposicao": True}
    nomes = {"declive": "declive (terreno.parquet)", "textura": "textura do solo (solo.parquet)",
             "carbono_organico": "carbono orgânico (solo.parquet)", "chuva_erosiva": "chuva diária (clima_diario.parquet)"}
    for k, c in comp.items():
        if c["nota"] is None:
            lac.append(f"Sem dado ou sem corte de referência para {nomes[k]}: componente não pontuado.")
    notas = [c["nota"] for c in comp.values() if c["nota"] is not None]
    soma = int(sum(notas))
    classe = None
    if len(notas) == 4:
        classe = "alto" if soma >= CORTE_ALTO else ("médio" if soma >= CORTE_MEDIO else "baixo")
    return {"classe": classe, "soma_notas": soma, "soma_maxima": 8, "componentes": comp, "lacunas": lac,
            "cortes_da_soma": {"medio_a_partir_de": CORTE_MEDIO, "alto_a_partir_de": CORTE_ALTO, "e_suposicao": True},
            "aviso": AVISO, "tecnico": "A avaliar com técnico local."}


# ----------------------------------------------------------------------------- carga de dados (arquivos do projeto)
def _solo_de_linha(r: pd.Series) -> dict:
    m = lambda p: float(np.mean([r[f"{p}_{x}"] for x in ("0-5cm", "5-15cm", "15-30cm")]))
    return {"argila_pct": m("clay"), "areia_pct": m("sand"), "carbono_g_kg": m("soc")}


def montar_tabela_pontos(raiz: Path = RAIZ) -> pd.DataFrame:
    """Uma linha por ponto: declive, argila, areia, carbono (média 0-30 cm) e dias de chuva erosiva/ano. Falta de arquivo = colunas NaN."""
    ter, solo, clima = raiz / "data/processed/terreno.parquet", raiz / "data/processed/solo.parquet", raiz / "data/processed/clima_diario.parquet"
    base = pd.DataFrame(columns=["ponto_id", "declive_pct", "declive_p90_pct", "argila_pct", "areia_pct", "carbono_g_kg", "dias_chuva_erosiva_ano"]).set_index("ponto_id")
    ids = set()
    t = pd.read_parquet(ter).set_index("ponto_id") if ter.exists() else None
    s = pd.read_parquet(solo).set_index("ponto_id") if solo.exists() else None
    for x in (t, s):
        if x is not None:
            ids |= set(x.index)
    if not ids:
        return base
    df = pd.DataFrame(index=sorted(ids))
    df.index.name = "ponto_id"
    df["declive_pct"] = t["declive_medio_1km_pct"] if t is not None else np.nan
    df["declive_p90_pct"] = t["declive_p90_1km_pct"] if t is not None else np.nan
    for c in ("argila_pct", "areia_pct", "carbono_g_kg"):
        df[c] = np.nan
    if s is not None:
        ok = s.dropna(subset=["clay_0-5cm"])
        ext = pd.DataFrame([_solo_de_linha(r) for _, r in ok.iterrows()], index=ok.index)
        df.loc[ext.index, ext.columns] = ext
    df["dias_chuva_erosiva_ano"] = np.nan
    if clima.exists():
        c = pd.read_parquet(clima, columns=["ponto_id", "data", "chuva_mm"])
        for pid, g in c.groupby("ponto_id"):
            v, _, _ = dias_chuva_erosiva_por_ano(g)
            if v is not None:
                df.loc[pid, "dias_chuva_erosiva_ano"] = v
    return df


_CACHE: dict = {}


def tabela_pontos_cache(raiz: Path = RAIZ) -> pd.DataFrame:
    if str(raiz) not in _CACHE:
        _CACHE[str(raiz)] = montar_tabela_pontos(raiz)
    return _CACHE[str(raiz)]


def risco_do_ponto(ponto_id: str, tabela: pd.DataFrame) -> dict:
    """Aplica `avaliar_risco` a um ponto da tabela. Ponto ausente: tudo lacuna."""
    ref = referencia_pontos(tabela)
    if ponto_id in tabela.index:
        r = tabela.loc[ponto_id]
        g = lambda k: None if pd.isna(r.get(k)) else float(r[k])
        out = avaliar_risco(g("declive_pct"), g("argila_pct"), g("areia_pct"), g("carbono_g_kg"), g("dias_chuva_erosiva_ano"), ref)
        out["declive_p90_pct"] = g("declive_p90_pct")
    else:
        out = avaliar_risco(None, None, None, None, None, ref)
        out["declive_p90_pct"] = None
    out["ponto_id"] = ponto_id
    return out
