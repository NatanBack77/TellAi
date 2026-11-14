"""L4: 20 perguntas estilo agricultor para a camada LLM/RAG.

15 com resposta CONFERIDA no PDF (arquivo, pagina 1-based, frase literal que e substring da pagina extraida por
pdftotext -f p -l p, espacos normalizados) e 5 'sem evidencia esperada' (assunto ausente do acervo; a ausencia foi
checada por busca de palavras-chave em indice/trechos.jsonl em 2026-11-13: ver NEGATIVAS_CHECAGEM).
Escritas ANTES de qualquer ajuste da busca nesta rodada; NAO usadas para calibrar nada (conjunto so de avaliacao).
Formato: (pergunta, arquivo, pagina, frase)  |  negativas: (pergunta, None, None, None)
"""
POSITIVAS = [
    ("Quantos milímetros de chuva o feijão-caupi precisa durante o ciclo?",
     "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", 1, "exige um mínimo de 300 mm de precipitação"),
    ("Qual a temperatura boa para plantar feijão-caupi?",
     "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", 1, "estão na faixa de 18oC a 34oC"),
    ("Em que época da planta a falta de chuva mais prejudica o feijão-caupi?",
     "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", 1, "florescimento/enchimento de vagens também é muito prejudicial"),
    ("Terra argilosa serve para plantar feijão-caupi?",
     "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", 2, "Solos argilosos do tipo 3 não são solos preferenciais"),
    ("Quais são os três níveis de risco do zoneamento do feijão-caupi no Ceará?",
     "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", 1, "em três níveis de risco: 20%, 30%, 40%"),
    ("O zoneamento de risco considera praga e doença na lavoura?",
     "mapa_zarc_ce_feijao_caupi_port121_2026.pdf", 1, "danos às plantas devido à ocorrência de pragas e doenças"),
    ("Com que culturas posso plantar junto com a palma forrageira?",
     "propagapalma_cartilha10_cultivos_consorciados_palma.pdf", 5, "o sorgo, o milheto, o feijão, a mandioca e o quiabo"),
    ("Qual a profundidade do sulco para plantar a palma?",
     "propagapalma_cartilha2_preparo_solo_plantio.pdf", 9, "profundidade média de 15 a 20 cm"),
    ("No consórcio de algodão com milho, quantas fileiras de cada devo plantar?",
     "embrapa_semiarido_dia_de_campo_unidades_demonstrativas.pdf", 4, "6 a 7 fileiras de algodão para uma ou duas de milho"),
    ("Qual o espaçamento da gliricídia quando consorciada com outras culturas?",
     "embrapa_semiarido_dia_de_campo_unidades_demonstrativas.pdf", 13, "4m x 1m para consórcio com culturas herbáceas"),
    ("Como controlar as pragas do algodão sem só usar veneno?",
     "embrapa_semiarido_dia_de_campo_unidades_demonstrativas.pdf", 7, "rotação de cultivos, destruição dos restos culturais"),
    ("Qual a temperatura ideal para o amendoim?",
     "mapa_zarc_ce_amendoim_port73_2026.pdf", 1, "faixa de 25ºC a 30ºC são as indicadas"),
    ("Quanta chuva por ano a palma forrageira pede para dar bem?",
     "mapa_zarc_ce_palma_forrageira_port284_2019.pdf", 1, "precipitação pluviométrica entre 368,4 a 812,4 mm/ano"),
    ("Quando o girassol mais sofre com a falta de água?",
     "mapa_zarc_ce_girassol_port97_2026.pdf", 1, "mais sensíveis ao déficit hídrico são do início da formação do capítulo"),
    ("O que a seca ou o excesso de umidade fazem com o algodão depois de 60 dias?",
     "mapa_zarc_ce_algodao_port169_2026.pdf", 1, "queda das estruturas frutíferas"),
]
NEGATIVAS = [
    ("Qual o preço da saca de milho hoje?", None, None, None),
    ("Como vacinar o gado contra febre aftosa?", None, None, None),
    ("Como tratar mastite nas cabras?", None, None, None),
    ("Qual a cotação do feijão no mercado esta semana?", None, None, None),
    ("Qual a receita de queijo de coalho?", None, None, None),
]
NEGATIVAS_CHECAGEM = ["aftosa", "mastite", "saca de", "cota[cç]ão", "queijo"]  # regex que NAO devem aparecer no acervo
L4 = POSITIVAS + NEGATIVAS
