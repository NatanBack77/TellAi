from curar import Curadoria

M = "file://data/plano_staging/material_antigravity/"
A = "file://docs_rag/"
c = Curadoria(5)

SORGO = "Embrapa Milho e Sorgo. Cultivo do Sorgo. Sistema de Produção, 9ª ed., jul/2015 (seção Plantio)"
c.add("sorgo", "espacamento_entre_linhas", "40 a 90", "cm", "sorgo_plantio", SORGO, M + "sorgo_plantio.pdf", 7,
      "espaçamento entre linhas, variando de 40 cm a 90 cm, em função da região", "sorgo granífero; fonte nacional")
c.add("sorgo", "densidade_plantas_ha", "140 a 170 mil", "plantas/ha", "sorgo_plantio", SORGO, M + "sorgo_plantio.pdf", 6,
      "pode variar de 140 a 170 mil plantas por hectare na colheita", "sorgo granífero; estande final")
c.add("sorgo", "profundidade_semeadura", "mais rasa com boa umidade no solo; aumenta se a umidade decresce", "", "sorgo_plantio", SORGO,
      M + "sorgo_plantio.pdf", 4, "Com bom nível de umidade no solo, a semeadura poderá ser mais rasa",
      "a fonte não dá valor em cm nesta passagem")
INT = "Embrapa. Instruções Técnicas, set/2016, sobre sorgo (arquivo sorgo_int127.pdf; título e autoria não constam no PDF)"
c.add("sorgo", "semente_kg_ha", "6 a 10", "kg/ha", "sorgo_int127", INT, M + "sorgo_int127.pdf", 1,
      "o gasto com sementes no plantio é de 6 kg a 10 kg por hectare", "texto trata de plantio no Nordeste; tipo de sorgo não identificado")
c.add("sorgo", "espacamento_linha_x_cova", "0,80 m entre linhas x 0,20 m entre covas, 3 sementes por cova", "", "sorgo_int127", INT,
      M + "sorgo_int127.pdf", 1, "0,80 m (80 cm) x espaçamento entre covas de 0,20 m (20 cm), colocando-se três sementes por cova",
      "Nordeste; tipo de sorgo não identificado")

GER = "Embrapa Algodão. Cultivo do Gergelim (sistema de produção)"
c.add("gergelim", "semente_kg_ha", "1,5 a 3,5", "kg/ha", "Cultivo-do-Gergelim", GER, M + "Cultivo-do-Gergelim.pdf", 9,
      "A quantidade de sementes por hectare varia entre de 1,5 kg a 3,5 kg", "varia com espaçamento e densidade")
c.add("gergelim", "profundidade_semeadura", "2", "cm", "Cultivo-do-Gergelim", GER, M + "Cultivo-do-Gergelim.pdf", 9,
      "em sulcos rasos contínuos ou em covas rasas, à profundidade de 2 cm", "")
c.add("gergelim", "espacamento_cultivar_ramificada", "0,80 a 1,0 m entre fileiras x 0,20 m entre plantas", "", "Cultivo-do-Gergelim", GER,
      M + "Cultivo-do-Gergelim.pdf", 10, "recomenda-se o espaçamento de 0,80 m a 1,0 m entre fileiras e de 0,20 m entre plantas", "cultivares ramificadas")
c.add("gergelim", "espacamento_cultivar_nao_ramificada", "0,60 a 0,70 m entre fileiras x 0,10 m entre plantas", "", "Cultivo-do-Gergelim", GER,
      M + "Cultivo-do-Gergelim.pdf", 10, "usar o espaçamento de 0,60 m a 0,70 m entre fileiras com 0,10 m entre plantas", "cultivares não ramificadas")
c.add("gergelim", "densidade_plantas_ha", "cerca de 100 mil", "plantas/ha", "Cultivo-do-Gergelim", GER, M + "Cultivo-do-Gergelim.pdf", 10,
      "em torno de 100 mil plantas por ha", "exige desbaste; fonte manda raleamento")

AM = "Embrapa Algodão. Recomendações Técnicas para o Cultivo do Amendoim em Pequenas Propriedades Agrícolas do Nordeste Brasileiro. Circular Técnica 102"
c.add("amendoim", "espacamento_sequeiro", "0,70 m entre linhas x 0,20 m entre plantas", "", "amendoim_cirtec102", AM, M + "amendoim_cirtec102.pdf", 2,
      "espaçamento convencional de amendoim cultivado em regime de sequeiro é de 0,70 m x 0,20 m", "Nordeste, sequeiro")
c.add("amendoim", "semente_kg_ha", "60 a 65", "kg/ha", "amendoim_cirtec102", AM, M + "amendoim_cirtec102.pdf", 2,
      "são necessários entre 60 e 65 kg/ha de sementes", "cultivares BR 1 e BRS Havana, espaçamento convencional")
c.add("amendoim", "inoculacao_referencia", "200 g de inoculante por 10 kg de sementes", "", "amendoim_cirtec102", AM, M + "amendoim_cirtec102.pdf", 2,
      "200g de inoculante/10kg de sementes", "fonte de nitrogênio biológico")

GIR = "Embrapa Meio-Norte. Manejo da cultura do girassol no Meio-Norte do Brasil. Circular Técnica 48, Teresina, dez/2008"
c.add("girassol", "espacamento", "70 a 90 cm entre linhas x 25 a 36 cm entre plantas", "", "girassol_cir48", GIR, M + "girassol_cir48.pdf", 6,
      "pode variar de 70 cm a 90 cm entre linhas e de 25 cm a 36 cm entre plantas", "Meio-Norte (PI/MA), não é semiárido cearense")
c.add("girassol", "densidade_plantas_ha", "40 a 45 mil", "plantas/ha", "girassol_cir48", GIR, M + "girassol_cir48.pdf", 6,
      "com a população variando entre 40 mil a 45 mil plantas por hectare", "Meio-Norte (PI/MA)")

ALG = "Embrapa Algodão. Cultivo do Algodão Colorido Orgânico na Região Semi-Árida do Nordeste Brasileiro. Documentos 204"
c.add("algodao", "espacamento", "0,75 a 1,00 m entre fileiras, 4 a 12 plantas por metro após desbaste", "", "algodao_doc204", ALG, M + "algodao_doc204.pdf", 25,
      "varia de 0,75 a 1,00 m entre fileiras, com 4 a 12 plantas por metro linear após desbaste", "algodão colorido orgânico, semiárido do Nordeste")
c.add("algodao", "semente_kg_ha", "15 a 25", "kg/ha", "algodao_doc204", ALG, M + "algodao_doc204.pdf", 26,
      "gasto de 15 a 25 kg/ha no espaçamento convencional para a cultura isolada", "plantio mecanizado; algodão colorido orgânico")
c.add("algodao", "profundidade_semeadura", "3 a 5", "cm", "algodao_doc204", ALG, M + "algodao_doc204.pdf", 26,
      "a uma profundidade de 3 a 5 cm", "algodão colorido orgânico")

MAN = "Embrapa Mandioca e Fruticultura. Sistema de Produção de Mandioca no Semiárido"
c.add("mandioca", "espacamento_fileira_simples", "1,0 x 0,5; 1,0 x 0,6 ou 1,0 x 0,8", "m", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 10,
      "recomendam-se os espaçamentos de 1,0 m x 0,5 m, 1,0 m x 0,6 m e 1,0 m x 0,8 m em fileiras simples", "semiárido")

CAU = "Embrapa Meio-Norte. Feijão-caupi: o produtor pergunta, a Embrapa responde"
c.add("feijao_caupi", "espacamento_porte_ereto", "0,5 a 0,6 m entre fileiras", "", "embrapa_meionorte_feijaocaupi_produtor_pergunta", CAU,
      A + "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", 112, "espaçamentos de 0,5 m a 0,6 m entre fileiras", "variedades de porte ereto e semiereto; Meio-Norte")
c.add("feijao_caupi", "sementes_por_metro_consorcio_milho", "6 a 8 sementes de caupi por metro de sulco", "", "embrapa_meionorte_feijaocaupi_produtor_pergunta", CAU,
      A + "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", 144, "para o feijão-caupi, colocam-se de seis a oito sementes por metro de sulco", "consórcio com milho; Meio-Norte")
c.add("feijao_caupi", "densidade_irrigado", "240 mil", "plantas/ha", "embrapa_meionorte_feijaocaupi_produtor_pergunta", CAU,
      A + "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", 136, "BRS Itaim (porte ereto) sob irrigação, é de 240 mil plantas por hectare", "cultivar BRS Itaim, irrigado")
c.add("feijao_caupi", "inoculacao_referencia", "250 g de inoculante comercial por 50 kg de sementes", "", "embrapa_meionorte_feijaocaupi_produtor_pergunta", CAU,
      A + "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", 104, "250 g do produto para cada 50 kg de sementes de feijão-caupi", "dose suficiente para 1 ha, segundo a fonte")

OP = "file://data/plano_staging/fontes_op/"   # PDFs baixados das URLs citadas pelo OpenCode (ver RELATORIO.md)
MIL = "Embrapa Milho e Sorgo. Cultivo do Milho. Sistema de Produção 1, 9. ed."
c.add("milho", "espacamento_convencional_x_reduzido", "convencional 80 a 90 cm entre fileiras; reduzido 45 a 50 cm", "cm", "op_sistema_de_producao_cultivo_do_milho", MIL,
      "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/486917/1/Sistema-de-Producao-Cultivo-do-Milho.pdf", 148,
      "espaçamento reduzido (45 a 50 cm entre fileiras) comparado ao espaçamento convencional (80 a 90 cm)", "fonte nacional, não específica do semiárido")

MLT = "Embrapa Milho e Sorgo. Cultivo do Milheto. Sistema de Produção, 5. ed."
URL_MLT = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/993985/1/Sistema-de-Producao-Cultivo-do-Milheto.pdf"
c.add("milheto", "semente_kg_ha", "8 a 12", "kg/ha", "op_sistema_de_producao_cultivo_do_milheto_p", MLT, URL_MLT, 74,
      "Quantidade de sementes (kg.ha -1 ) 8 a 12 8 a 12", "tabela 2: vale tanto para produção de sementes como de grãos; fonte nacional")
c.add("milheto", "espacamento_e_densidade", "40 cm entre linhas; 150.000 plantas/ha", "", "op_sistema_de_producao_cultivo_do_milheto_p", MLT, URL_MLT, 74,
      "Espaçamento entre linhas (cm) 40 40 Densidade de semeadura (plantas.ha -1 ) 150.000 150.000", "tabela 2; fonte nacional")

MAM = "Embrapa Algodão. O Cultivo Sustentável da Mamona no Semi-Árido Brasileiro"
URL_MAM = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/276142/1/CART01.pdf"
c.add("mamona", "espacamento", "3 m x 1 m, 1 planta por cova (3.333 plantas/ha)", "", "op_cart01", MAM, URL_MAM, 31,
      "melhor espaçamento é 3 m x 1 m (Figuras 19 e 20), 1 planta/cova, em sistema isolado ou consorciado, de sequeiro ou irrigado, ficando a população com 3.333 plantas/ha", "semiárido")
c.add("mamona", "profundidade_semeadura", "2 a 5 (4 a 5 em solo arenoso; mais rasa em solo argiloso)", "cm", "op_cart01", MAM, URL_MAM, 27,
      "profundidade de 2 a 5 cm, colocando-se duas sementes por cova", "semiárido")

FEI = "Embrapa Tabuleiros Costeiros. Informações Técnicas para o Cultivo do Feijoeiro (doc. 181)"
URL_FEI = "http://www.cpatc.embrapa.br/publicacoes_2013/doc_181.pdf"
c.add("feijao_comum", "semente_kg_ha", "20 a 120, conforme cultivar, espaçamento, densidade, poder germinativo e sistema", "kg/ha", "op_doc_181", FEI, URL_FEI, 56,
      "podendo variar de 20 a 120 kg/ha", "Tabuleiros Costeiros; não é semiárido")
c.add("feijao_comum", "plantas_por_metro_de_linha", "8 a 12", "plantas/m", "op_doc_181", FEI, URL_FEI, 57,
      "utiliza-se de 8 a 12 plantas por metro de linha de plantio", "Tabuleiros Costeiros")
c.add("feijao_comum", "densidade_plantas_ha", "200 a 250 mil, após a emergência, plantio solteiro", "plantas/ha", "op_doc_181", FEI, URL_FEI, 57,
      "a lavoura deve ficar com população entre 200 a 250 mil plantas/ha", "Tabuleiros Costeiros")
c.add("feijao_comum", "consorcio_com_milho", "2 a 2,5 m entre linhas de milho com 5 plantas/m, e 3 ou 4 linhas de feijão entre elas", "", "op_doc_181", FEI, URL_FEI, 56,
      "recomenda-se 2 a 2,5 m entre linhas de milho com 5 plantas/m e 3 ou 4 linhas de feijão entre as linhas do milho", "Tabuleiros Costeiros")

PAL = "Embrapa Semiárido. Sistema de Produção de Palma Forrageira para o Estado da Paraíba"
URL_PAL = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1142333/1/Sistema-de-Producao-de-Palma-Forrageira-para-o-Estado-da-Paraiba.pdf"
c.add("palma_forrageira", "espacamento_tradicional", "1,0 m x 1,0 m (10 mil plantas/ha)", "", "op_sistema_de_producao_de_palma_forrageira_", PAL, URL_PAL, 19,
      "O espaçamento 1,0 m x 1,0 m entre linhas e plantas é considerado tradicional para a palma-forrageira e proporciona 10 mil plantas por hectare", "semiárido da Paraíba")
c.add("palma_forrageira", "espacamento_adensado", "2,0 m entre linhas x 0,10 m entre plantas (50 mil plantas/ha)", "", "op_sistema_de_producao_de_palma_forrageira_", PAL, URL_PAL, 19,
      "o espaçamento de 2,0 m entre as linhas e 0,10 m entre as plantas possibilita 50 mil plantas por hectare", "semiárido da Paraíba")

GUA = "Embrapa Caprinos e Ovinos. Guandu para produção de forragem e de grãos (Comunicado Técnico 191, 2019)"
c.add("guandu", "espacamento_no_experimento", "0,75 m entre linhas x 0,20 m entre plantas (66.667 plantas/ha)", "", "op_cnpc2019cot191", GUA,
      "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1117099/1/CNPC2019Cot191.pdf", 4,
      "com espaçamento de 0,75 m entre linhas e 0,20 m entre plantas dentro da linha, resultando na densidade de 66.667 pl/ha",
      "ATENÇÃO: é a parcela de um experimento (Ceará/Sobral), não uma recomendação de plantio")

BPD = "Embrapa Semiárido. Comportamento de leguminosas para adubação verde (BPD 63)"
c.add("crotalaria_juncea", "espacamento_no_experimento", "60 cm x 20 cm", "", "op_bpd63", BPD, "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/154470/1/BPD63.pdf", 11,
      "60cm x 20 cm para as crotalárias e a mucuna anã", "ATENÇÃO: espaçamento usado em canteiros de experimento, não recomendação")

for cult in ("mucuna", "feijao_de_porco"):
    c.lacuna(cult, "espacamento_densidade_semente", "a fonte só dá o espaçamento de um experimento para 'mucuna anã' e 'as demais'; não atribuído a esta cultura")
c.gravar()
