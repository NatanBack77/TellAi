from curar import Curadoria

M = "file://data/plano_staging/material_antigravity/"
A = "file://docs_rag/"
c = Curadoria(7)
COND = "referência da fonte, não prescrição; depende de análise de solo"

GER = "Embrapa Algodão. Cultivo do Gergelim (sistema de produção)"
c.add("gergelim", "exigencia_nutrientes_referencia", "50 N - 14 P2O5 - 60 K2O por 1.000 kg de sementes produzidas", "kg/ha", "Cultivo-do-Gergelim", GER,
      M + "Cultivo-do-Gergelim.pdf", 6, "a planta precisa de 50 kg ha-1 – 14 kg ha-1 – 60 kg ha-1 de N-P2O5–K2O para produzir 1.000 kg de sementes",
      "é a exigência da planta, não a dose de adubo a aplicar")
c.add("gergelim", "base_da_recomendacao", "análise química do solo", "", "Cultivo-do-Gergelim", GER, M + "Cultivo-do-Gergelim.pdf", 5,
      "devem ser feitas com base em resultados de análise química", "correção de acidez e adubação")
c.add("gergelim", "calagem_antecedencia", "calcário incorporado pelo menos 2 meses antes da semeadura", "meses", "Cultivo-do-Gergelim", GER,
      M + "Cultivo-do-Gergelim.pdf", 6, "o calcário esteja incorporado pelo menos dois meses antes da semeadura do gergelim", "se houver necessidade de calagem")

MAN = "Embrapa Mandioca e Fruticultura. Sistema de Produção de Mandioca no Semiárido"
c.add("mandioca", "base_da_recomendacao", "análise química do solo, feita com antecedência", "", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 6,
      "A calagem e a adubação em mandioca devem, obrigatoriamente, ser definidas de acordo com a análise química do solo", "semiárido")
c.add("mandioca", "calcario_limite_referencia", "máximo de 1 t/ha por ano", "t/ha", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 7,
      "Aconselha-se o limite máximo de 1 t/ha de calcário por ano", "semiárido; " + COND)
c.add("mandioca", "calagem_antecedencia", "1 a 2 meses antes do plantio", "meses", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 7,
      "É importante que a aplicação ocorra de 1 a 2 meses antes do plantio", "calcário dolomítico; semiárido")
c.add("mandioca", "resposta_ao_nitrogenio", "pequena", "", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 6,
      "Quanto à adubação, a mandioca tem apresentado pequenas respostas à aplicação de N", "mesmo em solos com baixo teor de matéria orgânica, segundo a fonte")

AM = "Embrapa Algodão. Recomendações Técnicas para o Cultivo do Amendoim em Pequenas Propriedades Agrícolas do Nordeste Brasileiro. Circular Técnica 102"
c.add("amendoim", "base_da_recomendacao", "resultados da análise de solo", "", "amendoim_cirtec102", AM, M + "amendoim_cirtec102.pdf", 2,
      "dependerão das exigências reveladas nos resultados da análise de solo", "calcário e fertilizantes; Nordeste")
c.add("amendoim", "calagem_antecedencia", "calcário entre 30 e 45 dias antes do plantio", "dias", "amendoim_cirtec102", AM, M + "amendoim_cirtec102.pdf", 2,
      "calcário deve ser aplicado entre 30 e 45 dias antes do plantio", "Nordeste")
c.add("amendoim", "adubo_organico_referencia", "2 kg de esterco de curral curtido por m²", "kg/m²", "amendoim_cirtec102", AM, M + "amendoim_cirtec102.pdf", 2,
      "Orgânica: 2kg de esterco de curral curtido/m2", "Nordeste; " + COND)

ALG = "Embrapa Algodão. Cultivo do Algodão Colorido Orgânico na Região Semi-Árida do Nordeste Brasileiro. Documentos 204"
c.add("algodao", "adubo_organico_referencia", "20 t/ha de esterco de curral bem curtido, nas covas ou a lanço no plantio", "t/ha", "algodao_doc204", ALG, M + "algodao_doc204.pdf", 24,
      "recomenda-se usar o esterco de curral bem curtido, na dosagem de 20 t/ha", "algodão colorido orgânico, semiárido; " + COND)

CAU = "Embrapa Meio-Norte. Feijão-caupi: o produtor pergunta, a Embrapa responde"
c.add("feijao_caupi", "fosforo_referencia", "40 a 80 kg/ha de P2O5, sendo 40 para solo com teor alto (≥ 10 mg/kg) e 80 para teor baixo (< 10 mg/kg)", "kg/ha de P2O5",
      "embrapa_meionorte_feijaocaupi_produtor_pergunta", CAU, A + "embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf", 79,
      "As doses recomendadas geralmente situam-se entre 40 kg ha-1 e 80 kg ha-1 de P2O5, para solos com alto teor (≥ 10 mg kg-1) e baixo teor de fósforo (< 10 mg kg-1), respectivamente",
      "Norte e Nordeste do Brasil; " + COND)

c.add("sorgo", "adubacao_cobertura", "nitrogenada e potássica em cobertura, na fase de desenvolvimento inicial", "", "sorgo_plantio",
      "Embrapa Milho e Sorgo. Cultivo do Sorgo. Sistema de Produção, 9ª ed., jul/2015 (seção Plantio)", M + "sorgo_plantio.pdf", 4,
      "é o tempo de se fazer a adubação nitrogenada e potássica em cobertura", "sorgo granífero; fonte nacional; sem dose na passagem")

MAM = "Embrapa Algodão. O Cultivo Sustentável da Mamona no Semi-Árido Brasileiro"
URL_MAM = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/276142/1/CART01.pdf"
c.add("mamona", "calagem_referencia", "se o pH estiver muito ácido (abaixo de 5): calagem pelo menos 3 meses antes do plantio, com o solo úmido", "meses", "op_cart01", MAM, URL_MAM, 22,
      "caso o pH esteja muito ácido (abaixo de 5) fazer a calagem pelo menos 3 meses antes do plantio", "semiárido; " + COND)
c.add("mamona", "fosforo_referencia", "40 kg/ha de P2O5 nas covas, quando a análise do solo mostra teor abaixo de 10 mg/dm³", "kg/ha de P2O5", "op_cart01", MAM, URL_MAM, 22,
      "na quantidade de 40 kg/ha de P2O5, caso a análise do solo apresente teor abaixo de 10 mg/dm3", "semiárido; " + COND)

MLT = "Embrapa Milho e Sorgo. Cultivo do Milheto. Sistema de Produção, 5. ed."
URL_MLT = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/993985/1/Sistema-de-Producao-Cultivo-do-Milheto.pdf"
c.add("milheto", "base_da_recomendacao", "análise química e granulométrica (textura) do solo, feita em laboratório com controle de qualidade", "", "op_sistema_de_producao_cultivo_do_milheto_p", MLT, URL_MLT, 52,
      "análise química e granulométrica (textura), que deve ser realizada em laboratórios com controle de qualidade reconhecidos", "fonte nacional")

FEI = "Embrapa Tabuleiros Costeiros. Informações Técnicas para o Cultivo do Feijoeiro (doc. 181)"
c.add("feijao_comum", "base_da_calagem", "a necessidade de calagem é calculada com Al, Ca e Mg da análise de solo e o PRNT do calcário", "", "op_doc_181", FEI,
      "http://www.cpatc.embrapa.br/publicacoes_2013/doc_181.pdf", 49,
      "Al3+ = teor de aluminio, de acordo com a análise de solo e expresso em cmolc dm-3", "Tabuleiros Costeiros; fórmulas da fonte não reproduzidas aqui")

PAL = "Embrapa Semiárido. Sistema de Produção de Palma Forrageira para o Estado da Paraíba"
URL_PAL = "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1142333/1/Sistema-de-Producao-de-Palma-Forrageira-para-o-Estado-da-Paraiba.pdf"
c.add("palma_forrageira", "adubacao_organica_importancia", "essencial em solo arenoso: melhora fertilidade, reduz perda de nutrientes e aumenta a água disponível", "", "op_sistema_de_producao_de_palma_forrageira_", PAL, URL_PAL, 12,
      "a adubação orgânica também é essencial para melhorar a fertilidade, reduzir perdas de nutrientes por lixiviação e aumentar a água disponível para as plantas", "semiárido da Paraíba; sem dose na passagem")
c.add("palma_forrageira", "adubacao_quimica_parcelamento", "fertilizante químico em doses parceladas, para reduzir perdas por lixiviação", "", "op_sistema_de_producao_de_palma_forrageira_", PAL, URL_PAL, 13,
      "os fertilizantes químicos devem ser fornecidos de forma parcelada, para reduzir as perdas de nutrientes por lixiviação", "semiárido da Paraíba; sem dose na passagem")

c.add("guandu", "adubacao_usada_no_experimento", "37,2 kg/ha de N, 130,2 de P2O5 e 74,4 de K2O no sulco de plantio", "kg/ha", "op_cnpc2019cot191",
      "Embrapa Caprinos e Ovinos. Guandu para produção de forragem e de grãos (Comunicado Técnico 191, 2019)",
      "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1117099/1/CNPC2019Cot191.pdf", 4,
      "37,2 kg/ha de nitrogênio (N), 130,2 kg/ha fósforo (P2O5), 74,4 kg/ha potássio (K2O), no sulco de plantio",
      "ATENÇÃO: adubação aplicada em parcelas de um experimento, não recomendação")

for cult in ("milho", "girassol", "crotalaria_juncea", "mucuna", "feijao_de_porco"):
    c.lacuna(cult, "adubacao_referencia", "ainda não coletado")
c.gravar()
