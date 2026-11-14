# Resultado dos testes das melhorias com dados da FAO

Data: 2026-11-14. Motor de produção **não alterado**; único acréscimo: `Parametros.ciclo_override` (padrão `()`), usado em `ciclo.notas_ciclo`; teste `tests/test_fao_staging.py::test_ciclo_override_padrao_nao_muda_resultado` mostra que o padrão não muda o resultado. Dados: `data/culturas/fao_staging.csv` (269 linhas: 264 com dado e fonte, 5 lacunas explícitas). Scripts: `exp1_ciclo.py`, `exp2_etc.py`, `exp3_lacunas.py`, `exp4_matriz.py` (saídas em `saida/`). Pesquisa e URLs: `docs/25_PESQUISA_FAO.md`.

Amostra: 15 municípios do CE, uma célula POWER cada, escolhidos por quantis da **chuva anual** (não por resultado): salitre, quiterianópolis, arneiroz, choró, acopiara, altaneira, canindé, barbalha, jaguaribe, aurora, caririaçu, aracoiaba, miraíma, acarape, carnaubal (655 a 1134 mm/ano). Culturas atuais: milho e feijão-caupi. Motor com os padrões (10 000 sorteios, semente fixa, risco 0,30, clima 2001-2024).

## Como o "ciclo FAO" foi definido (regra fixada antes de rodar)

Duração = **soma dos 4 estágios** da Tabela 11 do FAO-56 (cap. 6), linha da FAO cuja soma é a **mediana inferior** das linhas da cultura; variantes `min` e `max` pegam a menor e a maior linha. Mandioca: só o "ano 1" (210 d). A soma difere do "Total" impresso em 3 culturas (erro da própria tabela da FAO: sorgo 125 x 130, caupi 100 x 110, gergelim 110 x 100). Sem linha FAO (guandu, palma, crotalária, feijão-de-porco, mucuna) o ciclo EcoCrop continua em todas as variantes.

| cultura | EcoCrop (mín-máx / ponto médio usado hoje) | FAO-56 Tabela 11 (soma dos estágios; nº de linhas) | ciclo FAO usado (mediana) |
|---|---|---|---|
| milho | 65-365 / 215 | 125-180 (6) | 140 |
| feijão-caupi | 30-240 / 135 | 100 (1; Mediterrâneo) | 100 |
| feijão comum | 50-270 / 160 | 95-110 (3) | 100 |
| sorgo | 90-300 / 195 | 125-130 (2) | 125 |
| milheto | 60-120 / 90 | 105-140 (2) | 105 |
| mandioca | 180-365 / 272 | 210-360 (2; ano 1 e ano 2) | 210 |
| algodão | 150-200 / 175 | 180-225 (4) | 195 |
| amendoim | 90-150 / 120 | 130-140 (3) | 140 |
| girassol | 70-200 / 135 | 130 (1) | 130 |
| mamona | 140-210 / 175 | 135-180 (2) | 135 |
| gergelim | 40-180 / 110 | 110 (1; China) | 110 |

Divergência EcoCrop x FAO: o ponto médio do EcoCrop é **bem maior** que o ciclo FAO em milho (215 x 140, razão 1,48), sorgo (1,53), feijão comum (1,60) e caupi (1,35); **menor** em milheto (0,73), algodão (0,90) e amendoim (0,86). Os ciclos FAO ficam dentro do intervalo EcoCrop em 8 de 11 culturas (fora: algodão, mamona, milheto). As linhas da FAO são de regiões diferentes do Ceará (Califórnia, Mediterrâneo, Nigéria, Índia, "clima árido") e **nenhuma é do semiárido brasileiro**.

## Teste 1: ciclo EcoCrop (atual) x ciclo FAO-56 (n = 15 municípios, motor completo)

Cultura atual **milho** (215 d -> 140 d):

| métrica | EcoCrop médio | FAO mediana | FAO mín (125 d) | FAO máx (180 d) |
|---|---|---|---|---|
| adequação média do milho (0-1) | 0,853 | 0,751 | 0,700 | 0,822 |
| desvio-padrão da adequação entre municípios | 0,097 | 0,135 | 0,143 | 0,112 |
| melhor época: inícios distintos (grade de 10 d) | 7 | 7 | 5 | 7 |
| mudou a melhor época (municípios de 15) | - | 13 | 15 | 8 |
| deslocamento médio da melhor época | - | 31 dias | 38 dias | 11 dias |
| culturas viáveis por município (média; mín-máx) | 15,07 (13-16) | 15,27 (14-16) | 15,00 (12-16) | 15,27 (14-16) |
| municípios em que muda o conjunto de viáveis | - | 3 (amendoim passa a viável em salitre, arneiroz, choró) | 3 | 3 |
| P(top-3) médio das 2 alternativas | 0,459 | 0,476 | 0,490 | 0,455 |
| taxa de empate técnico (alternativas com empate) | 100% | 100% | 100% | 100% |
| nº médio de culturas empatadas com cada alternativa | 11,9 | 12,3 | 12,3 | 12,3 |
| municípios em que muda o conjunto das 2 alternativas | - | 10 | 10 | 10 |
| conjuntos de alternativas distintos entre os 15 municípios | 3 | 1 | 2 | 2 |
| alternativas escolhidas (frequência nos 15) | guandu 15, caupi 9, crotalária 5, feijão comum 1 | guandu 15, crotalária 15 | guandu 15, crotalária 14, gergelim 1 | guandu 15, crotalária 14, mamona 1 |

Cultura atual **feijão-caupi** (135 d -> 100 d; a FAO tem uma só linha, então mediana = mín = máx): adequação 0,869 -> 0,741 (desvio entre municípios 0,098 -> 0,134); melhor época muda em 15/15 (18 dias em média); conjunto de viáveis muda em 3/15; alternativas mudam em 11/15 (EcoCrop: milho 12, milheto 8, gergelim 5, sorgo 3; FAO: milheto 14, gergelim 7, sorgo 6, milho 2, palma 1); P(top-3) 0,517 -> 0,543; empate técnico 100% nos dois, 11,1 empatadas em média (antes 11,1).

**Leitura (sem enfeitar):**
- Trocar o ciclo **mexe nas decisões**: a melhor época de plantio muda em 13 de 15 municípios (milho) e em 15 de 15 (caupi); o conjunto de alternativas muda em 10 a 11 de 15. É mudança de qualidade do dado (ciclo de uma tabela da FAO, com região declarada, no lugar de um ponto médio de intervalo de 65 a 365 dias), mas **não é validada para o semiárido**: não prova que a nova época seja a certa.
- **Empate técnico não muda: 100% antes e depois.** O ciclo FAO não separa as alternativas; guandu e crotalária seguem sendo as escolhidas no milho (as "alternativas" dependem da ordem de empate/sorteio, ver doc 10).
- A **queda de adequação (-0,10 a -0,13)** é um **efeito colateral da faixa de chuva**: com ciclo curto a chuva acumulada no ciclo cai e fica abaixo da faixa EcoCrop. A própria descrição do EcoCrop na FAO fala em "annual precipitation" (`gaez.fao.org/pages/ecocrop`, texto literal). Prova pelo teste: com `chuva_modo="anual"` o ciclo quase não importa para o milho (adequação 0,909 nos dois ciclos; melhor época idêntica em 15/15; P(top-3) 0,435 x 0,429; empatadas 11,5 x 11,5; conjunto de alternativas muda em 3/15) e, para o caupi, muda a época em 8/15 e a adequação em -0,0005. **Logo: o ciclo FAO só faz sentido junto da decisão sobre a faixa de chuva.**
- Diferenciação entre municípios: com o ciclo mediano o desvio da adequação entre municípios sobe (0,097 -> 0,135), mas isso é a queda de adequação nos municípios mais secos, não separação de alternativas; os conjuntos de alternativas ficam **mais** parecidos (3 -> 1 conjunto distinto no milho).

Arquivos: `saida/exp1_ciclo_linhas.csv` (uma linha por município x variante x cultura atual), `saida/exp1_resumo.json`.

## Teste 2: ETc = Kc x ETo e critério "atendimento hídrico"

Método: Kc da Tabela 12 do FAO-56 (faixas viram ponto médio), estágios da linha mediana da Tabela 11, curva de Kc por estágio (constante, linear, constante, linear), ETo diária de Hargreaves (`balanco_hidrico.py`), no início de plantio escolhido pelo motor com o ciclo FAO, média de 2001-2024. 11 culturas com Kc (as outras 5 não têm Kc na FAO-56: guandu, palma, crotalária, feijão-de-porco, mucuna).

Média dos 15 municípios:

| cultura | ciclo (d) | ETc (mm) | chuva no ciclo (mm) | chuva/ETc (mediana) | atendimento = min(1, chuva/ETc) | nota de chuva do motor | faixa FAO-24 Tab. 20 (mm) |
|---|---|---|---|---|---|---|---|
| algodão | 195 | 771 | 755 | 0,98 | 0,84 | 0,69 | 550-950 |
| amendoim | 140 | 497 | 667 | 1,36 | 0,93 | 0,75 | (sem linha) |
| feijão-caupi | 100 | 347 | 537 | 1,55 | 0,96 | 0,75 | (sem linha) |
| feijão comum | 100 | 348 | 536 | 1,52 | 0,96 | 0,74 | 250-500 |
| gergelim | 110 | 390 | 576 | 1,49 | 0,95 | 0,80 | classe "oil seeds" 300-600 |
| girassol | 130 | 455 | 637 | 1,41 | 0,94 | 0,78 | classe "oil seeds" 300-600 |
| mamona | 135 | 524 | 651 | 1,26 | 0,91 | 0,73 | classe "oil seeds" 300-600 |
| mandioca | 210 | 617 | 784 | 1,28 | 0,92 | 0,52 | (sem linha) |
| milheto | 105 | 351 | 548 | 1,53 | 0,96 | 0,92 | (sem linha) |
| milho | 140 | 526 | 660 | 1,26 | 0,92 | 0,75 | 400-750 |
| sorgo | 125 | 423 | 505 | 1,17 | 0,91 | 0,67 | 300-650 |

- **Coerência (conferência, não validação):** a ETc calculada fica dentro das faixas sazonais da FAO-24 onde há linha (milho 429-580 entre municípios; sorgo 356-495; algodão 691-839; feijão comum 292-377). Isto confere a ordem de grandeza do cálculo, não prova que sirva ao semiárido.
- **Separa as alternativas? Não.** (i) Pares de culturas com intervalo p10-p90 entre anos **sem sobreposição**: atendimento hídrico **0,0%**, nota de chuva do motor 0,0%, nota de temperatura 10,9% (média dos 15 municípios, 55 pares por município). (ii) Monte Carlo (SMAA) no universo das 11 culturas, sem e com o critério novo entre os critérios principais: empate técnico em **100%** das candidatas nos dois casos; nº médio de empatadas por candidata 8,29 -> 8,44 (caupi atual) e 8,59 -> 8,63 (milho atual); desvio do P(top-3) entre candidatas 0,204 -> 0,202 e 0,192 -> 0,189. O conjunto top-3 muda em 10 de 30 casos (município x cultura atual): **mexe na decisão sem separar**.
- Por quê: o atendimento satura perto de 1 (média 0,91-0,96 em 10 das 11 culturas); só o algodão se destaca (0,84), porque a ETc de ciclo longo é alta. Num ciclo com 505-784 mm de chuva a razão passa de 1 na mediana de quase todas as culturas; o que separa é o algodão x o resto, não as candidatas a rotação.
- **Limitações:** Kc de clima sub-úmido (UR mín ~45%, vento ~2 m/s) não ajustado ao semiárido (a FAO manda ajustar Kc mid; não feito); estágios de outras regiões e sem observação local; um Kc único por cultura (sem cultivar, sem densidade); ETo de Hargreaves (só Tmax/Tmin); razão chuva/ETc **não é balanço hídrico** (sem solo, sem escoamento, sem chuva efetiva, sem armazenamento); chuva de célula de ~50 km; mandioca só ano 1.
- **Uso que se sustenta:** substituir o campo informativo `chuva_sobre_demanda_hidrica` (que usa 7 valores de Brouwer e Heibloem, limites inferiores de faixa) por ETc calculada para 11 culturas, **como informação**, não como critério do ranking.

Arquivos: `saida/exp2_etc_sazonal.csv`, `saida/exp2_separacao_pares.csv`, `saida/exp2_smaa_com_sem_agua.csv`.

## Teste 3: quantas das 34 lacunas a FAO fecha

| atributo | lacunas | fechadas pela FAO | quais | qualidade do que fecha |
|---|---|---|---|---|
| demanda hídrica (mm/ciclo) | 9 | 2 por valor literal; +4 por cálculo | literal: mamona e gergelim (FAO-24 Tab. 20, **classe "oil seeds" 300-600**, não a cultura); por cálculo (ETc do teste 2): caupi, mandioca, mamona, gergelim | classe genérica; cálculo depende do Kc de outra região e da nossa ETo |
| N fixado (kg/ha) | 13 | 3 | feijão-caupi 9-125, feijão comum 3-57, guandu 4-200 (FAO "Soils and pulses", Tab. 8) | faixas muito largas; fecha a lacuna no papel e **não discrimina** |
| palha (kg/ha de MS) | 6 | **0** | - | a FAO não traz resíduo de colheita de caupi, feijão comum, mandioca, algodão, mamona, gergelim nas publicações abertas |
| N na parte aérea (kg/ha) | 6 | **0** | - | idem |
| **total** | **34** | **5 por valor literal (2 de classe, 3 de faixa larga)** | | **29 seguem abertas** |

Ficam abertas: demanda hídrica de guandu, palma, crotalária, feijão-de-porco, mucuna (sem Kc nem ETc na FAO-56; 5), mais as de N fixado (10: milho, sorgo, milheto, mandioca, algodão, girassol, mamona, gergelim, palma — não leguminosas, onde o certo biológico é "não fixa", mas isso é regra nossa, não dado de fonte — e feijão-de-porco, leguminosa sem número FAO), e as 12 de palha e N aéreo.

**Melhora a qualidade do dado já existente? Sim, como alerta:** a FAO (ICM 12, Tabela 5, Paraguai, consórcio com milho, ~7 meses) dá **mais** biomassa e N que a tabela atual: guandu 9153 x 6130 kg/ha de MS e 240 x 142,9 kg/ha de N; feijão-de-porco 7703 x 4670 e 246 x 153,8; mucuna 7500 x 4017 e 192 x 109,5. Mesma espécie, estudos distintos, diferença de 50% a 90% na MS: o "N e palha" do critério tem **incerteza maior que a diferença entre as culturas**. Para o amendoim, N fixado atual 40,9 kg/ha contra FAO 27-206 (Tab. 8) e 110-150 (Bulletin 16): o valor atual está no limite inferior das duas.

## Teste 4: matriz "anterior -> seguinte"

Só entram pares em que o texto da FAO traz a sequência entre duas das 16 culturas; cada trecho foi conferido literalmente numa página do documento baixado (`saida/exp4_matriz_candidata_fao.csv`, 0 falhas de conferência). Não altera `matriz_rotacao.csv`.

- Cobertura: 34/240 (14,2%) -> **55/240 (22,9%)** (+21 pares novos; mais 5 pares já presentes ganham uma evidência extra).
- Qualidade dos 21 novos: **4** com medida de campo (Paraguai, Chore, ICM 12 Tabela 6: algodão semeado sobre guandu, feijão-de-porco, crotalária, mucuna teve infestação de plantas daninhas relativa de 19%, 14%, 7% e 11% da testemunha; critério "plantas daninhas", não produtividade); **14** são rotações **propostas** pelos autores (ICM 12 Tabelas 15 e 18), sem efeito medido (grau neutro); **4** vêm de uma frase geral de revisão (Soils Bulletin 72: "Millet and sorghum yields are generally higher when grown the year following a grain legume" -> feijão comum e amendoim antes de milheto e sorgo; a mesma página diz que o benefício de N do amendoim é pequeno, então amendoim -> milheto/sorgo fica neutro); o 21º par (mucuna -> algodão) tem também +~950 kg/ha de algodão após milho/mucuna em plantio direto (média de 3 anos; confundido com o plantio direto).
- Nenhuma evidência é do semiárido; toda a base nova é **adubo verde e consórcio no Paraguai**, não lavoura de grão no sertão. Pares com adubos verdes (mucuna, crotalária, guandu, feijão-de-porco) são 12 dos 21.
- Não achei na FAO nenhum par para: sorgo/milheto/algodão -> caupi, milho -> feijão comum, amendoim/girassol/mamona como "seguinte", palma. As Tabelas de "Soils and pulses" (Tabela 17, equivalente em N de cereal após pulse: grão-de-bico, lentilha, feijão-mungo, feijão-caupi -> arroz/trigo) **não têm nenhum par das 16 culturas**.
- Não aumenta o poder de separar alternativas **no semiárido**: cobertura sobe, mas as 5 culturas candidatas mais comuns (caupi, milheto, sorgo, gergelim, guandu) já eram as com mais pares.

## O que "melhora o dado" x o que "só muda o número" (item 5)

| melhoria | mexe nas decisões? | sustentada por fonte? | classificação |
|---|---|---|---|
| ciclo FAO-56 no lugar do ponto médio EcoCrop | época muda em 13-15 de 15 municípios; alternativas em 10-11 de 15; empate 100% inalterado | sim, linha da Tabela 11 com região (nenhuma do semiárido brasileiro) | **melhora a qualidade do dado** (ciclo documentado, não ponto médio de 65-365 d), **mas** só depois de decidir a faixa de chuva (anual x ciclo); sem isso a adequação cai 0,10-0,13 por artefato |
| ETc como informação (substitui chuva/demanda de 7 valores) | não entra no ranking | sim (Kc FAO-56, ETo do projeto) | melhora a informação mostrada; ordem de grandeza conferida contra a FAO-24 |
| critério "atendimento hídrico" no ranking | muda o top-3 em 10 de 30 casos | Kc de outra região | **só muda o número**: não separa (0 pares, empate 100%) |
| N fixado de caupi, feijão comum e guandu (faixas) | não testado no motor (critério fora do ranking principal) | sim (Tab. 8) | fecha lacuna no papel; faixa de 4 a 200 não discrimina |
| N/palha de adubos verdes (ICM 12) | não aplicado | sim | revela que os valores atuais podem estar 35-90% abaixo; **melhora a consciência da incerteza**, ainda não o dado |
| 21 pares novos na matriz | não testado no motor | sim, trecho conferido | +8,7 pontos de cobertura, mas só 4 pares com medida de campo e fora do semiárido |

## Resultados negativos (como estão)

- A FAO **não** tem Kc, estágios, raiz nem Ky para guandu, mucuna, feijão-de-porco, crotalária juncea e palma forrageira.
- A FAO **não** tem calendário agrícola do Brasil (Crop Calendar: 58 países, Brasil ausente).
- A base **EcoCrop oficial** não abriu (exige login Google; `ecocrop.fao.org` devolve 503; Wayback offline): não dá para dizer se o espelho OpenCLIM diverge do oficial.
- O critério de água **não separa** alternativas; o ciclo FAO **não reduz** o empate técnico.
- Não há resíduo/palha nem N da parte aérea de caupi, feijão comum, mandioca, algodão, mamona e gergelim nas publicações FAO abertas.

## Reprodução

```
.venv/bin/python experimentos/fao_melhorias/construir_staging.py        # gera data/culturas/fao_staging.csv
.venv/bin/python -m src.culturas.fao_staging                            # valida (0 erros)
.venv/bin/python -m pytest tests/test_fao_staging.py -W error
.venv/bin/python -m experimentos.fao_melhorias.exp1_ciclo               # ~25 s
.venv/bin/python -m experimentos.fao_melhorias.exp2_etc
.venv/bin/python -m experimentos.fao_melhorias.exp3_lacunas
.venv/bin/python -m experimentos.fao_melhorias.exp4_matriz              # baixa 2 documentos FAO para .cache/ (git-ignore recomendado)
```
