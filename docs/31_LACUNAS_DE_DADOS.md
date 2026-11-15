# 31. O que o Sulco NÃO tem de dados (lacunas declaradas)

Atualizado em 2026-11-14. Cada linha vem de um relatório ou documento do projeto, indicado na coluna "Onde está registrado". O que não foi verificado está marcado. Este documento também alimenta a resposta do assistente quando alguém pergunta algo que não temos: ele deve **dizer que não tem** e oferecer o que existe, nunca preencher a lacuna.

## 1. Dinheiro e mercado
| O que falta | O que existe no lugar | Onde está registrado |
|---|---|---|
| **Preço recebido pelo agricultor, por cultura e município** | Preços mensais da CONAB só de 2025–2026 e, no Ceará, só feijão, milho, mandioca, algodão e mamona (mamona com 1 observação). A licença da CONAB não foi lida. | docs/27 (seção 4) |
| **Série de preços de longo prazo** (CEPEA, PGPM) | Nada: o CEPEA deu bloqueio (403) e os arquivos de preço mínimo deram 404 nas URLs testadas. CEASA-CE, Embrapa e Ematerce não foram abertos. | docs/27 |
| **Custo de produção** | Só milho 2ª safra em Crateús (CONAB), custo médio regional, não o do agricultor. Custo de entrada e mão de obra: **sem dado**. | docs/27 |
| **Lucro ou margem** | Nada. Existe só receita bruta por hectare (`renda.py`), que **não é lucro** e não orienta a escolha. | docs/19, docs/24 |
| **Crédito e seguro rural** | Garantia-Safra lido no IPECE-CE (renda até 1,5 salário mínimo, área de 0,6 a 5 ha, perda de 50% ou mais). **Pronaf e Proagro não foram lidos na norma** (vieram de busca); o valor atual do Garantia-Safra também não foi lido na fonte. | docs/27 |

## 2. Sementes e variedades
| O que falta | O que existe no lugar | Onde está registrado |
|---|---|---|
| **Cultivares recomendadas por local** | Nada confirmado. O Registro Nacional de Cultivares tem captcha e não foi baixado. A contagem de cultivares do ZARC para o Ceará está **marcada como não verificada**. | docs/27 (4a) |
| **Preço e oferta de sementes** | Preço de semente só para milho, com 2 observações da CONAB. | docs/27 |
| **Semente usada pelo agricultor** | Nada. O ciclo vem de tabelas de outras regiões; o agricultor pode informar o ciclo da própria semente. | docs/21 CALENDARIO_PLANTIO |
| O SIGEF (1.553 linhas do Ceará) | São **campos de produção de semente**, não lavoura comercial. Não representam o que o agricultor planta. | docs/27 |

## 3. Produção e resultado da lavoura
| O que falta | O que existe no lugar | Onde está registrado |
|---|---|---|
| **Produtividade medida por cultura e local** | Só a área colhida do IBGE (PAM) por município. O motor não tem produtividade. | docs/19, docs/24 |
| **Ganho de produtividade do consórcio no terreno do agricultor** | LER publicado em experimentos (21 estudos, 16 abertos, 8 na faixa de semiárido em sequeiro). É valor de um experimento, **não do seu terreno**; 8 dos 12 pares têm algum arranjo com LER abaixo de 1. | docs/29 |
| **Qualquer promessa de colheita, renda ou rendimento** | Proibida por regra do projeto. | memória do projeto, docs/19 |

## 4. Clima e previsão
| O que falta | O que existe no lugar | Onde está registrado |
|---|---|---|
| **Previsão de chuva ou do clima futuro** | Nada. O assistente recusa. | docs/21 CONVERSA_CONSULTIVA |
| **Previsão do verde (NDVI) além de 16 dias** | Só o próximo composto de 16 dias, com faixa de incerteza (ganho de 0,254 sobre a média histórica em dados de 2025–2026). A habilidade cai nos compostos seguintes (+0,163, +0,110, +0,065). O clima sozinho não melhora a previsão. | docs/21 DADOS_2025_NA_PREVISAO; experimentos/previsao_doc09 |
| **Clima exatamente na roça** | Chuva e temperatura do NASA POWER em células de cerca de 50 km; NDVI do MODIS a 250 m. **O satélite não vê a roça do agricultor.** | docs/24 |
| **Evapotranspiração da cultura (ETc) e balanço hídrico do solo** | Só evapotranspiração de referência. ETc não entrou no motor (faltam ETo e latitude no objeto de clima). | docs/21 CICLO_FAO_CHUVA_ANUAL |
| Umidade do solo (SMAP) | Coletada, **só informativa**; não entra no ranking. | docs/00 |

## 5. Solo
| O que falta | O que existe no lugar | Onde está registrado |
|---|---|---|
| **Análise de solo do agricultor** | Solo **estimado de mapa global** (SoilGrids): pH, areia, argila, carbono. Não é análise. Não trouxe ganho ao modelo de previsão. | docs/21 SOLO, docs/27 |
| **Fertilidade, salinidade, profundidade e drenagem** | O espelho do EcoCrop traz esses fatores por cultura, mas **só pH e textura** podem ser comparados com o mapa global; os outros quatro ficam como lacuna (37 lacunas explícitas em `solo_staging.csv`). | docs/27 (3) |
| Solo na decisão de quais culturas servem | Existe como opção **desligada** (`solo_modo='ecocrop'`). Ligada, parte do efeito é artefato (palma com nota zero em 182 de 184 pontos, contra o ZARC). | docs/27 (3) |

## 6. Calendário e ciclo
| O que falta | O que existe no lugar | Onde está registrado |
|---|---|---|
| **Calendário oficial de plantio** para guandu, crotalária, feijão-de-porco e mucuna | Nada. O assistente diz "não conferi essa época". Para palma e sorgo o zoneamento também não é usado. | docs/27 (2), docs/27_EPOCA |
| **Zoneamento de sequeiro fora do Ceará, de irrigado e de culturas fora das 11 mapeadas** | O ZARC cobre só risco climático de perda, só sequeiro nesta leitura, só o Ceará, só as culturas listadas. O significado de 0/20/30/40 não vem no dicionário oficial. | docs/27 (2) |
| **Ciclo das culturas no semiárido brasileiro** | Ciclo da FAO-56 e do EcoCrop, **de outras regiões** (nenhuma linha da tabela da FAO é do semiárido brasileiro). Cinco culturas ficam com o ciclo do EcoCrop. Sorgo, caupi e gergelim têm inconsistência na própria tabela da FAO. | docs/21 CICLO_FAO |
| **Faixa de chuva do sorgo** | Vem do espelho do EcoCrop (máximo de 700 mm por ano); a ficha oficial é inacessível. O motor dá o sorgo como inviável em todo o Ceará, embora o IBGE mostre área colhida. | docs/21 CICLO_FAO, docs/27 |

## 6b. Pragas, doenças e insumos (conferido em 2026-11-14)
| O que falta | O que existe no lugar | Onde está registrado |
|---|---|---|
| **Pragas e doenças por cultura e local** | **Nenhum dado estruturado.** A tabela de culturas não tem coluna de praga ou doença. O motor usa só um **substituto**: a diversidade de famílias botânicas na rotação ("proxy de pragas"). A tela mostra a lacuna "pragas e doenças: sem dado". A régua do desafio dá só 0,5 de 0,5 ponto a esse item. | docs/19 (linhas 7d, 19), docs/11 |
| **Produtos e defensivos (agrotóxicos)** | Nada. O assistente **não indica produto nem dose** (regra de segurança). | docs/30 (segurança) |
| **Dose de adubo e de calcário, recomendação de adubação** | **Nenhuma tabela de dose.** Da tabela de culturas só existem, por cultura, o nitrogênio acumulado e o nitrogênio fixado (`n_fixado_kg_ha`: **13 das 16 culturas ficam em lacuna, só 3 verificadas**) e a palha (`palha_ms_kg_ha`: 6 de 16 em lacuna). Isso descreve o que a planta devolve ao solo, **não quanto aplicar**. | data/culturas/tabela_culturas.csv, docs/21 CONVERSA_CONSULTIVA |
| Matéria orgânica, fósforo, potássio, calagem do solo do agricultor | Nada (ver seção 5: não há análise de solo). | docs/27 |

**O que existe de texto sobre isso:** os 50 documentos da Embrapa, do Ministério da Agricultura e da FAO que já estão indexados têm trechos que falam de pragas, doenças e defensivos (**416 de 3.203 trechos**, a maioria do guia da Embrapa Meio-Norte sobre feijão-caupi) e de adubação e nitrogênio (**780 trechos**, por exemplo da UNIVASF e da Embrapa Semiárido). São **texto de documento, não dado curado do projeto**: ninguém conferiu esses números para o Ceará nem os ligou ao local do agricultor. O assistente pode **resumir o que o documento diz, com a fonte**, mas **não deve transformar isso em dose, produto ou recomendação**; para isso a resposta é "converse com o técnico".

## 7. Decisão e validação
| O que falta | Onde está registrado |
|---|---|
| **Separar as alternativas de rotação:** o empate técnico é de 100% dos locais testados. Os dados atuais não dizem qual é melhor. | docs/19, docs/21 |
| **Validação com agricultores e técnicos locais.** O app não foi testado com agricultores. | docs/24 |
| **Tratamento e linguagem com agricultor do Nordeste, taxa de reformulação, voz "mais humana" aumentando confiança:** sem fonte; é opinião a testar. | docs/26 |
| Censo Agropecuário: adiado por decisão. | memória do projeto |

## 8. Como o assistente deve usar este documento
1. Se a pergunta cai em uma linha acima, responder com **"não tenho esse dado"** e dizer, em palavras simples, **o que existe no lugar**.
2. Não completar com número de fora, nem de memória.
3. Terminar com "converse com o técnico" quando a decisão depender do que falta.
4. Nunca transformar o que existe (receita bruta, preço, LER) em promessa de lucro, colheita ou melhor escolha.
