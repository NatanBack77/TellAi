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

# --- Fontes lidas em 2026-11-12 (valores/trechos copiados do texto ou tabela do PDF/HTML baixado) ---
D2 = "2026-11-12"
CONV = "[conversão declarada: {a} x 1000 = {b} kg/ha; 1 Mg = 1 t = 1000 kg]"
E_FAO_T5 = dict(
    fonte="Brouwer & Heibloem 1986, FAO Irrigation Water Management Training Manual No. 3 (Irrigation Water Needs), "
          "Cap. 2 Crop Water Needs, Tabela 5 'Approximate values of seasonal crop water needs'",
    url="https://www.fao.org/4/s2022e/s2022e02.htm",
    pagina="Cap. 2 (página HTML única), Tabela 5",
    contexto="REGIÃO: global/não específico do semiárido. Fonte dá FAIXA (mm/período total de crescimento); o valor "
             "gravado é o LIMITE INFERIOR da faixa (a faixa completa está no trecho). A fonte diz que são valores aproximados "
             "e que convém obter dados locais. Demanda total da cultura (ETm), não chuva.",
    data=D2,
)
E_SILVA2006 = dict(
    fonte="Silva, Muraoka, Guimarães & Buzetti 2006, Rev. Bras. Milho e Sorgo 5(2):202-217 (Acúmulo de nutrientes em plantas de "
          "cobertura e no milho cultivado em sucessão sob diferentes doses de N em plantio direto), Selvíria-MS",
    url="https://rbms.sede.embrapa.br/ojs/article/download/184/pdf_241/5902",
    pagina="p.213 (PDF p.12), Tabela 5 - tabela é IMAGEM no PDF: valores lidos visualmente (pdftoppm), não extraídos como texto",
    contexto="REGIÃO: Cerrado (Selvíria-MS, Latossolo), NÃO semiárido. Linha de controle (0 kg/ha N semeadura, 0 cobertura), "
             "ano agrícola 2001/02, milho grão em maturação fisiológica. Colunas: produtividade de grãos t/ha | palha t/ha | "
             "N nos grãos kg/t | N na palha kg/t | N total absorvido kg/ha. Outros tratamentos/ano 2002/03 dão valores diferentes "
             "(palha 5,65 a 7,91 t/ha; N total 103,12 a 207,25 kg/ha). 'Palha' aqui exclui os grãos.",
    data=D2,
)
E_TORRES = dict(
    fonte="Torres, Pereira, Andrioli, Polidoro & Fabian 2005, Rev. Bras. Ciência do Solo 29(4):609-618 (Decomposição e liberação "
          "de N de resíduos culturais de plantas de cobertura em solo de Cerrado), Uberaba-MG",
    url="https://www.redalyc.org/pdf/1802/180214035013.pdf",
    pagina="p.613 (PDF p.6), Quadro 2 (coluna ano agrícola 2000/01; coleta aos 110 DAP)",
    contexto="REGIÃO: Cerrado (Uberaba-MG, Latossolo), NÃO semiárido. É SORGO FORRAGEIRO como planta de cobertura (110 dias após "
             "plantio), não sorgo-grão. Ano 2000/01; em 2001/02 o mesmo quadro dá MS 4,0 Mg/ha e N 45,0 kg/ha (escolhido 2000/01 "
             "sem critério além de ser o primeiro ano; os dois anos diferem ~2x).",
    data=D2,
)
E_MAIA = dict(
    fonte="Maia, Miranda, Melo, Viana & Góis 2013, Agropecuária Científica no Semiárido (ACSA) 9(1):43-49 (Biomassa de feijão de "
          "porco sob diferentes densidades de semeadura em Mossoró, RN), UFERSA",
    url="https://acsa.revistas.ufcg.edu.br/acsa/index.php/ACSA/article/download/272/pdf/1018",
    pagina="PDF p.4, Tabela 3 (linha 'Média', coluna MSPA, local Horta)",
    contexto="REGIÃO: semiárido (Mossoró-RN), irrigação por aspersão, sem adubação. Dois locais: Horta (corte aos 59 DAS) = 4,67 Mg/ha "
             "[gravado] e Alagoinha (corte aos 90 DAS) = 19,89 Mg/ha; diferença ~4x e significativa (p<0,01). Escolhido Horta por "
             "ser o corte mais próximo dos 60-70 dias citados no artigo como usual; a escolha é arbitrária e a incerteza é grande. "
             "Média sobre 4 densidades de semeadura (10-40 plantas/m2).",
    data=D2,
)
E_LEAL = dict(
    fonte="Leal et al. 2012, Embrapa Agrobiologia, Boletim de Pesquisa e Desenvolvimento 83 (Feijão-de-porco na Baixada "
          "Fluminense: como tirar proveito máximo da sua ação como adubo-verde), Seropédica-RJ",
    url="https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/949680/1/bot08312.pdf",
    pagina="PDF p.7 (Resumo); mesmos valores na Tabela 2 (PDF p.16)",
    contexto="REGIÃO: Baixada Fluminense-RJ (úmido), NÃO semiárido. N acumulado na parte aérea com corte aos 4 meses: 153,8 kg/ha "
             "(plantio de primavera, gravado) e 143,3 kg/ha (plantio de verão); a ordem 'respectivamente' segue 'primavera e verão' "
             "do resumo. Valor de 4 meses; aos 2 e 3 meses o boletim traz médias menores (32,6 e 67,6 kg/ha). Inclui N do solo.",
    data=D2,
)
E_OKITO = dict(
    fonte="Okito, Alves, Urquiaga & Boddey 2004, Pesq. agropec. bras. 39(12):1183-1190 (Nitrogen fixation by groundnut and velvet "
          "bean and residual benefit to a subsequent maize crop), Embrapa Agrobiologia, Seropédica-RJ",
    url="https://apct.sede.embrapa.br/pab/article/download/6894/3950/22342",
    pagina="PDF p.3 Tabela 1 (MS e N acumulado); PDF p.4 Tabela 2 (N derivado da FBN, abundância natural de 15N)",
    contexto="REGIÃO: Seropédica-RJ (Baixada Fluminense), NÃO semiárido. Estudo único, uma safra.",
    data=D2,
)
E_SILVA2012 = dict(
    fonte="da Silva, Bonomo, Donato, Pires, Rosa & Donato 2012, Rev. Bras. Ciências Agrárias 7(supl.):866-875 (Composição mineral "
          "em cladódios de palma forrageira sob diferentes espaçamentos e adubações química), IF Baiano Guanambi-BA",
    url="https://www.redalyc.org/pdf/1190/119025455025.pdf",
    pagina="PDF p.9 (texto após Tabelas 6-7; colheita aos 620 dias após plantio)",
    contexto="REGIÃO: semiárido baiano (Guanambi-BA, Caatinga). Palma 'Gigante', média geral de espaçamentos e adubações. "
             "ATENÇÃO semântica: palma é forrageira colhida inteira (cladódios), não deixa 'palha'; o valor é a matéria seca "
             "total dos cladódios na colheita (620 dias), útil só se o cenário considerar o material como cobertura/adubo.",
    data=D2,
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
] + [
    # ---- 2026-11-12: demanda hídrica (FAO IWM Manual 3, Tabela 5; valor = limite inferior da faixa) ----
    (cid, "demanda_hidrica_mm_ciclo", v, "mm/período total de crescimento (limite inferior da faixa FAO)",
     dict(E_FAO_T5, contexto=E_FAO_T5["contexto"] + extra),
     "Table 5 APPROXIMATE VALUES OF SEASONAL CROP WATER NEEDS | Crop water need (mm/total growing period) | " + linha)
    for cid, v, linha, extra in [
        ("milho", "500", "Maize 500-800", ""),
        ("algodao", "700", "Cotton 700-1300", ""),
        ("amendoim", "500", "Peanut 500-700", ""),
        ("sorgo", "450", "Sorghum/Millet 450-650", " Linha combinada 'Sorghum/Millet'."),
        ("milheto", "450", "Sorghum/Millet 450-650",
         " Linha combinada 'Sorghum/Millet': valor de sorgo/milheto juntos, aplicado ao milheto."),
        ("girassol", "600", "Sunflower 600-1000", ""),
        ("feijao_comum", "300", "Bean 300-500",
         " Linha genérica 'Bean' (feijão) mapeada para feijão comum; a fonte não distingue caupi."),
    ]
] + [
    # ---- 2026-11-12: palha / N parte aérea / N fixado ----
    ("milho", "palha_ms_kg_ha", "5650", "kg/ha de palha seca (sem grãos) na maturação fisiológica", E_SILVA2006,
     "Tabela 5, ano agrícola 2001/02, dose 0 / cobertura 0: grãos 4,93 t/ha | palha 5,65 t/ha | N grãos 14,10 kg/t | "
     "N palha 7,45 kg/t | N total absorvido 111,61 kg/ha " + CONV.format(a="5,65 t/ha", b="5650")),
    ("milho", "n_acumulado_parte_aerea_kg_ha", "111,61", "kg/ha de N total absorvido (grãos + palha) na maturação fisiológica",
     E_SILVA2006,
     "Tabela 5, ano agrícola 2001/02, dose 0 / cobertura 0: grãos 4,93 t/ha | palha 5,65 t/ha | N grãos 14,10 kg/t | "
     "N palha 7,45 kg/t | N total absorvido 111,61 kg/ha"),
    ("sorgo", "palha_ms_kg_ha", "7100", "kg/ha de matéria seca da parte aérea (sorgo forrageiro de cobertura, 110 DAP)", E_TORRES,
     "Quadro 2: Sorgo 7,1 b 84,1 c 24,3 4,0 a 45,0 c 34,6 (colunas: 2000/01 MS Mg/ha, N acumulado kg/ha, C/N; "
     "2001/02 MS, N, C/N) " + CONV.format(a="7,1 Mg/ha", b="7100")),
    ("sorgo", "n_acumulado_parte_aerea_kg_ha", "84,1", "kg/ha de N na parte aérea (sorgo forrageiro de cobertura, 110 DAP)", E_TORRES,
     "Quadro 2: Sorgo 7,1 b 84,1 c 24,3 4,0 a 45,0 c 34,6 (colunas: 2000/01 MS Mg/ha, N acumulado kg/ha, C/N; "
     "2001/02 MS, N, C/N)"),
    ("feijao_de_porco", "palha_ms_kg_ha", "4670", "kg/ha de matéria seca da parte aérea (corte aos 59 DAS)", E_MAIA,
     "Média (Mg ha-1) - 22,34 b 91,79 a 4,67 b 19,89 a (colunas: MFPA Horta, MFPA Alagoinha, MSPA Horta, MSPA Alagoinha) "
     + CONV.format(a="4,67 Mg/ha", b="4670")),
    ("feijao_de_porco", "n_acumulado_parte_aerea_kg_ha", "153,8", "kg/ha de N na parte aérea (corte aos 4 meses, plantio de primavera)",
     E_LEAL,
     "obtendo 5511 e 5545 kg ha-1 de massa seca e acumulando 153,8 e 143,3 kg ha-1 de N, respectivamente"),
    ("amendoim", "palha_ms_kg_ha", "1648", "kg/ha de matéria seca da parte aérea sem os grãos (coluna 'Crop-grain')",
     dict(E_OKITO, contexto=E_OKITO["contexto"] + " Palha = matéria seca da planta menos o grão ('Crop-grain'); "
          "planta inteira = 2,651 kg/ha."),
     "Table 1 (Dry matter, kg ha-1: Crop-grain | Grain | Whole plant; Total N: Crop-grain | Grain | Whole plant): "
     "Groundnut 1,648b 1,002±23 2,651a 32.1c 49.4±1.4 78.0a"),
    ("amendoim", "n_acumulado_parte_aerea_kg_ha", "78.0", "kg/ha de N na planta inteira (parte aérea incl. grão)", E_OKITO,
     "Table 1 (Dry matter, kg ha-1: Crop-grain | Grain | Whole plant; Total N: Crop-grain | Grain | Whole plant): "
     "Groundnut 1,648b 1,002±23 2,651a 32.1c 49.4±1.4 78.0a"),
    ("amendoim", "n_fixado_kg_ha", "40.9", "kg/ha de N total derivado da FBN (15N abundância natural)", E_OKITO,
     "Table 2: Groundnut +0.96a 49.0 50.2 58.0 52.4 40.9ab (δ15N | %Ndfa com 3 plantas-referência | média %Ndfa | "
     "N total derivado da FBN kg ha-1)"),
    ("mucuna", "n_fixado_kg_ha", "59.6", "kg/ha de N total derivado da FBN (15N abundância natural)", E_OKITO,
     "Table 2: Velvet bean -0.82a 68.0 68.1 72.8 69.6 59.6a (δ15N | %Ndfa com 3 plantas-referência | média %Ndfa | "
     "N total derivado da FBN kg ha-1)"),
    ("palma_forrageira", "palha_ms_kg_ha", "17100", "kg/ha de matéria seca total dos cladódios aos 620 dias (colheita)", E_SILVA2012,
     "A produtividade média de matéria seca foi 17,10 Mg ha-1 (Tabela 7). " + CONV.format(a="17,10 Mg/ha", b="17100")),
    ("palma_forrageira", "n_acumulado_parte_aerea_kg_ha", "299,25", "kg/ha de N extraído nos cladódios aos 620 dias (colheita)",
     E_SILVA2012,
     "Ao avaliar a extração total de nutrientes aos 620 DAP, verifica-se que o macronutriente mais extraído foi o cálcio, "
     "com 458,28 kg ha-1, seguido por potássio (425,79 kg ha-1), nitrogênio (299,25 kg ha-1)"),
]

ATRIBUTOS_ESTUDO = ["palha_ms_kg_ha", "n_acumulado_parte_aerea_kg_ha", "n_fixado_kg_ha", "demanda_hidrica_mm_ciclo"]
MOTIVO_LACUNA = {
    "palha_ms_kg_ha": "Nao encontrado em fonte lida (buscas 2026-11-11/12). Descartados por nao dar kg/ha de campo: mamona "
                      "(Chaves et al. 2010, vaso, g/planta), caupi (Ferreira et al. 2011, vaso, g/planta), mandioca (Embrapa "
                      "Mandioca em Foco 34, so biomassa verde em cortes), algodao (Embrapa cap. 26 e Rosolem 2012 sem MS/N de "
                      "restos culturais), gergelim (Euba Neto et al. 2016, sem kg/ha de palha).",
    "n_acumulado_parte_aerea_kg_ha": "Nao encontrado em fonte lida (ver motivo de palha_ms_kg_ha para as mesmas culturas).",
    "n_fixado_kg_ha": "Nao encontrado em fonte lida (so crotalaria juncea, amendoim e mucuna tem valor de FBN lido). "
                      "Feijao-de-porco: so ha faixa 'fixa entre 120 a 280 kg ha-1 de N por ciclo' como citacao secundaria na "
                      "introducao de Maia et al. 2013, nao usada.",
    "demanda_hidrica_mm_ciclo": "A Tabela 5 do FAO IWM Manual 3 (lida) nao tem linha para esta cultura (so milho, algodao, "
                                "amendoim, sorgo/milheto, girassol, feijao); paginas FAO Crop Information de mandioca/milheto "
                                "vieram vazias. Nao estimado.",
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
                                     fonte=e["fonte"], url=e["url"], pagina=e["pagina"], trecho=t, contexto=e["contexto"],
                                     data_consulta=e.get("data", DATA_CONSULTA)))
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
