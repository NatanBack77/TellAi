# 10. Motor com ciclo de plantio e ranking com incerteza

Implementa as duas primeiras recomendações dos docs 07 (Etapa A, opções 1 e 4) e 08 (SMAA-2). Todos os números abaixo
vêm de `python -m src.pipeline.gerar_cenarios --cultura-atual milho` e de `python -m src.pipeline.comparar_cenarios`
(10 pontos do Ceará, clima NASA POWER 2001-2024). Nada agronômico foi escrito de memória: faixas e ciclo vêm de
`data/culturas/tabela_culturas.csv` (EcoCrop via espelho OpenCLIM, ver a tabela).

## 1. O que mudou

| Arquivo | Mudança |
|---|---|
| `src/culturas/parametros.py` (novo) | Todos os parâmetros que dependem de decisão do usuário, com padrão marcado SUPOSIÇÃO. Gera o texto de `suposicoes`. |
| `src/culturas/ciclo.py` (novo) | Para cada início de plantio (a cada 10 dias desde 1º/jan = 36 inícios) e cada ano: temperatura média e chuva acumulada no ciclo; notas trapezoidais; adequação = mínimo(temperatura, chuva); melhor janela. |
| `src/culturas/incerteza.py` (novo) | Monte Carlo estilo SMAA-2 em numpy, semente fixa. |
| `src/culturas/motor.py` | `gerar_cenarios(perfil, atual, tabela, n_alternativas, clima=, params=)`: exige a série diária do ponto. `viabilidade()` e `pontuar()` (perfil anual) continuam existindo só porque `sensibilidade.py` (doc 06) os usa. |
| `src/pipeline/gerar_cenarios.py` | Passa a série diária ao motor; novas opções de linha de comando (`--ciclo-modo`, `--chuva-modo`, `--risco-max`, `--passo-inicio`, `--n-sorteios`, `--semente`). |
| `src/pipeline/comparar_cenarios.py` (novo) | Compara os JSON gravados entre locais. |
| `src/app/logica.py`, `src/app/app.py` | Mostram faixa, P(top-3), posição, cobertura, empate técnico e melhor época, em linguagem simples. |

## 2. Chuva e temperatura dentro do ciclo

- **Início e duração.** Inícios: dia 0, 10, 20, ... 350 desde 1º/jan (`passo_inicio_dias=10`). Duração: vem de
  `ciclo_min_dias` e `ciclo_max_dias` da tabela. O padrão é o **ponto médio** (SUPOSIÇÃO); `min` e `max` são opções. Cada
  cenário traz `janela_plantio.sensibilidade_ciclo` com a melhor adequação usando o ciclo mínimo e o máximo.
  Os extremos do EcoCrop são largos (milho 65 a 365 dias, milheto 60 a 120). **O ciclo real é decisão pendente.**
- **Clima.** Série diária real do ponto, ano a ano. Temperatura do ciclo = média de (Tmax+Tmin)/2; chuva = soma no
  ciclo. Janela com dia faltante ou que passa do fim da série é descartada (nunca preenchida). Só entram anos em que
  **todos** os ciclos avaliados estão completos: com os ciclos médios atuais são 23 anos (2001-2023), pois a janela de 2024
  passa do fim da série; isto aparece em `lacunas` e em `janela_plantio.anos`.
- **Nota.** Trapézio da tabela (0 fora da faixa absoluta, 1 na ótima) para temperatura e para chuva. Adequação por
  início e ano = **mínimo** das duas (a ideia do modelo EcoCrop descrito no README do OpenCLIM; reimplementada, sem
  copiar código, pois o repositório não declara licença).
- **Melhor janela.** O início com maior adequação média entre anos; se vários empatam, o de maior fração de anos viáveis;
  persistindo, o início central do platô (nunca por nome). Saem: `melhor_inicio` (dd/mm), `inicios_equivalentes`,
  `adequacao_media`, distribuição entre anos (`p10`, `p50`, `p90`), `fracao_anos_viaveis`, temperatura e chuva médias do
  ciclo naquela janela, e `chuva_sobre_demanda_hidrica` (só quando a tabela tem `demanda_hidrica_mm_ciclo`; **informativo**,
  não entra no score).
- **Critérios do contrato.** A nota de temperatura e a de chuva de cada cenário são a média, entre os anos, das notas
  naquela melhor janela. O mínimo escolhe a janela e é reportado como adequação; não é aplicado de novo no score (para
  não contar duas vezes). Se o score deve usar o mínimo diretamente, é decisão pendente.
- **Filtro de viabilidade mais estreito.** Antes: média anual dentro da faixa absoluta. Agora: existe algum início em que a
  cultura fica dentro das faixas absolutas de temperatura **e** chuva em pelo menos `1 - risco_max` dos anos (padrão
  `risco_max=0,30`, SUPOSIÇÃO; não é o risco do ZARC). Cultura sem faixa completa ou sem `ciclo_min/max` na tabela =
  `indeterminada`, listada em `lacunas` e fora do ranking (não some em silêncio). Hoje nenhuma das 16 culturas está
  indeterminada; o teste `test_indeterminada_sem_ciclo_ou_sem_faixa_fica_visivel` cobre o caso.

## 3. Incerteza e ranking (estilo SMAA-2)

Cada um dos 10 000 sorteios (semente 20241112) escolhe: pesos (Dirichlet(1), uniforme no simplex), **o ano do clima**
(o mesmo para todas as culturas do ponto) e, para cada nota ausente, um valor Uniforme[0,1]. O score **não** é
renormalizado: a lacuna não é removida nem premiada (teste `test_lacuna_nao_e_removida_nem_premiada`).

Dois blocos por cultura:

1. **Ranking principal**: só os critérios que **todas** as candidatas têm (hoje temperatura, chuva, família; é calculado
   dos dados, não fixado). Cobertura: 0,65 do peso total, igual para todas.
2. **Complemento com N e palha**: cinco critérios, lacuna = U[0,1]. Fica em `faixa_incerteza.complemento_n_palha`, à parte.
   A cobertura própria de cada cultura (`cobertura.completa`) mostra quanto do peso tem dado (0,65 ou 1,0).

Saídas por cultura em `faixa_incerteza` (principal): `min`/`max` (= `score_p10`/`score_p90`, nomes que o app já lia),
`score_p50`, `posicao_p10`/`posicao_p90`, `posicao_media`, `p_top3`, `p_1o`, `aceitabilidade_posicao` (SMAA-2),
`empate_tecnico_com`, `cobertura`, `criterios_ranking`, `metodo`, `n_sorteios`, `semente`, `anos_clima`, `leitura`.

- **Empate.** Sem desempate alfabético. Dentro de um sorteio, scores iguais dividem as posições igualmente. **Empate
  técnico** (SUPOSIÇÃO de definição) = intervalos p10-p90 de score que se sobrepõem; a relação não é transitiva.
  Para escolher as 2 alternativas mostradas: maior P(top-3), depois menor posição média, e, se ainda houver empate
  exato, ordem de um sorteio com semente fixa (independe do nome; o cenário avisa em `lacunas`).
- **O que a faixa representa** (também em `faixa_incerteza.leitura`): sensibilidade do modelo a pesos, lacunas e anos de
  clima, dentro do declarado em `suposicoes`. **Não** é intervalo de confiança nem chance de a rotação dar certo.
  A pontuação central (`score`) usa os pesos-base renormalizados entre os critérios comuns e a média dos anos; por isso
  pode cair fora de [p10, p90] quando poucos anos ruins puxam a média (ex.: score 99,0 com faixa 100-100 em caridade_ce).
- **Conferência com o pacote `pysensmcda` 2.0.0** (MIT), instalado só num venv temporário no scratchpad:
  `tests/test_smaa_pysensmcda.py` alimenta o `smaa.simulate` com os mesmos pesos e uma soma ponderada; a
  aceitabilidade de posição é **igual** (diferença máxima < 1e-12). O teste é pulado se o pacote não estiver instalado
  (não é dependência do projeto). Outra conferência analítica: A=(1,0) e B=(0,1) dão P(1º)=0,5 (teste com 20 000 sorteios).
  Empate exato não tem equivalente no pacote; o tratamento é nosso.

## 4. Os locais agora se diferenciam?

Antes (cenários antigos, chuva anual): os 10 pontos tinham score 76,9 (atual) e 100,0 (alternativas) idênticos, com
algodão e amendoim escolhidos por ordem alfabética em 9 deles. Depois (ciclo médio, padrão):

| local | célula POWER | score atual | melhor início | chuva no ciclo (mm) | adequação média | alternativas (P(top-3)) |
|---|---|---|---|---|---|---|
| amontada_ce | -6_-64 | 74,6 | 27/12 | 902,1 | 0,940 | guandu (0,41), feijao_caupi (0,40) |
| caridade_ce | -8_-63 | 75,4 | 17/12 | 853,1 | 0,960 | feijao_caupi (0,45), guandu (0,45) |
| fortaleza_ce | -8_-62 | 75,8 | 07/11 | 963,4 | 0,970 | feijao_caupi (0,41), guandu (0,41) |
| ico_ce | -13_-62 | 74,4 | 17/12 | 792,0 | 0,934 | guandu (0,47), feijao_caupi (0,42) |
| ipaumirim_ce | -14_-62 | 73,8 | 17/12 | 793,0 | 0,919 | feijao_caupi (0,50), guandu (0,40) |
| limoeiro_do_norte_ce | -10_-61 | 66,6 | 27/12 | 690,9 | 0,732 | guandu (0,53), crotalaria_juncea (0,49) |
| pacajus_ce | -8_-62 | 75,8 | 07/11 | 963,4 | 0,970 | feijao_caupi (0,41), guandu (0,41) |
| pindoretama_ce | -8_-61 | 73,5 | 17/12 | 934,1 | 0,910 | guandu (0,49), feijao_caupi (0,45) |
| quixada_ce | -10_-62 | 71,0 | 17/12 | 742,9 | 0,847 | guandu (0,55), feijao_caupi (0,52) |
| santana_do_acarau_ce | -7_-64 | 75,6 | 17/12 | 920,6 | 0,965 | feijao_caupi (0,45), guandu (0,41) |

- **Sim, os scores diferem**: 9 valores distintos de score da cultura atual em 10 locais (antes 1), 9 de chuva no ciclo,
  3 de melhor início (27/12, 17/12 e 07/11; a grade é de 10 em 10 dias). Os mais secos (limoeiro_do_norte_ce: 690,9 mm;
  quixada_ce: 742,9 mm) tiram score menor e adequação menor; no limoeiro, amendoim e feijão-de-porco ficam **inviáveis**
  (em quixada, só feijão-de-porco) com `risco_max=0,30`; nos demais 8 pontos todas as 16 culturas seguem viáveis.
- **fortaleza_ce e pacajus_ce são idênticos** porque estão na mesma célula POWER (~50 km). O clima é da célula, então
  locais da mesma célula nunca se diferenciam por clima. Há 59 células para 195 pontos.
- **As alternativas ainda são quase as mesmas**: guandu em 10 de 10 locais, feijão-caupi em 9; crotalária só em limoeiro_do_norte_ce. A ordem
  entre elas muda por local, mas **não é separável**: cada alternativa mostrada tem empate técnico com 10 a 13 outras
  candidatas, P(top-3) entre 0,40 e 0,55 e posição típica (p10 a p90) entre 1º e 8º. A diferença real entre locais está
  no score e na janela da cultura atual, e em quais culturas ficam inviáveis, não em um ranking firme de alternativas.
- Scores de 100,0 (fortaleza, pacajus) com faixa 100-100: nenhum critério do ranking principal tem nota abaixo de 1 em
  mais de 90% dos sorteios; é o limite de a nota ser trapezoidal e saturar em 1.

### Sensibilidade às suposições (mesmos 10 pontos, culturas atual milho)

| suposição | score da cultura atual | alternativas escolhidas | observação |
|---|---|---|---|
| ciclo médio (padrão; milho 215 d) | 66,6 a 75,8 | guandu, caupi, crotalária | acima |
| ciclo mínimo (milho 65 d) | 43,0 a 56,1 | mamona e algodão em 9 pontos; crotalária e mamona em limoeiro | chuva em 65 dias (322 a 489 mm) fica perto do mínimo absoluto do milho; P(top-3) sobe para 0,52 a 0,97 |
| ciclo máximo (milho 365 d) | 70,5 a 76,3 | caupi com guandu ou crotalária | início do plantio quase irrelevante (chuva do ano inteiro); 6 inícios distintos |
| chuva dos 365 dias (`--chuva-modo anual`), ciclo médio | 70,5 a 76,3 | caupi com crotalária (guandu fora) | como o ciclo máximo: 6 inícios distintos; P(top-3) 0,39 a 0,57 |

**Conclusão: a duração do ciclo muda mais o resultado do que a diferença entre municípios.** Sem decidir o ciclo real (e
se a faixa de chuva do EcoCrop é anual ou do ciclo), a escolha de alternativas não é confiável.

## 5. Limites

- A resolução do clima é a célula POWER (~50 km); 195 pontos, 59 células. Ponto no litoral e ponto no sertão da mesma
  célula são iguais.
- Faixas EcoCrop genéricas e largas; a saturação em nota 1 faz muitas culturas empatarem. Não há ZARC (Etapa B), nem
  balanço hídrico, nem solo.
- Se a faixa de chuva do EcoCrop for anual (não verificado, M3), ciclos curtos ficam injustamente penalizados com
  `chuva_modo="ciclo"`.
- Só anos com ciclo completo (23 de 24).
- N e palha continuam em lacuna para 10 de 15 candidatas (min-max entre as que têm dado, de estudos diferentes).
- `src/culturas/sensibilidade.py` e o doc 06 ainda usam o perfil anual e o desempate alfabético do motor antigo (não foram
  tocados); seus números descrevem aquele motor.
- Suíte completa com `-W error`: ver relatório; `tests/test_rag.py` (2 testes de taxa de acerto do RAG) falham por mudança
  em `src/rag/` feita por outro agente, não por este trabalho.

## 6. Decisões pendentes (do usuário)

1. **Ciclo real** de cada cultura (ou regra: mínimo, médio, máximo, ou ciclo de cultivar do ZARC) e **data de início**.
2. A faixa de chuva do EcoCrop é **anual ou do ciclo**? Verificar na fonte (FAO) antes de confiar em `chuva_modo="ciclo"`.
3. **Nível de risco** (`risco_max`, hoje 0,30) para "viável".
4. **Definição de empate** (hoje: intervalos p10-p90 sobrepostos) e percentis da faixa.
5. **Pesos**: ordem de importância ou faixas com técnicos (`Parametros.ordem_pesos` já aceita a ordem; faixas min-max não foram implementadas).
6. O mínimo (temperatura, chuva) deve **entrar no score** em vez de só escolher a janela?
7. `demanda_hidrica_mm_ciclo` (7 culturas) deve virar filtro ou fica só informativa?
8. Preencher N e palha com fonte antes de usar os 5 critérios no ranking principal.

## 7. Como reproduzir

```
.venv/bin/python -m src.pipeline.gerar_cenarios --cultura-atual milho            # grava data/processed/cenarios/*.json
.venv/bin/python -m src.pipeline.comparar_cenarios                               # tabela da seção 4
.venv/bin/python -m src.pipeline.gerar_cenarios --cultura-atual milho --ciclo-modo min --saida /tmp/x
.venv/bin/python -m pytest tests -W error
```
