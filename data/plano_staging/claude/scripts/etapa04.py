from curar import Curadoria

M = "file://data/plano_staging/material_antigravity/"
c = Curadoria(4)

GER = "Embrapa Algodão. Cultivo do Gergelim (sistema de produção)"
c.add("gergelim", "solo_exigencia", "profundo (pelo menos 60 cm), bem drenado, boa fertilidade natural, textura franca (de franco-arenosa a franco-argilosa)", "",
      "Cultivo-do-Gergelim", GER, M + "Cultivo-do-Gergelim.pdf", 5,
      "atinge a plenitude em solos profundos, pelo menos 60 cm, bem drenados e de boa fertilidade natural, francos do ponto de vista textural, desde franco-arenosos até franco-argilosos", "")
c.add("gergelim", "solo_evitar", "solos muito argilosos (planta muito sensível a alagamento, mesmo curto)", "", "Cultivo-do-Gergelim", GER, M + "Cultivo-do-Gergelim.pdf", 5,
      "Os solos muito argilosos devem ser evitados, pois as plantas são extremamente susceptíveis, mesmo a curtos períodos de alagamento", "")

ALG = "Embrapa Algodão. Cultivo do Algodão Colorido Orgânico na Região Semi-Árida do Nordeste Brasileiro. Documentos 204"
c.add("algodao", "solo_exigencia", "profundo, bem estruturado, pH entre 5,5 e 6,5, sem encharcamento nem erosão", "", "algodao_doc204", ALG, M + "algodao_doc204.pdf", 16,
      "solos profundos, bem estruturados, de pH entre 5,5 e 6,5, não sujeitos a encharcamento ou erosão", "algodão colorido orgânico, semiárido do Nordeste")
c.add("algodao", "preparo_metodo", "aração e gradagem (método tradicional), de preferência com arado de aiveca ou de discos", "", "algodao_doc204", ALG, M + "algodao_doc204.pdf", 16,
      "O solo pode ser preparado pelo método tradicional de aração e gradagem, preferencialmente com arado de aiveca ou de discos", "semiárido do Nordeste")
c.add("algodao", "preparo_profundidade_aracao", "15 a 20", "cm", "algodao_doc204", ALG, M + "algodao_doc204.pdf", 16,
      "recomenda-se fazer aração a uma profundidade de 15 a 20 cm antes da gradagem", "quando o preparo é mecanizado, a trator")

MAN = "Embrapa Mandioca e Fruticultura. Sistema de Produção de Mandioca no Semiárido"
c.add("mandioca", "solo_exigencia", "bem drenado e profundo; textura média é a mais adequada", "", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 4,
      "necessita de solos bem drenados e profundos", "semiárido")
c.add("mandioca", "solo_textura_adequada", "textura média (menor resistência à penetração das raízes)", "", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 4,
      "de textura média, pois geralmente apresentam menor resistência à penetração", "semiárido")
c.add("mandioca", "solo_evitar", "solos com mais de 60% de argila, ou com argila + silte acima de 70%", "", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 4,
      "Os solos muito argilosos (mais de 60% de argila) ou aqueles em que a soma de argila mais silte é maior do que 70%, devem ser evitados", "semiárido")
c.add("mandioca", "preparo_plantio_direto", "revolver o solo até 0,4 m para corrigir pH e nutrientes; depois cultivar sem revolver", "", "mandioca_semiarido", MAN, M + "mandioca_semiarido.pdf", 5,
      "com o revolvimento do solo até a profundidade de 0,4 m para corrigir o pH e o teor de nutrientes", "semiárido; fonte descreve início do plantio direto")

AM = "Embrapa Algodão. Recomendações Técnicas para o Cultivo do Amendoim em Pequenas Propriedades Agrícolas do Nordeste Brasileiro. Circular Técnica 102"
c.add("amendoim", "ph_ideal", "6,0 a 6,2", "pH", "amendoim_cirtec102", AM, M + "amendoim_cirtec102.pdf", 2,
      "para o amendoim, o pH ideal se situa na faixa de 6.0 a 6.2", "Nordeste; corrigir só se o solo estiver ácido")

GIR = "Embrapa Meio-Norte. Manejo da cultura do girassol no Meio-Norte do Brasil. Circular Técnica 48, Teresina, dez/2008"
c.add("girassol", "solo_exigencia", "bem corrigido, profundo, fértil, plano e bem drenado", "", "girassol_cir48", GIR, M + "girassol_cir48.pdf", 3,
      "bom desempenho em solos bem-corrigidos, profundos, férteis, planos e bem-drenados", "Meio-Norte (PI/MA)")

c.add("mamona", "analise_de_solo_e_calagem", "fazer análise do solo; se o pH estiver abaixo de 5, calagem pelo menos 3 meses antes do plantio", "", "op_cart01",
      "Embrapa Algodão. O Cultivo Sustentável da Mamona no Semi-Árido Brasileiro", "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/276142/1/CART01.pdf", 22,
      "sempre que possível, análise do solo e, caso o pH esteja muito ácido (abaixo de 5) fazer a calagem pelo menos 3 meses antes do plantio", "semiárido")
c.add("milheto", "analise_de_solo_orientacao", "análise química e de textura, em laboratório com controle de qualidade, antes de definir correção e adubação", "", "op_sistema_de_producao_cultivo_do_milheto_p",
      "Embrapa Milho e Sorgo. Cultivo do Milheto. Sistema de Produção, 5. ed.",
      "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/993985/1/Sistema-de-Producao-Cultivo-do-Milheto.pdf", 52,
      "análise química e granulométrica (textura), que deve ser realizada em laboratórios com controle de qualidade reconhecidos", "fonte nacional")

for cult in ("milho", "sorgo", "feijao_caupi", "feijao_comum", "palma_forrageira", "guandu", "crotalaria_juncea", "mucuna", "feijao_de_porco"):
    c.lacuna(cult, "solo_exigencia_e_preparo", "ainda não coletado")
c.gravar()
