# 17. Avaliação da solução e pitch (2026-11-13)

Todos os números abaixo vêm de resultados validados do projeto (`docs/05`, `docs/16`, `experimentos/*/RESULTADO.md`, `relatorio_modelos.md`).

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

**A solução como um todo, contra o desafio**
| Pedido do desafio | Situação |
|---|---|
| Ferramenta de apoio, não substituta | Sim, com avisos, lacunas e riscos em cada tela |
| Dados de observação da Terra | POWER, MODIS e SRTM em uso; SMAP coletado (não melhorou o modelo) |
| 3 estratégias, incluindo a atual | Sim: rotação atual + 2 alternativas de 3 safras |
| Por quê, evidência, benefícios, lacunas, riscos | Sim; evidências do acervo ainda fracas (acerto de 54%) |
| Períodos de solo nu e de vulnerabilidade | Sim (diagnóstico real de 195 pontos) |
| Cenários de chuva e temperatura | Sim, com aviso de extrapolação |
| Solo, prioridades e restrições do agricultor | Parcial: o agricultor informa solo e rotação; mapa de solo em coleta; renda só com receita bruta do IBGE |
| Pragas e doenças | Lacuna declarada (só proxy por diversidade de famílias) |

Pontos fracos reconhecidos: as alternativas de rotação ficam em empate técnico (os dados não separam as melhores; separam bem rotação contra repetir a cultura),
ciclo e pesos são suposições a validar com técnico, e a resolução é de município, não de talhão.

## B. Pitch (1 minuto)

**SULCO — da órbita ao sulco.**

No semiárido do Nordeste, só **8,2% dos estabelecimentos têm assistência técnica** (Censo Agropecuário 2017). O agricultor decide o que plantar depois da safra,
sem ver o que o clima e a vegetação da própria terra dizem.

O SULCO junta **24 anos de dados da NASA** (chuva e temperatura do NASA POWER e vegetação do MODIS) com dados de produção do IBGE, para **195 locais, 184 deles no Ceará**.
O relevo (SRTM), o mapa de solo e o zoneamento agrícola oficial (ZARC) já estão coletados ou prontos e entram no app conforme ficam validados. O agricultor escolhe o município, diz o que planta hoje e o que importa mais: economizar água ou proteger o solo (a prioridade renda ainda é uma lacuna declarada).

Em troca, vê três coisas simples:
1. **O que a terra costuma fazer:** quando o campo fica nu, quando a vegetação mais sofre, o tamanho dos veranicos e o quanto a quadra chuvosa varia de um ano para o outro.
2. **Três caminhos de rotação para conversar com o técnico:** a rotação atual e duas alternativas de três safras, cada uma com a melhor época de plantio, o motivo, a evidência, o que falta saber e os riscos a avaliar no local.
3. **E se a chuva falhar?** Controles de chuva e temperatura mostram como cada caminho reage, e o app avisa quando o cenário foge do que já aconteceu.

O que nos diferencia é a **honestidade**: nenhum número é inventado; o que falta aparece como lacuna; e a incerteza é mostrada, não escondida. Por trás, um modelo de
previsão da vegetação reduz o erro em 28% sobre a média histórica e foi validado em anos que ficaram trancados até o fim (ele sustenta o diagnóstico; não dá nota às rotações). O SULCO **apoia a conversa com o técnico; não decide, nem promete que a rotação rende mais.**

## C. O que resolve e como (em 4 linhas)
- **Problema:** decidir rotação sem acesso a assistência técnica e sem ver o que clima e vegetação dizem da própria terra.
- **Como:** dados da NASA e do IBGE em 195 locais → diagnóstico do local → 3 rotações comparadas com incerteza → cenários de clima.
- **Valor:** transforma satélite em perguntas práticas (quando o campo fica nu? qual caminho aguenta uma quadra fraca?) para levar ao técnico.
- **Limite:** NDVI não é produtividade; a previsão da próxima quadra é da FUNCEME; a resolução é de município.

## D. Confiança: não há um único percentual
Medidas por componente (todas validadas): previsão da vegetação, 28% menos erro que a média histórica; faixa de incerteza, cobertura de 80,9% / 90,6% para metas de
80% / 90% (pior ano 72%); NDVI explica 3% a 10% da produtividade municipal (não usar como produtividade); chuva da quadra explica até 31% (milho). O selo "alta/média/baixa"
do diagnóstico é heurística de quantidade de dados, não probabilidade. Nenhuma rotação tem "percentual de acerto": as alternativas ficam em empate técnico.
