from curar import Curadoria

M = "file://data/plano_staging/material_antigravity/fao_table12.html"
FAO = "FAO. Irrigation and Drainage Paper 56 (Crop evapotranspiration), Tabela 12: coeficientes de cultura Kc de valor único"
CTX = ("climas sub-úmidos (UR mín ~45%, vento ~2 m/s); para clima semiárido a própria FAO manda ajustar. "
       "Texto das notas de rodapé não foi baixado. URL de origem não registrada pelo agente que baixou o arquivo")
c = Curadoria(6)
G = {  # linha do grupo (Kc inicial vem do grupo)
    "cereais": "i. Cereals | 0.3 | 1.15 | 0.4 |",
    "oleaginosas": "h. Oil Crops | 0.35 | 1.15 | 0.35 |",
    "fibras": "g. Fibre Crops | 0.35 |  |  |",
    "leguminosas": "e. Legumes (Leguminosae) | 0.4 | 1.15 | 0.55 |",
}


def kc(cultura, grupo_ini, ini, linha, mid, fim, extra=""):
    c.add(cultura, "kc_inicial", ini, "", "fao_table12", FAO, M, 1, G[grupo_ini] if grupo_ini else linha, "valor do GRUPO da tabela (a linha da cultura não o repete); " + CTX)
    c.add(cultura, "kc_medio", mid, "", "fao_table12", FAO, M, 1, linha, extra + CTX)
    c.add(cultura, "kc_final", fim, "", "fao_table12", FAO, M, 1, linha, extra + CTX)


kc("milho", "cereais", "0.3", "Maize, Field (grain) (field corn) |  | 1.20 | 0.60-0.35 11 | 2", "1.20", "0.60-0.35 (nota 11)", "milho grão; ")
kc("sorgo", "cereais", "0.3", "- grain |  | 1.00-1.10 | 0.55 | 1-2", "1.00-1.10", "0.55", "sorgo granífero; ")
kc("milheto", "cereais", "0.3", "Millet |  | 1.00 | 0.30 | 1.5", "1.00", "0.30")
kc("girassol", "oleaginosas", "0.35", "Sunflower |  | 1.0-1.15 9 | 0.35 | 2.0", "1.0-1.15 (nota 9)", "0.35")
kc("gergelim", "oleaginosas", "0.35", "Sesame |  | 1.10 | 0.25 | 1.0", "1.10", "0.25")
kc("mamona", "oleaginosas", "0.35", "Castorbean ( Ricinus ) |  | 1.15 | 0.55 | 0.3", "1.15", "0.55")
kc("amendoim", "leguminosas", "0.4", "Groundnut (Peanut) |  | 1.15 | 0.60 | 0.4", "1.15", "0.60")
kc("feijao_caupi", "leguminosas", "0.4", "Green Gram and Cowpeas |  | 1.05 | 0.60-0.35 6 | 0.4", "1.05", "0.60-0.35 (nota 6)")
kc("feijao_comum", "leguminosas", "0.4", "Beans, dry and Pulses | 0.4 | 1.15 2 | 0.35 | 0.4", "1.15 (nota 2)", "0.35", "feijão seco; ")
kc("algodao", "fibras", "0.35", "Cotton |  | 1.15-1.20 | 0.70-0.50 | 1.2-1.5", "1.15-1.20", "0.70-0.50")
# mandioca tem linhas por ano
c.add("mandioca", "kc_inicial_ano1", "0.3", "", "fao_table12", FAO, M, 1, "- year 1 | 0.3 | 0.80 3 | 0.30 | 1.0", "mandioca no 1º ano; " + CTX)
c.add("mandioca", "kc_medio_ano1", "0.80 (nota 3)", "", "fao_table12", FAO, M, 1, "- year 1 | 0.3 | 0.80 3 | 0.30 | 1.0", "mandioca no 1º ano; " + CTX)
c.add("mandioca", "kc_final_ano1", "0.30", "", "fao_table12", FAO, M, 1, "- year 1 | 0.3 | 0.80 3 | 0.30 | 1.0", "mandioca no 1º ano; " + CTX)

c.add("girassol", "fase_critica_deficit_hidrico", "de 10 a 15 dias antes do início do florescimento até 10 a 15 dias após o fim da floração", "", "girassol_cir48",
      "Embrapa Meio-Norte. Manejo da cultura do girassol no Meio-Norte do Brasil. Circular Técnica 48, Teresina, dez/2008",
      "file://data/plano_staging/material_antigravity/girassol_cir48.pdf", 2,
      "a fase mais crítica ao deficit hídrico é o período compreendido entre 10 e 15 dias antes do início do florescimento e 10 a 15 dias após o final da floração",
      "Meio-Norte (PI/MA)")
c.add("feijao_caupi", "fase_critica_deficit_hidrico", "floração e enchimento de grãos", "", "embrapa_meionorte_feijaocaupi_produtor_pergunta",
      "Embrapa Meio-Norte. Feijão-caupi: o produtor pergunta, a Embrapa responde",
      "file://docs_rag/embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", 26,
      "a fase fenológica de floração e enchimento de grãos da cultura, considerada a fase mais sensível ao deficit hídrico", "Meio-Norte")
for cult in ("palma_forrageira", "guandu", "crotalaria_juncea", "mucuna", "feijao_de_porco"):
    c.lacuna(cult, "kc_inicial_medio_final", "a cultura não consta na Tabela 12 da FAO-56 (conferido: nenhuma linha correspondente no arquivo baixado)")
c.gravar()
