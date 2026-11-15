# Calendário de plantio (2026-11-14)

O agricultor diz, por voz ou texto, "plantei milho em fevereiro". O assistente automático responde, conversando, **o que os dados mostram** sobre esse plantio e **o que vale levar ao técnico**. Nunca é ordem, nunca é previsão.

Código: `src/culturas/calendario_plantio.py` (cálculo, puro), `src/llm/intencao.py` (`extrair_plantios`), `src/llm/dialogo.py` (perguntas), `src/llm/calendario_conversa.py` (conversa), `src/llm/fatos.py` (`montar_folha_calendario`), `src/app/calendario_app.py` e `src/app/app.py` (página "Meu calendário"), `src/api/rota_calendario.py` (`POST /calendario`), `src/api/rota_conversa.py` (`plantios` no estado e no perfil), `src/app/perfil.py` (campo `plantios`).
Testes: `tests/test_calendario_plantio.py`, `tests/test_calendario_conversa.py`, `tests/test_calendario_app.py`, `tests/test_calendario_api.py`.

## Regras que não mudam
- **O modelo de linguagem nunca calcula nem decide.** Todo número vem do código, com origem. A IA (se ligada) só reescreve os fatos `[F#]`; o verificador de sempre vale, mais o do calendário (abaixo). Sem chave ou com texto reprovado, sai o texto padrão montado dos mesmos fatos.
- **Lacuna visível.** Cada bloco do cálculo traz `disponivel` e, se faltar dado, o `motivo`. O fato vira "ainda não temos...", nunca um número inventado.
- **Ciclo e fases são "referência de outras regiões"** (FAO-56, Tabela 11, ou EcoCrop) e a frase diz que "sua semente pode ser diferente: se souber o ciclo dela em dias, me diga". O campo opcional `ciclo_dias` sobrepõe a referência (nesse caso só há fração do ciclo, sem estágios, e a frase diz "pelo ciclo que você informou").
- **Nada de ordem nem de previsão:** o verificador rejeita "deve colher/plantar", "tem que", "precisa", "recomendo", "plante", "colha", "o ideal é", "vale a pena", "rende mais", "vai chover", "produtividade", "sua lavoura está verde/fraca/boa". O verde é da **região** vista do satélite (pixel de cerca de 250 m), nunca da lavoura.
- **Assistente automático, linguagem simples, uma pergunta por vez** (guia: `docs/26_PESQUISA_AGENTE_HUMANO.md`), com o fecho "Converse com o técnico."
- Testes e desenvolvimento **nunca chamam a DeepSeek**: provedor falso, `.env` não lido, rede bloqueada em `tests/conftest.py`.

## O que o cálculo devolve (por plantio)
Entrada: `ponto_id`, lista `[{cultura, quando, ciclo_dias?, manejo?}]`, `hoje` (injetável). `quando` tem 3 formas validadas por schema estrito (`validar_plantios`): `{"data": "AAAA-MM-DD"}`, `{"mes", "ano"?, "parte"?}` (começo = dias 1-10, meio = 11-20, fim = 21 em diante) ou `{"de", "ate", "precisao"}`. **Mês sem ano = o mais recente que já começou** (em 14/11/2026, "fevereiro" é 2026 e "dezembro" é 2025; o mês corrente vale até hoje).

| Bloco | O que é | De onde vem |
|---|---|---|
| `quando` | início, fim e referência (meio da faixa), precisão (dia, decêndio, mês, faixa) | o que o agricultor disse |
| `ciclo` | dias do ciclo, faixa mín-máx, estágios ini/dev/mid/late | agricultor > FAO-56 Tabela 11 (`fao_staging.csv`, via `ciclo_fao`) > EcoCrop (`tabela_culturas.csv`) |
| `fase`, `dias_desde` | dias desde o plantio e fase: estágio FAO ou fração do ciclo; faixa se só se sabe o mês | conta do código sobre o ciclo |
| `colheita` | janela esperada: início + ciclo mínimo até fim + ciclo máximo | idem |
| `zarc` | `dentro`, `parcial`, `fora`, `sem_zoneamento` ou `nao_se_aplica` (irrigado); menor risco (20/30/40%) que indica cada decêndio; janelas dos três riscos; solo | `zarc.janela` sobre `zarc_ce.parquet` (MAPA, sequeiro). A textura do perfil escolhe o solo; sem ela vale "qualquer" |
| `chuva` | mm do plantio até o fim do ciclo de referência (ou até o último dia com dado) e quantos dos N anos anteriores tiveram menos chuva no mesmo período | `clima_diario_atual.parquet` (NASA POWER, célula de cerca de 50 km). Mínimo de 10 anos com 90% dos dias; "abaixo/perto/acima" usa terços e é só redação |
| `veranico` | maior sequência de dias secos (menos de 1 mm, `config.yaml: veranico.limiar_chuva_mm`) **só em dias da época de chuva do local**, contra a mediana e o p90 dos maiores períodos secos do local | clima + `diagnostico.json: veranicos` |
| `verde` | diferença do último composto de 16 dias para a média do mesmo composto nos anos anteriores (pelo menos 8) e média desde o plantio, só pixel com confiabilidade 0 ou 1 | `ndvi_16d_atual.parquet`; "o verde da região", não da lavoura |
| `solo_nu` | meses em que o solo do local costuma ficar nu e quantos dias depois do começo da colheita isso começa | `diagnostico.json: solo_nu` (relativo ao próprio local) |
| `proximas` | culturas que a matriz de rotação mostra como favoráveis, neutras, desfavoráveis ou sem dado depois desta; tira as "não quero" do perfil e as inviáveis no local (motor) | `matriz_rotacao.consulta` + `avaliar_sequencia.avaliacao_local`. **Sem ranking: as favoráveis ficam empatadas** e o texto diz que os dados não mostram qual é melhor |

Situações: `em_andamento`, `ciclo_concluido` (passou da janela de colheita), `planejamento` (data futura: só ZARC, colheita esperada, solo nu e rotação) e `esclarecimento` (cultura fora da lista, data a mais de 1 ano no futuro ou de mais de 2 anos atrás): o chat **pergunta o mês de novo** em vez de calcular.

## Conversa
1. **Entender** (`intencao.extrair_plantios`, sem IA): verbos plantei, plantamos, semeei, botei, coloquei, "plantado desde"; culturas com sinônimos e erro de grafia ("miilho", "mandioka", "sorgu"); tempo: mês (também "fev", "fervereiro"), começo/meio/fim, "dia 10 de fevereiro", "10/02", "ontem", "anteontem", "semana passada", "mês passado", "faz dois meses", "há duas semanas", "no inverno" e "na quadra" (época de chuva, fevereiro a maio; pergunta o mês). Várias culturas na frase ficam na fila.
2. **Perguntar** (`dialogo.proxima_pergunta_plantio`), uma coisa por vez, na ordem: cultura, mês, começo/meio/fim, ciclo da semente, confirmação.
3. **Confirmar**: "Entendi: milho plantado no começo de fevereiro. Está certo?" Só então o plantio entra em `estado.plantios` (lista validada por schema; o estado nunca guarda o texto das mensagens).
4. **Responder** com a folha de fatos (`fatos.montar_folha_calendario`): `resumo` (fase, colheita, zoneamento) na primeira vez e, depois, uma oferta por vez ("Quer ver como choveu desde o plantio?"): chuva e período seco, terra descoberta depois da colheita, o que vem depois na rotação. Perguntas de acompanhamento ("como choveu?", "e o verde?", "quando colho?") funcionam quando já há plantios no estado **ou no perfil**.
5. **Escrever**: até cerca de 90 palavras de fatos (texto padrão: até cerca de 100 contando a pergunta e o fecho). A IA, se ligada, recebe só frases simples dos fatos (nada de nome do município, ponto, IBGE, lat ou lon) e o prompt inteiro cabe em 2.800 tokens (o teste mede).

Pedidos de lucro, produtividade ou previsão do tempo dentro da conversa do calendário recebem a mesma recusa acolhedora da conversa consultiva, sem perder o que já foi entendido.

## Verificador do calendário (além do padrão)
Rejeita ordem ou recomendação, previsão de clima, colheita ou produtividade, "sua lavoura está...", mais de 100 palavras, e, nos assuntos resumo e colheita, texto que fala do ciclo sem dizer "referência de outras regiões" (ou "ciclo que você informou") e, no resumo, sem lembrar da semente. Rejeitado = texto padrão (dos mesmos fatos).

## Tela e API
- **App, página "Meu calendário"**: caixa de conversa; formulário (cultura, mês, começo/meio/fim, ciclo da semente opcional, sequeiro ou irrigado); lista de plantios com "Tirar"; para cada um, uma **linha do tempo** (altair: plantio, fases de referência, colheita esperada, janela do zoneamento, terra descoberta depois, e a linha de "hoje") e as frases simples com a origem de cada uma; baixar e carregar o perfil JSON (campo `plantios`, validação por schema, sem identificador); botão "Ver no calendário" vindo da conversa (também em "Pergunte ao Sulco").
- **`POST /calendario`** (`rota_calendario.py`): `{ponto_id, plantios: [...], textura?, proibidas?, proximas?}` devolve o cálculo e os `fatos` (texto técnico, texto simples, origem, lacuna). `hoje` é o do servidor. Schema estrito (`extra="forbid"`): erro de schema = 422, município inexistente = 404, data impossível = 200 com `status: "esclarecimento"`.
- **`POST /conversa`**: aceita `estado.plantios` e `perfil.plantios` (schema estrito, 422 se inválido); a saída ganhou o campo opcional `calendario` (`null` nas conversas de antes), então o contrato anterior segue igual.
- **Ligar no `main.py`** (dono do arquivo; não foi editado aqui). Hoje `main.py` ainda não inclui nem a rota `/conversa`:
  ```python
  from src.api.rota_conversa import router as rota_conversa
  from src.api.rota_calendario import router as rota_calendario
  app.include_router(rota_conversa)
  app.include_router(rota_calendario)
  ```
  Sugestão: acrescentar `"/calendario"` a `limite_taxa.PESADAS` (a primeira chamada carrega o motor para filtrar as culturas viáveis).

## Exemplos de conversa completa (texto padrão, sem IA; hoje = 14/11/2026, município de Quixadá)
### Exemplo 1: milho em fevereiro (a ordem das perguntas, a confirmação e três assuntos)
```
Agricultor: plantei milho em fevereiro
Sulco: Entendi: milho plantado em fevereiro. Foi no começo, no meio ou no fim do mês?
Agricultor: no começo
Sulco: Você sabe quantos dias a sua semente leva até a colheita? Se não souber, tudo bem.
Agricultor: não sei
Sulco: Entendi: milho plantado no começo de fevereiro. Está certo?
Agricultor: sim
Sulco: Anotado. Para olhar os dados do seu local, preciso saber o município. Em que município fica a sua roça?
Agricultor: Quixadá
Sulco: Pela referência da FAO (de outras regiões), o milho leva uns 140 dias até a colheita. Hoje faz entre 277 e 286 dias: já passou do ciclo. Sua semente pode ser diferente: se souber o ciclo dela em dias, me diga.
       A colheita costuma ficar entre 06/06 e 09/08 (ciclo de 125 a 180 dias). Essa época já passou.
       O zoneamento do Ministério da Agricultura não indica plantio do milho nesse período. A janela (risco até 30%) vai do 2º decêndio de fevereiro ao 1º decêndio de março.
       Converse com o técnico.
       Quer ver como choveu desde o plantio?
Agricultor: sim
Sulco: Do plantio até o fim do ciclo de referência (24/06), choveram 511 mm no seu local. Isso é perto do que costuma chover nessa época: choveu mais que em 9 dos 25 anos anteriores.
       O maior veranico (período seco na época de chuva, com menos de 1 mm por dia) foi de 7 dias seguidos desde o plantio. No seu local o comum é uns 9 dias, e em 1 de cada 10 anos passa de 15: este ano ficou dentro do comum.
       Converse com o técnico.
       Quer ver quando a terra costuma ficar descoberta depois da colheita?
Agricultor: sim
Sulco: A colheita costuma ficar entre 06/06 e 09/08 (ciclo de 125 a 180 dias). Essa época já passou.
       No seu local, a terra costuma ficar mais descoberta, com pouco verde, de outubro a dezembro. Contando do começo da colheita esperada, isso começa em uns 117 dias. O satélite não vê a sua roça.
       Converse com o técnico.
       Quer ver o que os documentos dizem sobre o que pode vir depois, na rotação?
Agricultor: o que vem depois?
Sulco: Os documentos não mostram cultura favorável depois do milho; sem efeito claro: algodão e girassol. Aparecem como desfavoráveis: milheto.
       Converse com o técnico.
```
Note como a fase vem da FAO (ciclo de outras regiões), o plantio de começo de fevereiro cai **fora** da janela do zoneamento (que começa no 2º decêndio) e isso é dito sem dizer "errou" nem "replante". O ciclo de 140 dias, os 277 a 286 dias, os 511 mm e os "9 dos 25 anos" são números do cálculo (cada um com origem no fato correspondente).

### Exemplo 2: o agricultor sabe o ciclo da semente
```
Agricultor: semeei feijão de corda no meio de março, a semente leva uns 70 dias
Sulco: Entendi: feijão-caupi plantado no meio de março, ciclo de 70 dias. Está certo?
Agricultor: sim
Sulco: Você plantou o feijão-caupi no meio de março.
       Pelo ciclo que você informou, de 70 dias, hoje faz entre 239 e 248 dias: já passou do ciclo.
       Pelo ciclo que você informou, a colheita fica entre 20/05 e 29/05. Essa época já passou.
       O zoneamento do Ministério da Agricultura indica plantio do feijão-caupi nessa época no seu município, com risco de até 20% de perda por clima.
       Converse com o técnico.
       Quer ver como choveu desde o plantio?
Agricultor: como choveu?
Sulco: Do plantio até o fim do ciclo de referência (23/05), choveram 366 mm no seu local. Isso é mais do que costuma chover nessa época: choveu mais que em 17 dos 25 anos anteriores.
       O maior veranico (período seco na época de chuva, com menos de 1 mm por dia) foi de 3 dias seguidos desde o plantio. No seu local o comum é uns 9 dias, e em 1 de cada 10 anos passa de 15: este ano ficou dentro do comum.
       Converse com o técnico.
```
Com o ciclo informado, a frase deixa de dizer "referência de outras regiões" e de pedir a semente. (Aqui o texto "fim do ciclo de referência" no assunto da chuva é o rótulo do período contado.)

### Exemplo 3: "no inverno", cultura sem zoneamento (lacuna dita) e pergunta sobre o solo
```
Agricultor: plantei sorgo no inverno
Sulco: Entendi que foi na época de chuva, de fevereiro a maio. Em que mês você plantou o sorgo?
Agricultor: abril
Sulco: Foi no começo, no meio ou no fim do mês?
Agricultor: no fim
Sulco: Você sabe quantos dias a sua semente leva até a colheita? Se não souber, tudo bem.
Agricultor: não sei
Sulco: Entendi: sorgo plantado no fim de abril de 2026. Está certo?
Agricultor: sim
Sulco: Você plantou o sorgo no fim de abril de 2026.
       Pela referência da FAO (de outras regiões), o sorgo leva uns 130 dias até a colheita. Hoje faz entre 198 e 207 dias: já passou do ciclo. Sua semente pode ser diferente: se souber o ciclo dela em dias, me diga.
       A colheita costuma ficar entre 24/08 e 07/09 (ciclo de 125 a 130 dias). Essa época já passou.
       O zoneamento do Ministério da Agricultura não traz o sorgo para o seu município: não conferi essa época.
       Converse com o técnico.
       Quer ver como choveu desde o plantio?
Agricultor: e a terra, fica descoberta depois da colheita?
Sulco: A colheita costuma ficar entre 24/08 e 07/09 (ciclo de 125 a 130 dias). Essa época já passou.
       No seu local, a terra costuma ficar mais descoberta, com pouco verde, de outubro a dezembro. Contando do começo da colheita esperada, isso começa em uns 38 dias. O satélite não vê a sua roça.
       Converse com o técnico.
       Quer ver como choveu desde o plantio?
```
Outros casos que o teste cobre: "plantei miilho em fervereiro" (erros de grafia), "plantei feijão" (pergunta se é de corda ou comum), "plantei milho e sorgo em março" (duas culturas: pergunta uma de cada vez), "plantei melancia" (fora da lista: franqueza e pede outra cultura), data futura ("planejamento"), data a 3 anos atrás ou a 2 anos à frente (esclarecimento: pergunta o mês de novo) e pedido de lucro ou previsão (recusa).

## Limites
- **A referência não é a sua semente.** Os ciclos da FAO vêm de outras regiões (Califórnia, Mediterrâneo, Nigéria, Índia...); nenhuma linha é do semiárido brasileiro. O ciclo informado pelo agricultor sobrepõe, mas então só há fração do ciclo.
- **Mês sem dia = faixa.** Os dias desde o plantio, a fase e a colheita aparecem como faixa; chuva, período seco e verde usam o meio do mês como referência (dito na frase).
- **Clima de 50 km, satélite de 250 m.** A chuva da roça pode ser bem diferente da célula; o verde é da região.
- **"Veranico" só vale na época de chuva do local** (quinzenas mais chuvosas do diagnóstico). Fora dela é normal ficar seco e não conta.
- **Terços de "abaixo/perto/acima"** são só para a redação; os números (mm, mediana, mínimo, máximo, anos) ficam no texto técnico.
- **Sem ZARC** para sorgo, guandu, palma... : lacuna dita; não se usa a janela aproximada das anuais (decisão para não parecer indicação). Irrigado: o ZARC usado é de sequeiro e não se aplica.
- **Rotação sem ranking:** a matriz diz favorável, neutro, desfavorável ou sem dado por documento; o Pareto e o motor de três caminhos não entram no calendário. A viabilidade no local vem do motor (3 a 4 s na primeira consulta por município).
- "No inverno" é entendido como a época de chuva (fevereiro a maio, a quadra do Ceará, a mesma do painel da quadra do app); por ser ambíguo, o assistente pergunta o mês.
- Não há previsão: nem de chuva, nem de colheita, nem de produtividade, nem de preço.
