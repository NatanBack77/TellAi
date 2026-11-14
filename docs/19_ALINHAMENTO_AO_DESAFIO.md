# 19. Alinhamento da solução ao desafio (NASA Space Apps 2026) — recalculado em 2026-11-13

Régua própria (não é nota oficial, não foi validada por ninguém de fora): cada ponto do texto do desafio vale o mesmo; 1 = atende, 0,75 = quase, 0,5 = parcial, 0,25 = só começo, 0 = não atende, n/a = não se aplica.
Esta é a **2ª avaliação**: refeita depois de implementar risco de erosão, ETo, receita bruta, calor e chuva extrema, mapa com camadas, filtros, glossário com trechos, ZARC, solo estimado, rotação de 3 safras, MILP, ACI e teste prospectivo. Conferido no código, na tela (rodada do app com `streamlit.testing.AppTest` em 2026-11-13: sem exceção; as 5 opções de camada do mapa, o modo irrigado e as 5 seções novas renderizam) e nos testes (86 testes de risco, balanço, renda, extremos, MILP, ZARC, app e API passam; a suíte completa parou na 1ª falha com 211 passando e 1 falhando: `tests/test_mvp.py::test_resposta_por_selecao_abaixo_de_5_segundos`, teste de tempo de resposta rodado junto com outros processos pesados, não reexecutado isolado; o resto da suíte depois dele não rodou).
Nota 0,75 é usada onde o item está entregue na tela, mas com uma limitação clara declarada na coluna "Situação". O texto do desafio usa "may" (pode) quase sempre: só o núcleo é obrigatório.

## Resultado
| | Antes | **Agora** |
|---|---|---|
| Núcleo (itens 1 a 11) | 9,5 de 11 = 86% | **10,0 de 11 = 91%** |
| Opcionais (itens 12 a 46) | 18,75 de 35 = 54% | **22,75 de 35 = 65%** |
| **Total** | 28,25 de 46 = 61% | **32,75 de 46 = 71%** |
Geada (item 13) continua n/a (semiárido tropical) e fora da conta. A subida (+4,5 pontos) vem quase toda de indicadores NOVOS na tela; quase nenhum deles muda a pontuação dos três caminhos (ver "O que não dizer").

## A. Núcleo: o que o desafio pede
| # | Pedido | Antes | Agora | Evidência e o que aparece na tela |
|---|---|---|---|---|
| 1 | Ferramenta de apoio à decisão | 1 | 1 | `src/app/app.py` (Meu local, Glossário, Limites) + `src/api/main.py` (13 rotas, incl. `/rotacao`, `/plano`, `/zarc`, `/solo`); `tests/test_app.py`, `tests/test_api.py` passam |
| 2 | Observações da Terra da NASA | 1 | 1 | POWER e MODIS no app; SMAP coletado (informativo). Sem mudança |
| 3 | Informação local de solo | 0,5 | 0,5 | Tela: "Solo estimado pelo mapa SoilGrids... argila 20%, areia 58%, carbono 11 g/kg, pH 6,2" (`mvp.solo_estimado`), usado se o agricultor não informa a textura. Continua sem análise de solo local; cortes de textura 15/35% sem fonte verificada (aviso na própria tela); SoilGrids como feature do modelo NÃO deu ganho (`experimentos/soilgrids/RESULTADO.md`). Não sobe |
| 4 | Características das culturas | 1 | 1 | Tabela de 16 culturas (`src/culturas/tabela_culturas.py`) com fonte e trecho. Kc ausente (lacuna) |
| 5 | Prioridades do agricultor | 0,5 | 0,75 | Prioridades água, solo e renda; "renda" agora tem dado (receita bruta IBGE/PAM, `src/culturas/renda.py`) mas só entra na rotação de 3 safras (3b); nos 3 caminhos a tela avisa "escolher 'renda extra' NÃO altera o ranking" (`mvp.py:72`). Filtros de manejo/água/equipamento/mercado (`src/app/filtros.py`). Falta preço, custo, preferência real de mercado |
| 6 | Comparar ≥3 estratégias com a rotação atual | 1 | 1 | Seção 3 (atual + 2 alternativas) e 3b (3 safras com a rotação do agricultor, 225 sequências; MILP em `src/culturas/rotacao_milp.py`, 8 testes) |
| 7a | Por que foi sugerida | 1 | 1 | Critérios com dado e fonte na tela |
| 7b | Evidência que sustenta | 0,5 | 0,75 | Acerto do RAG no conjunto TESTE (25 perguntas, não usado para ajustar): 80% antes da tradução PT-EN, **88% (22/25)** depois (`docs/21_resultados_fases/L_R.md` seção 3). Ressalvas: conjunto pequeno, só 3 perguntas em inglês (0/3 → 2/3), L4 positivas 73%, DEV 67%; a tela diz que os trechos "podem não ser do semiárido nem confirmar o valor da tabela" |
| 7c | Benefícios | 1 | 1 | Só critérios com dado |
| 7d | Lacunas de informação | 1 | 1 | Linhas "LACUNA:" visíveis em cada estratégia (pragas, renda, Kc, forragem) |
| 7e | Riscos para avaliação local | 1 | 1 | "Risco a avaliar com técnico" em cada estratégia |

## B. Condições e dados (seção "Understanding Conditions & Data")
| # | Pedido | Antes | Agora | Evidência e o que aparece na tela |
|---|---|---|---|---|
| 8 | Temperatura | 1 | 1 | Adequação por ciclo; cenário +0 a +3 °C (`painel_cenario`) |
| 9 | Estresse por calor (ECOSTRESS) | 0,5 | 0,75 | Seção 5b: dias quentes por ano (Tmax acima do percentil 90 do dia do calendário, limiar 33,7 a 39,2 °C em Quixadá) e tendência Mann-Kendall (`src/culturas/extremos.py`, `tests/test_extremos.py`). É temperatura do ar do POWER, **não ECOSTRESS** (temperatura de superfície); período-base 2001-2024, não 1961-1990 |
| 10 | Chuva | 1 | 1 | Quadra fev-mai, veranicos, cenário |
| 11 | Umidade do solo | 0,5 | 0,5 | SMAP só informativo; não melhorou o modelo. Sem mudança |
| 12 | Evaporação / evapotranspiração | 0 | 0,5 | Seção 5c: ETo Hargreaves-Samani por quinzena, chuva menos ETo com faixa p10-p90 (`src/culturas/balanco_hidrico.py`, `tests/test_balanco_hidrico.py`; conferência da radiação com o POWER). Só ETo de **referência**: sem Kc (lacuna na tela), sem Penman-Monteith (faltam vento e umidade, não coletados), sem produto de ET da NASA, e não entra na nota das estratégias |
| 13 | Risco de geada | n/a | n/a | Semiárido tropical |
| 14 | Precipitação extrema (GPM) | 0,5 | 0,75 | Seção 5b: dias de chuva extrema (acima do p95 dos dias chuvosos; limiar 17,3 mm/dia em Quixadá) por ano e tendência. Vem do POWER diário, **não do GPM**; chuva de 24 h não mostra intensidade em minutos (aviso na tela) |
| 15 | Estresse da vegetação | 1 | 1 | Anomalias de NDVI |
| 16 | Tendências hídricas de longo prazo (GRACE) | 0,5 | 0,5 | Mann-Kendall de chuva e NDVI; sem GRACE. Sem mudança |
| 17 | Períodos de campo nu | 1 | 1 | Gráfico por quinzena; agora também camada "Solo nu" no mapa, por ano |
| 18 | Épocas em que a cultura atual está vulnerável | 1 | 1 | Adequação por data de plantio |
| 19 | Interromper ciclos de pragas | 0,5 | 0,5 | Só proxy (diversidade de famílias); lacuna "pragas e doenças: sem dado" na tela |
| 20 | Reduzir demanda de água | 0,5 | 0,5 | Prioridade água; filtro "água disponível" compara demanda do ciclo (limite inferior FAO), chuva do ciclo e irrigação informada (`filtros.py:96`). Demanda só em parte das culturas e sem Kc: não sobe |
| 21 | Melhorar infiltração | 0 | 0,25 | Só começo: o indicador da seção 5 se chama "erosão e escoamento" e usa declive, textura, carbono e dias de chuva erosiva; **não mede infiltração** nem diz quanto uma estratégia melhora a infiltração |
| 22 | Renda complementar | 0,25 | 0,5 | Seção 5d: receita bruta por hectare do município (média 2021-2023, valores correntes), com lacuna visível para culturas sem produto no PAM (palma, crotalária, milheto etc.) (`renda.py`, `tests/test_renda.py`). NÃO é lucro, sem custo, preço futuro nem mercado; não muda os 3 caminhos |

## C. Modelagem, explicação e fusão de dados
| # | Pedido | Antes | Agora | Evidência e o que aparece na tela |
|---|---|---|---|---|
| 23 | Explicar termos científicos | 0,5 | 0,75 | Página Glossário com 13 termos (`mvp.py:614`), 6 com trecho literal do acervo e página do PDF, conferido por teste (`tests/test_mvp.py`). ET e balanço hídrico agora dizem o que o app calcula (ETo, chuva menos ETo) e o que não (Kc, balanço do solo). Falta "anomalia de umidade do solo" dedicada |
| 24 | Satélite × campo e combinação | 0,5 | 0,5 | Página Limites; sem medição de campo. Sem mudança |
| 25 | Comparar IA e estatística | 1 | 1 | Walk-forward, vários modelos; **teste prospectivo 2025+** (`experimentos/prospectivo_2025/RESULTADO.md`): XGBoost +0,254 de skill vs climatologia [IC95 0,187 a 0,311] com modelo congelado (a faixa da seleção era +0,32 e da confirmação selada +0,26); só 2 anos, poder baixo; fraco em dez-fev. SoilGrids testado sem ganho |
| 26 | IA para transições sazonais, campo nu, estresse | 1 | 1 | STL, solo nu, anomalias |
| 27 | Explicar incerteza e onde o especialista valida | 1 | 1 | Faixa p10-p90, empate técnico, "a avaliar com técnico"; ACI conformal (`tests/test_conformal_aci.py`) |
| 28 | Harmonizar dados em grade comum | 0,5 | 0,5 | Harmonizado por ponto e janela; sem grade espacial; ECOSTRESS, GPM, GRACE e GEDI não usados |

## D. Estratégias de rotação
| # | Pedido | Antes | Agora | Evidência e o que aparece na tela |
|---|---|---|---|---|
| 29a | Ciclagem de nutrientes | 0,5 | 0,5 | N na biomassa (10 culturas) e N fixado (3). Sem mudança |
| 29b | Risco de erosão | 0 | 0,5 | Seção 5: classe do local ("baixo", soma de notas 1 de 8, cortes 3 e 5 como SUPOSIÇÃO), fontes Embrapa/SiBCS/Wischmeier (`risco_solo.py`, `secao_risco_solo.py`, `tests/test_risco_solo.py`) e camada no mapa. Indicador relativo entre os 195 pontos (tercis), "NÃO é RUSLE". Não separa uma rotação da outra; só a palha entra na comparação |
| 29c | Matéria orgânica | 0,5 | 0,5 | Palha como proxy; carbono do SoilGrids só informativo |
| 29d | Potencial forrageiro | 0 | 0 | Seção de forragem mostra "LACUNA declarada" com trechos lidos (`forragem.py`); nenhum número, nada pontuado |
| 29e | Mercado | 0 | 0,25 | Filtro de mercado usa a área colhida no município (IBGE/PAM) como proxy de escoamento local; receita bruta. Sem preço nem demanda |
| 30 | Alinhar rotações às prioridades | 0,5 | 0,75 | Água, solo e renda viram ordem de critérios; renda tem critério real na rotação de 3 safras (`rotacao.py`, `renda_por_cultura`); nos 3 caminhos renda não altera o ranking (avisado). Ordem é suposição a validar |
| 31 | Explicar fixadoras, cobertura, raízes profundas, tolerantes à seca | 0,5 | 0,75 | Glossário: fixadoras de N, adubação verde, raízes profundas, cada uma com trecho do acervo. "Tolerantes à seca" não tem verbete |

## E. Mapas e visualização
| # | Pedido | Antes | Agora | Evidência e o que aparece na tela |
|---|---|---|---|---|
| 32 | Mapa interativo com tendências no tempo | 0,25 | 0,5 | Seletor "Colorir os pontos por" (solo nu, declive, variabilidade da quadra, risco de erosão) e controle de ano para solo nu e quadra (`camadas.py`, `app.py:88`); ponto sem dado fica cinza. Tendências (Mann-Kendall) continuam em tabelas por local, não no mapa |
| 33 | Vulnerabilidades em escala de campo | 0 | 0,25 | Camadas de erosão, declive e solo nu, mas por ponto de município (NDVI 250 m, declive ~30 m, solo 250 m, clima ~50 km). Não é escala de talhão. Sem estresse hídrico em camada |
| 34a | Linhas do tempo | 0,5 | 0,75 | Por quinzena, por data de plantio, por ano (calor e chuva extrema, mapa por ano) |
| 34b | Sobreposição comparando conjuntos | 0 | 0 | Uma camada por vez; não há sobreposição nem comparação lado a lado |
| 34c | Controles deslizantes de cenário | 1 | 1 | Chuva e temperatura, com aviso de extrapolação |

## F. Design centrado no agricultor
| # | Pedido | Antes | Agora | Evidência e o que aparece na tela |
|---|---|---|---|---|
| 35 | Fácil de interpretar | 0,75 | 0,75 | Linguagem simples, glossário, avisos. **Nenhum teste com agricultor**; a tela ficou densa (13 seções e expansores). Não sobe |
| 36 | Agricultor informar prioridades e restrições | 0,5 | 0,75 | Selecionadores "Como você planta" (sequeiro/irrigado), água de irrigação em mm, equipamento, preferência de mercado (`filtros.py`, `app.py:186`). Os filtros só marcam atende/não atende/LACUNA e não mudam a nota; equipamento é sempre lacuna; "irrigado" só consulta o ZARC irrigado, que na rodada não trazia milho, feijão-caupi nem crotalária (LACUNA na tela) |
| 37 | Apoia e não substitui | 1 | 1 | Aviso fixo, "a avaliar com técnico local", página Limites |

## Maiores lacunas, em ordem de retorno
1. **Teste com agricultor ou técnico (itens 35, 36, 37)**. É a única evidência de que "fácil de interpretar" é verdade; hoje é 0 evidência externa. Mesmo 3 a 5 conversas curtas, registradas, valem mais que qualquer indicador novo. Custo: dias, sem código.
2. **Fazer erosão, ETo, calor e renda influenciarem os caminhos (itens 5, 20, 21, 29b, 30)**. Hoje são seções ao lado; os 3 caminhos ignoram erosão e ETo, e "renda" não os reordena. Ligar ao menos erosão (cobertura/palha) e renda ao ranking, sempre declarando que é suposição.
3. **Kc e demanda de água por cultura (itens 12, 20)**. Sem Kc, ETc não existe e "reduzir demanda de água" fica em 0,5. Precisa de fonte lida (FAO-56 tabela 12 ou equivalente); sem fonte, continua lacuna.
4. **Preço, custo e mercado (itens 5, 22, 29e)**. Só receita bruta histórica do IBGE (e nenhuma para palma e adubos verdes). Sem fonte de preço/custo, permanece lacuna.
5. **Sobreposição de camadas e tendência no mapa (itens 32, 34b)** e **escala de campo (33)**. Mapa por ponto, uma camada por vez; escala de talhão exigiria dado que não temos.
6. **Bases NASA citadas e não usadas (itens 9, 14, 16, 28, 11)**: ECOSTRESS, GPM, GRACE, GEDI. Usar ou registrar por que foram descartadas; hoje o app usa proxies do POWER e não diz GPM nem ECOSTRESS.
7. **Pragas (19), forragem (29d), textura sem fonte (3)**. Pragas só proxy de famílias; forragem sem número lido nos PDFs; cortes de textura 15/35 sem fonte verificada; sem análise de solo local.

Não aplicável ou de baixo retorno: geada (13), GEDI em caatinga baixa, GRACE em escala de município.

## O que NÃO dizer ao júri
- Que a pontuação é "nota do desafio" ou "71% de aderência". É uma régua nossa, feita pela própria equipe, com pesos iguais e notas dadas por nós.
- Que o app calcula evapotranspiração da cultura, balanço hídrico do solo, RUSLE ou perda de solo. É ETo de referência, "chuva menos ETo" e um indicador relativo de risco (tercis entre os 195 pontos).
- Que o app usa ECOSTRESS, GPM, GRACE ou GEDI. Calor e chuva extrema vêm do POWER (temperatura do ar e chuva diária de células de ~50 km).
- Que a "renda" orienta a escolha. Nos três caminhos ela NÃO altera o ranking; só entra na rotação de 3 safras, e é receita BRUTA histórica, não lucro nem previsão; sem dado para palma, crotalária e milheto.
- Que o app mede infiltração, escala de talhão ou forragem.
- Que a rotação sugerida "rende mais". Os caminhos costumam estar em empate técnico (13 culturas empatadas no exemplo de Quixadá).
- Que o filtro "irrigado" ou de equipamento muda a recomendação. Só marca atende, não atende ou lacuna.
- Que o RAG "acerta 88%". É 22/25 em um conjunto pequeno (3 perguntas em inglês); L4 foi 73%, DEV 67%, e a tela avisa que os trechos podem não ser do semiárido.
- Que a previsão de NDVI é validada em campo. O teste prospectivo 2025+ (skill +0,254 vs climatologia) cobre só 2 anos, é fraco no início da estação chuvosa (fev -0,014) e é módulo de apoio, não o produto.
- Que o SoilGrids melhora o modelo (não melhorou), nem que há dado de solo local (é estimativa de mapa global).
- Que o app foi testado com agricultores. Não foi.
