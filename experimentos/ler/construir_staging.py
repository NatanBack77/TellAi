"""Monta data/culturas/ler_staging.csv (STAGING: NÃO alimenta o motor) a partir de números LIDOS nos PDFs/artigos abertos.

Cada linha = um resultado de LER (UET) publicado. Nada é estimado: campo não lido fica vazio (lacuna). O script também confere
(a) soma dos parciais = total publicado e (b) razão produtividade consorciada/solteira = parcial publicado, quando as produtividades
foram lidas; divergências > 0,03 vão para experimentos/ler/saida/conferencia.csv e para a coluna `conferencia`.

Uso: python experimentos/ler/construir_staging.py
"""
from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SAIDA_CSV = RAIZ / "data/culturas/ler_staging.csv"
CONF_CSV = RAIZ / "experimentos/ler/saida/conferencia.csv"
DATA_CONSULTA = "2026-11-14"

COLUNAS = ["id_linha", "id_estudo", "componentes", "par_a", "par_b", "arranjo", "densidade", "local", "uf", "semiarido", "anos",
           "regime", "chuva_mm_periodo", "ler_min", "ler_max", "ler_parciais", "prod_solteira_kg_ha", "prod_consorciada_kg_ha",
           "ater", "lec", "tipo_evidencia", "entra_na_faixa", "fonte", "url_aberta", "acesso", "pagina_tabela", "observacao",
           "conferencia", "data_consulta"]

# ---------------------------------------------------------------- estudos (metadados comuns)
E = {
 "tavora2007": dict(
    fonte="Távora, F.J.A.F. et al. 2007 (autores no cabeçalho do PDF: Távora, uma doutoranda e E. Bleicher). Sistemas de consórcio do milho, sorgo e feijão-caupi em séries de substituição. R. Bras. Agrociência 13(3):311-317",
    url="https://periodicos.ufpel.edu.br/index.php/CAST/article/view/1378/1362", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Quixadá (Fazenda Experimental Lavoura Seca)", uf="CE", semiarido="sim", anos="2003 (11/mar-11/jul)", regime="sequeiro", chuva="630"),
 "pinto2011mamona": dict(
    fonte="Pinto, Sizenando Filho, Cysne & Pitombeira 2011. Produtividade e índices de competição da mamona consorciada com gergelim, algodão, milho e feijão caupi. Revista Verde 6(2):75-85",
    url="https://dialnet.unirioja.es/descarga/articulo/7432904.pdf", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Quixadá (Fazenda Experimental Lavoura Seca)", uf="CE", semiarido="sim", anos="2010 (plantio 8/abr)", regime="sequeiro", chuva="287,8 (mar-jun)"),
 "pinto2011girassol": dict(
    fonte="Pinto, Sizenando Filho & Pitombeira 2011. Comportamento do girassol e feijão caupi consorciados. Revista Verde 6(2):69-74",
    url="https://dialnet.unirioja.es/descarga/articulo/7432875.pdf", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Quixadá", uf="CE", semiarido="sim", anos="2009 (18/mar-1/jul)", regime="sequeiro", chuva="928,6 (mar-jul)"),
 "furtado2012": dict(
    fonte="Furtado, Sousa Junior, Sousa, Lacerda & Souza 2012. Produtividade e uso eficiente da terra no consórcio de mamona com gergelim e feijão-caupi no semiárido paraibano. Revista Verde 7(2):156-162",
    url="https://gvaa.com.br/revista/index.php/RVADS/article/download/1376/2261/8291", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Pombal (Sítio Monte Alegre)", uf="PB", semiarido="sim", anos="2011 (mar-nov)", regime="sequeiro", chuva=""),
 "azevedo2007": dict(
    fonte="Azevedo, Beltrão, Severino, Santos & Leão 2007. Rendimento e eficiência agronômica do consórcio da mamoneira com cereais e feijão caupi no semi-árido nordestino. Rev. bras. ol. fibros. 11(3):145-162",
    url="https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/277391/1/1132007004rbof1131451622007.pdf", acesso="texto integral lido; Tabelas 4-6 são imagem (lidas visualmente, médias marginais por fator)",
    local="Monteiro (Estação Experimental, Cariris Velhos)", uf="PB", semiarido="sim", anos="1994 e 1995", regime="sequeiro", chuva="612,3 (1994); 561 (1995)"),
 "albuquerque1997": dict(
    fonte="Albuquerque & Rao 1997. Espaçamento da palma forrageira em consórcio com sorgo e feijão-de-corda no Sertão de Pernambuco. R. Bras. Zootec. 26(4):645-650",
    url="https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/131391/1/Rev.BrasileiradeZootecniav.26n.4p.6456501997.pdf", acesso="texto integral lido (PDF baixado, pdftotext; OCR com ruído, números conferidos no resumo e na Tabela 3)",
    local="Petrolina (Estação Experimental da Caatinga, Embrapa-CPATSA)", uf="PE", semiarido="sim", anos="dez/1982 a 1988 (2 triênios)", regime="sequeiro", chuva="572 (média anual do local)"),
 "tavora1990mandioca": dict(
    fonte="Távora et al. 1990. Consórcio da mandioca no primeiro e segundo ciclos com as culturas do feijão caupi, soja tropical e amendoim. Ciência Agronômica 21(1/2):1-9",
    url="https://periodicos.ufc.br/revistacienciaagronomica/article/download/91105/249059/346456", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Pacajus", uf="CE", semiarido="nao_confirmado", anos="1987/88", regime="sequeiro", chuva="irregular em 1987, normal em 1988 (Fig. 1, valores não lidos)"),
 "essentia2017": dict(
    fonte="Consórcios de milho, feijão e mandioca em presença de bagana de carnaúba em um Argissolo no litoral norte do Ceará sob condições de sequeiro. Essentia (Sobral) 18(1):2-23, 2017",
    url="https://essentia.uvanet.br/index.php/ESSENTIA/article/view/72/92", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Bela Cruz (Fazenda Cajueiro do Boi)", uf="CE", semiarido="nao_confirmado", anos="2013", regime="sequeiro", chuva="680"),
 "barreto1986": dict(
    fonte="Barreto & Serpa 1986. Comportamento das culturas de milho e feijão (Phaseolus vulgaris L.) nos sistemas de cultivo isolado e consorciado, sob o efeito da adubação fosfatada. Embrapa-CNPCo, Comunicado Técnico 20",
    url="https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/358299/1/CPATCCOM.TEC.2086.pdf", acesso="texto integral lido (PDF baixado; OCR ruim, tabela conferida pela soma)",
    local="Poço Verde", uf="SE", semiarido="provavel", anos="1979", regime="sequeiro", chuva=""),
 "tavora_lopes1990": dict(
    fonte="Távora & Lopes 1990. Deficiência hídrica no consórcio milho x caupi. Pesq. agropec. bras. 25(7):1011-1022",
    url="https://apct.sede.embrapa.br/pab/article/download/13547/7691/60300", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Petrolina (Estação de Bebedouro, Embrapa-CPATSA)", uf="PE", semiarido="sim", anos="nov/1982 a mar/1983", regime="irrigado com déficit hídrico imposto (aspersão em linha)", chuva=""),
 "morgado1985": dict(
    fonte="Morgado & Rao 1985. População de plantas e níveis de água no consórcio milho x caupi. Pesq. agropec. bras. 20(1):45-55",
    url="https://apct.sede.embrapa.br/pab/article/download/14975/8695/66348", acesso="texto integral lido (PDF baixado, pdftotext); Fig. 4 (valores por lâmina) é gráfico, só o texto foi lido",
    local="Petrolina (Estação de Bebedouro, Embrapa-CPATSA)", uf="PE", semiarido="sim", anos="mai-set/1983 (pós-chuva)", regime="irrigado (aspersão em linha, lâminas diferenciais)", chuva=""),
 "beltrao1986": dict(
    fonte="Beltrão, Nóbrega, Azevêdo, Vieira & Crisóstomo 1986. Algodoeiro herbáceo em consórcio com cultivares de caupi. Pesq. agropec. bras. 21(3):271-284",
    url="https://apct.sede.embrapa.br/pab/article/download/14727/8411/65372", acesso="texto lido; tabelas do PDF ilegíveis (OCR), só números do resumo e do texto",
    local="Gurinhém", uf="PB", semiarido="nao_confirmado", anos="1983 (estação chuvosa)", regime="sequeiro", chuva="294,2 (emergência à última colheita)"),
 "diaconia_se2022": dict(
    fonte="Diaconia/CDJBC (Santiago et al.) 2022. Desempenho do uso da terra em consórcios agroecológicos com algodão no Alto Sertão de Sergipe. Cadernos de Agroecologia 17(2)",
    url="https://cadernos.aba-agroecologia.org.br/cadernos/article/download/6952/5089/30024", acesso="texto integral lido (PDF baixado)",
    local="Alto Sertão Sergipano (5 consórcios de famílias)", uf="SE", semiarido="sim", anos="safra 2020", regime="sequeiro (agricultores)", chuva=""),
 "diaconia_pb2022": dict(
    fonte="Diaconia/Arribaçã (Melo et al.) 2022. Uso eficiente da terra com algodão em consórcios agroecológicos no Cariri Paraibano. Cadernos de Agroecologia 17(2)",
    url="https://cadernos.aba-agroecologia.org.br/cadernos/article/download/6982/5104/30049", acesso="texto integral lido (PDF baixado)",
    local="Cariri Paraibano (5 famílias: Livramento, São João do Tigre, Amparo, Sumé)", uf="PB", semiarido="sim", anos="safra 2020", regime="sequeiro (agricultores)", chuva=""),
 "pereira2015": dict(
    fonte="Pereira, Almeida, Firmino, Oliveira & Sousa Filho 2015. Renda orgânica do gergelim e uso eficiente da terra com culturas alimentares. II SBRNS (Quixadá-CE), Embrapa Algodão",
    url="https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1020165/1/sbrns3.pdf", acesso="texto integral lido (PDF baixado)",
    local="São Francisco de Assis do Piauí (Vale do Canindé)", uf="PI", semiarido="sim", anos="2014", regime="não informado", chuva=""),
 "silva2013": dict(
    fonte="Silva, Oliveira, Silva, Nascimento, Bezerra, Costa & Araújo 2013. Crescimento e produção de cultivares de algodão herbáceo consorciados no Cariri cearense. Revista ACSA 9(3):104-109",
    url="https://acsa.revistas.ufcg.edu.br/acsa/index.php/ACSA/article/download/283/pdf/1493", acesso="texto integral lido (PDF baixado, pdftotext)",
    local="Missão Velha (Estação Experimental)", uf="CE", semiarido="sim", anos="2011", regime="sequeiro", chuva=""),
 "pinto2013girassol_mamona": dict(
    fonte="Pinto, Pitombeira, Souza, Vidal Neto, Távora & Bezerra 2013. Configuração de fileira no consórcio mamona x girassol: produtividade e seus componentes. Rev. Bras. Ciências Agrárias 8(1):33-41",
    url="https://www.redalyc.org/pdf/1190/119025752016.pdf", acesso="texto lido (PDF baixado); só quadros de ANOVA e médias, sem LER",
    local="Quixadá (Fazenda Lavoura Seca)", uf="CE", semiarido="sim", anos="2008, 2009 e 2010", regime="sequeiro", chuva=""),
 "morais2018": dict(
    fonte="Morais et al. 2018. Habilidade competitiva e biológica do consórcio beterraba com caupi-hortaliça. Revista Ceres 65(5):433-442",
    url="https://www.redalyc.org/journal/3052/305257970008/305257970008.pdf", acesso="texto integral lido (PDF baixado)",
    local="Mossoró (UFERSA)", uf="RN", semiarido="sim", anos="não anotado", regime="irrigado (hortaliça)", chuva=""),
}


def L(est, **kw):
    e = E[est]
    d = dict(id_estudo=est, fonte=e["fonte"], url_aberta=e["url"], acesso=e["acesso"], local=e["local"], uf=e["uf"],
             semiarido=e["semiarido"], anos=e["anos"], regime=e["regime"], chuva_mm_periodo=e["chuva"], tipo_evidencia="experimento_pareado",
             entra_na_faixa="sim" if e["semiarido"] in ("sim", "provavel") and e["regime"].startswith("sequeiro") else "nao", ater="", lec="", densidade="", observacao="", data_consulta=DATA_CONSULTA)
    d.update(kw)
    return d


R: list[dict] = []
# ---------------- Távora 2007 (Quixadá): solteiros kg/ha: FC 1003,25; M 2203,25; S 2258,00 (Tabelas 2, 4, 6); LER = Tabela 7 (p.315)
SOL_T = {"feijao_caupi": 1003.25, "milho": 2203.25, "sorgo": 2258.00}
tav = [  # (par, arranjo, ler, parciais, produtividade consorciada)
 (("feijao_caupi", "milho"), "milho 75% + caupi 25% (séries de substituição, fileiras alternadas)", 1.28, {"milho": 1.02, "feijao_caupi": 0.26}, {"milho": 2237.75, "feijao_caupi": 263.25}),
 (("feijao_caupi", "milho"), "milho 50% + caupi 50%", 1.22, {"milho": 0.85, "feijao_caupi": 0.37}, {"milho": 1878.25, "feijao_caupi": 368.25}),
 (("feijao_caupi", "milho"), "milho 25% + caupi 75%", 1.05, {"milho": 0.43, "feijao_caupi": 0.62}, {"milho": 939.50, "feijao_caupi": 625.00}),
 (("milho", "sorgo"), "milho 75% + sorgo 25%", 1.15, {"milho": 0.84, "sorgo": 0.31}, {"milho": 1847.00, "sorgo": 705.00}),
 (("milho", "sorgo"), "milho 50% + sorgo 50%", 1.00, {"milho": 0.51, "sorgo": 0.49}, {"milho": 1126.75, "sorgo": 1101.75}),
 (("milho", "sorgo"), "milho 25% + sorgo 75%", 0.98, {"milho": 0.21, "sorgo": 0.77}, {"milho": 453.25, "sorgo": 1750.00}),
 (("feijao_caupi", "sorgo"), "caupi 75% + sorgo 25%", 0.87, {"feijao_caupi": 0.38, "sorgo": 0.49}, {"feijao_caupi": 378.00, "sorgo": 1104.75}),
 (("feijao_caupi", "sorgo"), "caupi 50% + sorgo 50%", 1.28, {"feijao_caupi": 0.27, "sorgo": 1.01}, {"feijao_caupi": 267.50, "sorgo": 2284.50}),
 (("feijao_caupi", "sorgo"), "caupi 25% + sorgo 75%", 1.35, {"feijao_caupi": 0.26, "sorgo": 1.09}, {"feijao_caupi": 262.25, "sorgo": 2461.25}),
]
for par, arr, ler, parc, cons in tav:
    R.append(L("tavora2007", componentes="|".join(par), par_a=par[0], par_b=par[1], arranjo=arr, ler_min=ler, ler_max=ler, ler_parciais=parc,
               prod_solteira_kg_ha={k: SOL_T[k] for k in par}, prod_consorciada_kg_ha=cons, pagina_tabela="Tabela 7, p. 315 (rendimentos: Tabelas 2, 4, 6, p. 313-315)",
               observacao="Séries de substituição (proporção da área de cada cultura), mesma data de semeadura, espaçamento 0,8x0,2 m (milho, caupi) e 0,8x0,1 m (sorgo). Uma safra, uma localidade."))

# ---------------- Pinto 2011 (mamona, Quixadá 2010): LER Tabela 2 (p.79), ATER (REAT) e CET Tabela 3 (p.80)
SOL_P = {"mamona": 547.91, "gergelim": 640.10, "algodao": 863.28, "milho": 688.80, "feijao_caupi": 656.25}
pm = [("gergelim", 1.03, 0.23, 0.80, 101.04, 535.67, 0.46, 0.18), ("algodao", 0.95, 0.38, 0.57, 207.29, 487.50, 0.47, 0.21),
      ("milho", 1.10, 0.47, 0.63, 255.21, 413.54, 0.54, 0.29), ("feijao_caupi", 0.91, 0.23, 0.68, 126.04, 445.83, 0.39, 0.15)]
for c, ler, pa, pb, ya, yb, ater, lec in pm:
    par = tuple(sorted(("mamona", c)))
    R.append(L("pinto2011mamona", componentes="|".join(par), par_a=par[0], par_b=par[1],
               arranjo="mamona (BRS Energia, 10.000 pl/ha, 1x1 m) + consorte na entrelinha (0,5 m)", densidade="mamona 10.000; gergelim 80.000; algodão 40.000; milho 40.000; caupi 40.000 pl/ha",
               ler_min=ler, ler_max=ler, ler_parciais={"mamona": pa, c: pb}, prod_solteira_kg_ha={"mamona": SOL_P["mamona"], c: SOL_P[c]},
               prod_consorciada_kg_ha={"mamona": ya, c: yb}, ater=ater, lec=lec, pagina_tabela="Tabela 2 p. 79; Tabela 3 p. 80",
               observacao="Safra seca (287,8 mm de mar a jun). ATER (REAT) < 1 em todos os pares e CET < 0,25 em três de quatro (o autor chama de falta de complementaridade). Valor 'ater' como publicado."))

# ---------------- Pinto 2011 (girassol x caupi, Quixadá 2009): Tabela 3 (p.71-72) e Tabela 4 (p.72)
SOL_G = {"girassol": 1414.06, "feijao_caupi": 1002.18}
for arr, ler, pa, pb, ya, yb in [("girassol 75% + caupi 25%", 1.28, 0.62, 0.67, 863.28, 661.87), ("girassol 50% + caupi 50%", 1.02, 0.51, 0.52, 694.53, 497.18),
                                 ("girassol 25% + caupi 75%", 0.59, 0.34, 0.25, 482.81, 248.43)]:
    R.append(L("pinto2011girassol", componentes="feijao_caupi|girassol", par_a="feijao_caupi", par_b="girassol", arranjo=arr + " (séries de substituição)",
               densidade="girassol 0,8x0,25 m; caupi 0,8x0,5 m", ler_min=ler, ler_max=ler, ler_parciais={"girassol": pa, "feijao_caupi": pb},
               prod_solteira_kg_ha=SOL_G, prod_consorciada_kg_ha={"girassol": ya, "feijao_caupi": yb}, pagina_tabela="Tabela 3 (rendimentos) e Tabela 4 (UET), p. 71-72",
               observacao="Uma safra, uma localidade; chuva alta no ano (928,6 mm)."))

# ---------------- Furtado 2012 (mamona, Pombal): Tabela 5 (p.161)
SOL_F = {"IAC2028": 826.0, "Nordestina": 386.7, "feijao_caupi": 250.0, "gergelim": 1674.0}
for cult, c, ler, pa, pb, ya, yb in [("IAC 2028", "feijao_caupi", 1.30, 0.79, 0.52, 657.3, 129.3), ("IAC 2028", "gergelim", 0.80, 0.52, 0.28, 431.5, 473.4),
                                     ("BRS Nordestina", "feijao_caupi", 1.51, 0.94, 0.57, 363.9, 143.5), ("BRS Nordestina", "gergelim", 1.37, 0.91, 0.46, 353.5, 777.5)]:
    k = "IAC2028" if "IAC" in cult else "Nordestina"
    par = tuple(sorted(("mamona", c)))
    R.append(L("furtado2012", componentes="|".join(par), par_a=par[0], par_b=par[1], arranjo=f"mamona {cult} (3 fileiras a 2 m) + 2 fileiras do consorte na entrelinha, semeado 15 dias depois",
               densidade="mamona 5.000 (Nordestina) ou 10.000 (IAC 2028 solteira) pl/ha; caupi 40.000; gergelim 200.000", ler_min=ler, ler_max=ler,
               ler_parciais={"mamona": pa, c: pb}, prod_solteira_kg_ha={"mamona_" + k: SOL_F[k], c: SOL_F[c]}, prod_consorciada_kg_ha={"mamona_" + k: ya, c: yb},
               pagina_tabela="Tabela 5, p. 161", observacao="Uma safra, um local. O texto diz que o consórcio IAC 2028 + gergelim reduziu 20% (LER 0,80)."))

# ---------------- Azevedo 2007 (Monteiro-PB): médias marginais por fator (Tabelas 4-6, p.152-153); UET total
for c, lo, hi, arr, sol in [("sorgo", 1.23, 1.54, "mamona 1.250-5.000 pl/ha + sorgo 10.000-40.000 pl/ha, fileiras alternadas, modelo aditivo (Exp. I)", {"mamona": 1393.75, "sorgo": 1615.05}),
                            ("milho", 0.97, 1.48, "mamona 1.250-5.000 pl/ha + milho 5.000-20.000 pl/ha (Exp. II)", {"mamona": 766.38, "milho": 2299.75}),
                            ("feijao_caupi", 1.13, 1.50, "mamona 1.250-5.000 pl/ha + caupi 10.000-40.000 pl/ha (Exp. III)", {"mamona": 657.13, "feijao_caupi": 691.38})]:
    par = tuple(sorted(("mamona", c)))
    R.append(L("azevedo2007", componentes="|".join(par), par_a=par[0], par_b=par[1], arranjo=arr, ler_min=lo, ler_max=hi,
               prod_solteira_kg_ha=sol, pagina_tabela="Tabelas 4-6, p. 152-153 (médias marginais por população; 2 anos)",
               observacao=f"Faixa = menor e maior UET total entre as médias marginais por população de mamona e do consorte (não são parcelas individuais). Texto p. 154-155: maior UET (1,48) com a maior população de mamona nos experimentos II e III."))

# ---------------- Corrêa, Távora & Pitombeira (resumo)
R.append(L("tavora2007", id_estudo="correa2008", componentes="feijao_caupi|mamona|sorgo", par_a="", par_b="",
           arranjo="mamona (BRS 149 Nordestina e BRS 188 Paraguaçu) com caupi e com sorgo granífero", ler_min=1.08, ler_max=1.45,
           fonte="Corrêa, Távora & Pitombeira. Comportamento de cultivares de mamona em sistemas de cultivo isolados e consorciados com caupi e sorgo granífero. Revista Ciência Agronômica 37(2) (a página do periódico lista 2006 e 2008)",
           url_aberta="https://periodicos.ufc.br/revistacienciaagronomica/article/view/83702", acesso="RESUMO (a ferramenta de leitura devolveu só o resumo; PDF completo não aberto)",
           local="Quixadá", uf="CE", semiarido="sim", anos="não lido", regime="não lido", chuva_mm_periodo="", tipo_evidencia="resumo_apenas", entra_na_faixa="nao",
           pagina_tabela="resumo (sem página)", observacao="Resumo: 'o consórcio reduziu tanto a produtividade da mamona como das consorciadas'; 'UET variou de 1,08 a 1,45' (tratamentos de mamona x caupi e mamona x sorgo misturados no resumo; arranjo, produtividades e parciais não lidos)."))

# ---------------- Albuquerque & Rao 1997 (palma): Tabela 3 (p.649)
for c, v1, v2, vm, ycact in [("feijao_caupi", 1.48, 1.82, 1.65, "palma 12,1 (isolada) vs 6,6 (c/ caupi) no 1º corte; 8,2 vs 8,8 no 2º; média 10,2 vs 7,7 t MS/ha/corte"),
                             ("sorgo", 1.27, 1.49, 1.38, "palma 12,1 (isolada) vs 4,7 (c/ sorgo) no 1º corte; 8,2 vs 6,9 no 2º; média 10,2 vs 5,8 t MS/ha/corte")]:
    par = tuple(sorted(("palma_forrageira", c)))
    R.append(L("albuquerque1997", componentes="|".join(par), par_a=par[0], par_b=par[1],
               arranjo="palma (espaçamentos 1x1 a 3x1x0,5 m) com 1 fileira dupla do consorte entre fileiras da palma; palma cortada a cada 3 anos",
               densidade="caupi 40.000 e sorgo 133.000 pl/ha (desbaste)", ler_min=v1, ler_max=v2, ler_parciais={"media_dos_dois_triênios": vm},
               prod_consorciada_kg_ha=ycact, pagina_tabela="Tabela 3, p. 649", observacao=f"LER do 1º triênio {v1}, 2º triênio {v2}, média {vm}. O LER usa forragem da palma (t MS) + grão do consorte, com palma como cultura perene (ciclo de corte trienal) e consorte anual: o LER não corrige o tempo de ocupação da terra."))
R.append(L("albuquerque1997", id_estudo="albuquerque1983", componentes="feijao_caupi|palma_forrageira|sorgo", par_a="", par_b="",
           arranjo="palma (5 espaçamentos) com sorgo granífero e com feijão macássar entre fileiras (resultados preliminares, 1º ano)",
           fonte="Albuquerque, Rao & Bernardino 1983. Consórcio da palma (Opuntia ficus-indica Mill.) com sorgo e feijão macássar no sertão do Sub-Médio São Francisco (resultados preliminares). Anais I Reunião sobre Culturas Consorciadas no Nordeste, Teresina",
           url_aberta="https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/131393/1/ID16918Ireuniaosobreculturasconsorciadasnonordestep172183..pdf", acesso="PDF aberto; OCR muito ruim, só o resumo foi lido com segurança",
           anos="1982/83", ler_min="", ler_max="", tipo_evidencia="sem_LER", entra_na_faixa="nao", pagina_tabela="resumo (p. 172)",
           observacao="Resumo: em volume da palma e peso de grãos NÃO houve vantagem do consórcio; só considerando a área foliar da palma houve vantagem de 24% (sorgo) e 33% (caupi). Autores: resultados preliminares, sem conclusão sobre viabilidade. Sem LER de produção."))

# ---------------- Távora (1990) mandioca: Tabela 8 (p.6)
for cult, c, v9, v20 in [("Saracura", "feijao_caupi", 1.49, 0.79), ("Jaburu", "feijao_caupi", 1.69, 0.99), ("Saracura", "amendoim", 1.35, 0.89), ("Jaburu", "amendoim", 1.55, 1.21)]:
    par = tuple(sorted(("mandioca", c)))
    for ciclo, v in (("1º ciclo (9 meses, 1987)", v9), ("2º ciclo (20 meses, 1988, após poda)", v20)):
        R.append(L("tavora1990mandioca", componentes="|".join(par), par_a=par[0], par_b=par[1], arranjo=f"mandioca {cult} em fileira dupla (2,0x0,6x0,6 m) + consorte em fileiras duplas alternadas; {ciclo}",
                   ler_min=v, ler_max=v, pagina_tabela="Tabela 8, p. 6",
                   observacao="Consórcio vantajoso só no 1º ciclo; no 2º ciclo, após poda, os autores 'desaconselham' (exceto Jaburu+amendoim, 1,21). 'semiarido=nao_confirmado': Pacajus fica no litoral leste do CE; o artigo não classifica o clima."))

# ---------------- Essentia 2017 (Bela Cruz): Tabela 7 (PDF p.18)
R.append(L("essentia2017", componentes="feijao_caupi|milho", par_a="feijao_caupi", par_b="milho", arranjo="milho + feijão-caupi (fileiras 2 e 4 do milho substituídas pelo feijão)", densidade="espaçamento 0,5x0,5 m (cultivo solteiro)",
           ler_min=1.34, ler_max=1.34, ler_parciais={"milho": 0.64, "feijao_caupi": 0.70}, pagina_tabela="Tabela 7 (PDF p. 18)",
           semiarido="sim", entra_na_faixa="sim", observacao=("Local classificado pelo próprio artigo como Bshw semiárido (litoral norte do CE), ano com 680 mm (2/3 da média). Inconsistência interna do artigo: o texto diz "
                       "'UET de 1,28 a 1,54' e o resumo diz 1,9 para milho+feijão+mandioca, mas a Tabela 7 traz 0,87 a 1,98; usei a tabela. 1º ano da mandioca (sem raiz colhida).")))
R.append(L("essentia2017", componentes="mandioca|milho", par_a="mandioca", par_b="milho", arranjo="milho + mandioca", ler_min=0.98, ler_max=0.98, ler_parciais={"milho": 0.98, "mandioca": 0.00},
           pagina_tabela="Tabela 7 (PDF p. 18)", entra_na_faixa="nao", observacao="Parcial da mandioca = 0,00 porque a raiz não foi colhida no 1º ano: o valor não mede o consórcio inteiro. Fora da faixa."))
R.append(L("essentia2017", componentes="feijao_caupi|mandioca", par_a="feijao_caupi", par_b="mandioca", arranjo="feijão + mandioca", ler_min=0.87, ler_max=0.87, ler_parciais={"feijao_caupi": 0.87, "mandioca": 0.00},
           pagina_tabela="Tabela 7 (PDF p. 18)", entra_na_faixa="nao", observacao="Mesmo problema: mandioca sem colheita de raiz no 1º ano. Fora da faixa."))
R.append(L("essentia2017", componentes="feijao_caupi|mandioca|milho", par_a="", par_b="", arranjo="milho + feijão + mandioca", ler_min=1.98, ler_max=1.98,
           ler_parciais={"milho": 1.34, "feijao_caupi": 0.64, "mandioca": 0.00}, pagina_tabela="Tabela 7 (PDF p. 18)", entra_na_faixa="nao",
           observacao="Três culturas; mandioca sem raiz no 1º ano. O resumo do artigo diz 1,9 e a tabela 1,98."))

# ---------------- Barreto & Serpa 1986 (milho x feijão comum, Poço Verde-SE): Tabela 1 (p.6)
for p2o5, ler, pm_, pf in [(0, 0.85, 0.56, 0.29), (100, 1.27, 0.87, 0.40), (200, 1.29, 0.85, 0.44), (300, 1.14, 0.67, 0.47)]:
    R.append(L("barreto1986", componentes="feijao_comum|milho", par_a="feijao_comum", par_b="milho", arranjo=f"milho + feijão comum (IPA 74/19), uma fileira de milho para três de feijão (leitura parcial do OCR), {p2o5} kg/ha de P2O5",
               densidade="milho 50.000 pl/ha (solteiro); feijão 0,50 m entre fileiras", ler_min=ler, ler_max=ler, ler_parciais={"milho": pm_, "feijao_comum": pf}, pagina_tabela="Tabela 1, p. 6",
               observacao=("Sem P2O5 o LER foi < 1 (0,85). Parcial do milho em 200 kg/ha saiu '0,05' no OCR; 0,85 = 1,29 - 0,44 (inferido pela soma, marcado)." if p2o5 == 200 else
                           "Sem P2O5 o LER foi < 1 (0,85)." if p2o5 == 0 else "Adubação fosfatada muda o LER.")))
R[-2]["conferencia"] = "parcial do milho inferido por soma (OCR ilegível)"

# ---------------- Irrigados (Petrolina): fora da faixa
for lab, ler, pm_, pf, ym_s, ym_c, yf_s, yf_c in [("déficit na 1ª fase", 1.00, 0.51, 0.49, 1387, 712, 1258, 615), ("déficit na 2ª fase", 1.01, 0.57, 0.44, 875, 503, 1308, 564), ("controle (sem déficit)", 0.88, 0.40, 0.48, 1948, 788, 1400, 660)]:
    R.append(L("tavora_lopes1990", componentes="feijao_caupi|milho", par_a="feijao_caupi", par_b="milho", arranjo=f"milho + caupi, {lab}", ler_min=ler, ler_max=ler,
               ler_parciais={"milho": pm_, "feijao_caupi": pf}, prod_solteira_kg_ha={"milho": ym_s, "feijao_caupi": yf_s}, prod_consorciada_kg_ha={"milho": ym_c, "feijao_caupi": yf_c},
               pagina_tabela="Tabelas 6 e 7, p. 1020", entra_na_faixa="nao", observacao="Irrigado com déficit imposto: não é sequeiro. Texto: sem vantagem do consórcio sob escassez de água em qualquer fase."))
R.append(L("morgado1985", componentes="feijao_caupi|milho", par_a="feijao_caupi", par_b="milho", arranjo="milho 10.000 pl/ha + caupi (menor população de milho), lâminas ≥ 200 mm", ler_min=1.10, ler_max=1.20,
           pagina_tabela="Fig. 4 e texto, p. 52-53", entra_na_faixa="nao", observacao="Texto: UET total > 1,0 em todas as lâminas; 20% (1,20) entre 200 e 280 mm e 10% (1,10) abaixo de 200 mm. Só o texto foi lido (gráfico não)."))
R.append(L("morgado1985", componentes="feijao_caupi|milho", par_a="feijao_caupi", par_b="milho", arranjo="populações maiores de milho (m2 e m3) + caupi", ler_min="", ler_max=1.00,
           pagina_tabela="texto p. 52-53", entra_na_faixa="nao", observacao="Texto: com as populações maiores de milho 'o consórcio não mostrou nenhuma vantagem'; UET total 'não foi maior que 1,0 com nenhuma lâmina' na população m2. Valor numérico não lido (gráfico). Resumo: vantagem só com a menor população de milho e ≥ 200 mm."))
R.append(L("morgado1985", id_estudo="rao_morgado1984_citado", componentes="feijao_caupi|milho", par_a="feijao_caupi", par_b="milho", arranjo="síntese de 34 experimentos no Nordeste (citada por Morgado & Rao 1985)", ler_min=1.41, ler_max=1.41,
           fonte="Rao & Morgado 1984 (síntese de 34 experimentos, NÃO aberta); citada em Morgado & Rao 1985, Pesq. agropec. bras. 20(1):45-55", acesso="citação secundária (original não aberto)",
           anos="vários", local="Nordeste (vários)", uf="NE", semiarido="nao_confirmado", regime="não informado", tipo_evidencia="citacao_secundaria", entra_na_faixa="nao",
           pagina_tabela="Introdução, p. 46", observacao="Texto: 'o consórcio milho x caupi produziu 41% mais do que as culturas isoladas' (lido como LER médio 1,41; interpretação nossa)."))

# ---------------- Beltrão 1986 (algodão x caupi, Gurinhém-PB): só resumo/texto
for cv, ler, obs in [("TVx 1836-013J", 1.56, "Resumo: LER 1,56; algodão -13,8%; caupi -31,9% (904 -> 615 kg/ha); renda líquida +33,41% sobre o algodão solteiro."),
                     ("Pitiúba", 1.17, "Texto: 'algodão + caupi cv. Pitiúba teria sido 17% mais eficiente que o monocultivo'; essa cultivar reduziu o algodão em 31,1% (resumo PT) ou 33,1% (resumo EN): divergência no artigo. Renda bruta do consórcio foi menor que a do algodão solteiro (sem diferença estatística).")]:
    R.append(L("beltrao1986", componentes="algodao|feijao_caupi", par_a="algodao", par_b="feijao_caupi", arranjo=f"algodão herbáceo CNPA 2H + caupi {cv}", ler_min=ler, ler_max=ler,
               pagina_tabela="resumo p. 271; texto p. 282-283 (tabelas ilegíveis)", entra_na_faixa="nao", observacao=obs + " Gurinhém fica no Agreste paraibano: semiárido não confirmado."))

# ---------------- Diaconia (levantamentos de agricultores, SEM testemunha pareada): fora da faixa
R.append(L("diaconia_se2022", componentes="algodao|feijao_caupi|gergelim|milho", par_a="", par_b="", arranjo="algodão + feijão de corda + gergelim + milho (faixas alternadas), 5 propriedades", ler_min=1.01, ler_max=2.25,
           ler_parciais={"consorcios_1_a_5": "2,25; 1,42; 1,01; 1,17; 2,05"}, tipo_evidencia="levantamento_sem_testemunha", entra_na_faixa="nao", pagina_tabela="Tabela 1, p. 4",
           observacao="Produtividade solteira = média municipal do IBGE (PAM: milho 2003-2018, feijão de corda 2003-2018, algodão 2015) e gergelim da Embrapa Algodão 2009, NÃO uma testemunha na mesma área/safra. Produção do consórcio vem de caderno de campo das famílias. O LER mistura 4 culturas; milho em consórcio (480 kg/ha) acima da média IBGE (260). Evidência fraca."))
R.append(L("diaconia_pb2022", componentes="algodao|feijao_caupi|gergelim|milho", par_a="", par_b="", arranjo="algodão + feijão de corda + gergelim + milho, 5 famílias", ler_min=1.20, ler_max=3.21,
           ler_parciais={"familias_F1_a_F5": "2,51; 2,03; 3,21; 1,63; 1,20"}, tipo_evidencia="levantamento_sem_testemunha", entra_na_faixa="nao", pagina_tabela="Tabela 1, p. 4",
           observacao="Mesmo método (monocultivo = média oficial, não testemunha). LER 3,21 é implausível como ganho de área; ver docs/29."))

# ---------------- Pereira 2015 (Piauí): valores > 2 com 2 culturas; marcado como não confiável
for par, rng, ex in [(("gergelim", "milho"), (2.2, 2.6), "gergelim + milho"), (("feijao_caupi", "gergelim"), (2.1, 2.6), "gergelim + feijão vigna"), (("feijao_caupi", "milho"), (1.9, 2.6), "milho + feijão vigna")]:
    R.append(L("pereira2015", componentes="|".join(par), par_a=par[0], par_b=par[1], arranjo=f"{ex}, arranjos 1:1, 1:2, 2:1, 2:2 (fileiras)", densidade="1,00 m entre fileiras, 10 pl/m", ler_min=rng[0], ler_max=rng[1],
               pagina_tabela="Tabela 2, p. 5", tipo_evidencia="experimento_pareado", entra_na_faixa="nao",
               conferencia="valor > 2 com 2 culturas: improvável como LER convencional",
               observacao="Média do experimento 2,07 com testemunhas = 1,0. A fórmula (1) do artigo não saiu legível no PDF e as produtividades não são apresentadas. Valores acima de 2 com duas culturas só ocorrem se as duas parciais passarem de 1 em média, o que é incomum: tratar como NÃO confiável até conferir o método. Fora da faixa."))

# ---------------- Morais 2018 (beterraba): irrigado, hortaliça
R.append(L("morais2018", componentes="beterraba|feijao_caupi", par_a="beterraba", par_b="feijao_caupi", arranjo="beterraba + caupi-hortaliça, fileiras 2:2, 3:3 e 4:4; adubação verde com flor-de-seda (20-65 t/ha MS)", ler_min=1.03, ler_max=1.22,
           ler_parciais={"2:2": 1.16, "3:3": 1.03, "4:4": 1.05, "máximo (65 t/ha de flor-de-seda)": 1.22}, pagina_tabela="Tabela 6, p. 441; texto p. 440",
           entra_na_faixa="nao", observacao="Hortaliça irrigada, fora do escopo do motor (beterraba não está na tabela de culturas)."))


# ---------------- abertos SEM LER (registrados para a lacuna ficar visível)
R.append(L("silva2013", componentes="algodao|gergelim", par_a="algodao", par_b="gergelim", arranjo="algodão (BRS Aroeira e BRS 04-1515) + gergelim BRS Seda", ler_min="", ler_max="",
           tipo_evidencia="sem_LER", entra_na_faixa="nao", pagina_tabela="resumo, p. 104", observacao="Não calcula LER. Resumo: consórcios algodão+gergelim e algodão+amendoim 'não foram vantajosos, pois a cultura principal foi influenciada negativamente pelas intercalares'."))
R.append(L("silva2013", componentes="algodao|amendoim", par_a="algodao", par_b="amendoim", arranjo="algodão + amendoim BR1", ler_min="", ler_max="",
           tipo_evidencia="sem_LER", entra_na_faixa="nao", pagina_tabela="resumo, p. 104", observacao="Não calcula LER (só dados do algodão). Mesmo resumo: 'não foram vantajosos' para o algodão."))
R.append(L("pinto2013girassol_mamona", componentes="girassol|mamona", par_a="girassol", par_b="mamona", arranjo="mamona x girassol em configurações de fileira (2Ma:2Gi etc.)", ler_min="", ler_max="",
           tipo_evidencia="sem_LER", entra_na_faixa="nao", pagina_tabela="Tabelas 5-10", observacao="Aberto: não calcula LER; usa soma das produtividades. Outro artigo do mesmo grupo (Rev. Bras. Ciências Agrárias 7 supl.:728-736, 2012, redalyc 119025455004) também aberto e sem LER."))

# ---------------------------------------------------------------- conferência e escrita
def _fmt(v):
    if isinstance(v, dict):
        return "; ".join(f"{k}={x}" for k, x in v.items())
    return "" if v is None else str(v)


def conferir(r: dict) -> str:
    msgs = []
    pa = r.get("ler_parciais")
    if isinstance(pa, dict) and all(isinstance(x, (int, float)) for x in pa.values()) and r["ler_min"] == r["ler_max"] and r["ler_min"] != "":
        s = sum(pa.values())
        if abs(s - float(r["ler_min"])) > 0.03:
            msgs.append(f"soma dos parciais {s:.2f} != total {r['ler_min']}")
    sol, con = r.get("prod_solteira_kg_ha"), r.get("prod_consorciada_kg_ha")
    if isinstance(sol, dict) and isinstance(con, dict) and isinstance(pa, dict):
        for k, v in con.items():
            ks = k if k in sol else next((x for x in sol if x.startswith(k)), None)
            if ks in sol and k in pa and sol[ks]:
                calc = v / sol[ks]
                if abs(calc - pa[k]) > 0.03:
                    msgs.append(f"{k}: {v}/{sol[ks]}={calc:.2f} != parcial publicado {pa[k]}")
    return "; ".join(msgs)


def main():
    for i, r in enumerate(R, 1):
        r["id_linha"] = f"L{i:03d}"
        c = conferir(r)
        if c:
            r["conferencia"] = (r.get("conferencia", "") + "; " if r.get("conferencia") else "") + c
        for k in COLUNAS:
            r.setdefault(k, "")
    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    CONF_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, extrasaction="ignore")
        w.writeheader()
        for r in R:
            w.writerow({k: _fmt(r.get(k)) for k in COLUNAS})
    with open(CONF_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id_linha", "id_estudo", "arranjo", "conferencia"])
        for r in R:
            if r.get("conferencia"):
                w.writerow([r["id_linha"], r["id_estudo"], r["arranjo"], r["conferencia"]])
    print(f"{len(R)} linhas -> {SAIDA_CSV}")
    print(f"{sum(1 for r in R if r.get('conferencia'))} com observação de conferência -> {CONF_CSV}")


if __name__ == "__main__":
    main()
