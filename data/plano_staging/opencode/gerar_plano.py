# -*- coding: utf-8 -*-
"""Gera os CSVs de curadoria das etapas 1, 8, 9 e 10 do plano de plantio.

Cada linha = um atributo por cultura, com fonte aberta (url), pagina do PDF e
trecho literal. Linhas sem fonte consultada entram como status=lacuna.
"""
import csv
import os

DATA = "2026-11-15"
OUT = os.path.dirname(os.path.abspath(__file__))
COLS = ["cultura_id", "etapa", "atributo", "valor", "unidade", "status",
        "fonte", "url", "pagina", "trecho", "contexto", "data_consulta"]

ROWS = []


def r(cultura, etapa, atributo, valor, unidade="", status="verificado",
      fonte="", url="", pagina="", trecho="", contexto=""):
    ROWS.append({
        "cultura_id": cultura, "etapa": etapa, "atributo": atributo,
        "valor": valor, "unidade": unidade, "status": status,
        "fonte": fonte, "url": url, "pagina": pagina, "trecho": trecho,
        "contexto": contexto, "data_consulta": DATA,
    })


def lac(cultura, etapa, atributo, motivo):
    r(cultura, etapa, atributo, "", "", "lacuna", "", "", "", "",
      "Sem fonte consultada: " + motivo)


# ---------------------------------------------------------------- fontes ----
F_MILHO = ("Embrapa Milho e Sorgo. Cultivo do Milho. Sistema de Produção 1, "
           "9. ed., nov. 2015")
U_MILHO = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
           "486917/1/Sistema-de-Producao-Cultivo-do-Milho.pdf")
F_SORGO = ("Embrapa Milho e Sorgo. Cultivo do Sorgo. Sistema de Produção 2, "
           "9. ed., jul. 2015")
U_SORGO = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
           "994083/1/Sistema-de-Producao-Cultivo-do-Sorgo.pdf")
F_CAUPI = ("Embrapa Meio-Norte. Feijão-caupi: o produtor pergunta, a Embrapa "
           "responde (500 perguntas)")
U_CAUPI = ("file://docs_rag/embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf")
F_FEIJAO = ("Embrapa Tabuleiros Costeiros. Informações Técnicas para o Cultivo "
            "do Feijoeiro Comum na Região Nordeste Brasileira 2012-2014 "
            "(Documentos 181)")
U_FEIJAO = "http://www.cpatc.embrapa.br/publicacoes_2013/doc_181.pdf"

# ================================================================= MILHO ====
c = "milho"
# Etapa 1
r(c, 1, "finalidade",
  "Produção de grãos para alimentação humana e animal", "", "verificado",
  F_MILHO, U_MILHO, "40",
  "No milho, o interesse antropocêntrico reside principalmente na produção de "
  "grãos, para alimentação humana e animal.")
r(c, 1, "limitacao_principal",
  "Sensível ao déficit hídrico; na safrinha o risco climático (seca e geada) "
  "reduz o potencial", "", "verificado",
  F_MILHO, U_MILHO, "22",
  "o principal fator de risco é o déficit hídrico", "Brasil Central; vale "
  "também para sequeiro no semiárido")
lac(c, 1, "vantagem_semiarido",
    "o documento não trata de aptidão específica ao semiárido")

# Etapa 8
r(c, 8, "fases_fenologicas",
  "VE (emergência), V1-Vn (vegetativo) e R1-R6 (reprodutivo)", "",
  "verificado", F_MILHO, U_MILHO, "30",
  "No estádio V5 (cinco folhas completamente desenvolvidas), tanto a iniciação "
  "das folhas como das espigas vai estar completa")
r(c, 8, "fase_duracao_dias", "65", "dias após emergência até a floração",
  "verificado", F_MILHO, U_MILHO, "26",
  "genótipo de milho de ciclo normal, cuja floração acontece aos 65 dias após "
  "a emergência")
r(c, 8, "pcc_daninhas", "V5 a V8, geralmente 20 a 40", "dias após emergência",
  "verificado", F_MILHO, U_MILHO, "162",
  "O período crítico de competição (PCC) das plantas daninhas ou forrageiras "
  "no milho ocorre entre os estádios V5 (5 folhas totalmente expandidas) e V8, "
  "geralmente, entre 20 e 40 dias após emergência")
r(c, 8, "plantas_daninhas_criticas",
  "caruru (Amaranthus spp.), picão-preto (Bidens spp.), leiteira (Euphorbia "
  "heterophylla), corda-de-viola (Ipomoea spp.), trapoeraba (Commelina "
  "benghalensis), guanxuma (Sida spp.)", "", "verificado",
  F_MILHO, U_MILHO, "209",
  "a ocorrência tanto de espécies dicotiledôneas, como Amaranthus spp (caruru) "
  "... Ipomoea spp (corda-de-viola) ... Commelina benghalensis (trapoeraba) e "
  "Sida spp. (guanxuma)")
r(c, 8, "praga",
  "Lagarta-do-cartucho (Spodoptera frugiperda) | dano: ataca as folhas do "
  "cartucho e pode matar plantas jovens | fase de risco: vegetativa | manejo: "
  "vigilância constante da lavoura", "", "verificado",
  F_MILHO, U_MILHO, "32",
  "idade ao ataque da lagarta do cartucho (Spodoptera frugiperda), exigindo "
  "assim constante vigilância")
r(c, 8, "praga",
  "Lagarta-elasmo (Elasmopalpus lignosellus) | dano: ataca plântulas | fase de "
  "risco: inicial | manejo: manter alta umidade do solo reduz os problemas",
  "", "verificado", F_MILHO, U_MILHO, "295",
  "A alta umidade do solo contribui para reduzir os problemas causados pela "
  "lagarta-elasmo no milho")
r(c, 8, "praga",
  "Cigarrinha-do-milho (Dalbulus maidis) | dano: transmite os enfezamentos "
  "pálido e vermelho | fase de risco: todo o ciclo | manejo: eliminar "
  "hospedeiros (gramíneas) do patógeno e do vetor", "", "verificado",
  F_MILHO, U_MILHO, "300",
  "para o controle da doença, os métodos culturais, na forma de eliminação dos "
  "hospedeiros nativos do patógeno e do vetor (gramíneas em geral), têm sido "
  "os mais eficientes")
r(c, 8, "doenca",
  "Enfezamento pálido e enfezamento vermelho | sintoma: clorose nas bordas das "
  "folhas, nanismo com entrenós curtos e avermelhamento generalizado | manejo: "
  "eliminação de gramíneas hospedeiras", "", "verificado",
  F_MILHO, U_MILHO, "298",
  "Enfezamento pálido - no início, plantas podem apresentar folhas com "
  "deformações e posteriormente inicia-se pela descoloração (clorose) das "
  "bordas da base das folhas")
lac(c, 8, "desbaste", "o documento não indica desbaste para milho")
lac(c, 8, "amontoa", "o documento não descreve amontoa para milho")

# Etapa 9
r(c, 9, "colheita_indicador",
  "Grãos com cerca de 25% de umidade, colhidos por colheitadeira mecanizada",
  "", "verificado", F_MILHO, U_MILHO, "347",
  "O milho geralmente é colhido com 25% de umidade, utilizando-se "
  "colheitadeiras mecanizadas")
r(c, 9, "colheita_umidade", "25", "% (base úmida, colheita mecanizada)",
  "verificado", F_MILHO, U_MILHO, "347",
  "O milho geralmente é colhido com 25% de umidade")
r(c, 9, "colheita_metodo",
  "Manual (colheita de espigas e debulha) ou mecanizada", "", "verificado",
  F_MILHO, U_MILHO, "347",
  "bem como a debulha manual ... Na colheita mecanizada, a regulagem adequada "
  "das máquinas é importante")
r(c, 9, "colheita_perdas", "1,0 a 1,5 (manual); 8 a 10 (mecanizada)", "%",
  "verificado", F_MILHO, U_MILHO, "347",
  "Estimam-se em 1,0 a 1,5% as perdas promovidas pela colheita manual ... As "
  "perdas devido a colheita mecanizada são da ordem de 8 a 10%")

# Etapa 10
r(c, 10, "secagem_umidade_alvo", "13", "% máximo para armazenamento a granel",
  "verificado", F_MILHO, U_MILHO, "347",
  "para o armazenamento após a colheita na propriedade ou em armazéns, os "
  "grãos deverão ter no máximo 13% de umidade")
r(c, 10, "secagem_alternativa", "colher entre 12 e 14", "% quando não há "
  "secagem", "verificado", F_MILHO, U_MILHO, "347",
  "é interessante colher o produto com menor teor possível de umidade, em "
  "torno de 12 a 14%")
r(c, 10, "praga_armazenamento",
  "Gorgulho/caruncho (Sitophilus zeamais) e traça-dos-cereais (Sitotroga "
  "cerealella) | dano: consomem os grãos armazenados", "", "verificado",
  F_MILHO, U_MILHO, "339",
  "o gorgulho ou caruncho, Sitophilus zeamais, e a traça-dos-cereais, "
  "o gorgulho ou caruncho, Sitophilus zeamais, e a traça-doscereais, Sitotroga "
  "cerearella, são responsáveis pela maior parte das perdas")
r(c, 10, "manejo_preventivo",
  "Limpeza dos grãos antes de ensacar, umidade adequada, limpeza e "
  "desinfestação do armazém e monitoramento da infestação", "", "verificado",
  F_MILHO, U_MILHO, "361",
  "depende de cuidados como: limpeza dos grãos antes de ensacá-los, umidade "
  "adequada do grão, limpeza e desinfestação do armazém")
r(c, 10, "monitoramento_armazem",
  "Monitorar a infestação; lote com infestação de campo deve ser submetido a "
  "tratamento curativo (expurgo)", "", "verificado",
  F_MILHO, U_MILHO, "345",
  "deve ser monitorado quanto à infestação por insetos-praga. Caso exista "
  "infestação proveniente do campo, este produto deve ser submetido a "
  "tratamento curativo (expurgo)")
lac(c, 10, "embalagem", "o documento não detalha embalagem para pequena escala")
lac(c, 10, "tempo_armazenamento", "o documento não fixa prazo de armazenamento")

# ================================================================= SORGO ====
c = "sorgo"
r(c, 1, "finalidade",
  "Produção de grãos para alimentação animal e para rações, em sucessão a "
  "culturas de verão", "", "verificado", F_SORGO, U_SORGO, "2",
  "o cultivo de sorgo em sucessão a culturas de verão tem contribuído para a "
  "oferta sustentável de alimentos de boa qualidade para alimentação animal")
r(c, 1, "vantagem_semiarido",
  "Alto potencial de grãos e matéria seca e capacidade de suportar estresses "
  "ambientais; tolerante a solos de menor fertilidade", "", "verificado",
  F_SORGO, U_SORGO, "2",
  "alto potencial de produção de grãos e matéria seca da cultura, além da sua "
  "extraordinária capacidade de suportar estresses ambientais")
r(c, 1, "limitacao_principal",
  "A produtividade cai conforme o estresse hídrico e a época de plantio "
  "tardia", "", "verificado", F_SORGO, U_SORGO, "3",
  "A perda de produtividade em função da exposição da cultura a déficit hídrico "
  "varia principalmente em função do estádio fenológico das plantas, do tempo "
  "de duração do estresse e do genótipo das plantas")

# Etapa 8
r(c, 8, "fases_fenologicas",
  "9 estádios: 3ª folha (10 d), 5ª folha (21 d), diferenciação do ponto de "
  "crescimento (30 d), última folha, emborrachamento, 50% floração (60 d), "
  "leitoso (70 d), pastoso (85 d), maturação fisiológica (95 d)", "",
  "verificado", F_SORGO, U_SORGO, "107",
  "Estádio 6 (50% de floração) – O período da emergência a 50% de floração "
  "(cerca de 60 dias)... Estádio 9 (Maturação fisiológica) ... (cerca de 95 "
  "dias após a emergência)")
r(c, 8, "fase_duracao_dias", "95", "dias após emergência até a maturação "
  "fisiológica", "verificado", F_SORGO, U_SORGO, "107",
  "Estádio 9 (Maturação fisiológica) – Os grãos estão com 22 a 23% de umidade "
  "(cerca de 95 dias após a emergência)")
r(c, 8, "praga",
  "Pulgão-do-sorgo (Rhopalosiphum maidis) e mosca-do-sorgo | dano: sugam a "
  "seiva e podem transmitir viroses | fase de risco: vegetativa | manejo: "
  "monitoramento e controle cultural", "", "lacuna", "", "", "", "",
  "Sem trecho literal coletado para sorgo; a lista de pragas do capítulo de "
  "pragas não foi transcrita")
lac(c, 8, "pcc_daninhas", "o capítulo de plantas daninhas do sorgo não foi "
    "transcrito com o período crítico")
lac(c, 8, "plantas_daninhas_criticas", "o capítulo de plantas daninhas do "
    "sorgo não foi transcrito")

# Etapa 9
r(c, 9, "colheita_indicador",
  "Grãos entre 17% e 14% de umidade quando há secagem artificial; 12% a 13% "
  "sem secagem", "", "verificado", F_SORGO, U_SORGO, "156",
  "Para a colheita de grãos, o ponto ideal está entre 17% e 14% de umidade com "
  "secagem artificial. Sem recursos para secagem artificial, a colheita só "
  "poderá ser feita quando a umidade cair para 12% a 13%")
r(c, 9, "colheita_umidade", "14 a 17", "% com secagem artificial",
  "verificado", F_SORGO, U_SORGO, "156",
  "o ponto ideal está entre 17% e 14% de umidade com secagem artificial")

# Etapa 10
r(c, 10, "secagem_umidade_alvo", "12 a 13", "% para colheita sem secagem",
  "verificado", F_SORGO, U_SORGO, "156",
  "a colheita só poderá ser feita quando a umidade cair para 12% a 13%")
r(c, 10, "praga_armazenamento",
  "Gorgulho (Sitophilus zeamais), traça dos cereais (Sitotroga cerealella), "
  "rizoperta (Rhyzopertha dominica) e tribólio (Tribolium castaneum)", "",
  "verificado", F_SORGO, U_SORGO, "228",
  "As principais pragas do grão de sorgo armazenado são o gorgulho, Sitophilus "
  "zeamais e a traça dos cereais, Sitotroga cerealella")
r(c, 10, "manejo_preventivo",
  "Aeração dos silos reduz populações de Sitophilus zeamais e Tribolium "
  "castaneum", "", "verificado", F_SORGO, U_SORGO, "232",
  "populações de Sitophilus zeamais e Tribolium castaneum foram "
  "significativamente reduzidas nos silos submetidos a aeração")
lac(c, 10, "embalagem", "o documento não detalha embalagem para pequena escala")
lac(c, 10, "tempo_armazenamento", "o documento não fixa prazo de armazenamento")

# ============================================================ FEIJÃO-CAUPI ===
c = "feijao_caupi"
r(c, 1, "finalidade",
  "Produção de grãos secos, verdes e de forragem; importante na agricultura "
  "familiar do Norte e Nordeste", "", "verificado", F_CAUPI, U_CAUPI, "14",
  "A cultura do feijão-caupi ocupa posição de destaque entre as atividades "
  "agropecuárias do Brasil, principalmente nas regiões Norte e Nordeste")
lac(c, 1, "vantagem_semiarido",
    "o acervo local não traz trecho específico de vantagem para o semiárido")
lac(c, 1, "limitacao_principal",
    "o acervo local não traz trecho específico de limitação")

# Etapa 8
r(c, 8, "fases_fenologicas",
  "Fase I germinação e emergência; Fase II crescimento e desenvolvimento; "
  "Fase III floração e enchimento de grãos; Fase IV maturação fisiológica e "
  "colheita", "", "verificado", F_CAUPI, U_CAUPI, "29",
  "Fase I: Germinação e emergência; Fase II: Crescimento e desenvolvimento; "
  "Fase III: Floração e enchimento de grãos; Fase IV: Maturação fisiológica e "
  "colheita")
r(c, 8, "fase_duracao_dias",
  "Grupo I (precoce) 15/25/20/10 = 70 d; Grupo II (médio) 15/25/25/15 = 80 d; "
  "Grupo III (tardio) 20/30/25/15 = 90 d", "dias por fase (I/II/III/IV) e "
  "total", "verificado", F_CAUPI, U_CAUPI, "29",
  "Fase I: Germinação e emergência; Fase II: Crescimento e desenvolvimento; "
  "Fase III: Floração e enchimento de grãos; Fase IV: Maturação fisiológica e "
  "colheita", "duração por fase (dias) na tabela da p.29: Grupo I 15/25/20/10 "
  "(total 70); Grupo II 15/25/25/15 (80); Grupo III 20/30/25/15 (90)")
r(c, 8, "pcc_daninhas", "15 a 40", "dias após a semeadura", "verificado",
  F_CAUPI, U_CAUPI, "122",
  "o intervalo compreendido entre 15 e 40 dias após a semeadura, quando é "
  "obrigatório o controle das plantas daninhas")
r(c, 8, "capina",
  "Capina manual com enxada é eficaz; rendimento de 8 a 10 dias-homem por "
  "hectare", "", "verificado", F_CAUPI, U_CAUPI, "124",
  "sendo necessários 8 a 10 dias por homem para capinar 1 ha")
r(c, 8, "praga",
  "Vaquinhas (Diabrotica speciosa e Cerotoma arcuata), lagarta-do-cartucho, "
  "mosca-branca, cigarrinha-verde, tripes, lagartas-das-vagens (Maruca sp. e "
  "Etiella zinckenella) e percevejos | dano: desfolha, sucção e ataque às "
  "vagens | fase de risco: todo o ciclo", "", "verificado",
  F_CAUPI, U_CAUPI, "187",
  "vaquinhas (Diabrotica speciosa e Cerotoma arcuata), mosca-branca (Bemisia "
  "tabaci biótipo B), cigarrinha-verde ... lagartas-das-vagens")
r(c, 8, "praga",
  "Manhoso (Chalcodermus bimaculatus) | dano: perfura vagens e grãos; os "
  "orifícios de alimentação permanecem abertos | fase de risco: vagens em "
  "formação", "", "verificado", F_CAUPI, U_CAUPI, "200",
  "Os orifícios de alimentação permanecem abertos")
r(c, 8, "doenca",
  "Murcha de fusário (Fusarium oxysporum f. sp. phaseoli), podridão-cinzenta "
  "do caule (Macrophomina phaseolina) e murcha de esclerócio (Sclerotium "
  "rolfsii) | sintoma: murcha e podridões | manejo: rotação e sementes sadias",
  "", "verificado", F_CAUPI, U_CAUPI, "151",
  "a murcha de fusário (Fusarium oxysporum f. sp. phaseoli), a "
  "podridão-cinzenta do caule (Macrophomina phaseolina) e a murcha de "
  "esclerócio (Sclerotium rolfsii)")
lac(c, 8, "desbaste", "o documento não indica desbaste para feijão-caupi")
lac(c, 8, "amontoa", "o documento não descreve amontoa para feijão-caupi")

# Etapa 9
r(c, 9, "colheita_indicador",
  "Vagens secas: a casca da vagem estala, sinal de umidade adequada", "",
  "verificado", F_CAUPI, U_CAUPI, "229",
  "verificar se a casca da vagem está estalando. Isso é sinal de que os grãos "
  "estão com umidade adequada para o armazenamento")
r(c, 9, "colheita_dias_apos_plantio",
  "Grupo I <75 d; Grupo II 75-85 d; Grupo III >85 d", "dias até a maturação "
  "fisiológica", "verificado", F_CAUPI, U_CAUPI, "54",
  "Grupo I – Precoce (n < 75 dias). Grupo II – Médio (75 dias ≤ n ≤ 85 dias). "
  "Grupo III – Tardio (n > 85 dias)")
r(c, 9, "colheita_metodo",
  "Manual é o sistema mais comum na agricultura familiar; cultivares de porte "
  "semiprostrado se adequam melhor", "", "verificado",
  F_CAUPI, U_CAUPI, "64",
  "As variedades de porte semiprostrado enquadram-se melhor ao sistema de "
  "colheita manual, mais comum na agricultura familiar")

# Etapa 10
r(c, 10, "secagem_umidade_alvo",
  "Secagem ao sol até a casca estalar (cerca de 2 dias); grãos em camadas de "
  "10 cm revolvidos a cada 30 minutos", "", "verificado",
  F_CAUPI, U_CAUPI, "230",
  "recomenda-se fazer a secagem ao sol em terreiros ou em lonas, esparramando "
  "os grãos em camadas de cerca de 10 cm")
r(c, 10, "secagem_umidade_alvo", "14 a 16", "% pode usar aeração em silos "
  "ventilados em vez de secagem", "verificado", F_CAUPI, U_CAUPI, "233",
  "Para produtos com teor de umidade entre 14% e 16%"
  "substituída por aeração em silos ventilados")
r(c, 10, "armazenamento_umidade_segura", "13", "% para comercialização "
  "(referência de peso)", "verificado", F_CAUPI, U_CAUPI, "236",
  "a umidade de referência para a comercialização (U = 13% a 15%, dependendo "
  "do interesse)")
r(c, 10, "embalagem",
  "Sacaria é preferível para o curto período de armazenamento brasileiro; "
  "também se usa granel", "", "verificado", F_CAUPI, U_CAUPI, "234",
  "O armazenamento pode ser feito a granel ou em sacaria ... é preferível "
  "fazê-lo em sacaria, quando em")
r(c, 10, "praga_armazenamento",
  "Caruncho-do-feijão-caupi (Callosobruchus maculatus) e traça (Plodia "
  "interpunctella) | dano: atacam grãos íntegros e farináceos", "",
  "verificado", F_CAUPI, U_CAUPI, "200",
  "As principais pragas de grãos armazenados do feijão-caupi são: o "
  "caruncho-do-feijão-caupi (Callosobruchus maculatus) e a traça (Plodia "
  "interpunctella)")
r(c, 10, "manejo_preventivo",
  "Produtos caseiros que dificultam a ação dos carunchos: óleos vegetais, "
  "gordura animal, folhas de eucalipto, terra de formigueiro e "
  "pimenta-do-reino", "", "verificado", F_CAUPI, U_CAUPI, "235",
  "mistura de produtos que dificultam a ação dos carunchos, como óleos "
  "vegetais, gordura animal, folhas de eucalipto, terra de formigueiro e "
  "pimenta-do-reino")
r(c, 10, "manejo_preventivo",
  "Evitar entrada de ar favorece a conservação em pequenas quantidades", "",
  "verificado", F_CAUPI, U_CAUPI, "236",
  "Toda forma de armazenamento que evite a entrada de ar favorece a "
  "conservação")

# =========================================================== FEIJÃO-COMUM ===
c = "feijao_comum"
lac(c, 1, "finalidade", "o documento técnico do Nordeste não traz frase de "
    "finalidade/importância transcrita nesta coleta")
lac(c, 1, "vantagem_semiarido", "não localizado trecho específico")
lac(c, 1, "limitacao_principal", "não localizado trecho específico")

# Etapa 8
r(c, 8, "pcc_daninhas", "15 a 30", "dias após a emergência", "verificado",
  F_FEIJAO, U_FEIJAO, "58",
  "o período em que ela é mais prejudicada pela competição com as plantas "
  "daninhas vai dos 15 aos 30 dias após a emergência das plantas de feijão")
r(c, 8, "capina",
  "Capina manual e cultivadores; iniciar quando as plantas daninhas ainda são "
  "pequenas; evitar revolvimento excessivo do solo", "", "verificado",
  F_FEIJAO, U_FEIJAO, "59",
  "A capina manual é uma operação demorada, deve ser iniciada no início de "
  "desenvolvimento das plantas daninhas")
r(c, 8, "doenca",
  "Antracnose (Colletotrichum lindemuthianum), ferrugem (Uromyces "
  "appendiculatus) e mancha-angular (Phaeoisariopsis griseola) | sintoma: "
  "lesões e pústulas em folhas, hastes e vagens | manejo: sementes sadias, "
  "resistência genética e rotação", "", "verificado",
  F_FEIJAO, U_FEIJAO, "82",
  "Ocorre mais nas folhas, embora seja observada também em vagens e hastes"
  "surgem manchas pequenas, esbranquiçadas e levemente salientes")
r(c, 8, "praga",
  "Lagartas-das-vagens | dano: alimentam-se das vagens e dos grãos, "
  "destruindo-os na fase de formação", "", "verificado",
  F_FEIJAO, U_FEIJAO, "158",
  "As lagartas alimentam-se das vagens e dos grãos, destruindo-os na fase de "
  "formação")
lac(c, 8, "plantas_daninhas_criticas", "lista de espécies não transcrita")

# Etapa 9
r(c, 9, "colheita_indicador",
  "Colheita manual com grãos em torno de 18% de água; mecânica direta com "
  "cerca de 15%", "", "verificado", F_FEIJAO, U_FEIJAO, "76",
  "as plantas são arrancadas inteiras quando os grãos apresentarem teor de "
  "água em torno de 18%")
r(c, 9, "colheita_metodo",
  "Manual (arranquio e leiras), semimecanizada ou mecanizada direta", "",
  "verificado", F_FEIJAO, U_FEIJAO, "76",
  "A colheita pode ser de forma manual, semi-mecanizada e mecanizada")
r(c, 9, "colheita_cuidados",
  "Na colheita manual, dispor as plantas em leiras com as raízes para cima até "
  "o teor de água cair para 14%", "", "verificado",
  F_FEIJAO, U_FEIJAO, "76",
  "dispondo-se as plantas no campo, em leiras e com as raízes para cima, até "
  "reduzirem o teor de água para 14%")

# Etapa 10
r(c, 10, "secagem_umidade_alvo", "13", "% para beneficiamento e armazenamento",
  "verificado", F_FEIJAO, U_FEIJAO, "78",
  "Objetiva-se com a secagem, alcançar teores de água em torno de 13%, "
  "adequados para beneficiamento e armazenamento")
r(c, 10, "secagem_temperatura_maxima", "38", "°C (secadores)", "verificado",
  F_FEIJAO, U_FEIJAO, "78",
  "a qual não deve ultrapassar 38oC, quando em secadores")
r(c, 10, "beneficiamento",
  "Pré-limpeza com peneiras e ventiladores, secagem, classificação por "
  "tamanho e mesa densimétrica opcional", "", "verificado",
  F_FEIJAO, U_FEIJAO, "78",
  "a primeira fase do beneficiamento é a pré-limpeza, para remoção de pedras, "
  "terra, torrões e restos vegetais")
r(c, 10, "armazenamento_umidade_segura",
  "15 (até 20 dias); 12 (estocagem prolongada); <10 em recipientes vedados",
  "%", "verificado", F_FEIJAO, U_FEIJAO, "79",
  "Quando o armazenamento destina-se a curtos períodos, não superior a 20 "
  "dias, o teor de umidade de 15% garante a boa qualidade ... recomenda-se "
  "reduzir a umidade para 12%")
r(c, 10, "embalagem",
  "Granel, sacos de aniagem, polipropileno ou plástico, e silos", "",
  "verificado", F_FEIJAO, U_FEIJAO, "79",
  "O feijão pode ser armazenado a granel, em sacos de aniagem, de "
  "polipropileno ou de plástico, e em silos")
r(c, 10, "praga_armazenamento",
  "Caruncho-pequeno (Zabrotes subfasciatus) e caruncho (Acanthoscelides "
  "obtectus) | dano: atacam os grãos armazenados", "", "verificado",
  F_FEIJAO, U_FEIJAO, "158",
  "Caruncho-pequeno Zabrotes subfasciatus e Caruncho Acanthoscelides obtectus")
r(c, 10, "manejo_preventivo",
  "Pilhas que permitam expurgos periódicos e circulação de ar; expurgo prévio "
  "em recipientes vedados", "", "verificado", F_FEIJAO, U_FEIJAO, "79",
  "recomenda-se que as pilhas sejam dispostas de forma a permitir expurgos "
  "periódicos e a maior circulação possível do ar entre elas")


# ============================================================== MILHETO ====
F_MILHETO = ("Embrapa Milho e Sorgo. Cultivo do Milheto. Sistema de Produção, "
             "5. ed., abr. 2016")
U_MILHETO = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
             "993985/1/Sistema-de-Producao-Cultivo-do-Milheto.pdf")
c = "milheto"
r(c, 1, "finalidade",
  "Produção de palhada/cobertura do solo, forragem e grãos para ração animal",
  "", "verificado", F_MILHETO, U_MILHETO, "96",
  "A grande utilização do milheto no Brasil é como planta de cobertura para o "
  "sistema de plantio direto")
r(c, 1, "vantagem_semiarido",
  "No Nordeste o clima favorece o estabelecimento da cultura, muito usada como "
  "planta forrageira", "", "verificado", F_MILHETO, U_MILHETO, "96",
  "No Nordeste, onde as condições de clima favorecem o estabelecimento da "
  "cultura, ela é muito utilizada como planta forrageira na alimentação de "
  "bovinos e de outros animais")
lac(c, 1, "limitacao_principal", "não localizado trecho específico")
r(c, 8, "fases_fenologicas",
  "Florescimento aos 48 DAE (BRS 1501); maturação fisiológica de 90 a 120 DAE "
  "conforme o genótipo", "", "verificado", F_MILHETO, U_MILHETO, "8",
  "ocorre em BRS 1501 aos 48 DAE")
r(c, 8, "fase_duracao_dias", "104 (BRS 1501/1502); 97 (BRS 1503); 90 (variedades "
  "comuns); 120 (Souna III)", "dias após emergência até a maturação "
  "fisiológica", "verificado", F_MILHETO, U_MILHETO, "9",
  "BRS1501 e BRS1502 ocorre aos 104 DAE, e, nesse momento, as sementes estão "
  "com 15% de umidade")
r(c, 8, "praga",
  "Percevejos (Nezara viridula e Piezodorus guildinii) | dano: sugam o grão em "
  "desenvolvimento, que fica manchado e menor | fase de risco: enchimento de "
  "grãos", "", "verificado", F_MILHETO, U_MILHETO, "95",
  "Estes insetos alimentam-se no grão em desenvolvimento ... Os grãos tornam-se "
  "manchados e ficam reduzidos no tamanho")
r(c, 8, "doenca",
  "Ergot (Claviceps fusiformis), míldio, ferrugem, mancha de Pyricularia, "
  "carvão e podridão seca do colmo | sintoma: estruturas e manchas nas "
  "panículas/folhas | manejo: uso de sementes sadias e cultivares resistentes",
  "", "verificado", F_MILHETO, U_MILHETO, "79",
  "O ergot é uma doença que ocorre")
lac(c, 8, "plantas_daninhas_criticas", "lista de espécies não transcrita")
lac(c, 8, "desbaste", "o documento não indica desbaste")
r(c, 9, "colheita_indicador",
  "Maturação fisiológica com 15% a 20% de umidade, conforme a cultivar", "",
  "verificado", F_MILHETO, U_MILHETO, "9",
  "nesse momento, as sementes estão com 15% de umidade ... a semente estará "
  "com 20% de umidade")
r(c, 9, "colheita_dias_apos_plantio", "90 a 120", "dias após emergência",
  "verificado", F_MILHETO, U_MILHETO, "9",
  "Para as variedades comum, ED9 ocorre aos 90 DAE")
r(c, 9, "colheita_metodo",
  "Colheita de grãos para ração, além do uso como cobertura e pastejo", "",
  "verificado", F_MILHETO, U_MILHETO, "96",
  "os grãos de milheto colhidos são processados quase que exclusivamente para a "
  "elaboração de ração animal")
r(c, 10, "secagem_umidade_alvo",
  "Abaixo de 15%; acima disso as sementes ficam sujeitas a danos excessivos",
  "%", "verificado", F_MILHETO, U_MILHETO, "96",
  "Sementes com teor de umidade acima de 15% estão sujeitas a danos excessivos")
r(c, 10, "beneficiamento",
  "Limpeza e secagem, separação, tratamento e secagem, embalagem e "
  "armazenamento", "", "verificado", F_MILHETO, U_MILHETO, "96",
  "as sementes passam pelas etapas: a) limpeza e secagem; b) separação; c) "
  "tratamento e secagem, d) embalagem; e) armazenamento")
lac(c, 10, "praga_armazenamento", "não localizado trecho específico")

# ============================================================== GIRASSOL ====
F_GIRASSOL = ("Embrapa-CNPSo. A Cultura do Girassol. Circular Técnica 13")
U_GIRASSOL = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
              "445832/1/ID2434.pdf")
c = "girassol"
r(c, 1, "finalidade",
  "Produção de aquênios para óleo de qualidade nutricional e para rotação de "
  "culturas", "", "verificado", F_GIRASSOL, U_GIRASSOL, "7",
  "o óleo de girassol destaca-se por suas excelentes características "
  "físico-químicas e nutricionais")
r(c, 1, "vantagem_semiarido",
  "Ampla adaptabilidade edafoclimática e rendimento pouco influenciado por "
  "latitude, altitude e fotoperíodo", "", "verificado",
  F_GIRASSOL, U_GIRASSOL, "7",
  "Apresenta ampla adaptabilidade às diferentes condições edafoclimáticas e seu "
  "rendimento é pouco influenciado pela latitude, pela altitude e pelo "
  "fotoperíodo")
r(c, 1, "limitacao_principal",
  "Baixa eficiência no uso da água: menos de dois gramas de grão por litro",
  "", "verificado", F_GIRASSOL, U_GIRASSOL, "10",
  "o girassol tem baixa eficiência no uso da água. Cada litro de água "
  "consumido produz menos de dois gramas")
r(c, 8, "capina",
  "Capina/mecânico até cerca de 30 dias após a emergência", "", "verificado",
  F_GIRASSOL, U_GIRASSOL, "16",
  "podendo ser feito, de modo geral, até os 30 dias após a emergência")
r(c, 8, "praga",
  "Percevejos e desfolhadores | dano: sugam a região de inserção do capítulo "
  "(murcha e perda do capítulo) e desfolham | fase de risco: floração e "
  "enchimento de grãos | manejo: monitoramento dos focos", "", "verificado",
  F_GIRASSOL, U_GIRASSOL, "28",
  "Os percevejos podem causar danos às plantas de girassol e afetar seriamente a "
  "produção
  "de floração inicial até a fase de final de florescimento")
r(c, 8, "doenca",
  "Mancha de alternária (Alternaria helianthi) e podridão branca (Sclerotinia "
  "sclerotiorum) | sintoma: manchas em folhas, haste e capítulo e podridão do "
  "colo | fase de risco: a partir do florescimento", "", "verificado",
  F_GIRASSOL, U_GIRASSOL, "25",
  "a mancha de alternária, causada pelo fungo Alternaria helianthi e a podridão "
  "branca, causada pelo fungo Sclerotinia sclerotiorum, são as mais importantes")
lac(c, 8, "plantas_daninhas_criticas", "lista de espécies não transcrita")
r(c, 9, "colheita_indicador",
  "Aquênios com 14% a 16% de umidade; folhas secas e caule/capítulo "
  "castanho-escuro a marrom", "", "verificado", F_GIRASSOL, U_GIRASSOL, "29",
  "A colheita deve ser iniciada quando a umidade dos aquênios estiver entre 14% "
  "a 16%")
r(c, 9, "colheita_dias_apos_plantio", "90 a 130", "dias após emergência",
  "verificado", F_GIRASSOL, U_GIRASSOL, "29",
  "Nas cultivares precoces e tardias, ocorre ao redor de 90 a 130 dias, "
  "respectivamente, após a emergência das plantas")
r(c, 9, "colheita_cuidados",
  "Colheita antecipada aumenta quebra de grãos em 25% a 30%; colheita atrasada "
  "eleva perdas por pássaros e acamamento", "", "verificado",
  F_GIRASSOL, U_GIRASSOL, "29",
  "A colheita antecipada, com maior teor de umidade, compromete a qualidade do "
  "produto ... aumento da quebra de grãos, que pode atingir 25% a 30%")
r(c, 10, "secagem_cuidados",
  "Secagem exige cuidado por risco de incêndio (aquênios e resíduos "
  "combustíveis)", "", "verificado", F_GIRASSOL, U_GIRASSOL, "29",
  "cuidados especiais em função da possibilidade de incêndio ocasionado ... "
  "pela secagem rápida dos aquênios e resíduos combustíveis")
lac(c, 10, "secagem_umidade_alvo", "o documento não define umidade-alvo")
lac(c, 10, "armazenamento_umidade_segura", "não localizado trecho específico")
lac(c, 10, "praga_armazenamento", "não localizado trecho específico")

# ============================================================== GERGELIM ====
F_GERGELIM = "Embrapa Algodão. Cultivo do Gergelim (sistema de produção)"
U_GERGELIM = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
              "1155372/1/Cultivo-do-Gergelim.pdf")
c = "gergelim"
r(c, 1, "finalidade",
  "Produção de sementes com mais de 50% de óleo para as indústrias "
  "alimentícia e oleoquímica e para biodiesel", "", "verificado",
  F_GERGELIM, U_GERGELIM, "2",
  "obtenção de sementes com teores de óleo superior a 50% de elevada "
  "estabilidade química
  "indústrias alimentícias e óleo química, e potencialmente para a produção de "
  "energia, via biodiesel")
r(c, 1, "vantagem_semiarido",
  "Ampla adaptabilidade a clima quente, bom nível de resistência à seca e "
  "facilidade de cultivo", "", "verificado", F_GERGELIM, U_GERGELIM, "3",
  "O gergelim apresenta ampla adaptabilidade às condições edafoclimáticas de "
  "clima quente; tem bom nível de resistência à seca e facilidade de cultivo")
r(c, 1, "limitacao_principal",
  "Frutos abrem após a maturação completa e podem causar perdas de 50% ou mais "
  "de sementes", "", "verificado", F_GERGELIM, U_GERGELIM, "26",
  "perdas de sementes de 50%, ou mais, podem ocorrer em decorrência da abertura "
  "dos frutos depois da maturação completa")
r(c, 8, "fase_duracao_dias", "90 a 110", "dias (ciclo da maioria das "
  "cultivares)", "verificado", F_GERGELIM, U_GERGELIM, "26",
  "em sincronia com o ciclo da cultivar, que, na maioria, é de 90 a 110 dias")
r(c, 8, "praga",
  "Lagarta-enroladeira, pulgão (Aphis sp.) e mosca-branca (Bemisia "
  "argentifolii) | dano: enrolam folhas, formam colônias na face inferior e "
  "transmitem viroses | manejo: eliminação de ervas daninhas e barreiras com "
  "milho ou sorgo", "", "verificado", F_GERGELIM, U_GERGELIM, "24",
  "Formam colônias na face inferior das folhas ... são transmissores de viroses")
r(c, 8, "doenca",
  "Podridão-negra (Macrophomina phaseolina), murcha-de-fusário, manchas "
  "foliares por Cercospora sesami, filoidia e mancha-bacteriana | sintoma: "
  "manchas e murcha | manejo: eliminação de ervas daninhas e material sadio",
  "", "verificado", F_GERGELIM, U_GERGELIM, "16",
  "Sintomas de podridão-negra causada por Macrophomina phaseolina")
lac(c, 8, "plantas_daninhas_criticas", "lista de espécies não transcrita")
r(c, 9, "colheita_indicador",
  "Amarelecimento completo das hastes, folhas e frutos, antes de abrirem "
  "totalmente; em cultivares deiscentes, a abertura dos frutos da base indica o "
  "ponto", "", "verificado", F_GERGELIM, U_GERGELIM, "26",
  "assim que as hastes, folhas e frutos atinjam o amarelecimento completo e "
  "antes que os frutos estejam totalmente abertos")
r(c, 9, "colheita_dias_apos_plantio", "90 a 110", "dias", "verificado",
  F_GERGELIM, U_GERGELIM, "26",
  "a colheita do gergelim deve ser programada para a época de estiagem e em "
  "sincronia com o ciclo da cultivar")
r(c, 9, "colheita_metodo",
  "Manual: corte na base a 20 cm do solo, feixes de 30 cm, medas para secagem "
  "ao sol por cerca de 10 dias e batedura sobre lona", "", "verificado",
  F_GERGELIM, U_GERGELIM, "26",
  "As plantas devem ser cortadas na base, a uma distância de 20 cm do solo ... "
  "para secagem ao sol, durante 10 dias, aproximadamente")
r(c, 10, "secagem_umidade_alvo",
  "Secagem dos feixes ao sol por cerca de 10 dias até a batedura", "",
  "verificado", F_GERGELIM, U_GERGELIM, "26",
  "empilhados no campo em forma de meda ... para secagem ao sol, durante 10 "
  "dias, aproximadamente")
r(c, 10, "secagem_cuidados",
  "Cobrir os feixes com lona em caso de chuva, para evitar escurecimento e "
  "oxidação das sementes", "", "verificado", F_GERGELIM, U_GERGELIM, "28",
  "agruparam os feixes sob uma lona plástica grande ... formando uma cobertura "
  "total à prova de chuvas")
r(c, 10, "armazenamento_umidade_segura",
  "Local ventilado, sobre estrado de madeira, protegido de chuvas e orvalho",
  "", "verificado", F_GERGELIM, U_GERGELIM, "27",
  "obedecendo às normas gerais de armazenamento, como local ventilado, sobre "
  "estrado de madeira, proteção contra chuvas e orvalho")
lac(c, 10, "praga_armazenamento", "não localizado trecho específico")

# ============================================================== AMENDOIM ====
F_AMENDOIM = ("Embrapa Algodão. Sistemas de Produção 7: Cultivo de Amendoim, "
              "nov. 2025")
U_AMENDOIM = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
              "1183110/1/SISTEMAS-DE-PRODUCAO-AMENDOIM-2025.pdf")
c = "amendoim"
r(c, 1, "finalidade",
  "Produção de grãos como fonte de óleo e para alimentação", "",
  "verificado", F_AMENDOIM, U_AMENDOIM, "6",
  "Os grãos de amendoim são fonte de óleo")
r(c, 1, "limitacao_principal",
  "Déficit hídrico no final do ciclo afeta a formação das vagens", "",
  "verificado", F_AMENDOIM, U_AMENDOIM, "17",
  "Déficit hídrico no final do ciclo da cultura")
lac(c, 1, "vantagem_semiarido", "não localizado trecho específico")
r(c, 8, "praga",
  "Percevejo-preto (Cyrtomenus mirabilis), lagartas (Spodoptera), cigarrinha, "
  "tripes e ácaro | dano: ataque a folhas e vagens | manejo: manejo integrado "
  "com amostragem da lavoura", "", "verificado", F_AMENDOIM, U_AMENDOIM, "72",
  "Adulto do percevejo-preto Cyrtomenus mirabilis")
r(c, 8, "doenca",
  "Murcha-de-Sclerotium (Sclerotium rolfsii), cercosporioses e mancha-anela | "
  "sintoma: murcha e manchas foliares | manejo: cultivares moderadamente "
  "resistentes e rotação", "", "verificado", F_AMENDOIM, U_AMENDOIM, "32",
  "É moderadamente resistente às cercosporioses e à mancha-anela")
lac(c, 8, "pcc_daninhas", "período crítico não transcrito do capítulo 9")
lac(c, 8, "plantas_daninhas_criticas", "lista de espécies não transcrita")
r(c, 9, "colheita_indicador",
  "Vagens maduras: o lado interno da casca deixa de ser espesso e branco, "
  "seguindo a escala de maturação", "", "verificado",
  F_AMENDOIM, U_AMENDOIM, "86",
  "Já as vagens imaturas apresentam o lado interno da casca espesso e branco")
r(c, 9, "colheita_metodo",
  "Em duas etapas: arranquio e recolhimento; manual/semimecanizada na "
  "agricultura familiar e totalmente mecanizada nas grandes lavouras", "",
  "verificado", F_AMENDOIM, U_AMENDOIM, "86",
  "A colheita de amendoim é feita em duas etapas")
r(c, 9, "colheita_cuidados",
  "O arranquio corta raízes cerca de 5 cm abaixo das vagens e as plantas são "
  "enleiradas com as vagens para cima para cura no campo", "", "verificado",
  F_AMENDOIM, U_AMENDOIM, "87",
  "as lâminas cortadoras penetrando no solo, à profundidade de aproximadamente "
  "5 cm abaixo das vagens da planta")
r(c, 10, "secagem_umidade_alvo",
  "A secagem natural no campo não basta; é necessária secagem artificial na "
  "unidade de recebimento", "", "verificado", F_AMENDOIM, U_AMENDOIM, "88",
  "Em geral, o processo de secagem natural no campo não é suficiente
  "atinjam a umidade adequada de armazenamento")
r(c, 10, "armazenamento_umidade_segura",
  "Amendoim em vagem armazenado a granel em galpões ou silos", "",
  "verificado", F_AMENDOIM, U_AMENDOIM, "89",
  "geralmente é armazenado a granel em galpões ou silos")
r(c, 10, "manejo_preventivo",
  "Proteção contra roedores, boa pré-limpeza, secagem adequada e limpeza "
  "periódica reduzem pragas de armazenamento", "", "verificado",
  F_AMENDOIM, U_AMENDOIM, "89",
  "com proteção contra roedores, uma boa pré-limpeza e uma secagem adequada, "
  "bem como a execução periódica de limpeza contribuem para a redução da "
  "ocorrência de pragas de armazenamento")
r(c, 10, "contaminante_critico",
  "Separar e identificar lotes com aflatoxina acima do permitido pela "
  "legislação", "", "verificado", F_AMENDOIM, U_AMENDOIM, "90",
  "a correta separação e identificação de lotes que estejam com teores de "
  "aflatoxina acima dos permitidos
  "aflatoxina acima dos permitidos")

# ================================================================ MAMONA ====
F_MAMONA = ("Embrapa Algodão. O Cultivo Sustentável da Mamona no Semi-Árido "
            "Brasileiro (Cartilha 1)")
U_MAMONA = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
            "276142/1/CART01.pdf")
c = "mamona"
r(c, 1, "finalidade",
  "Produção de óleo; no Semiárido apontada como principal alternativa para "
  "produção de óleo", "", "verificado", F_MAMONA, U_MAMONA, "5",
  "no Semi-Árido brasileiro, onde a mamona será a principal alternativa para "
  "produção de óleo")
r(c, 1, "vantagem_semiarido",
  "Grande adaptabilidade edafoclimática ao semiárido brasileiro", "",
  "verificado", F_MAMONA, U_MAMONA, "10",
  "A grande adaptabilidade edafoclimática da mamona no semi-árido brasileiro")
r(c, 1, "limitacao_principal",
  "Cultivares de frutos deiscentes devem ser evitadas por perdas e dificuldade "
  "de colheita", "", "verificado", F_MAMONA, U_MAMONA, "36",
  "plantio de cultivares com frutos deiscentes deve ser evitado, devido às "
  "perdas e à dificuldade de colheita")
r(c, 8, "fase_duracao_dias", "230 a 250", "dias da emergência à última colheita "
  "(BRS Nordestina)", "verificado", F_MAMONA, U_MAMONA, "18",
  "Ciclo da emergência à última colheita: 230 a 250 dias")
r(c, 8, "desbaste",
  "Raleamento ou desbaste com solo úmido, entre 15 e 20 dias após a germinação",
  "", "verificado", F_MAMONA, U_MAMONA, "33",
  "Raleamento ou desbaste Deve ser realizado com o solo úmido, entre 15 e 20 "
  "dias após a germinação")
r(c, 8, "praga",
  "Percevejo verde, lagarta rosca (Agrotis ipsilon), lagarta elasmo "
  "(Elasmopalpus lignosellus) e ácaros | dano: atacam folhas, hastes e cachos | "
  "manejo: monitoramento e destruição de restos culturais", "",
  "verificado", F_MAMONA, U_MAMONA, "43",
  "Lagarta rosca (Agrotis ipsilon): Lagartas de cor esc")
r(c, 8, "doenca",
  "Mofo cinzento (principal doença), podridão de Macrophomina, murcha de "
  "fusário, podridão dos ramos e cercosporiose | sintoma: podridões e murcha | "
  "manejo: poda, eliminação de restos de cultura e plantas asselvajadas", "",
  "verificado", F_MAMONA, U_MAMONA, "50",
  "Mofo cinzento: Principal doença da mamona")
r(c, 9, "colheita_indicador",
  "Colheita escalonada, colhendo sucessivamente todos os cachos maduros ou "
  "secos", "", "verificado", F_MAMONA, U_MAMONA, "25",
  "colheita escalonada colhendo-se, de forma sucessiva, todos os cachos que "
  "estiverem maduros ou secos")
r(c, 9, "colheita_metodo",
  "Manual: corte na base do cacho com ferramenta afiada e transporte ao "
  "terreiro para secagem", "", "verificado", F_MAMONA, U_MAMONA, "36",
  "Fazer o corte na base do cacho, com uso de ferramentas afiadas ... Depositar "
  "os cachos em cesto ou carroça e colocá-los no terreiro, para secar")
r(c, 9, "colheita_dias_apos_plantio", "230 a 250", "dias até a última colheita",
  "verificado", F_MAMONA, U_MAMONA, "18",
  "Ciclo da emergência à última colheita: 230 a 250 dias")
r(c, 10, "secagem_umidade_alvo",
  "Terreiro de chão batido ou alvenaria para secagem dos cachos antes do "
  "descascamento", "", "verificado", F_MAMONA, U_MAMONA, "37",
  "O terreiro para secagem pode ser construídos em chão batido")
r(c, 10, "beneficiamento",
  "Descascamento por batimento manual com varas ou por máquina manual, "
  "elétrica ou mecânica", "", "verificado", F_MAMONA, U_MAMONA, "58",
  "Beneficiamento/descascamento: Atividade feita através do batimento manual "
  "com o uso de varas flexíveis de madeira")
r(c, 10, "secagem_umidade_alvo",
  "Cerca de 10% de umidade para que as sementes se soltem da casca", "",
  "verificado", F_MAMONA, U_MAMONA, "60",
  "material a ser beneficiado precisa estar com unidade de 10%, para que as "
  "sementes larguem da casc")
lac(c, 10, "armazenamento_umidade_segura", "não localizado trecho específico")

# =============================================================== ALGODÃO ====
F_ALGODAO = ("Embrapa Algodão. Cultivo do Algodão Colorido Orgânico na Região "
             "Semi-Árida do Nordeste Brasileiro (Documentos 204)")
U_ALGODAO = ("https://www.infoteca.cnptia.embrapa.br/bitstream/doc/278113/1/"
             "DOC204.pdf")
F_ALGODAO2 = ("Embrapa Algodão. Algodão em Pluma. Coleção Agroindústria "
              "Familiar")
U_ALGODAO2 = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
              "659531/1/AGROINDFAMAlgodaoempluma1ed012009.pdf")
c = "algodao"
r(c, 1, "finalidade",
  "Produção de fibra (pluma) para a indústria têxtil, com caroço como "
  "subproduto", "", "verificado", F_ALGODAO2, U_ALGODAO2, "14",
  "Algodão em pluma é o produto resultante do processo de beneficiamento do "
  "algodão em caroço
  "algodão em caroço")
r(c, 1, "vantagem_semiarido",
  "Cultivares locais com alto grau de resistência à seca, plantáveis no "
  "Seridó e Sertão", "", "verificado", F_ALGODAO, U_ALGODAO, "19",
  "possui alto grau de resistência a seca, podendo ser plantada nas regiões do "
  "seridó e sertão")
r(c, 1, "limitacao_principal",
  "O bicudo do algodoeiro aumentou os custos de produção e reduziu a área no "
  "Nordeste", "", "verificado", F_ALGODAO, U_ALGODAO, "11",
  "o surgimento do bicudo do algodoeiro (Anthonomus grandis Boheman) o que "
  "ocasionou aumento nos custos de produção")
r(c, 8, "amontoa",
  "Amontoa é a operação de chegar terra às fileiras por ocasião das capinas",
  "", "verificado", F_ALGODAO, U_ALGODAO, "18",
  "Amontoa - é a operação de \"chegar terra\" às fileiras por ocasião das "
  "capinas")
r(c, 8, "capina",
  "Capinas alternadas nas entrelinhas, com intervalo de 2 a 5 dias entre "
  "passagens", "", "verificado", F_ALGODAO, U_ALGODAO, "18",
  "Capinas alternadas- consiste em se realizar a capina nas entrelinhas, dando "
  "um intervalo de 2 a 5 dias entre cada passagem")
r(c, 8, "pcc_daninhas",
  "Primeiros 15 a 60 dias após a emergência", "dias", "verificado",
  F_ALGODAO, U_ALGODAO, "33",
  "os primeiros 15-60 dias após emergência da plântula, foram o período em que "
  "as plantas daninhas causaram maiores prejuízos à cultura")
r(c, 8, "praga",
  "Broca, bicudo, lagarta das maçãs e lagarta rosada | dano: atacam botões, "
  "maçãs e capulhos | manejo: cultivares de ciclo curto, uniformidade de "
  "plantio e destruição dos restos culturais", "", "verificado",
  F_ALGODAO, U_ALGODAO, "28",
  "reduzir o tempo de exposição das plantas à colonização e infestação de "
  "pragas (broca, bicudo, lagarta das maçãs e lagarta rosada)")
r(c, 8, "doenca",
  "Baixa incidência de doenças foliares e de solo no Nordeste; escolher áreas "
  "livres de patógenos", "", "verificado", F_ALGODAO, U_ALGODAO, "33",
  "a incidência de doenças foliares e de solo é baixa na região Nordeste")
r(c, 9, "colheita_indicador",
  "60% dos capulhos abertos na primeira colheita; segunda colheita cerca de 15 "
  "dias depois", "", "verificado", F_ALGODAO, U_ALGODAO, "34",
  "iniciando-se quando 60 % dos capulhos estiverem abertos, sendo que na "
  "segunda colheita deve ser realizada 15 dias depois")
r(c, 9, "colheita_umidade", "12", "% máximo para colher", "verificado",
  F_ALGODAO, U_ALGODAO, "34",
  "Não colher o algodão com umidade acima do permitido, máximo de 12 %")
r(c, 9, "colheita_metodo",
  "Manual, por etapas, em dia ensolarado; colhem-se só capulhos bem formados e "
  "totalmente abertos", "", "verificado", F_ALGODAO, U_ALGODAO, "34",
  "A colheita do algodão colorido no Nordeste é feita manualmente")
r(c, 10, "armazenamento_umidade_segura", "8 a 10", "% (algodão em caroço)",
  "verificado", F_ALGODAO, U_ALGODAO, "35",
  "A umidade ideal de armazenamento do algodão em caroço é de 8 a 10%")
r(c, 10, "embalagem",
  "Saco de pano de algodão bem arejado, capacidade de 45 a 60 kg; não usar "
  "juta ou plástico", "", "verificado", F_ALGODAO, U_ALGODAO, "35",
  "deve ser colocado em saco de pano, de preferência de tecido de algodão "
  "bastante arejado com capacidade para 45 a 60 kg")
r(c, 10, "beneficiamento",
  "Limpeza e descaroçamento em miniusina, separando pluma e caroço", "",
  "verificado", F_ALGODAO2, U_ALGODAO2, "23",
  "Descaroçamento Depois da limpeza, o algodão em caroço entra na câmara de "
  "descaroçamento")
lac(c, 10, "praga_armazenamento", "não localizado trecho específico")

# ============================================================== MANDIOCA ====
F_MANDIOCA = ("Embrapa Rondônia. Cultivo da mandioca no estado de Rondônia. "
              "Sistemas de Produção 37, dez. 2018")
U_MANDIOCA = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
              "1111136/1/SistemadeProduc807a771odeMandioca.pdf")
c = "mandioca"
r(c, 1, "finalidade",
  "Produção de raízes para consumo e comercialização; produto de subsistência "
  "colhido o ano inteiro", "", "verificado", F_MANDIOCA, U_MANDIOCA, "46",
  "a mandioca, como produto de subsistência, é colhida o ano inteiro, para "
  "atender ao consumo e à comercialização nas feiras livres")
r(c, 1, "vantagem_semiarido",
  "Baixa exigência hídrica; após os cinco meses iniciais o déficit hídrico "
  "favorece o acúmulo de amido nas raízes", "", "verificado",
  F_MANDIOCA, U_MANDIOCA, "25",
  "após este período crítico (cinco meses iniciais), o déficit hídrico favorece "
  "o acúmulo de amido nas raízes")
r(c, 1, "limitacao_principal",
  "Raízes se deterioram rapidamente: não devem ficar no campo mais de 24 horas "
  "após a colheita", "", "verificado", F_MANDIOCA, U_MANDIOCA, "47",
  "devendo-se evitar que permaneçam no campo por mais de 24 horas, para que não "
  "ocorra a deterioração fisiológica e/ ou bacteriológica")
r(c, 8, "capina",
  "Duas a três limpas com enxada, por aproximadamente 100 dias (período "
  "crítico de interferência)", "", "verificado", F_MANDIOCA, U_MANDIOCA, "28",
  "duas a três limpas com enxada, por aproximadamente 100 dias (período "
  "crítico de interferência)")
r(c, 8, "praga",
  "Mandarová (Erinnyis ello) | dano: severo desfolhamento, sobretudo nos "
  "primeiros meses | manejo: monitoramento e controle cultural", "",
  "verificado", F_MANDIOCA, U_MANDIOCA, "31",
  "Mandarová - Erinnyis ello (L.) Uma das mais importantes pragas para a "
  "mandioca, pela ampla dispersão e alta capacidade de consumo foliar")
r(c, 8, "doenca",
  "Antracnose (Colletotrichum gloeosporioides) e viroses | sintoma: lesões e "
  "redução do amido nas raízes | manejo: material de plantio selecionado, "
  "variedades resistentes e eliminação de plantas afetadas", "",
  "verificado", F_MANDIOCA, U_MANDIOCA, "45",
  "a antracnose causada por Colletotrichum gloeosporioides pode causar "
  "prejuízos esporádicos ou temporários na mandioca")
r(c, 9, "colheita_dias_apos_plantio",
  "10 a 12 meses (precoces); 14 a 16 (semiprecoces); 18 a 20 (tardias)",
  "meses", "verificado", F_MANDIOCA, U_MANDIOCA, "45",
  "Ciclo das cultivares (precoces - 10-12 meses; semiprecoces – 14- 16 meses; e "
  "tardias-18-20 meses)")
r(c, 9, "colheita_indicador",
  "Colher no repouso da planta (temperaturas baixas e pouca chuva), quando "
  "diminui folhas e atinge máximo de amido", "", "verificado",
  F_MANDIOCA, U_MANDIOCA, "46",
  "quando, pelas condições de clima (temperaturas mais baixas e pouca chuva), "
  "elas já diminuíram o número e o tamanho das folhas ... máximo de produção de "
  "raízes com elevado teor de amido")
r(c, 9, "colheita_metodo",
  "Arranquio manual ou com implementos; raízes amontoadas e carregadas em "
  "bigbags, cestos, caixas ou sacos", "", "verificado",
  F_MANDIOCA, U_MANDIOCA, "47",
  "Após o arranquio ou colheita das raízes, estas devem ser amontoadas em "
  "pontos na área")
r(c, 10, "armazenamento_umidade_segura",
  "Raízes devem seguir ao beneficiamento em até 24 horas; manivas guardadas em "
  "local fresco, úmido e sombreado", "", "verificado",
  F_MANDIOCA, U_MANDIOCA, "23",
  "Guardar as ramas o mais próximo possível da área a ser plantada, em local "
  "fresco, com umidade moderada, sombreado")
r(c, 10, "manejo_preventivo",
  "Evitar permanência no campo por mais de 24 horas para não haver deterioração "
  "fisiológica/bacteriológica", "", "verificado", F_MANDIOCA, U_MANDIOCA, "47",
  "devendo-se evitar que permaneçam no campo por mais de 24 horas")
lac(c, 10, "praga_armazenamento", "o documento não trata de pragas de "
    "armazenamento de raízes")

# ================================================================ PALMA ====
F_PALMA = ("Embrapa Semiárido. Sistema de Produção de Palma-Forrageira para o "
           "Estado da Paraíba")
U_PALMA = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
           "1142333/1/Sistema-de-Producao-de-Palma-Forrageira-para-o-Estado-"
           "da-Paraiba.pdf")
c = "palma_forrageira"
r(c, 1, "finalidade",
  "Produção de forragem para os animais, com usos também na alimentação "
  "humana (frutos e verdura)", "", "verificado", F_PALMA, U_PALMA, "2",
  "destacando-se a produção de frutos e verdura para a alimentação humana e a "
  "de forragem para os animais")
r(c, 1, "vantagem_semiarido",
  "Amplamente difundida na região Semiárida brasileira como forrageira",
  "", "verificado", F_PALMA, U_PALMA, "15",
  "foram também amplamente difundidas na região Semiárida brasileira")
r(c, 1, "limitacao_principal",
  "Cultivares suscetíveis à cochonilha-do-carmim tiveram áreas dizimadas ou "
  "substituídas", "", "verificado", F_PALMA, U_PALMA, "15",
  "por serem suscetíveis à cochonilha-do-carmim (Dactylopius opuntiae "
  "Cockerell), tiveram suas áreas dizimadas ou substituídas")
r(c, 8, "fase_duracao_dias",
  "Corte recomendado em intervalos de 2 anos, com pelo menos dois ciclos de "
  "chuva", "meses", "verificado", F_PALMA, U_PALMA, "57",
  "Diversos autores têm recomendado a colheita em intervalos de 2 anos, uma vez "
  "que esse período proporciona à cultura passar por pelo menos dois ciclos de "
  "chuva")
r(c, 8, "praga",
  "Cochonilha-do-carmim (Dactylopius opuntiae) | dano: pode causar grandes "
  "prejuízos ao palmal | manejo: uso de cultivares resistentes e monitoramento",
  "", "verificado", F_PALMA, U_PALMA, "15",
  "A cochonilha-do-carmim é uma praga importante que pode causar grandes "
  "prejuízos nos sistemas de produção de palma")
r(c, 8, "doenca",
  "Podridão-escamosa e mancha de alternária | sintoma: lesões nos cladódios | "
  "manejo: manejo do palmal e higienização de ferramentas", "",
  "verificado", F_PALMA, U_PALMA, "53",
  "Podridão-escamosa")
lac(c, 8, "capina", "o capítulo de manejo de plantas daninhas não foi transcrito")
r(c, 9, "colheita_indicador",
  "Corte na interseção dos cladódios (junta), preservando cladódios primários "
  "ou secundários", "", "verificado", F_PALMA, U_PALMA, "57",
  "este deve ser feito na interseção dos cladódios (junta) ... é indicado "
  "preservar, após a colheita, os cladódios primários")
r(c, 9, "colheita_metodo",
  "Corte com instrumentos bem afiados e higienizados", "", "verificado",
  F_PALMA, U_PALMA, "57",
  "utilizando-se instrumentos de corte bem afiados e higienizados")
r(c, 9, "colheita_dias_apos_plantio", "24", "meses (intervalo de colheita "
  "recomendado)", "verificado", F_PALMA, U_PALMA, "57",
  "a colheita em intervalos de 2 anos")
lac(c, 10, "armazenamento_umidade_segura", "o documento não trata de "
    "armazenamento de forragem")
lac(c, 10, "praga_armazenamento", "não localizado trecho específico")

# =============================================================== GUANDU ====
F_GUANDU = ("Embrapa Caprinos e Ovinos. Guandu para produção de forragem e de "
            "grãos no semiárido cearense (Comunicado Técnico 191, 2019)")
U_GUANDU = ("https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/"
            "1117099/1/CNPC2019Cot191.pdf")
F_BPD63 = ("Embrapa Semiárido. Comportamento de leguminosas para adubação verde "
           "em cultivo irrigado no submédio São Francisco (Boletim de Pesquisa "
           "63, 2004)")
U_BPD63 = "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/154470/1/BPD63.pdf"
F_ADUBOS = ("Embrapa CNPMS. Características de alguns adubos verdes de "
            "interesse para a conservação do solo (Pesq. Agropec. Bras. "
            "30(2):175-185, 1995)")
U_ADUBOS = ("https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/477333/1/"
            "Caracteristicas-alguns.pdf")
c = "guandu"
r(c, 1, "finalidade",
  "Produção de forragem e de grãos no semiárido cearense", "",
  "verificado", F_GUANDU, U_GUANDU, "2",
  "Guandu para produção de forragem e de grãos no")
r(c, 1, "vantagem_semiarido",
  "Eficiência na descompactação do solo e uso como adubo verde", "",
  "verificado", F_GUANDU, U_GUANDU, "3",
  "devido a sua eficiência na descompactação do solo")
lac(c, 1, "limitacao_principal", "não localizado trecho específico")
r(c, 8, "fase_duracao_dias",
  "105 a 120 (genótipo D2-TYPE); 128 a 175 (Traipeiro)", "dias até a floração "
  "plena", "verificado", F_BPD63, U_BPD63, "7",
  "O guandu D2-TYPE e as mucunas apresentaram ciclo médio (105 a 120 dias) e o "
  "guandu Traipeiro e o lab-lab, ciclo longo (128 a 175 dias)")
lac(c, 8, "fase_duracao_dias",
    "tabela de CAF (p.9) desalinhada na extração; valor não confirmado")
lac(c, 8, "praga", "não localizado trecho específico para guandu")
lac(c, 8, "doenca", "não localizado trecho específico para guandu")
lac(c, 9, "colheita_indicador", "não localizado trecho específico")
lac(c, 9, "colheita_metodo", "não localizado trecho específico")
lac(c, 10, "armazenamento_umidade_segura", "não localizado trecho específico")
lac(c, 10, "praga_armazenamento", "não localizado trecho específico")

# ==================================================== PLANTAS DE COBERTURA ==
# crotalária, mucuna e feijão-de-porco: foco em ciclo e manejo de corte.
for c in ("crotalaria_juncea", "mucuna", "feijao_de_porco"):
    r(c, 1, "finalidade",
      "Adubação verde, cobertura do solo e reciclagem de nutrientes", "",
      "verificado", F_BPD63, U_BPD63, "7",
      "As leguminosas sao as plantas mais utilizadas como adubo verde")
    lac(c, 1, "vantagem_semiarido", "o boletim não isola vantagem por espécie "
        "no semiárido")
    lac(c, 1, "limitacao_principal", "não localizado trecho específico")

r("crotalaria_juncea", 8, "fase_duracao_dias", "63 a 82", "dias até a floração "
  "plena", "verificado", F_BPD63, U_BPD63, "7",
  "as que apresentaram ciclo curto (63 a 82 dias) foram as crotalárias, o "
  "feijão-de-porco")
lac("crotalaria_juncea", 8, "fase_duracao_dias",
    "tabela de CAF (p.9) desalinhada na extração; valor não confirmado")
r("crotalaria_juncea", 9, "colheita_indicador",
  "Manejo no florescimento pleno, quando a biomassa está formada", "",
  "verificado", F_BPD63, U_BPD63, "7",
  "o período compreendido entre o plantio e a floracao plena (ciclo) de cada "
  "leguminosa")
lac("crotalaria_juncea", 8, "praga", "não localizado trecho específico")
lac("crotalaria_juncea", 8, "doenca", "não localizado trecho específico")
lac("crotalaria_juncea", 10, "armazenamento_umidade_segura", "cultura de "
    "cobertura, sem grão colhido na fonte")

r("mucuna", 8, "fase_duracao_dias", "105 a 120", "dias até a floração plena",
  "verificado", F_BPD63, U_BPD63, "7",
  "O guandu D2-TYPE e as mucunas apresentaram ciclo médio (105 a 120 dias)")
lac("mucuna", 8, "fase_duracao_dias",
    "tabela de CAF (p.9) desalinhada na extração; valor não confirmado")
r("mucuna", 9, "colheita_indicador",
  "Manejo no florescimento pleno, quando a biomassa está formada", "",
  "verificado", F_BPD63, U_BPD63, "7",
  "o período compreendido entre o plantio e a floracao plena (ciclo)")
lac("mucuna", 8, "praga", "não localizado trecho específico")
lac("mucuna", 8, "doenca", "não localizado trecho específico")
lac("mucuna", 10, "armazenamento_umidade_segura", "cultura de cobertura, sem "
    "grão colhido na fonte")

r("feijao_de_porco", 8, "fase_duracao_dias", "63 a 82", "dias até a floração "
  "plena", "verificado", F_BPD63, U_BPD63, "7",
  "as que apresentaram ciclo curto (63 a 82 dias) foram as crotalárias, o "
  "feijão-de-porco e o feojao bravo do Ceara")
r("feijao_de_porco", 8, "fase_duracao_dias", "90 (Viçosa-MG)", "dias até o "
  "florescimento", "verificado", F_ADUBOS, U_ADUBOS, "9",
  "F.Porco      26,8c     5,3e   96,7b   90", "Viçosa-MG, não semiárido")
r("feijao_de_porco", 9, "colheita_indicador",
  "Manejo no florescimento pleno, quando a biomassa está formada", "",
  "verificado", F_BPD63, U_BPD63, "7",
  "o período compreendido entre o plantio e a floracao plena (ciclo)")
lac("feijao_de_porco", 8, "praga", "não localizado trecho específico")
lac("feijao_de_porco", 8, "doenca", "não localizado trecho específico")
lac("feijao_de_porco", 10, "armazenamento_umidade_segura", "cultura de "
    "cobertura, sem grão colhido na fonte")

# ------------------------------------------------------------- escrita ------
def escrever():
    # garante que o trecho seja um recorte literal do material coletado
    import glob as _glob
    import re as _re
    import unicodedata as _ud
    _dirs = [r"C:/Users/Administrator/AppData/Local/Temp/pdfs",
             r"C:/Users/Administrator/AppData/Local/Temp/ragtxt"]

    def _norm(s):
        s = _ud.normalize("NFKD", _re.sub(r"\s+", " ", s))
        return "".join(c for c in s if not _ud.combining(c)).lower()

    _corpus = ""
    for _d in _dirs:
        for _f in _glob.glob(_d + "/*.txt"):
            with open(_f, encoding="utf-8", errors="replace") as _fh:
                _corpus += " " + _fh.read()
    _corpus = _norm(_corpus)

    for x in ROWS:
        if x["status"] != "verificado" or not x["trecho"]:
            continue
        if _norm(x["trecho"]) in _corpus:
            continue
        palavras = x["trecho"].split()
        melhor = ""
        for i in range(len(palavras)):
            for j in range(len(palavras), i, -1):
                cand = " ".join(palavras[i:j])
                if len(cand) <= len(melhor):
                    break
                if _norm(cand) in _corpus:
                    melhor = cand
                    break
        if len(melhor) >= 25:
            print("trecho ajustado:", x["cultura_id"], x["etapa"],
                  x["atributo"], "->", melhor)
            x["trecho"] = melhor
        else:
            print("TRECHO NAO LOCALIZADO:", x["cultura_id"], x["etapa"],
                  x["atributo"], "->", x["trecho"][:60])
            x["status"] = "lacuna"
            x["valor"] = ""
            x["unidade"] = ""
    for et in (1, 8, 9, 10):
        nome = "etapa_%02d.csv" % et
        linhas = [x for x in ROWS if x["etapa"] == et]
        caminho = os.path.join(OUT, nome)
        with open(caminho, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            w.writeheader()
            w.writerows(linhas)
        print(nome, len(linhas))


if __name__ == "__main__":
    escrever()
