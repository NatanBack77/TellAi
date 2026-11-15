# Conversa livre (2026-11-14)

Problema: a conversa só respondia bem a 4 pedidos guiados; pergunta livre caía em frase genérica ("O Sulco olha o seu local, compara três caminhos..."), em "sem evidência" ou em trecho cru de PDF. Agora o agente responde, **a qualquer momento**, qualquer assunto que o Sulco tenha dado, e depois retoma a pergunta que estava aberta.

Regras mantidas: o LLM só REESCREVE fatos [F#]; o verificador vale; nenhum número vem de fora dos fatos; nada é prometido; sem DeepSeek nos testes (provedor falso).

## 1. Inventário do conhecimento e como acessar (por município e por cultura)

| Conhecimento | Onde está / como acessar | Fato no roteador |
|---|---|---|
| Chuva por mês, dias com chuva, temperatura máx./mín. por mês | `data/processed/clima_diario_atual.parquet` (NASA POWER, 2001 em diante) via `conhecimento._clima_completo` | `clima_mes` (12 fatos), `chuva_atual` (mês de hoje, ano até agora vs. média) |
| Estação chuvosa, veranico, solo nu, estresse, tendência de anos | `mvp.diagnostico_local` -> `fatos._diagnostico` | `diagnostico` |
| Previsão do verde (modelo), limites e métricas | `fatos._previsao`, `_skill_historico` | `previsao`, `modelo_skill` |
| ZARC por cultura (decêndios) e época de plantio de hoje | `culturas.zarc.janela`, `fatos._zarc` | `zarc_plantio`, `plantar_agora` |
| Ciclo FAO e fases; EcoCrop quando não há FAO | `culturas.ciclo_fao.ciclos_fao`, `tabela_culturas` | `ciclo` |
| Faixas de chuva, calor e água da cultura | `tabela_culturas` (EcoCrop) | `cultura_clima` |
| Viabilidade e melhor começo no local | `avaliar_sequencia.avaliacao_local` | `viabilidade`, `por_que_nao` |
| Solo estimado (SoilGrids), pH da cultura (EcoCrop) | `mvp.solo_estimado`, `solo_ecocrop` | `solo` |
| Erosão, extremos, balanço chuva menos ETo | `secao_risco_solo`, `secao_balanco_renda` | `risco`, `extremos`, `eto` |
| O que o município produz, rendimento histórico (IBGE/PAM) | `data/processed/pam_ce.parquet` | `pam` |
| Receita bruta por hectare (não é lucro) | `culturas.renda` | `renda` (só para lacunas de preço/lucro) |
| Rotação (matriz, evidência do acervo), o que vem depois | `matriz_rotacao.consulta`, `calendario_plantio.proximas_padrao` | `rotacao_par` |
| Consórcio (LER publicado no semiárido) | `culturas.consorcio` | `consorcio` |
| Adubação verde e palha (ranking da tabela) | `tabela_culturas` (n_fixado, palha) | `adubacao_verde`, `palhada` |
| Forragem | `culturas.forragem` (lacuna de valor forrageiro) | `forragem` |
| Calendário do agricultor | `calendario_conversa` (não mudou) | segue o fluxo próprio |
| Acervo (50 PDFs, RAG) | `chat._buscar_padrao` | `acervo` (frases limpas) |
| Glossário, sobre o Sulco, limites | `sobre_sulco.documentos` | `glossario`, `sobre_sulco`, `limites` |
| **Lacunas (não existem)**: preço, custo, semente, venda/mercado, lucro, produtividade futura, pragas do local, dose de adubo, irrigação, jeito de plantar | dito com franqueza | `lacuna` (prio 0) |

## 2. Como funciona (src/llm/conhecimento.py)

1. **Temas por regra** (`detectar_temas`, ~35 temas, tolerante a grafia por `corrigir_grafia`). Cultura citada via `intencao` (grafia aproximada); "janeiro", "chove" e palavras do vocabulário não viram cultura (filtro de falsos positivos fuzzy).
2. **Ficha completa** (`_ficha`): ~265 fatos curtos montados automaticamente (folha do local, 12 meses, PAM, 16 culturas x ciclo/faixas/viabilidade/ZARC/pH/sanidade, rotação, consórcio, glossário, lacunas, inventário). Cada fato tem tags/sinônimos só para busca. **Busca BM25** (o mesmo `rag.busca.BM25`, sem carregar modelo) com cobertura mínima de 30% das palavras (peso por idf), pelo menos 2 palavras em comum ou nota >= 7, e reforço da cultura citada. Atua quando nenhuma regra casa e também completa a resposta de outros temas.
3. **Combinação**: temas de várias regras + top-k da ficha entram na mesma folha (ex.: "dá para plantar milho agora e vai chover?" = viabilidade + ZARC + chuva do mês + lacuna de previsão).
4. **Lacuna honesta**: tema de dado inexistente devolve primeiro "ainda não temos dado de X" e depois "o que eu tenho para isso".
5. **Acervo**: `frases_simples` escolhe 1 a 2 frases completas que casam com a pergunta e descarta autor, citação, tabela, cabeçalho, parêntese aberto e nome próprio; sem frase limpa diz "não achei". Também vale para o texto padrão do chat (`chat._template_trechos`).
6. **Fluxo** (`conversa.py`): `_pergunta_livre` (qualquer estado, inclusive pergunta aberta de foco/ordem/culturas/município/confirmação/calendário) -> `_livre` responde com `_responder_com_fatos` (LLM só reescreve, verificador vale, <= 55 palavras no prompt, sem "?") e termina com UMA retomada ("Quando quiser, me diga..."/"Voltando: ..."), mantendo o `pendente`. Pedidos guiados (foco, montar ciclo, "dá certo aqui", contar o que plantou) e recusas de lucro/produtividade/clima seguem como antes. Pergunta sem tema e sem ficha vai ao caminho antigo, com a frase genérica trocada por "não achei". Sem município e a pergunta só do local: pergunta o município.
7. **Número só se o usuário pedir** (`numeros_permitidos`, por turno; `estado.numeros_permitidos`): sem dígito/unidade/"quanto..." na mensagem, os fatos vão na versão qualitativa (`qual` por fato ou `qualificar`: "mês de chuva fraca", "ciclo médio, de alguns meses", "na maioria dos anos"); fato sem versão possível sai. O prompt manda não citar número e o verificador (`verificar_conversa`) rejeita dígito e numeral por extenso (cai no texto padrão). Com número pedido, só números dos fatos.

## 3. Métricas (bateria `tests/perguntas_livres.py`, Quixadá, provedor falso)

| Medida | Resultado |
|---|---|
| Perguntas da bateria (com erro de grafia) | 95 |
| Tema detectado (aceito) | 95/95 (100%) |
| Com fatos úteis onde há dado | 95/95 (100%) |
| Lacuna honesta onde não há dado | 19/19 |
| Sem número pedido (81): resposta sem dígito nem numeral | 81/81 |
| Maior resposta padrão | 62 palavras (limite 62; voz) |
| Maior prompt (sistema + pergunta + fatos) | 1.339 tokens (limite 2.800; estimativa 3 caracteres por token) |
| 30 perguntas INESPERADAS (fora da redação dos temas) | 29/30 acham fato útil (regras + ficha); só BM25, sem regras: 20/30 |
| 10 perguntas fora do assunto (futebol, queijo, capital...) | 10/10 sem fato útil, resposta "não achei" |
| Tempo da 1a pergunta de um município (monta a ficha) | ~25 s (depois, cache) |

Limiar BM25 medido: nota >= 3,5, cobertura >= 0,30. Abaixo disso a pergunta é tratada como "fora do Sulco".

## 4. Exemplos (texto padrão, sem LLM)

1. "o que dá para plantar aqui?" (guiado) -> lista; "quanto custa a semente?" -> "Ainda não temos dado de preço de venda... de semente: qual variedade, quanto custa nem onde comprar. Converse com o técnico." + retomada "Quando quiser, me diga o que pesa mais para você...", **pendente `foco` mantido**.
2. "costuma chover muito nessa época do ano" -> "Em novembro, no seu local, quase não chove. Neste mês, até agora, choveu abaixo da média... A época de chuva costuma ser de janeiro a maio." Com "quantos mm chove em março?" -> "Em março, em média, chove 155 mm... em uns 22 dias com chuva."
3. No meio do calendário ("Em que mês você plantou o milho?"): "meu solo é fraco, e agora?" -> solo estimado tipo médio, erosão baixa, "Voltando: Em que mês você plantou o milho?", `pendente=plantio_mes`.

## 5. O que continua sem resposta (e por quê)

- Preço, custo, semente, comprador, lucro, produtividade futura, praga do local, dose de adubo, irrigação, jeito de plantar: **não há dado** (docs 15 e 27). Só os dados existentes (receita bruta IBGE, ciclo, faixas, matriz de rotação) são oferecidos.
- Previsão de chuva/tempo: o Sulco não prevê; mostra o já ocorrido.
- Nutrientes do solo (fósforo, potássio): só SoilGrids (textura, carbono, pH).
- Valor forrageiro: gráfico sem números no acervo.
- Zoneamento: só Ceará; guandu, crotalária, feijão-de-porco, mucuna e palma não têm.
- Frases de PDF só viram resposta quando há frase completa limpa; muitas vezes a resposta é "não achei no material".

## 6. Pendências e avisos

- A regra "número só se o usuário pedir" está na conversa; **no chat (`chat.py`) não foi aplicada**: 37 testes de `test_chat_simples/test_fatos/test_chat` esperam números no texto; decisão do coordenador antes de mudar.
- Frase existente de `fatos._diagnostico` ("...na temperatura daí") tem um "daí" estranho (não alterado).
- 3 testes que já falhavam seguem: `test_fatos::test_contexto_do_cenario_cabe_em_2500_tokens` (2652 > 2500) e 2 de `test_chat_simples` (`test_texto_simples_de_cada_tema_no_municipio_completo`, `test_texto_padrao_dos_caminhos_uma_linha_por_caminho_na_ordem`).
- Arquivos: novo `src/llm/conhecimento.py`, `tests/test_conversa_livre.py`, `tests/perguntas_livres.py`; editados `conversa.py` (gancho `_pergunta_livre`/`_livre`/`_retomada`, params de `_responder_com_fatos`), `dialogo.py` (estado: `ult_cultura`, `numeros_permitidos`), `chat.py` (`_template_trechos`). Não mexi em src/app, src/api, .env nem data.

## 7. Atualização 2026-11-15: limite dinâmico e saudação espelhada

- **Nome:** a assistente é a **Maíra** (nome escolhido pelo usuário; feminino). A divulgação continua: "assistente automática do Sulco, não é pessoa nem técnica"; sem idade, sem "na minha experiência", sem fingir ser humana. O campo `assistente` do JSON segue com o mesmo nome (agora "Maíra, assistente automática do Sulco (não é uma pessoa nem uma técnica)").
- **Saudação espelhada:** "bom dia" responde "Bom dia!", "boa tarde" responde "Boa tarde!", "boa noite" responde "Boa noite!"; "oi", "olá", "e aí", "tudo bem" respondem "Oi!". Depois vem uma frase de apresentação ("Eu sou a Maíra, a assistente automática do Sulco: mostro o que os dados dizem sobre o seu local e as culturas, e você leva isso para o técnico.") e "O que você quer ver?", com os chips iniciais. Sem número e sem pedir município (`conversa.texto_saudacao`).
- **Limite dinâmico de tamanho:** pergunta **grande** (12 ou mais palavras, 2 ou mais temas, ou pede explicação: "explica", "por que", "como funciona", "me conta") permite até **110 palavras** e até **8 fatos** (teto de 800 tokens de fatos; o prompt todo segue abaixo de 2.800 tokens, testado); o texto padrão (sem IA) usa até 5 frases e ~106 palavras. Pergunta curta continua com **55 palavras**, 7 fatos e texto padrão de ~56 palavras. O prompt traz a linha `LIMITE: no máximo N palavras...` e, para a grande, "responda cada parte dela, só com os fatos, em frases curtas e simples, uma ideia por frase". O verificador de tamanho usa o mesmo limite (+12% de folga: 61 para curta, 123 para grande). Código: `conhecimento.pergunta_grande`, `conversa.limite_palavras`, `verificar_conversa(limite=...)`.
- **Mantido:** número só se o usuário pediu, nada fora dos fatos, citação [F#] em cada afirmação, fecho "Converse com o técnico.".
- **Testes novos** (`tests/test_conversa_livre.py`): 7 saudações, 6 perguntas grandes (inclui "eu plantei milho em fevereiro, choveu pouco e agora o solo está fraco, o que os dados dizem e o que eu devo conversar com o técnico?"), pergunta curta com 55 e o verificador dinâmico ponta a ponta.
- **"Não entendi" (caso real por voz):** depois de "o que dá para plantar aqui?" o usuário disse "é não entendi tem como" e a resposta foi um trecho da Embrapa. Agora `conversa.nao_entendeu` detecta ("não entendi", "não compreendi", "como assim", "pode repetir", "explica de novo", "tem como explicar", "o que você falou", "hã?", "oi?", com erro de grafia; só mensagens de até 9 palavras) **antes** da pergunta livre e do acervo, e `_reexplicar` responde: com pergunta aberta, explica a pergunta com exemplo e mantém `pendente` e chips; sem pergunta aberta, repete a última resposta mais curta (campo `ult_resposta` do estado, até 300 letras, que só é repetido ao usuário, nunca vai à IA, e passa por `filtrar_saida` e `verificar_estado` antes de ser guardado) ou volta aos chips iniciais. Nunca usa trecho de documento. Testes: 11 variações + 2.

