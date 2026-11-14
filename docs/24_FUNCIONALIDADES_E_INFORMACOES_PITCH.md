# 24. O que o Sulco entrega: funcionalidades e informações (para o pitch)

Atualizado em 2026-11-14. Cada linha foi conferida no código ou nos resultados do repositório; o que não é verificado está marcado. Não é nota oficial do desafio.

## Em uma frase
**Sulco, da órbita ao sulco:** o agricultor marca o município, diz o que planta hoje e o que importa mais, e recebe, em linguagem simples, o que 24 anos de dados da NASA mostram sobre a terra dele e **três caminhos de rotação para conversar com o técnico**, com o que se sabe, o que não se sabe e o que conferir. **Apoia, não decide.**

## 1. Funcionalidades (o que o agricultor faz)
| # | Funcionalidade | O que o agricultor faz | O que recebe |
|---|---|---|---|
| 1 | **Mapa e escolha do local** | Clica no mapa ou escolhe um dos 184 municípios do Ceará (195 pontos) | Camadas coloridas por indicador (solo nu, declive, variabilidade da quadra, risco de erosão) com linha do tempo por ano |
| 2 | **Perfil do agricultor** | Informa a cultura atual (16 opções), a prioridade (economizar água, proteger o solo, renda extra), o manejo (sequeiro ou irrigado), a água disponível, equipamento, preferência de mercado e textura/matéria orgânica do solo, se souber | Os resultados se ajustam ao perfil; o que não tem dado vira **lacuna visível** |
| 3 | **O que os satélites mostram do local** | Só olha | Épocas em que o campo costuma ficar nu, períodos de estresse da vegetação, estação chuvosa, veranicos, tendência de 24 anos, com a confiança do diagnóstico |
| 4 | **Três caminhos para comparar** | Compara lado a lado | A rotação atual e duas alternativas, cada uma com: **por que** foi sugerida, **evidência** (trechos de documentos da Embrapa/MAPA com arquivo e página), **benefícios**, **lacunas**, **riscos para o técnico revisar**, melhor época de plantio, faixa de incerteza e **empate técnico** quando os dados não separam |
| 5 | **Rotação de 3 safras e plano de várias safras** | Informa a rotação que já usa; escolhe quantas safras e se aceita repetir | Sequências comparadas com a dele; o plano de várias safras aparece como **proposta** |
| 6 | **Cenário "e se..."** | Move chuva e temperatura | Recalcula as épocas de plantio e os caminhos, com aviso de extrapolação |
| 7 | **Indicadores do local** | Só olha | Risco de erosão (relativo), calor e chuva extrema por ano, chuva menos evapotranspiração por quinzena, receita bruta por hectare (**não é lucro**), solo estimado, calendário do ZARC |
| 8 | **Previsão da vegetação** | Só olha (também via API) | Anomalia prevista do NDVI para o próximo composto de 16 dias, com faixa de 80% e 90% e os limites do modelo |
| 9 | **Chat "Pergunte ao Sulco"** | Pergunta em português | Resposta **curta e em linguagem simples** (sem siglas e sem marcadores de citação), feita a partir dos dados do local, dos documentos da Embrapa/MAPA e do glossário; diz "sem evidência" quando não há base e **recusa** pedidos de lucro ou de escolher a rotação. As fontes ficam num bloco "De onde veio esta resposta" |
| 10 | **Cartão do município** | Baixa (HTML ou PDF) | Uma folha para levar ao técnico: local, épocas de solo nu e estresse, janela de plantio, três caminhos com lacunas e "o que conferir" |
| 11 | **Glossário e "Limites dos dados"** | Lê | Termos explicados (NDVI, evapotranspiração, empate técnico...) e o que o sistema **não** vê |
| 12 | **API** | (para técnicos e outros sistemas) | Os mesmos resultados em JSON (`/diagnostico`, `/cenarios`, `/rotacao`, `/modelo/previsao`, `/evidencias`, `/chat`), com limite de taxa |

## 2. Informações entregues
**Do satélite e do clima (NASA):** NDVI (MODIS, 250 m, 24 anos) e confiabilidade; chuva, temperaturas e radiação (POWER, ~50 km); umidade do solo (SMAP, coletada); relevo (SRTM).
**De outras fontes públicas:** zoneamento agrícola de risco climático (ZARC/MAPA), produção agrícola municipal (IBGE), solo (SoilGrids, estimativa de mapa global).
**Calculadas pelo sistema:** épocas típicas de solo nu e de estresse; adequação de cada cultura por data de plantio; risco de erosão, calor e chuva extrema; evapotranspiração de referência; receita bruta por hectare; previsão do NDVI do próximo composto.
**Da tabela de culturas (16 culturas, com fonte, página e trecho):** faixas de temperatura e chuva, ciclo, família, palha e nitrogênio onde há estudo; demais campos são lacuna declarada.
**Do acervo (50 documentos reais, 3.203 trechos):** a evidência citada nas respostas e no chat.

## 3. Diferenciais
1. **Não finge certeza:** lacunas, empate técnico e limites ficam à mostra em todas as telas.
2. **Todo número tem origem:** fonte e página na tabela de culturas; o texto da IA passa por um verificador e a busca vazia vira "sem evidência".
3. **Ponte entre a NASA e a conversa com o técnico:** o cartão e o chat preparam o agricultor, sem decidir por ele.

## 4. Números que se pode citar (todos verificados)
- 195 pontos (184 municípios do Ceará), 24 anos de dados.
- Previsão do NDVI: ganho de **+0,254** sobre a climatologia **em dados de 2025–2026 que o modelo nunca viu**; vence em 85,5% dos pontos; a faixa de 80% e 90% cobre 85,7% e 93,6%. Vale 1 composto (16 dias) à frente.
- Busca nos documentos: 88% de acerto em 25 perguntas de teste (22 de 25; só 3 em inglês).

## 5. O que NÃO dizer (a lista completa está em `docs/19`)
Que o Sulco diz qual rotação rende mais ou prevê safra, lucro ou clima; que há balanço hídrico do solo (só ETo de referência) ou ETc; que usamos GPM, ECOSTRESS, GRACE ou GEDI; que a "renda" orienta a escolha; que o app foi testado com agricultores (**não foi**); que o solo é medido (é estimativa de mapa global); que o 88% do RAG é geral (são 25 perguntas).

## 6. O que dizer quando perguntarem "isso resolve?"
"Resolve a **barreira de acesso**: transforma 24 anos de dados da NASA em um retrato simples da terra e em três caminhos comparados, com as lacunas à mostra. **Não resolve a decisão:** as alternativas ficam em empate técnico com os dados atuais, e por isso o produto leva o agricultor ao técnico em vez de decidir por ele. **O próximo passo é validar com técnicos locais.**"
