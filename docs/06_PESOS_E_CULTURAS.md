# 06. Pesos do score e lista de culturas (para o usuário decidir)

> **HISTÓRICO (revisado em 2026-11-14).** Este texto descreve o motor ANTIGO (perfil anual de clima, desempate alfabético, 10 pontos, janelas de ciclo sorteadas por mim). Foi superado: o motor atual usa ciclo de plantio, ranking com incerteza e empate declarado em vez de ordem alfabética; ver `docs/10_MOTOR_CICLO_E_INCERTEZA.md` (e `docs/22_PESQUISA_ROTACAO.md` para a rotação de 3 safras). Os números abaixo foram gerados por `python -m src.culturas.sensibilidade` com aquele motor e NÃO descrevem o app de hoje; `docs/15_PENDENCIAS.md` C4 registra que `sensibilidade.py` ainda reflete o motor antigo (e que no ciclo só entram 23 anos de clima, porque a janela de 2024 passa do fim da série). As perguntas ao usuário (seção final) seguem como registro de decisões, não como pendências abertas: confira `docs/15` e `docs/03`. Não use este arquivo para afirmar nada sobre a recomendação atual.

Este texto **não escolhe pesos**. Mostra o que muda e o que não muda quando os pesos mudam, para você decidir.
Todos os números vêm de `python -m src.culturas.sensibilidade` (resultado completo em
`data/processed/sensibilidade_pesos.json`; testes em `tests/test_sensibilidade.py`).

## Como foi o teste
- 10 pontos do Ceará sorteados com semente fixa: acarau, ararenda, baturite, bela_cruz, eusebio, icapui, maracanau,
  pereiro, tejucuoca e vicosa_do_ceara.
- Cultura atual: milho. Candidatas: as outras 15 da tabela que passam no filtro de viabilidade.
- 1000 conjuntos de pesos sorteados (Dirichlet, todos somam 1) e uma grade de 1001 combinações (passos de 0,1). O motor
  não foi alterado. Os pesos propostos (0,25 / 0,25 / 0,20 / 0,15 / 0,15) são chamados de "base".
- **Suposição minha, sem fonte**: o motor pede temperatura e chuva "do ciclo". Montei isso como média de 2001-2024 de uma
  janela de dias. Usei 3 janelas para ver se isso importa: 120 dias desde 1º/fev, 150 dias desde 1º/jan e 90 dias
  desde 1º/mar. Não sei qual janela representa o ciclo real; é uma pergunta para você (abaixo).

## O que é robusto
- **Crotalaria juncea está no top 3 em 100% dos pesos sorteados**, nas 3 janelas, nos 10 pontos.
- **7 das 15 candidatas ficam fora do top 3 em praticamente todos os pesos**: feijao_de_porco, guandu, mamona, mandioca, mucuna
  e palma_forrageira (0,0% nas 3 janelas) e girassol (0,0% em 120 d e 150 d; 0,3% em 90 d). Milheto, algodao, sorgo e feijao_comum
  entram pouco ou só em uma janela (ex.: sorgo 9,2% e milheto 1,9% só em 90 d; algodao 61,1% em 150 d).
- Com os pesos base, o 1º lugar é o mesmo em 99,5% (janela 120 d), 98,9% (150 d) e 96,1% (90 d) dos sorteios de pesos.
  Cuidado: ver o próximo bloco, esse número é inflado por empates.

## O que depende dos pesos (ou do desempate)
- **O corte do top 3 é decidido por empate.** Em 70,4% (120 d), 100% (150 d) e 37,8% (90 d) dos sorteios, a 3ª e a 4ª
  colocadas têm a mesma nota. O motor desempata por **ordem alfabética** (não é critério agronômico). Se eu inverto o
  desempate, o top 3 muda nesses mesmos percentuais. Ou seja, quem fica em 3º muitas vezes é decidido pelo nome.
- A razão: o filtro e a nota de clima quase não separam. Dos 15 candidatos, 14 ou 15 passam na viabilidade
  (8 a 15 na janela de 90 dias), e, por ponto, de 0 a 10 delas tiram nota 1,0 em temperatura **e** chuva (média por ponto: 7,5 em 120 d, 9,0 em 150 d, 4,5 em 90 d).
  Com notas iguais, só sobram os outros critérios (e as lacunas, ver abaixo).
- Quais aparecem no top 3 (amendoim, feijao_caupi, algodao, gergelim) **trocam conforme a janela do ciclo**:
  na janela 120 d: amendoim 70,2%, feijao_caupi 69,6%, algodao 30,4%, gergelim 29,6%; na 150 d: amendoim 100%, algodao 61,1%,
  feijao_caupi 38,9%, gergelim 0%; na 90 d: feijao_caupi 97,6%, gergelim 60,3%, amendoim 33,6%.
  Isto depende mais da janela do ciclo do que dos pesos.
- Correlação média de ranking entre dois conjuntos de pesos sorteados: 0,879 (120 d), 0,922 (150 d), 0,779 (90 d). É
  alta, mas o ranking completo inclui as culturas que nunca chegam ao topo; o que importa é o top 3, descrito acima.
- Se os pesos são sorteados nas pontas (grade com pesos extremos), o 1º lugar igual ao do peso base cai para 47% a 99%
  conforme o ponto (por exemplo 71,4% em acarau, 120 d).

## Culturas com lacunas (scores com número diferente de critérios)
Hoje só 5 das 15 candidatas têm nota nos 5 critérios (milheto, girassol, guandu, crotalaria_juncea, mucuna). As outras 10 têm 3
(temperatura, chuva e família), porque N na biomassa e palha estão em lacuna na tabela.

- O motor renormaliza: cultura sem N/palha é avaliada só nos outros critérios. Resultado: **ter dado, aqui, acaba prejudicando** (nota 0 a 1 em N e palha contra nenhuma nota nas outras).
  Com os pesos base, a nota média das culturas com 5 critérios é 74,7 (120 d), 76,4 (150 d) e 70,7 (90 d); das com 3 critérios é
  88,5, 92,7 e 81,2. A explicação provável é que as com 5 critérios recebem também notas min-max (entre só 5 culturas) em N e palha, que puxam a média para baixo.
- Mesmo assim, o top 3 não muda quando só se usam os critérios comuns a todas (temperatura, chuva, família): o top 1
  é o mesmo em 100% (120 d e 150 d) e 93,5% (90 d) dos sorteios; o conjunto do top 3 igual em 100%, 100% e 92,4%. Em média só 33% das vagas do top 3
  ficam com culturas de 5 critérios.
- Com lacuna contada como 0 ou como 1 (limites, não uma nota), a melhor cultura pelo motor tem o intervalo de nota sobreposto ao de
  em média 8,8 (120 d), 11,6 (150 d) e 4,4 (90 d) outras candidatas. Ou seja, com as lacunas atuais, o ranking não se
  separa com segurança.
- A nota de N/palha (min-max) depende de quais culturas são candidatas. Nestes 10 pontos o conjunto de culturas com N foi quase o
  mesmo, então as notas não variaram, mas variariam se uma delas fosse inviável (ex.: nota de mucuna 0,23 e guandu 0,52 mudariam).

### Forma justa de comparar (proposta, sem inventar nota)
1. **Ranquear pelos critérios que todas as candidatas têm** (hoje: temperatura, chuva, família). É justo e dá o mesmo
   top 3 do motor atual em 92% a 100% dos sorteios.
2. Mostrar N e palha **ao lado**, só para quem tem dado, como informação, e marcar "N/palha: sem dado" nas demais.
3. Mostrar a **cobertura** (peso dos critérios com nota / peso total) em cada score, para que 88 com 3 critérios não seja lido
   como igual a 88 com 5.
4. Para o empate, declarar na tela "empate" em vez de ordem alfabética, ou usar um desempate que você escolher.
Isto é recomendação de método, não de peso. Mudar o motor depende da sua decisão.

## Perguntas objetivas para você
1. Os pesos 0,25 / 0,25 / 0,20 / 0,15 / 0,15 ficam, ou você quer outros? Se os pesos mudarem, o top 3 só muda onde há empate/pouca diferença (acima).
2. Vale o ranking só pelos critérios comuns, com N e palha como informação extra (itens 1 a 4 acima)?
3. Qual é o "ciclo" para a comparação com as faixas de temperatura e chuva (data de início e duração)? A janela muda quais culturas aparecem.
4. Como desempatar quando duas culturas têm a mesma nota: alguma regra sua, ou mostrar as duas como empatadas?
5. Faltam culturas do semiárido na lista de 16 (são 1 atual + 15 candidatas)? Perguntas, sem valor nenhum adicionado: melancia, abóbora/jerimum,
   quiabo, maxixe, capins forrageiros, leucena, gliricídia, sisal, cebola ou outras que você usa?
6. A lista deve incluir culturas de cobertura/adubação verde (crotalaria, mucuna, feijão-de-porco) junto com culturas comerciais, ou separar em dois rankings?
   Hoje elas competem na mesma lista, e são as únicas com dado de N e palha.
7. Quer que a lacuna de N e palha seja preenchida com busca de fonte antes de decidir os pesos? Com mais culturas com 5 critérios, os pesos de N e palha passam a pesar de verdade.

## Limites
- 10 pontos, uma cultura atual (milho). Pode rodar com `--atual` outra cultura.
- Pesos sorteados são uniformes sobre as combinações; não representam preferências reais de ninguém.
- A janela do ciclo é suposição minha (ver acima). A tabela de culturas pode mudar (outro agente edita), então os números devem ser reproduzidos com o comando acima.
