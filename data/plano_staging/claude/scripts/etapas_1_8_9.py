"""Revisa valor x trecho das etapas 1, 8 e 9 do OpenCode. Nao altera o original: grava claude/etapa_01|08|09.csv
e claude/correcoes_1_8_9.csv (antes/depois). Toda linha so entra se o trecho existir na pagina citada."""
import csv, json, os
import curar
from curar import norm, paginas, COLS, DATA

ORIG = r"C:\Users\Administrator\Documents\Projects\2 - Pessoal\ai\sulco-nasa\data\plano_staging\opencode"
UM = json.load(open(os.path.join(curar.HERE, "urlmap.json")))
REV = "REVISÃO TÉCNICA: "


def regiao(f):
    if "Rondônia" in f: return "Embrapa Rondônia (Amazônia; não é semiárido)"
    if "Feijoeiro" in f or "Tabuleiros Costeiros" in f: return "Embrapa Tabuleiros Costeiros, publicação para a região Nordeste (2012–2014)"
    if "Meio-Norte" in f: return "Embrapa Meio-Norte (Piauí e Maranhão; não é o Ceará)"
    if "CNPSo" in f: return "Embrapa Soja (fonte nacional)"
    if "Milho e Sorgo" in f: return "Embrapa Milho e Sorgo (fonte nacional)"
    if "Caprinos" in f: return "Embrapa Caprinos e Ovinos (Sobral, Ceará; semiárido cearense)"
    if "Semi-Árid" in f or "Semiárid" in f: return "semiárido do Nordeste"
    if "Algodão" in f: return "Embrapa Algodão (Nordeste)"
    if "Mandioca" in f: return "Embrapa Mandioca e Fruticultura"
    return ""


# (etapa, cultura, atributo, prefixo do valor) -> novos campos. 'remover': True descarta a linha.
E = {}
def ed(et, c, a, p, **kw): E[(et, c, a, p)] = kw

# ---------------- ETAPA 1
ed(1, "milho", "limitacao_principal", "Sensível", valor="O principal fator de risco é o déficit hídrico")
ed(1, "sorgo", "finalidade", "Produção de grãos", valor="Produção de grãos para alimentação animal, cultivado em sucessão a culturas de verão")
ed(1, "sorgo", "vantagem_semiarido", "Alto potencial", valor="Alto potencial de produção de grãos e matéria seca e extraordinária capacidade de suportar estresses ambientais", ctx="a fonte é nacional e não cita o semiárido")
ed(1, "sorgo", "limitacao_principal", "A produtividade", valor="A sensibilidade ao déficit hídrico varia com o estádio da planta, a duração do estresse e o genótipo")
ed(1, "feijao_caupi", "finalidade", "Produção de grãos secos", pagina=14, atributo="importancia_regional", valor="Cultura de destaque entre as atividades agropecuárias do Brasil, principalmente nas regiões Norte e Nordeste")
ed(1, "milheto", "finalidade", "Produção de palhada", valor="Principal uso no Brasil: planta de cobertura para o sistema de plantio direto")
ed(1, "girassol", "finalidade", "Produção de aquênios", valor="Produção de óleo, de excelentes características físico-químicas e nutricionais")
ed(1, "girassol", "limitacao_principal", "Baixa eficiência", valor="Baixa eficiência no uso da água: cada litro de água consumido produz menos de dois gramas")
ed(1, "gergelim", "finalidade", "Produção de sementes", valor="Sementes para as indústrias alimentícia e oleoquímica e, potencialmente, para biodiesel")
ed(1, "amendoim", "finalidade", "Produção de grãos", valor="Os grãos de amendoim são fonte de óleo")
ed(1, "amendoim", "limitacao_principal", "Déficit", valor="Temperaturas acima de 32 °C afetam negativamente várias fases do ciclo, especialmente o florescimento",
   trecho="Temperaturas acima de 32 °C afetam negativamente várias fases do ciclo de desenvolvimento da planta, especialmente durante o florescimento")
ed(1, "algodao", "finalidade", "Produção de fibra", valor="Fibra (pluma) limpa e pronta para a fiação, obtida no beneficiamento, que separa a fibra do caroço",
   trecho="consiste em separar a fibra das sementes, por meio de processos mecânicos, em que se retira o caroço, obtendo-se fibras limpas e prontas para a fiação")
ed(1, "algodao", "limitacao_principal", "O bicudo", valor="O surgimento do bicudo do algodoeiro aumentou os custos de produção")
ed(1, "mandioca", "vantagem_semiarido", "Baixa exigência", valor="Após os cinco meses iniciais (período crítico), o déficit hídrico favorece o acúmulo de amido nas raízes")
ed(1, "mandioca", "limitacao_principal", "Raízes", valor="Evitar que as raízes colhidas permaneçam no campo por mais de 24 horas, para que não ocorra deterioração fisiológica ou bacteriológica")
ed(1, "guandu", "vantagem_semiarido", "Eficiência", valor="Eficiência na descompactação do solo")
for cc in ("crotalaria_juncea", "mucuna", "feijao_de_porco"):
    ed(1, cc, "finalidade", "Adubação verde", valor="Leguminosa usada como adubo verde", ctx="a fonte trata das leguminosas em geral, não desta espécie em particular")

# ---------------- ETAPA 8
ed(8, "milho", "fases_fenologicas", "VE", atributo="estadio_V5", valor="No estádio V5 (cinco folhas completamente desenvolvidas), a iniciação das folhas e das espigas está completa")
ed(8, "milho", "plantas_daninhas_criticas", "caruru", valor="Dicotiledôneas citadas pela fonte: caruru, balãozinho, picão-preto, leiteira, corda-de-viola, nabiça, poaia-branca, trapoeraba e guanxuma",
   trecho="como Amaranthus spp (caruru), Cardiospermum halicacabum (balãozinho), Bidens spp. (picão -preto),Euphorbia heterophylla (leiteira), Ipomoea spp (corda de- viola), Raphanus sativus (nabiça), Richardia brasiliensis (poaia -branca), Commelina benghalensis(trapoeraba) e Sida spp. (guanxuma)")
ed(8, "milho", "praga", "Lagarta-do-cartucho", valor="Lagarta-do-cartucho (Spodoptera frugiperda): a fase do cartucho deixa o milho muito suscetível ao ataque; a fonte exige vigilância constante",
   trecho="conferem à cultura do milho elevada suscetibilidade ao ataque da lagarta do cartucho (Spodoptera frugiperda), exigindo assim constante vigilância")
ed(8, "milho", "praga", "Lagarta-elasmo", valor="Lagarta-elasmo: a alta umidade do solo contribui para reduzir os problemas que ela causa no milho", ctx=REV + "a página também cita inseticida; a tela não orienta")
ed(8, "milho", "praga", "Cigarrinha", atributo="doenca_manejo_cultural",
   valor="Para o controle da doença descrita, os métodos culturais, como a eliminação dos hospedeiros nativos do patógeno e do vetor (gramíneas em geral), têm sido os mais eficientes",
   ctx="vem logo depois da seção de enfezamentos; a frase não nomeia a doença nem a cigarrinha")
ed(8, "milho", "doenca", "Enfezamento", valor="Enfezamento pálido: no início, folhas com deformações e depois clorose das bordas da base das folhas, que pode progredir para toda a planta, com nanismo acentuado",
   trecho="Enfezamento pálido - no início, plantas podem apresentar folhas com deformações e posteriormente inicia-se pela descoloração (clorose) das bordas da base das folhas que pode progredir para toda a planta, nanismo acentuado")
ed(8, "sorgo", "fases_fenologicas", "9 est", valor="50% de floração por volta dos 60 dias; grão leitoso por volta dos 70; pastoso por volta dos 85 (dias após a emergência)", unidade="dias",
   trecho="Estádio 6 (50% de floração) – O período da emergência a 50% de floração (cerca de 60 dias) é de aproximadamente 2/3 do período da emergência à maturação fisiológica. Estádio 7 (Leitoso) – Cerca de 50% da matéria seca dos grãos já foram acumulados (cerca de 70 dias após a emergência), e o peso do colmo diminui. Estádio 8 (Pastoso) – Cerca de ¾ de matéria seca dos grãos já foram acumulados (cerca de 85 dias após a emergência)")
ed(8, "feijao_caupi", "capina", "Capina manual", pagina=124, valor="São necessários 8 a 10 dias por homem para capinar 1 ha")
ed(8, "feijao_caupi", "praga", "Vaquinhas", valor="Pragas citadas pela fonte: lagarta-elasmo, vaquinhas, mosca-branca, cigarrinha-verde, larva-minadora, tripes, lagartas-das-vagens, percevejos, manhoso e caruncho",
   trecho="lagarta-elasmo (Elasmopalpus lignosellus), vaquinhas (Diabrotica speciosa e Cerotoma arcuata), mosca-branca (Bemisia tabaci biótipo B), cigarrinha-verde (Emposca sp.), larva-minadora (Liriomyza sp.), tripes (Thrips palmi e outras espécies), lagartas-das-vagens (Maruca sp. e Etiella zinckenella), percevejos (Crinocerus sanctus, Nezara viridula e Piezodorus guildinii), manhoso (Chalcodermus bimaculatus) e caruncho (Callosobruchus maculatus)")
ed(8, "feijao_caupi", "praga", "Manhoso", valor="Manhoso: a postura deixa uma cicatriz saliente e os orifícios de alimentação permanecem abertos",
   trecho="formam, posteriormente, uma cicatriz saliente, característica da postura do manhoso. Os orifícios de alimentação permanecem abertos")
ed(8, "feijao_caupi", "doenca", "Murcha", valor="Doenças causadas por fungos de solo: podridões radiculares (Rhizoctonia solani e Fusarium solani), murcha de fusário, podridão-cinzenta do caule e murcha de esclerócio",
   trecho="podridões radiculares provocadas por Rhizoctonia solani e Fusarium solani f. sp. phaseoli, a murcha de fusário (Fusarium oxysporum f. sp. phaseoli), a podridão-cinzenta do caule (Macrophomina phaseolina) e a murcha de esclerócio (Sclerotium rolfsii)")
ed(8, "feijao_comum", "capina", "Capina manual", valor="Capina manual e cultivadores à tração animal ou mecânicos, com o solo pouco úmido",
   trecho="Realizado por meio de capina manual e por meio de cultivadores à tração animal e mecânico, com o solo pouco úmido para aumentar a eficiência de controle")
ed(8, "feijao_comum", "doenca", "Antracnose", valor="Ferrugem (Uromyces appendiculatus): ocorre mais nas folhas, também em vagens e hastes; manchas pequenas e esbranquiçadas na face inferior das folhas viram pústulas marrom-avermelhadas",
   trecho="Ferrugem (Uromyces appendiculatus) Ocorre mais nas folhas, embora seja observada também em vagens e hastes. Primeiro surgem manchas pequenas, esbranquiçadas e levemente salientes na parte inferior das folhas. Estas manchas aumentam de tamanho até produzirem pústulas maduras, de cor marrom-avermelhada")
ed(8, "milheto", "fases_fenologicas", "Florescimento", remover=True)
ed(8, "milheto", "fase_duracao_dias", "104", valor="104 (BRS1501 e BRS1502)", unidade="dias", ctx="maturidade fisiológica, em dias após a emergência (DAE)",
   trecho="a maturidade fisiológica das cultivares de milheto BRS1501 e BRS1502 ocorre aos 104 DAE")
ed(8, "milheto", "praga", "Percevejos", atributo="praga_sintoma", valor="Sintoma de ataque de insetos sugadores: grãos manchados e reduzidos no tamanho; panículas com grãos mal formados e manchados",
   trecho="Os grãos tornam-se manchados e ficam reduzidos no tamanho. Panículas com grãos mal formados e manchados são sintoma do ataque desses insetos")
ed(8, "milheto", "doenca", "Ergot", valor="Ergot: ocorre em praticamente todas as regiões onde o milheto é cultivado; a exsudação açucarada e pegajosa das flores doentes adere aos grãos, dificulta a colheita e dá mau aspecto ao produto",
   trecho="O ergot é uma doença que ocorre em praticamente todas as regiões onde o milheto é cultivado. As perdas da produção ocorrem em decorrência da exsudação de substância açucarada e pegajosa oriunda de flores doentes que aderem aos grãos, dificultando a colheita e dando um mau aspecto ao produto")
ed(8, "girassol", "praga", "Percevejos", valor="Insetos atacam da floração inicial ao fim do florescimento, sugam a seiva na região de inserção do capítulo e podem causar murcha e perda do capítulo em formação",
   trecho="a partir da fase de floração inicial até a fase de final de florescimento. Estes insetos afetam, preferencialmente, a região de inserção do capítulo, onde sugam a seiva, podendo ocasionar a murcha e a perda do capítulo em formação")
ed(8, "girassol", "doenca", "Mancha", valor="As duas doenças mais importantes: mancha de alternária (Alternaria helianthi), que afeta folhas, haste e capítulo, e podridão branca (Sclerotinia sclerotiorum)",
   trecho="a mancha de alternária, causada pelo fungo Alternaria helianthi e a podridão branca, causada pelo fungo Sclerotinia sclerotiorum, são as mais importantes. A mancha de alternária, que afeta folhas, haste e capítulo")
ed(8, "gergelim", "praga", "Lagarta-enroladeira", valor="Pulgões (cultivos irrigados): ataque inicial em reboleiras; formam colônias na face inferior das folhas, que ficam brilhosas pela 'mela'; a fumagina impede a fotossíntese; transmitem viroses",
   trecho="pulgões ocorrem em cultivos irrigados. O ataque inicial é feito em reboleiras. Formam colônias na face inferior das folhas (Figura 2), que se tornam brilhosas por causa da excreção da “mela” proveniente da sucção do açúcar. O açúcar serve de substrato para o desenvolvimento da fumagina, que impede a fotossíntese. Eles são transmissores de viroses",
   ctx=REV + "a fonte recomenda inseticida sistêmico; a tela não orienta")
ed(8, "gergelim", "doenca", "Podridão-negra", valor="Podridão-negra, causada por Macrophomina phaseolina, com sintomas no caule e nas plantas de gergelim")
ed(8, "amendoim", "praga", "Percevejo-preto", valor="Percevejo-preto (Cyrtomenus mirabilis): ocorre em solos pobres que antes foram pastagem; adultos pretos de cerca de 7 mm; ataca raízes e vagens",
   trecho="Percevejo-preto (Cyrtomenus mirabilis (Perty) Perty) Descrição: Sua ocorrência é comum em solos pobres que anteriormente tenham sido ocupados por pastagens. Os adultos são de coloração preta (Figura 11.4) com aproximadamente 7 mm de comprimento, enquanto as formas jovens possuem coloração esbranquiçada (Gallo et al., 2002). Danos: Atacam as raízes e vagens das plantas")
ed(8, "amendoim", "doenca", "Murcha-de-Sclerotium", valor="Cercosporioses e mancha-anelar: a cultivar BRS 425 OL é moderadamente resistente às duas",
   trecho="BRS 425 OL – Cultivar do tipo runner alto oleico, ciclo de 135 a 140 dias. As sementes de cor creme são arredondadas, predominando na peneira 40/50. É moderadamente resistente às cercosporioses e à mancha-anelar")
ed(8, "mamona", "fase_duracao_dias", "230", unidade="dias", ctx="da emergência à última colheita")
ed(8, "mamona", "praga", "Percevejo verde", valor="Lagarta rosca (Agrotis ipsilon): lagartas escuras que vivem no solo de dia e à noite cortam o colo das plantas jovens",
   trecho="Lagarta rosca (Agrotis ipsilon): Lagartas de cor escura (Figura 32), borboleta de cor marrom (Figura 33); durante o dia vivem no solo e, à noite, cortam o colo das plantas jovens",
   ctx=REV + "a fonte indica inseticidas; a tela não orienta")
ed(8, "mamona", "doenca", "Mofo", valor="Mofo cinzento: principal doença da mamona, pode reduzir a produção a zero; o fungo infecta na floração, fixa-se nos cachos jovens e seca os frutos jovens",
   trecho="Mofo cinzento: Principal doença da mamona, identificada nos Estados Unidos em 1918 e, no Brasil, 1932, podendo reduzir a produção a zero. Doença provocada pelo fungo Botryotinia ricini, na sua forma perfeita, correspondente à forma imperfeita de Amphobotrys ricini, que se infecta na fase de floração, cujos fungos se fixam nos cachos jovens, provocando o secamento dos frutos jovens")
ed(8, "algodao", "praga", "Broca", atributo="praga_manejo_cultural",
   valor="A pesquisa prefere cultivares de ciclo curto no algodão orgânico, para reduzir o tempo de exposição das plantas à colonização e infestação de pragas (broca, bicudo, lagarta das maçãs e lagarta rosada)",
   trecho="a utilização de cultivares de algodão de ciclo curto seja preferida pelo produtor de algodão orgânico, na tentativa de reduzir o tempo de exposição das plantas à colonização e infestação de pragas (broca, bicudo, lagarta das maçãs e lagarta rosada)")
ed(8, "algodao", "doenca", "Baixa", valor="A incidência de doenças foliares e de solo é baixa na região Nordeste")
ed(8, "mandioca", "praga", "Mandarová", valor="Mandarová (Erinnyis ello): uma das mais importantes pragas, pela ampla dispersão e alta capacidade de consumo foliar; a lagarta pode causar severo desfolhamento e, nos primeiros meses, até a morte de plantas jovens",
   trecho="Mandarová - Erinnyis ello (L.) Uma das mais importantes pragas para a mandioca, pela ampla dispersão e alta capacidade de consumo foliar. A lagarta pode causar severo desfolhamento, o qual, durante os primeiros meses de cultivo, pode até ocasionar a morte de plantas jovens")
ed(8, "mandioca", "doenca", "Antracnose", valor="Antracnose (Colletotrichum gloeosporioides): pode causar prejuízos esporádicos ou temporários e, em certas épocas, perdas significativas na produção de raízes e redução da qualidade",
   trecho="a antracnose causada por Colletotrichum gloeosporioides pode causar prejuízos esporádicos ou temporários na mandioca; em determinadas épocas ela ocorre de maneira mais intensiva, causando perdas significativas na produção de raízes e redução da qualidade dos produtos")
ed(8, "palma_forrageira", "praga", "Cochonilha", valor="Cochonilha-do-carmim: praga importante que pode causar grandes prejuízos; cultivares resistentes são a principal medida de controle",
   trecho="A cochonilha-do-carmim é uma praga importante que pode causar grandes prejuízos nos sistemas de produção de palma-forrageira. Dessa forma, a utilização de cultivares resistentes, seja em novas áreas ou para reforma do palmal, é a principal medida de controle")
ed(8, "palma_forrageira", "doenca", "Podridão-escamosa", valor="Podridão-escamosa: relacionada ao fungo Scytalidium lignicola; geralmente começa no local de inserção dos cladódios primários, secundários ou terciários",
   trecho="Essa doença é comumente relacionada ao fungo Scytalidium lignicola Pes. Geralmente, essa podridão ocorre a partir do local de inserção dos cladódios primários, secundários ou terciários")

# ---------------- ETAPA 9
ed(9, "milho", "colheita_umidade", "25", unidade="%", ctx="colheita mecanizada")
ed(9, "milho", "colheita_metodo", "Manual", valor="A colheita manual é mais apropriada para pequenas propriedades e terrenos declivosos; na mecanizada, a regulagem adequada das máquinas é importante",
   trecho="É mais apropriada para pequenas propriedades e terrenos declivosos. Na colheita mecanizada, a regulagem adequada das máquinas é importante")
ed(9, "milho", "colheita_perdas", "1,0", valor="1,0 a 1,5 (colheita manual)", unidade="%")
ed(9, "sorgo", "colheita_umidade", "14", unidade="%", ctx="com secagem artificial")
ed(9, "feijao_caupi", "colheita_indicador", "Vagens secas", valor="Verificar se a casca da vagem está estalando: sinal de que os grãos estão com umidade adequada para o armazenamento")
ed(9, "feijao_caupi", "colheita_dias_apos_plantio", "Grupo I", atributo="ciclo_grupos_de_maturacao", unidade="dias",
   valor="Dias da emergência à maturação fisiológica: precoce (menos de 75), médio (75 a 85), tardio (mais de 85)",
   trecho="Grupo I – Precoce (n < 75 dias). • Grupo II – Médio (75 dias ≤ n ≤ 85 dias). • Grupo III – Tardio (n > 85 dias)")
ed(9, "feijao_comum", "colheita_indicador", "Colheita manual", valor="Colheita manual: arrancar as plantas inteiras quando os grãos têm cerca de 18% de água",
   trecho="as plantas são arrancadas inteiras quando os grãos apresentarem teor de água em torno de 18%")
ed(9, "feijao_comum", "colheita_metodo", "Manual", valor="Manual, semimecanizada ou mecanizada")
ed(9, "milheto", "colheita_indicador", "Maturação", valor="Na maturidade fisiológica as sementes têm 15% de umidade (BRS1501 e BRS1502, aos 104 dias) ou 20% (BRS1503, aos 97 dias)",
   trecho="ocorre aos 104 DAE, e, nesse momento, as sementes estão com 15% de umidade. Já a maturação fisiológica da cultivar BRS1503 ocorre antes, aos 97 DAE, e a semente estará com 20% de umidade")
ed(9, "milheto", "colheita_dias_apos_plantio", "90", unidade="dias", ctx="maturidade fisiológica, em dias após a emergência: 90 nas variedades comuns e 120 no Souna III",
   trecho="Para as variedades comum, ED9 ocorre aos 90 DAE (Costa e Priesnit, 2014). A maturidade fisiológica de sementes no genótipo Souna III ocorre aos 120 DAE")
ed(9, "milheto", "colheita_metodo", "Colheita de grãos", atributo="uso_dos_graos", valor="Os grãos colhidos são processados quase exclusivamente para a elaboração de ração animal")
ed(9, "girassol", "colheita_indicador", "Aquênios", valor="Iniciar a colheita quando a umidade dos aquênios estiver entre 14% e 16%")
ed(9, "girassol", "colheita_dias_apos_plantio", "90", unidade="dias", ctx="da emergência: cultivares precoces e tardias, respectivamente")
ed(9, "girassol", "colheita_cuidados", "Colheita antecipada", valor="A colheita antecipada, com maior teor de umidade, compromete a qualidade do produto")
ed(9, "gergelim", "colheita_indicador", "Amarelecimento", valor="Colher quando hastes, folhas e frutos atingirem o amarelecimento completo e antes de os frutos estarem totalmente abertos")
ed(9, "gergelim", "colheita_dias_apos_plantio", "90", unidade="dias", ctx="ciclo da maioria das cultivares",
   trecho="A colheita do gergelim deve ser programada para a época de estiagem e em sincronia com o ciclo da cultivar, que, na maioria, é de 90 a 110 dias")
ed(9, "gergelim", "colheita_metodo", "Manual", valor="As plantas devem ser cortadas na base, a 20 cm do solo")
ed(9, "amendoim", "colheita_indicador", "Vagens maduras", valor="No estádio R7 a película das sementes tem cor definida, diferente de branco; vagens imaturas têm o lado interno da casca espesso e branco",
   trecho="R7, associada à película das sementes com coloração definida, diferente de branco (Figura 13.1). Já as vagens imaturas apresentam o lado interno da casca espesso e branco")
ed(9, "amendoim", "colheita_metodo", "Em duas", valor="Em duas etapas: arranquio e recolhimento", trecho="A colheita de amendoim é feita em duas etapas: arranquio e recolhimento")
ed(9, "amendoim", "colheita_cuidados", "O arranquio", valor="No arranquio mecanizado, as lâminas cortadoras penetram no solo a cerca de 5 cm abaixo das vagens, para cortar as raízes e afofar o solo",
   trecho="O arranquio ocorre com as lâminas cortadoras penetrando no solo, à profundidade de aproximadamente 5 cm abaixo das vagens da planta, com a finalidade de cortar as raízes e proporcionar o afofamento do solo ao redor das vagens")
ed(9, "mamona", "colheita_metodo", "Manual", valor="Cortar o cacho na base, com ferramenta afiada (faca, canivete, tesoura ou foice pequena), e levar ao terreiro para secar",
   trecho="Fazer o corte na base do cacho, com uso de ferramentas afiadas, como: faca, canivete, tesoura ou foice pequena. Depositar os cachos em cesto ou carroça e colocá-los no terreiro, para secar")
ed(9, "algodao", "colheita_umidade", "12", unidade="%", ctx="máximo para colher")
ed(9, "algodao", "colheita_metodo", "Manual", valor="A colheita do algodão colorido no Nordeste é feita manualmente")
ed(9, "mandioca", "colheita_indicador", "Colher", trecho="são aquelas em que as plantas se encontram em período de repouso, ou seja, quando, pelas condições de clima (temperaturas mais baixas e pouca chuva), elas já diminuíram o número e o tamanho das folhas e dos lobos foliares, condição em que atinge o máximo de produção de raízes com elevado teor de amido")
ed(9, "mandioca", "colheita_metodo", "Arranquio", valor="Após o arranquio ou colheita das raízes, estas devem ser amontoadas em pontos na área")
ed(9, "palma_forrageira", "colheita_indicador", "Corte", valor="É indicado preservar os cladódios primários após a colheita")
ed(9, "palma_forrageira", "colheita_dias_apos_plantio", "24", valor="24 (2 anos)", unidade="meses", ctx="intervalo de colheita recomendado por diversos autores")
for cc in ("crotalaria_juncea", "mucuna", "feijao_de_porco"):
    ed(9, cc, "colheita_indicador", "Manejo", atributo="ciclo_ate_floracao_plena", valor="O ciclo da leguminosa de adubação verde é contado do plantio até a floração plena", ctx="a fonte define o ciclo; não diz quando manejar")

UN_OK = ("", "%", "°C", "dias", "meses")


def limpa_unidade(r, extra):
    u = r["unidade"].strip()
    if u in UN_OK: return u, extra
    for base in ("dias", "meses", "%"):
        if u.startswith(base):
            resto = u[len(base):].strip(" ()")
            return base, "; ".join(x for x in (extra, resto) if x)
    return "", "; ".join(x for x in (extra, u) if x)


def confere(arq, pag, trecho):
    t = norm(trecho)
    return any(1 <= pag <= len(v) and t in v[pag - 1] for v in paginas(arq))


log, rejeit = [], []
for et in (1, 8, 9):
    rows = list(csv.DictReader(open(ORIG + rf"\etapa_{et:02d}.csv", encoding="utf-8")))
    out, usadas = [], set()
    for r in rows:
        new = dict(r)
        if r["status"] != "verificado":
            if r["valor"].strip():   # lacuna com texto escrito sem trecho literal: o texto não pode ficar
                log.append((et, r["cultura_id"], r["atributo"], r["valor"], "(valor descartado: linha sem trecho literal da fonte)"))
                new["valor"] = ""
                new["contexto"] = (r["contexto"].strip() + "; " if r["contexto"].strip() else "") + "texto sem trecho literal da fonte foi descartado"
            if r["trecho"].strip() or r["fonte"].strip():   # lacuna não carrega fonte nem trecho: sem trecho conferido não há fonte
                log.append((et, r["cultura_id"], r["atributo"], f"(fonte/trecho removidos: {r['trecho'][:60]})", "(lacuna sem fonte)"))
                new.update(fonte="", url="", pagina="", trecho="")
            out.append(new); continue
        key = next((k for k in E if k[0] == et and k[1] == r["cultura_id"] and k[2] == r["atributo"] and r["valor"].startswith(k[3]) and k not in usadas), None)
        extra = ""
        if key:
            usadas.add(key); e = E[key]
            if e.get("remover"):
                log.append((et, r["cultura_id"], r["atributo"], r["valor"], "(linha removida: o trecho não identifica o estádio descrito)")); continue
            for k in ("atributo", "valor", "unidade", "trecho", "pagina"):
                if k in e: new[k] = e[k]
            extra = e.get("ctx", "")
            if new["valor"] != r["valor"] or new["trecho"] != r["trecho"] or new["atributo"] != r["atributo"]:
                log.append((et, r["cultura_id"], r["atributo"], r["valor"], new["valor"]))
        new["unidade"], extra = limpa_unidade(new, extra)
        reg = regiao(r["fonte"])
        new["contexto"] = "; ".join(x for x in (r["contexto"].strip(), extra, reg) if x)
        arq = UM.get(r["url"]); pag = int(new["pagina"])
        if not arq or not confere(arq, pag, new["trecho"]):
            rejeit.append((et, r["cultura_id"], r["atributo"], pag, new["trecho"][:70])); continue
        out.append(new)
    nao = [k for k in E if k[0] == et and k not in usadas]
    if nao: print("etapa", et, "correções que não casaram:", nao)

    def nova(cultura, atributo, valor, unidade, trecho, pag, ctx="", ref=None):
        ref = ref or next(x for x in rows if x["cultura_id"] == cultura and x["status"] == "verificado")
        arq = UM[ref["url"]]
        if not confere(arq, pag, trecho):
            rejeit.append((et, cultura, atributo, pag, trecho[:70])); return
        out.append(dict(cultura_id=cultura, etapa=et, atributo=atributo, valor=valor, unidade=unidade, status="verificado", fonte=ref["fonte"],
                        url=ref["url"], pagina=pag, trecho=trecho, contexto="; ".join(x for x in (ctx, regiao(ref["fonte"])) if x), data_consulta=DATA))
        log.append((et, cultura, atributo, "(linha nova)", valor))
    if et == 8:
        mil = next(x for x in rows if x["cultura_id"] == "milheto" and x["atributo"] == "fase_duracao_dias")
        nova("milheto", "fase_duracao_dias", "97 (BRS1503)", "dias", "a maturação fisiológica da cultivar BRS1503 ocorre antes, aos 97 DAE", 9, "maturidade fisiológica, em dias após a emergência", mil)
        nova("milheto", "fase_duracao_dias", "90 (variedades comuns)", "dias", "Para as variedades comum, ED9 ocorre aos 90 DAE", 9, "maturidade fisiológica, em dias após a emergência", mil)
        nova("milheto", "fase_duracao_dias", "120 (Souna III)", "dias", "A maturidade fisiológica de sementes no genótipo Souna III ocorre aos 120 DAE", 9, "maturidade fisiológica, em dias após a emergência", mil)
        fc = next(x for x in rows if x["cultura_id"] == "feijao_comum" and x["atributo"] == "capina")
        nova("feijao_comum", "capina_momento", "Iniciar no começo do desenvolvimento das plantas daninhas (a capina manual é demorada)", "",
             "Como a capina manual é uma operação demorada, deve ser iniciada no início de desenvolvimento das plantas daninhas", 59, "", fc)
        fd = next(x for x in rows if x["cultura_id"] == "feijao_comum" and x["atributo"] == "doenca")
        nova("feijao_comum", "doenca_manejo", "Ferrugem: o controle se dá pela resistência genética", "",
             "O controle desta enfermidade se dá através da resistência genética", 82, "", fd)
    if et == 9:
        nova("amendoim", "colheita_metodo_pequenos_produtores", "Pequenos produtores fazem, na maioria das situações, o arranquio e o despencamento manualmente", "",
             "Pequenos produtores na maioria das situações fazem o arranquio e despencamento manuais", 86, "")
    with open(os.path.join(curar.OUT, f"etapa_{et:02d}.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(out)
    v = sum(1 for o in out if o["status"] == "verificado")
    print(f"etapa {et}: {v} verificadas, {len(out) - v} lacunas")

print("REJEITADAS:", rejeit)
with open(os.path.join(curar.OUT, "correcoes_1_8_9.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["etapa", "cultura_id", "atributo", "valor_antes", "valor_depois"]); w.writerows(log)
print("correções registradas:", len(log))
