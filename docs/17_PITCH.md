# 17. Avaliação da solução e pitch (2026-11-13; revisado em 2026-11-14 para o que o app entrega hoje)

Todos os números abaixo vêm de resultados validados do projeto (`docs/05`, `docs/16`, `docs/19`, `docs/21_resultados_fases/`, `experimentos/*/RESULTADO.md`). O que NÃO dizer ao júri está em `docs/19_ALINHAMENTO_AO_DESAFIO.md` (seção final) e vale para tudo aqui; a régua de 71% do `docs/19` é nossa, não é nota do desafio, e não deve ir ao pitch.

## A. Avaliação honesta

**O que o modelo de previsão faz bem (anomalia de NDVI, 195 pontos, 2001–2024)**
- Prevê se a vegetação do próximo composto de 16 dias ficará acima ou abaixo do normal. Em 2022–2024, anos que não foram usados para escolher nada:
  erro (RMSE) de 0,072 contra 0,100 da média histórica (**28% menos erro**); skill de **+0,28**; R² de +0,35.
- Validação: walk-forward ano a ano (12 anos), teste com embaralhamento (placebo), correção por número de modelos testados e confirmação selada.
  Sem sinal de overfitting nem de underfitting (erro de teste só 15–20% acima do de treino; mais dados não mudam o erro). Generaliza para locais nunca vistos (skill +0,28 a +0,31).
- Faixa de incerteza (ACI por estação): cobre **80,9% e 90,6%** quando promete 80% e 90%. A garantia é de longo prazo: o pior ano (2022) cobriu 72%.

**O que o modelo NÃO faz**
- O ganho vem da persistência (a vegetação de hoje se parece com a de ontem). O clima, sozinho, não supera a média histórica; terreno e índices do Pacífico/Atlântico não ajudaram.
- Não prevê produtividade: o NDVI explica só 3% a 10% da variação do rendimento municipal do IBGE. A chuva de fevereiro a maio explica mais (milho: 31%).
- Não prevê a próxima quadra chuvosa (os índices testados não anteciparam a chuva com 24 anos de dados). Para isso, a fonte certa é a FUNCEME.

**O que o app entrega HOJE** (conferido em `docs/19` e `docs/21_resultados_fases/`; não é promessa de rendimento)
- Mapa dos 195 pontos que pode ser colorido por camada (solo nu, declive, variabilidade da quadra, risco de erosão), com controle de ano para solo nu e quadra.
- Solo estimado pelo mapa SoilGrids (250 m, pixel de ~2 km; não é análise do talhão) e ZARC oficial do MAPA (só Ceará) como filtro das datas de plantio.
- Indicador de **risco de erosão e escoamento** (relativo entre os 195 pontos; NÃO é RUSLE; não mede infiltração), **ETo de referência** e chuva menos ETo por quinzena (sem Kc), **receita bruta por hectare** do município (IBGE, não é lucro), **dias de calor e de chuva extrema** por ano com tendência (do POWER, não de ECOSTRESS nem GPM).
- Três caminhos (rotação atual + 2 alternativas) e rotação de **3 safras** com regras (MILP opcional); filtros do agricultor (sequeiro/irrigado, água, equipamento, mercado) que só marcam atende, não atende ou lacuna; cenários de chuva e temperatura; glossário e página de Limites.
- API (`src/api/main.py`, 13 rotas, `docs/12_API.md`) com os mesmos cálculos do app.
- Evidências por busca no acervo (50 PDFs, 3.203 trechos): acerto top-5 de **88% (22/25)** num conjunto de teste pequeno; ressalvas: só 3 perguntas em inglês, 73% nas 15 perguntas novas (L4), 67% no conjunto de ajuste, e a tela avisa que os trechos podem não ser do semiárido.
- Previsão de NDVI (apoio): teste prospectivo 2025+ com o modelo congelado, skill **+0,254** contra a climatologia [IC95 0,187 a 0,311]; só 2 anos, fraco em dez-fev (`experimentos/prospectivo_2025/RESULTADO.md`).
- Camada LLM (DeepSeek): código e testes prontos, **não ligada ao app e nunca chamada de verdade** (sem chave; `docs/14_LLM.md`). O texto da tela é o template.

**A solução como um todo, contra o desafio**
| Pedido do desafio | Situação |
|---|---|
| Ferramenta de apoio, não substituta | Sim, com avisos, lacunas e riscos em cada tela |
| Dados de observação da Terra | POWER, MODIS e SRTM em uso; SMAP coletado (informativo, não melhorou o modelo); ECOSTRESS, GPM, GRACE, GEDI e Landsat não usados (motivos em `docs/16` seção G) |
| 3 estratégias, incluindo a atual | Sim: rotação atual + 2 alternativas e rotação de 3 safras |
| Por quê, evidência, benefícios, lacunas, riscos | Sim; evidências do acervo com ressalvas (88% em 25 perguntas de teste) |
| Períodos de solo nu e de vulnerabilidade | Sim (diagnóstico de 195 pontos; camada no mapa) |
| Cenários de chuva e temperatura | Sim, com aviso de extrapolação |
| Calor, chuva extrema, evapotranspiração, erosão | Indicadores novos na tela, com proxies declarados (POWER, ETo de referência, risco relativo); quase nenhum altera a nota dos 3 caminhos |
| Solo, prioridades e restrições do agricultor | Parcial: solo estimado por mapa global (sem análise local); prioridades água e solo ordenam critérios; "renda" não altera o ranking dos 3 caminhos, só a rotação de 3 safras, com receita bruta histórica |
| Pragas e doenças, forragem | Lacuna declarada (pragas só proxy por diversidade de famílias; forragem sem número) |
| Teste com agricultor | Não feito |

Pontos fracos reconhecidos: as alternativas de rotação ficam em empate técnico (os dados não separam as melhores; separam bem rotação contra repetir a cultura),
ciclo e pesos são suposições a validar com técnico, e a resolução é de município, não de talhão.

## B. Pitch (1 minuto)

**SULCO — da órbita ao sulco.**

No semiárido do Nordeste, só **8,2% dos estabelecimentos têm assistência técnica** (Censo Agropecuário 2017). O agricultor decide o que plantar depois da safra,
sem ver o que o clima e a vegetação da própria terra dizem.

O SULCO junta **24 anos de dados da NASA** (chuva e temperatura do NASA POWER e vegetação do MODIS) com dados de produção do IBGE, para **195 locais, 184 deles no Ceará**.
O relevo (SRTM), o mapa de solo (SoilGrids) e o zoneamento agrícola oficial (ZARC) já estão no app. O agricultor escolhe o município no mapa, diz o que planta hoje e o que importa mais: economizar água, proteger o solo ou renda extra (a renda só entra na rotação de 3 safras, como receita bruta histórica do IBGE; não reordena os três caminhos).

Em troca, vê três coisas simples:
1. **O que a terra costuma fazer:** quando o campo fica nu, quando a vegetação mais sofre, o tamanho dos veranicos, o quanto a quadra chuvosa varia, dias de calor e de chuva forte por ano, e um indicador relativo de risco de erosão.
2. **Três caminhos de rotação para conversar com o técnico:** a rotação atual e duas alternativas de três safras, cada uma com a melhor época de plantio (filtrada pelo ZARC no Ceará), o motivo, a evidência, o que falta saber e os riscos a avaliar no local.
3. **E se a chuva falhar?** Controles de chuva e temperatura mostram como cada caminho reage, e o app avisa quando o cenário foge do que já aconteceu.

O que nos diferencia é a **honestidade**: nenhum número é inventado; o que falta aparece como lacuna; e a incerteza é mostrada, não escondida. Por trás, um modelo de
previsão da vegetação reduz o erro em 28% sobre a média histórica, foi validado em anos que ficaram trancados e depois conferido em 2025-2026 sem retreinar (skill +0,254; só 2 anos) (ele sustenta o diagnóstico; não dá nota às rotações). O SULCO **apoia a conversa com o técnico; não decide, nem promete que a rotação rende mais.**

## C. O que resolve e como (em 4 linhas)
- **Problema:** decidir rotação sem acesso a assistência técnica e sem ver o que clima e vegetação dizem da própria terra.
- **Como:** dados da NASA e do IBGE em 195 locais → diagnóstico do local → 3 rotações comparadas com incerteza → cenários de clima.
- **Valor:** transforma satélite em perguntas práticas (quando o campo fica nu? qual caminho aguenta uma quadra fraca?) para levar ao técnico.
- **Limite:** NDVI não é produtividade; a previsão da próxima quadra é da FUNCEME; a resolução é de município.

## D. Confiança: não há um único percentual
Medidas por componente (todas validadas): previsão da vegetação, 28% menos erro que a média histórica; faixa de incerteza, cobertura de 80,9% / 90,6% para metas de
80% / 90% (pior ano 72%); NDVI explica 3% a 10% da produtividade municipal (não usar como produtividade); chuva da quadra explica até 31% (milho). O selo "alta/média/baixa"
do diagnóstico é heurística de quantidade de dados, não probabilidade. Nenhuma rotação tem "percentual de acerto": as alternativas ficam em empate técnico.

## E. Roteiro de 2 minutos (demo ao vivo)
Cada passo existe no app (`src/app/app.py`, rodar com `.venv/bin/python -m streamlit run src/app/app.py`; confira antes que o mapa abre: sem internet ele aparece sem fundo, só os pontos). Os trechos entre aspas são frases honestas para dizer; nenhum número deve ser improvisado fora deste arquivo. **Ensaiar com cronômetro: o tempo de cada passo abaixo é meta, não foi medido.**
1. (0:00 a 0:15, Meu local) "No semiárido só 8,2% dos estabelecimentos têm assistência técnica. O SULCO ajuda o agricultor a preparar a conversa com o técnico; ele não decide por ele."
2. (0:15 a 0:30, seção 1) Clicar num ponto do mapa (ou escolher na lista, ex.: Quixadá), escolher a cultura atual e a prioridade. Opcional: trocar "Colorir os pontos por" para solo nu ou risco de erosão. "Cada ponto é um município; o satélite enxerga quilômetros e pixels de 250 m, não o seu talhão."
3. (0:30 a 0:55, seção 2) Mostrar quando o campo fica nu e quando a vegetação sofre. "Isto vem de 24 anos de NDVI do MODIS e de chuva e temperatura do NASA POWER."
4. (0:55 a 1:20, seção 3) Mostrar os três caminhos: motivo, evidência, LACUNA, risco para avaliar com o técnico. "As alternativas costumam ficar em empate técnico: o app mostra o empate, não escolhe um vencedor falso. Rendimento não é prometido."
5. (1:20 a 1:40, seção 4) Mexer no controle de chuva. "E se a chuva falhar? O app avisa quando o cenário foge do que já aconteceu."
6. (1:40 a 1:55, seções 5 e 5b) "Também mostramos risco relativo de erosão e dias de calor e de chuva forte; calor e chuva vêm do POWER, não de ECOSTRESS nem GPM, e a erosão é um indicador relativo, não perda de solo."
7. (1:55 a 2:00, página Limites) Fechar na página "Limites dos dados". "Falta teste com agricultor; é o próximo passo."
Se der problema: o app roda offline do cache; não depender de LLM (o texto é template). Não mostrar a camada LLM como funcionando.

## F. Perguntas difíceis dos jurados e respostas honestas
Base: `docs/19` e `docs/21_resultados_fases/`.
- **"Vocês provam que a rotação sugerida rende mais?"** Não. Nenhuma ferramenta daria essa prova só com satélite. Separamos bem rotação de repetir a cultura, mas as alternativas ficam em empate técnico (no exemplo de Quixadá, 13 culturas empatadas). O app prepara a conversa com o técnico.
- **"Qual a precisão do modelo?"** Não há um percentual único. Previsão de NDVI: 28% menos erro que a média histórica em 2022-2024 (anos selados) e skill +0,254 em 2025-2026 com modelo congelado, mas só 2 anos e fraco em dez-fev. É módulo de apoio. NDVI explica 3% a 10% da produtividade municipal, então não prevê rendimento.
- **"Vocês usam ECOSTRESS, GPM, GRACE ou GEDI?"** Não. Calor e chuva extrema vêm do POWER (célula de ~50 km). Os motivos estão em `docs/16` seção G; ECOSTRESS e GPM seriam os próximos para calor de superfície e chuva horária.
- **"O app calcula evapotranspiração e erosão?"** ETo de referência (Hargreaves-Samani), sem Kc, e chuva menos ETo; não é balanço hídrico do solo nem evapotranspiração da cultura. Erosão é um indicador relativo entre os 195 pontos (cortes são suposição), não RUSLE e não mede infiltração.
- **"O RAG acerta 88%?"** 22 de 25 perguntas de um conjunto de teste pequeno, com só 3 perguntas em inglês; nas 15 perguntas novas foi 73% e no conjunto de ajuste 67%. A tela avisa que os trechos podem não ser do semiárido.
- **"A renda orienta a escolha?"** Nos três caminhos não: escolher "renda extra" não reordena. Só na rotação de 3 safras, com receita bruta histórica do IBGE (não é lucro, sem preço futuro, sem dado para palma, crotalária e milheto).
- **"Isso foi testado com agricultores?"** Não. É a maior lacuna; o plano é 3 a 5 conversas curtas com técnico ou agricultor.
- **"E o solo do agricultor?"** Se ele não informar, usamos uma estimativa do mapa SoilGrids (pixel de ~2 km), que não melhorou a previsão e não foi comparada com análise de campo. Cortes de textura sem fonte verificada (aviso na tela).
- **"O filtro irrigado ou de equipamento muda a recomendação?"** Não; só marca atende, não atende ou lacuna.
- **"O LLM escreve as explicações?"** Hoje não: o texto é por template. A camada LLM existe com verificador, mas nunca foi chamada com chave real e não está ligada ao app.
- **"Por que o clima do mesmo município é igual ao do vizinho?"** 195 pontos caem em só 59 células do POWER (~50 km); pontos da mesma célula têm o mesmo clima.
- **"Sua régua de aderência ao desafio?"** É nossa, com pesos iguais e notas dadas por nós; não é nota oficial. Não citar o percentual.
- **"Como a solução se conecta aos Objetivos de Desenvolvimento Sustentável (ODS da ONU)?"** Conecta diretamente a 5 metas mensuráveis da Agenda 2030 (detalhadas em `docs/34_ODS_E_IMPACTO_SUSTENTAVEL.md`): ODS 2 (Meta 2.4 - LER e diversificação de safras contra fome), ODS 6 (Meta 6.4 - ETo e umidade SMAP reduzindo solo nu), ODS 12 (Meta 12.4 - leguminosas com fixação BNF reduzindo adubo fóssil), ODS 13 (Meta 13.1 - resiliência a calor/veranicos e incerteza ACI) e ODS 15 (Meta 15.3 - contenção da desertificação da Caatinga e risco de erosão SRTM).
