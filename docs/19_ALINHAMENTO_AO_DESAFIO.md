# 19. Alinhamento da solução ao desafio (NASA Space Apps 2026) — 2026-11-13

Régua própria (não é nota oficial): cada ponto do texto do desafio vale o mesmo; 1 = atende, 0,5 = parcial, 0,25 = só começo, 0 = não atende, n/a = não se aplica.
Conferido no código e na tela (`src/app/app.py`, `src/app/mvp.py`) e nos documentos do repositório. O texto do desafio usa "may" (pode) quase sempre: só o núcleo é obrigatório.

## Resultado
- **Núcleo do desafio (itens 1 a 11): 9,5 de 11 = 86%.**
- **Itens opcionais e de aprofundamento (itens 12 a 46): 18,75 de 35 = 54%.**
- **Total: 28,25 de 46 = 61%.** (frost/geada é n/a no semiárido tropical e ficou fora da conta)

## A. Núcleo: o que o desafio pede
| # | Pedido | Situação | Nota |
|---|---|---|---|
| 1 | Ferramenta de apoio à decisão (app, modelo, mapa) | App Streamlit com mapa, seções, API | 1 |
| 2 | Usar observações da Terra da NASA | POWER e MODIS no app; SMAP e SRTM coletados | 1 |
| 3 | Informação local de solo | SoilGrids estimado (mapa global, ~2 km) + textura e matéria orgânica informadas pelo agricultor; sem análise de solo local | 0,5 |
| 4 | Características das culturas | Tabela de 16 culturas com fonte, página e trecho | 1 |
| 5 | Prioridades do agricultor | Água e solo; "renda" é lacuna; sem disponibilidade de água, equipamento ou preferência de mercado | 0,5 |
| 6 | Comparar ≥3 estratégias, incluindo a rotação existente | Atual + 2 alternativas; rotação de 3 safras com a rotação do agricultor | 1 |
| 7a | Por que foi sugerida | Critérios com dado e fonte | 1 |
| 7b | Evidência que sustenta | Trechos do acervo, mas acerto do RAG 54% (meta 80%) | 0,5 |
| 7c | Benefícios | Só critérios com dado | 1 |
| 7d | Lacunas de informação | Visíveis em cada estratégia | 1 |
| 7e | Riscos para avaliação local | Visíveis em cada estratégia | 1 |

## B. Condições e dados (seção "Understanding Conditions & Data")
| # | Pedido | Situação | Nota |
|---|---|---|---|
| 8 | Temperatura | Adequação por ciclo, cenário de +0 a +3 °C | 1 |
| 9 | Estresse por calor (ECOSTRESS) | Tmax entra no modelo; sem índice de calor nem ECOSTRESS | 0,5 |
| 10 | Chuva | Quadra fev–mai, veranicos, cenário de chuva | 1 |
| 11 | Umidade do solo | SMAP coletado, só informativo; não melhorou o modelo | 0,5 |
| 12 | Evaporação / evapotranspiração | NÃO calculada (declarada como lacuna no glossário) | 0 |
| 13 | Risco de geada | n/a (semiárido tropical) | n/a |
| 14 | Precipitação extrema (GPM) | Veranicos e variabilidade da quadra; sem índice de chuva extrema nem GPM | 0,5 |
| 15 | Estresse da vegetação | Anomalias de NDVI, períodos de estresse | 1 |
| 16 | Tendências hídricas de longo prazo (GRACE) | Tendência de chuva e NDVI (Mann-Kendall); sem GRACE | 0,5 |
| 17 | Períodos de campo nu | Gráfico por quinzena, com frequência por ano | 1 |
| 18 | Épocas em que a cultura atual está vulnerável | Adequação por data de plantio e cruzamento do ciclo com solo nu e estresse | 1 |
| 19 | Interromper ciclos de pragas | Só proxy (diversidade de famílias); sem dado de pragas | 0,5 |
| 20 | Reduzir demanda de água | Prioridade "água" (encaixe da chuva) e demanda hídrica em 7 de 16 culturas | 0,5 |
| 21 | Melhorar infiltração | Não tratado (declive coletado, fora do app) | 0 |
| 22 | Renda complementar | Valor da produção do IBGE coletado, ainda não usado | 0,25 |

## C. Modelagem, explicação e fusão de dados
| # | Pedido | Situação | Nota |
|---|---|---|---|
| 23 | Explicar termos científicos (ET, anomalia de umidade, NDVI, balanço hídrico) | Glossário de 8 termos; ET e balanço hídrico declarados como não calculados | 0,5 |
| 24 | Satélite × medição em campo e combinação | Página "Limites" explica resolução (250 m a 50 km × talhão); combina com dados do IBGE, sem medição de campo | 0,5 |
| 25 | Comparar abordagens de IA e estatística | Ridge, XGBoost, HGB, RF, ET, ElasticNet, rede neural, ensembles, stacking; walk-forward; 6 métodos de conformal | 1 |
| 26 | IA para transições sazonais, campo nu, estresse | Decomposição sazonal (STL), solo nu, anomalias | 1 |
| 27 | Explicar incerteza e onde o especialista valida | Faixa de incerteza, empate técnico, riscos para revisão local | 1 |
| 28 | Harmonizar dados em grade comum (SMAP, ECOSTRESS, GPM, Landsat/MODIS, GEDI, solo) | Harmonizado por ponto e janela de 16 dias; sem grade espacial; ECOSTRESS, GPM e GEDI fora | 0,5 |

## D. Estratégias de rotação
| # | Pedido | Situação | Nota |
|---|---|---|---|
| 29a | Ciclagem de nutrientes | N na biomassa (11 culturas) e N fixado (4 culturas) | 0,5 |
| 29b | Risco de erosão | NÃO medido (SRTM e solo coletados, fora do app) | 0 |
| 29c | Matéria orgânica | Palha como proxy | 0,5 |
| 29d | Potencial forrageiro | Não pontuado | 0 |
| 29e | Mercado | Lacuna declarada | 0 |
| 30 | Alinhar rotações às prioridades do agricultor | 3 prioridades viram ordem de critérios (suposição a validar) | 0,5 |
| 31 | Explicar fixadoras de N, cobertura, raízes profundas, tolerantes à seca | Trechos do acervo por critério; sem explicação dedicada | 0,5 |

## E. Mapas e visualização
| # | Pedido | Situação | Nota |
|---|---|---|---|
| 32 | Mapa interativo com tendências no tempo | Mapa clicável de 195 pontos; tendências em gráficos por local, não no mapa | 0,25 |
| 33 | Vulnerabilidades em escala de campo (erosão, estresse hídrico, geada) | Resolução de município | 0 |
| 34a | Linhas do tempo | Gráficos por quinzena e por data de plantio | 0,5 |
| 34b | Sobreposição comparando conjuntos de dados | Não | 0 |
| 34c | Controles deslizantes de cenário (chuva e temperatura) | Sim, com aviso de extrapolação | 1 |

## F. Design centrado no agricultor
| # | Pedido | Situação | Nota |
|---|---|---|---|
| 35 | Fácil de interpretar | Linguagem simples, glossário, avisos; sem teste com agricultor | 0,75 |
| 36 | O agricultor informar prioridades e restrições (água, equipamento, mercado) | Cultura, prioridade, rotação, textura, matéria orgânica; sem água disponível, equipamento nem mercado | 0,5 |
| 37 | Lembrar que apoia e não substitui; destacar onde o julgamento humano pesa | Aviso fixo, riscos para revisão local, página de limites | 1 |

## Maiores lacunas, em ordem de valor para o desafio e esforço
Os dados de todas já estão no repositório ou são derivados do clima que já temos.
1. **Erosão e infiltração** (itens 21, 29b, 33): combinar declive do SRTM com textura e carbono do SoilGrids em um indicador de risco por local, com camada no mapa. Pede o desafio de forma repetida e é o principal vazio do "soil health".
2. **Evapotranspiração e balanço hídrico** (itens 12, 20, 23): ETo por Hargreaves-Samani com Tmax, Tmin e radiação do POWER, e saldo chuva menos ETo por quinzena. O desafio cita ET, evaporação e balanço hídrico mais de uma vez.
3. **Renda** (itens 5, 22, 29e): receita bruta por hectare do valor da produção do IBGE, na prioridade "renda".
4. **Calor e chuva extrema** (itens 9, 14): dias com Tmax acima de um limiar e índice de chuva extrema a partir do POWER diário (ou GPM/IMERG para nomear a base).
5. **Mapa com camadas e linha do tempo** (itens 32, 34a, 34b): colorir os pontos por indicador (solo nu, declive, variabilidade da quadra, tendência) e adicionar um controle de ano.
6. **Entradas do agricultor** (item 36): irrigado ou sequeiro (o ZARC já tem manejo irrigado), água disponível e preferência de mercado, como filtros.
7. **Explicações curtas** (itens 23 e 31): fixadoras de N, adubação verde, raízes profundas, ET e balanço hídrico no glossário, com trecho do acervo.
8. **Forragem** (29d): valor forrageiro de palma, sorgo e milheto, usando os PDFs do MAPA já no acervo.
9. **Bases NASA fora do app** (itens 9, 14, 16, 28): ECOSTRESS, GPM, GRACE e GEDI. Registrar por que cada uma foi usada ou descartada, o que ajuda na avaliação mesmo sem uso.

Não aplicável ou de baixo retorno: geada (13), GEDI em caatinga baixa, GRACE em escala de município.
