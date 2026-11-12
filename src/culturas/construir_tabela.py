"""Gera data/culturas/tabela_culturas.csv (formato longo: uma linha por cultura x atributo).

Regras: nenhum número é digitado de memória.
- Faixas climáticas, ciclo e família vêm LIDOS do CSV do FAO EcoCrop (espelho OpenCLIM/ecocrop),
  passado em --ecocrop. O valor é copiado do arquivo, nunca digitado aqui.
- Palha / N vêm de ESTUDOS (listados em ESTUDOS abaixo), cada valor com o trecho copiado do PDF
  lido em 2026-11-11. Tudo que não foi achado vira linha `lacuna` com o motivo.

Uso: python -m src.culturas.construir_tabela --ecocrop /caminho/EcoCrop_DB.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .tabela_culturas import CAMINHO_PADRAO, COLUNAS

DATA_CONSULTA = "2026-11-11"

ECOCROP_FONTE = ("FAO EcoCrop (via espelho OpenCLIM/ecocrop, EcoCrop_DB.csv, commit ea43ecd, "
                 "sha256 4187e884...d48d106)")
ECOCROP_URL = ("https://raw.githubusercontent.com/OpenCLIM/ecocrop/"
               "ea43ecd418fd1a1ea08d32c7dce64b7fae02dec4/EcoCrop_DB.csv")
ECOCROP_OBS = ("Valor lido do espelho do GitHub; a base oficial (gaez.fao.org/pages/ecocrop) pediu login "
               "Google / retornou 503 e NAO foi consultada diretamente.")

# cultura_id, nome em português, código EcoPort (EcoCrop). Escolha de culturas = proposta a revisar.
CULTURAS = [
    ("milho", "Milho", "2175"),
    ("feijao_caupi", "Feijão-caupi", "2153"),
    ("feijao_comum", "Feijão comum", "1668"),
    ("sorgo", "Sorgo", "48747"),
    ("milheto", "Milheto", "8418"),
    ("mandioca", "Mandioca", "1420"),
    ("algodao", "Algodão", "1160"),
    ("amendoim", "Amendoim", "2199"),
    ("girassol", "Girassol", "1191"),
    ("mamona", "Mamona", "1866"),
    ("gergelim", "Gergelim", "1937"),
    ("guandu", "Feijão-guandu", "576"),
    ("palma_forrageira", "Palma forrageira", "8094"),
    ("crotalaria_juncea", "Crotalária juncea", "801"),
    ("feijao_de_porco", "Feijão-de-porco", "609"),
    ("mucuna", "Mucuna", "7832"),
]

# atributo -> (coluna EcoCrop, unidade, descrição da coluna conforme README do OpenCLIM)
ATRIBUTOS_ECOCROP = {
    "temp_min_abs_c": ("TMIN", "°C", "absolute minimum temperature"),
    "temp_otima_min_c": ("TOPMN", "°C", "optimal minimum temperature"),
    "temp_otima_max_c": ("TOPMX", "°C", "optimal maximum temperature"),
    "temp_max_abs_c": ("TMAX", "°C", "absolute maximum temperature"),
    "chuva_min_abs_mm": ("RMIN", "mm", "absolute minimum rainfall"),
    "chuva_otima_min_mm": ("ROPMN", "mm", "optimal minimum rainfall"),
    "chuva_otima_max_mm": ("ROPMX", "mm", "optimal maximum rainfall"),
    "chuva_max_abs_mm": ("RMAX", "mm", "absolute maximum rainfall"),
    "ciclo_min_dias": ("GMIN", "dias", "minimum crop cycle"),
    "ciclo_max_dias": ("GMAX", "dias", "maximum crop cycle"),
}
CHUVA_NOTA = (" Período de referência da chuva (anual vs. ciclo) NAO verificado na fonte oficial; "
              "o código do OpenCLIM compara com a chuva total acumulada no ciclo (ecocrop_testdata_run.py).")

# Estudos lidos (valores copiados do texto/tabela do PDF baixado em 2026-11-11).
E_SILVA = dict(
    fonte="Silva et al. 2011, Cadernos de Agroecologia v.6 n.2 (resumo 10413, VII CBA), Selvíria-MS, 70 dias após semeadura",
    url="https://revista.aba-agroecologia.org.br/cad/article/download/10413/7117/50413",
    pagina="p.3, Tabela 1",
    contexto="Estudo único, Latossolo de Cerrado (Selvíria-MS), corte aos 70 DAS; não generalizar para o semiárido.",
)
E_MOREIRA = dict(
    fonte="Moreira et al. 2012, FERTBIO 2012 (Embrapa Milho e Sorgo/UFSJ), Matozinhos-MG, corte em pleno florescimento (84 dias)",
    url="https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/936257/1/Produtividadeacumulo.pdf",
    pagina="p.3 Tabela 2 (matéria seca); p.4 tabela de acúmulo de macronutrientes (impressa como 'Tabela 7')",
    contexto="Estudo único, Latossolo Vermelho Amarelo (Matozinhos-MG); não generalizar para o semiárido.",
)
E_PERIN = dict(
    fonte="Perin et al. 2004, Pesq. agropec. bras. v.39 n.1 p.35-40 (Embrapa Agrobiologia/UFV), Viçosa-MG, cultivo isolado, 68 dias após plantio",
    url="https://seer.sct.embrapa.br/index.php/pab/article/download/6733/3789",
    pagina="p.39, Tabela 3",
    contexto="Estudo único (Cambissolo, Viçosa-MG), N derivado da fixação biológica por abundância natural de 15N.",
)

# (cultura_id, atributo, valor, unidade, estudo, trecho copiado)
ESTUDOS = [
    ("crotalaria_juncea", "palha_ms_kg_ha", "11250", "kg/ha de matéria seca da parte aérea", E_SILVA,
     "Crotalária juncea (11.250 kg ha -1) > milheto (7.430 kg ha -1) > guandu (6.130 kg ha -1) > mucuna-verde (4.017 kg ha -1)"),
    ("milheto", "palha_ms_kg_ha", "7430", "kg/ha de matéria seca da parte aérea", E_SILVA,
     "Crotalária juncea (11.250 kg ha -1) > milheto (7.430 kg ha -1) > guandu (6.130 kg ha -1) > mucuna-verde (4.017 kg ha -1)"),
    ("guandu", "palha_ms_kg_ha", "6130", "kg/ha de matéria seca da parte aérea", E_SILVA,
     "Crotalária juncea (11.250 kg ha -1) > milheto (7.430 kg ha -1) > guandu (6.130 kg ha -1) > mucuna-verde (4.017 kg ha -1)"),
    ("mucuna", "palha_ms_kg_ha", "4017", "kg/ha de matéria seca da parte aérea", E_SILVA,
     "Crotalária juncea (11.250 kg ha -1) > milheto (7.430 kg ha -1) > guandu (6.130 kg ha -1) > mucuna-verde (4.017 kg ha -1)"),
    ("crotalaria_juncea", "n_acumulado_parte_aerea_kg_ha", "196,9", "kg/ha de N na parte aérea (inclui N do solo, não só fixado)", E_SILVA,
     "Crotalária   196,9 a     20,0 a      232,3 a"),
    ("guandu", "n_acumulado_parte_aerea_kg_ha", "142,9", "kg/ha de N na parte aérea (inclui N do solo, não só fixado)", E_SILVA,
     "Guandu       142,9 b     15,3 c      139,9 b"),
    ("mucuna", "n_acumulado_parte_aerea_kg_ha", "109,5", "kg/ha de N na parte aérea (inclui N do solo, não só fixado)", E_SILVA,
     "Mucuna       109,5 c     11,4 d      103,5 bc"),
    ("milheto", "n_acumulado_parte_aerea_kg_ha", "83,9", "kg/ha de N na parte aérea (inclui N do solo, não só fixado)", E_SILVA,
     "Milheto       83,9 d     17,1 b      226,1 a"),
    ("girassol", "palha_ms_kg_ha", "10258", "kg/ha de matéria seca da parte aérea", E_MOREIRA,
     "Girassol                                                                                      10258 A"),
    ("girassol", "n_acumulado_parte_aerea_kg_ha", "123,5", "kg/ha de N na parte aérea (inclui N do solo, não só fixado)", E_MOREIRA,
     "Girassol                         123,5AB           4880,5A"),
    ("crotalaria_juncea", "n_fixado_kg_ha", "173,215", "kg/ha de N derivado da fixação biológica (FBN)", E_PERIN,
     "Crotalária 3,435 57,039 173,215"),
]

ATRIBUTOS_ESTUDO = ["palha_ms_kg_ha", "n_acumulado_parte_aerea_kg_ha", "n_fixado_kg_ha", "demanda_hidrica_mm_ciclo"]
MOTIVO_LACUNA = {
    "palha_ms_kg_ha": "Nao encontrado em fonte lida. Sorgo e milho: Silva et al. 2009 (PAB 44(11):1504-1512) tem a tabela, "
                      "mas ela esta em imagem no PDF e nao foi lida.",
    "n_acumulado_parte_aerea_kg_ha": "Nao encontrado em fonte lida.",
    "n_fixado_kg_ha": "Nao encontrado em fonte lida (so crotalaria juncea tem valor de FBN lido).",
    "demanda_hidrica_mm_ciclo": "Nao buscado/nao lido: nenhuma fonte FAO de demanda hidrica (ex.: FAO Irrigation and Drainage "
                                "Paper 33/56) foi lida. A faixa de chuva do EcoCrop e o unico criterio hidrico com fonte.",
}


def _linha(**kw) -> dict:
    base = {c: "" for c in COLUNAS}
    base["data_consulta"] = DATA_CONSULTA
    base.update(kw)
    return base


def construir(ecocrop_csv: Path) -> list[dict]:
    with open(ecocrop_csv, encoding="utf-8", errors="replace", newline="") as f:
        eco = {r["EcoPortCode"]: r for r in csv.DictReader(f)}
    linhas: list[dict] = []
    for cid, pt, code in CULTURAS:
        r = eco[code]
        ident = dict(cultura_id=cid, cultura_pt=pt, nome_cientifico=r["ScientificName"], ecoport_code=code)
        for atrib, (col, unid, desc) in ATRIBUTOS_ECOCROP.items():
            v = (r.get(col) or "").strip()
            pag = f"EcoPortCode={code}, coluna {col} ({desc})"
            ctx = ECOCROP_OBS + (CHUVA_NOTA if atrib.startswith("chuva") else "")
            if v in ("", "NA"):
                linhas.append(_linha(**ident, atributo=atrib, unidade=unid, status="lacuna", fonte=ECOCROP_FONTE,
                                     url=ECOCROP_URL, pagina=pag, contexto="Campo vazio/NA na fonte. " + ctx))
            else:
                linhas.append(_linha(**ident, atributo=atrib, valor=v, unidade=unid, status="verificado",
                                     fonte=ECOCROP_FONTE, url=ECOCROP_URL, pagina=pag,
                                     trecho=f"EcoPortCode={code}; {col}={v}", contexto=ctx))
        fam = r["FAMNAME"].split(":")[-1].strip()
        linhas.append(_linha(**ident, atributo="familia_botanica", valor=fam, unidade="texto", status="verificado",
                             fonte=ECOCROP_FONTE, url=ECOCROP_URL,
                             pagina=f"EcoPortCode={code}, coluna FAMNAME (último nível)",
                             trecho=f"EcoPortCode={code}; FAMNAME={r['FAMNAME']}", contexto=ECOCROP_OBS))
        for atrib in ATRIBUTOS_ESTUDO:
            ach = next(((v, u, e, t) for c, a, v, u, e, t in ESTUDOS if c == cid and a == atrib), None)
            if ach:
                v, u, e, t = ach
                linhas.append(_linha(**ident, atributo=atrib, valor=v.replace(",", "."), unidade=u, status="verificado",
                                     fonte=e["fonte"], url=e["url"], pagina=e["pagina"], trecho=t, contexto=e["contexto"]))
            else:
                linhas.append(_linha(**ident, atributo=atrib, status="lacuna", contexto=MOTIVO_LACUNA[atrib]))
    return linhas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecocrop", required=True, type=Path)
    ap.add_argument("--saida", type=Path, default=CAMINHO_PADRAO)
    a = ap.parse_args()
    linhas = construir(a.ecocrop)
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    with open(a.saida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} linhas gravadas em {a.saida}")


if __name__ == "__main__":
    main()
