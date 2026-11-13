# 08. Pesquisa: lacunas, empates, faixa de incerteza e pesos (para o usuário decidir)

Data da pesquisa: 2026-11-12. Pesquisa só de leitura: nenhum código, dado ou `.env` foi alterado.
Contexto: `docs/06_PESOS_E_CULTURAS.md`, `src/culturas/motor.py`, `src/culturas/sensibilidade.py`.

**Como ler este texto.** Cada afirmação marcada **[LI]** vem de uma página que eu abri (URL ao lado). **[OPINIÃO]** é
minha leitura de como aplicar ao SULCO. O que só apareceu em resumo de busca e eu não abri está na seção 10 e **não** é
usado como base. Onde a fonte não dizia, escrevo "não consta".

---

## 1. Resumo em 10 linhas

1. O motor hoje **renormaliza**: cultura sem N e palha é pontuada só em 3 critérios. Isso é uma escolha com
   justificativa formal **só quando o critério "não se aplica"** (Labreuche e Destercke, IJCAI 2019 [LI]). Aqui N e palha
   **se aplicam, mas não temos o dado**. Então a justificativa não vale. [OPINIÃO]
2. O caminho mais usado na literatura para "dado incompleto + pesos incertos" é o **SMAA** (Stochastic Multicriteria
   Acceptability Analysis): sorteia pesos e valores incertos milhares de vezes e conta **quantas vezes cada cultura
   ficou em cada posição**. Isso dá, de graça, empate honesto, faixa de posição e cobertura.
3. Dá para fazer em ~40 linhas de numpy (o repositório já sorteia pesos Dirichlet em `sensibilidade.py`). Existe pacote
   Python com SMAA (`pysensmcda` 2.0.0, MIT), que eu instalei num ambiente de teste fora do projeto só para conferir a API.
   Mas tem poucas estrelas (2); sugiro usá-lo para **conferir** a conta, não como dependência.
4. Para pesos "sem chute": **nenhuma fonte Embrapa/Emater com pesos prontos para estes 5 critérios foi encontrada**. Os
   pesos têm de ser levantados com técnicos (AHP simples ou só ordem de importância) e, mesmo assim, a incerteza dos
   pesos continua alta: o estudo SMART-Farm (67 especialistas, Delphi) manteve incerteza alta após 2 rodadas e por isso
   propagou os pesos por Monte Carlo [LI]. É o mesmo que recomendo.
5. TOPSIS, PROMETHEE, ELECTRE e Pareto **não resolvem** o problema central (dado faltante) e acrescentam parâmetros novos
   sem fonte (limiares, veto) ou instabilidade (TOPSIS). Valem como apoio, não como substituto.
6. "Conformal" e "ranking bayesiano" não se encaixam agora: não há resultado observado ("a melhor rotação foi X") para
   calibrar. [OPINIÃO]

---

## 2. O problema, em termos simples

| Sintoma | Causa no código (`motor.py`) | O que a literatura sugere |
|---|---|---|
| Cultura com lacuna sai com nota maior | `pontuar()` divide por `pw = soma dos pesos usados`; critérios sem nota saem do cálculo | Não premiar: comparar só critérios comuns, **ou** tratar o valor ausente como desconhecido (faixa), **ou** mostrar cobertura |
| Empate decidido por ordem alfabética | `sorted(..., key=(-score, c))` | Declarar empate; usar índice de aceitabilidade por posição (SMAA) |
| `faixa_incerteza` vazia | Campo fixo `None` | Monte Carlo sobre pesos e valores; reportar intervalo e probabilidade de posição |
| Pesos sem fonte | `PESOS` é "proposta de projeto" (M1) | Levantar com técnicos (AHP/Delphi) e propagar a incerteza residual |

---

## 3. Dado faltante sem premiar a lacuna

### 3.1 Renormalizar (o que o motor faz hoje)
- **Fonte lida:** Labreuche e Destercke, "How to Handle Missing Values in Multi-Criteria Decision Aiding?", IJCAI 2019
  (https://ijcai.org/proceedings/2019/243.md).
- **Fato [LI]:** eles tratam o valor ausente como sinal de que o atributo "não é relevante e deve ser removido do
  modelo". Para o Choquet de 2 aditividade, "os pesos restantes são divididos pela sua soma", o que equivale à
  renormalização. O resultado é um modelo restrito, **não um intervalo de nota**. Eles dizem que a abordagem robusta
  "é pessimista demais".
- **Aplicação [OPINIÃO]:** o motor reproduz esse operador, mas o pressuposto ("não se aplica") é falso para N e palha:
  toda cultura fixa nitrogênio e deixa palha, só não temos o número. Renormalizar é aceitável como **visão
  secundária** ("nota pelos critérios comuns"), não como nota que concorre com a de quem tem 5 critérios.
- **Custo:** zero (já existe). **Risco:** exatamente o viés descrito em `docs/06`.

### 3.2 Comparar só os critérios comuns (já proposto no doc 06)
- **Ideia [OPINIÃO]:** ranking = nota nos critérios que **todas** as candidatas têm (temperatura, chuva, família). N e
  palha aparecem ao lado, só para quem tem dado, como informação. Não é método da literatura; é um desenho de
  apresentação que elimina o prêmio por construção.
- **Custo:** baixo (poucas linhas em `gerar_cenarios`). **Ganho:** acaba o viés. **Risco:** perde-se o efeito de N/palha
  no ranking, justamente o que o projeto quer valorizar (adubação verde). Resolve-se preenchendo as lacunas com fonte.

### 3.3 Lacuna como incerteza (faixa), não como zero nem como ausência
- **Fonte lida:** Wikipedia, "Stochastic multicriteria acceptability analysis"
  (https://en.wikipedia.org/wiki/Stochastic_multicriteria_acceptability_analysis) e resumo de Lahdelma e Salminen
  (2001), SMAA-2, Operations Research 49(3) (https://sal.aalto.fi/publications/abstracts/plah01.html).
- **Fato [LI]:** o SMAA foi feito para dados "incertos, imprecisos ou parcialmente ausentes", modelados por
  distribuições de probabilidade; simula por sorteio. O SMAA-2 considera **todas as posições** (não só o 1º lugar) e
  calcula fatores de confiança.
- **Não consta nas páginas abertas:** uma regra pronta de "como sortear um valor ausente". A escolha abaixo é minha.
- **Como entraria [OPINIÃO]:** nota da lacuna sorteada uniformemente em [0, 1] (o máximo de ignorância; coincide com
  os "limites 0 e 1" que o `sensibilidade.py` já usa). Alternativa mais informativa, mas que exige decisão: sortear dentro da faixa
  observada nas culturas que têm dado.

```
para cada sorteio s em 1..N:
    w = Dirichlet(alfa)                       # pesos (ou restritos por técnicos)
    para cada cultura c:
        para cada critério k:
            nota[c,k] = nota_conhecida          se há dado
                      = Uniforme(0,1)           se é lacuna
        score[c] = soma(w[k]*nota[c,k])         # SEM renormalizar: lacuna entra com incerteza
    ranking[s] = ordena(score)
saída: por cultura, percentis 5 e 95 do score, P(1º), P(top-3), intervalo de posição
```
- **Efeito esperado:** cultura com 2 critérios em lacuna ganha faixa **larga** em vez de nota alta. Quem tem tudo medido
  ganha faixa estreita. Lacuna deixa de ser vantagem e vira "incerteza visível".
- **Custo:** baixo-médio. **Risco:** faixas largas demais podem fazer quase tudo virar "empate técnico"; isso é
  informação honesta, mas precisa ser explicada ao técnico.

### 3.4 Mostrar a cobertura
- **Ideia [OPINIÃO]:** `cobertura = soma(pesos dos critérios com dado) / soma(pesos totais)` ao lado de cada score.
  Já está no doc 06; é o item mais barato e deveria sair primeiro. Com `PESOS` atuais, N+palha = 0,35, então culturas
  sem N/palha têm cobertura 0,65.

---

## 4. Empates e ranking por intervalos

### 4.1 Aceitabilidade por posição (SMAA-2)
- **Fonte lida:** README do `pysensmcda` (https://github.com/jwieckowski/pysensmcda) e resumo SMAA-2 acima.
- **Fato [LI]:** saídas do SMAA: índices de aceitabilidade de posição, vetores de pesos centrais, fatores de
  confiança, aceitabilidade das k melhores posições.
- **Como entraria [OPINIÃO]:** a mesma simulação da seção 3.3 já devolve tudo. "Empate" passa a ser **definido pelos
  dados**: duas culturas estão empatadas se as faixas de posição se sobrepõem muito, em vez de nota idêntica decidida por
  alfabeto. Tela: "1º–3º (54% dos sorteios no top 3)".
- **Cuidado:** é probabilidade **sobre o modelo e seus pesos**, não chance de sucesso agronômico. Isso precisa estar escrito.

### 4.2 Cautela com tabelas de posição
- **Fonte lida:** Goldstein e Spiegelhalter (1996), JRSS A 159(3) (https://econpapers.repec.org/RePEc:bla:jorssa:v:159:y:1996:i:3:p:385-409).
- **Fato [LI]:** o resumo pede cuidado e "sensibilidade" ao interpretar diferenças aparentes e levar em conta a
  incerteza do modelo. A frase sobre "intervalos para posições" não aparece no resumo que abri; vem de resumos de busca (seção 10).

### 4.3 Dominância de Pareto
- **Fonte lida:** https://en.wikipedia.org/wiki/Pareto_front. **Fato [LI]:** A domina B se é pelo menos igual em todos os
  critérios e melhor em um. Não precisa de pesos.
- **Aplicação [OPINIÃO]:** pelos números do doc 06 (7,5 de 15 candidatas tiram 1,0 em temperatura e chuva), a maioria
  empata nesses dois e a diferença cai em "família" (0 ou 1). A frente de não-dominadas tende a ficar grande. Serve para
  **eliminar claramente piores**, não para escolher. Custo baixo; ganho baixo-médio.

### 4.4 PROMETHEE e ELECTRE
- **Fontes lidas:** https://en.wikipedia.org/wiki/Preference_ranking_organization_method_for_enrichment_evaluation e
  https://en.wikipedia.org/wiki/%C3%89LECTRE.
- **Fatos [LI]:** PROMETHEE converte diferenças em graus de preferência com funções (limiares de indiferença/preferência),
  calcula fluxos positivo e negativo; PROMETHEE I dá **ranking parcial com "incomparável"**, PROMETHEE II dá ranking completo
  (Brans e Vincke, Management Science, 1985). ELECTRE (Roy, anos 1960) é família de métodos de **sobreclassificação** com
  coeficientes de importância e **limiares de veto**; a página diz que o método não determina os pesos.
- **Aplicação [OPINIÃO]:** o "incomparável" do PROMETHEE I é uma boa ideia de apresentação para empate. Mas exige limiares
  (indiferença, preferência, veto) que seriam **mais números sem fonte**, o problema que queremos reduzir. Nenhum dos dois
  trata dado faltante por si. Custo médio; ganho baixo agora.

### 4.5 TOPSIS
- **Fonte lida:** Shyur e Shih (2024), Informatica 35(4) (https://informatica.vu.lt/journal/INFORMATICA/article/1356/read).
- **Fato [LI]:** TOPSIS sofre **inversão de ranking** quando se adiciona alternativa, porque a normalização min-max e as
  soluções ideais dependem do conjunto de alternativas; os autores comparam distâncias e normalizações e não eliminam o problema por completo.
- **Aplicação [OPINIÃO]:** o motor já tem essa fragilidade na nota de N/palha (min-max entre as candidatas, ver M4 e doc 06).
  Trocar por TOPSIS aumentaria a dependência do conjunto. **Não recomendo.** Custo médio; ganho negativo.

---

## 5. Propagar incerteza para uma faixa honesta

| Fonte de incerteza | Como sortear | Fonte/justificativa |
|---|---|---|
| Pesos | Dirichlet/uniforme no simplex, ou restrito (ordem de importância, faixas min-max dos técnicos) | Já usado em `sensibilidade.py`; `pysensmcda.sampling` lista Dirichlet, simplex uniforme, `ordered_simplex` e Hit-And-Run para restrições lineares [LI, README] |
| Valores com lacuna | Uniforme em [0,1] (ou faixa observada) | Seção 3.3 [OPINIÃO] |
| Clima | Sortear **um ano** de 2001-2024 em vez de usar a média | [OPINIÃO]: o perfil é média de 24 anos; a variação entre anos é incerteza real, medida, sem inventar número. Hoje é descartada |
| Faixas EcoCrop | Perturbar limites (±x%) | `pysensmcda.sampling` tem incerteza de critério com tolerância absoluta/relativa [LI, README]; o valor de x seria suposição nova |

- **Exemplo real do mesmo tipo:** Schader et al. (2019), Ecological Indicators 106:105503, SMART-Farm
  (https://orgprints.org/id/eprint/36325 e https://agris.fao.org/search/en/records/65dec904b766d82b18fe5559).
  **Fatos [LI]:** pesos vindos de Delphi adaptado (67 especialistas, 21 países) continuaram incertos após 2 rodadas; usaram
  Monte Carlo para levar isso aos resultados de 4 fazendas; algumas diferenças aparentes de até 23% **não** eram
  significativas e algumas de 5% eram. É a prova de que "nota com número exato" engana, e que o procedimento escala.
- **ProMCDA** faz algo parecido (ver seção 7), mas roda incerteza ou nos pesos **ou** nos indicadores, não nos dois ao mesmo tempo [LI].
- **Conformal.** Fonte lida: Angelopoulos e Bates (https://arxiv.org/abs/2107.07511). **Fato [LI]:** envolve qualquer modelo
  em conjuntos/intervalos com garantia sem pressupor distribuição; a condição exata da garantia não consta na página
  aberta. **[OPINIÃO]:** precisa de resultados observados para calibrar. O SULCO não tem "rotação certa" observada, só um
  score construído. **Não aplicável agora.** Poderia valer no módulo de modelos (previsão de NDVI), não no ranking.
- **Ranking bayesiano:** não encontrei/abri fonte própria. A simulação sobre pesos e valores já dá distribuição de
  posições; um modelo bayesiano formal seria custo alto sem ganho claro. **[OPINIÃO]**

**O que a "faixa" significa (para não enganar):** é a variação do score quando pesos, lacunas e clima variam dentro do
que declaramos. **Não** é intervalo de confiança estatístico nem chance de dar certo na roça. Escrever isso no JSON.

Formato sugerido para `faixa_incerteza` [OPINIÃO]:
```
{"score_p05":.., "score_p95":.., "p_top1":.., "p_top3":.., "posicao_p05":.., "posicao_p95":..,
 "cobertura":0.65, "metodo":"MC pesos+lacunas+anos", "n_sorteios":10000, "semente":..,
 "leitura":"sensibilidade do modelo, não probabilidade de sucesso"}
```

---

## 6. Pesos sem chute

| Opção | Ideia | Fonte | Custo | Risco |
|---|---|---|---|---|
| A. Só **ordem** de importância dos 5 critérios (por técnico) | Cada técnico ordena; sorteia-se pesos respeitando as ordens | `pysensmcda.sampling.ordered_simplex` e SMAA-O (ordinal) listados no README [LI]; base: Lahdelma et al. 2003 (citado no README, artigo não aberto) | Muito baixo: 15 min por técnico | Perde intensidade ("muito mais importante") |
| B. **Faixa** min-max por critério | Técnico dá, p.ex., "chuva: entre 20% e 35%" | Restrições lineares/Hit-And-Run no README [LI] | Baixo | Técnicos podem dar faixas incoerentes (soma) |
| C. **AHP** | Comparações par a par, escala 1 a 9, autovetor, razão de consistência | https://en.wikipedia.org/wiki/Analytic_hierarchy_process [LI]; `pymcdm` lista AHP entre os métodos de pesos [LI] | Médio: 10 comparações para 5 critérios, por técnico | Críticas conhecidas (inversão de ranking, escala verbal) [LI] |
| D. **Delphi** | Rodadas anônimas com retorno do resumo do grupo | https://en.wikipedia.org/wiki/Delphi_method [LI] | Alto: 2+ rodadas, painel, tempo | Consenso não é verdade; depende da escolha dos especialistas [LI]; SMART-Farm mostrou incerteza residual alta [LI] |

Fatos úteis sobre AHP em grupo: a página https://bpmsg.com/category/ahp/page/7 [LI] diz que 0,1 para a razão de
consistência é "regra prática", acima disso pode ser aceitável conforme o projeto, e que o consolidado do grupo pode
ficar consistente mesmo com matrizes individuais acima de 10% (agregação por média geométrica ponderada). Não consegui
confirmar na fonte primária de Saaty o limiar nem a tabela de índices aleatórios.

**Sobre Embrapa/Emater [LI]:**
- Não encontrei, nas páginas que abri, pesos AHP publicados para estes cinco critérios. **Não dá para copiar pesos da
  literatura.** Isto não prova que não existam; só que a busca não achou.
- Pereira et al., GEONORDESTE 2014 (Embrapa Informática/Meio Ambiente, https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1002079/1/GeonordesteAselecaodecriterios.pdf):
  proposta de metodologia **coletiva, com especialistas**, para escolher critérios do zoneamento agroecológico, separando
  **critérios determinantes (não ponderáveis)** dos que são ponderados. O texto não menciona AHP. **[OPINIÃO]:** isso casa com o
  SULCO: o filtro de viabilidade EcoCrop é "determinante"; só o que passa dele deve receber peso. É um argumento de
  método para citar com técnicos.
- Delarmelinda et al. (2011), Rev. Bras. Ciência do Solo 35(6) (https://www.redalyc.org/pdf/1802/180221446001.pdf):
  seis especialistas interpretaram a aptidão agrícola de 10 perfis de solo no Acre; a interpretação "não foi
  inteiramente reproduzível", variou com experiência e conhecimento do ambiente. **[OPINIÃO]:** técnicos discordam; por isso
  usar **faixa de pesos**, não um peso médio único.

**Recomendação de pesos [OPINIÃO]:** começar por A+B (ordem e faixa, 3 a 5 técnicos, uma conversa), com AHP só se
quiserem. Delphi completo só se o projeto virar produto institucional. Em qualquer caso, a incerteza residual entra no
Monte Carlo da seção 5.

---

## 7. Pacotes e repositórios (todos abertos e conferidos)

Dados de licença/atividade vêm do PyPI (JSON) e da API do GitHub em 2026-11-12.

| Projeto | Existe? | Licença | Última atividade | Pacote Python | O que tem (conferido) | Observação |
|---|---|---|---|---|---|---|
| **pymcdm** (github.com/kotbaton/pymcdm) | Sim | MIT | release 1.4.0 em 2026-01-31; push 2026-09-06; 25 estrelas | `pip install pymcdm`, Python >= 3.11 | Pasta de métodos inclui TOPSIS, VIKOR, WSM, WPM, PROMETHEE II, COMET e outros; PROMETHEE I em `partial`; pesos incluem AHP, entropia, CRITIC | Documentação não cita SMAA, sensibilidade nem dado faltante [LI]. Não vi ELECTRE |
| **pysensmcda** (github.com/jwieckowski/pysensmcda) | Sim | MIT | 2.0.0 em 2026-08-20; 2 estrelas | `pip install pysensmcda`, Python >= 3.10 | Módulos `sampling`, `smaa`, `eors`, `robustness`; aceitabilidade de posição, pesos centrais, SMAA-2, SMAA-O, incerteza de matriz | **Instalei num ambiente de teste fora do projeto**: `smaa.simulate(método, matriz, tipos, num_samples, seed)` existe e devolve `rank_acceptability`, `rankings`, `weights`. Não rodei com dados do SULCO. Adoção baixa |
| **scikit-criteria** (github.com/quatrope/scikit-criteria) | Sim | BSD-3-Clause | 0.10 em 2026-08-06; push 2026-11-10; 105 estrelas | `scikit-criteria` | Coleção de métodos MCDA (descrição do PyPI) | Não conferi a lista de métodos nem dado faltante |
| **pyDecision** (github.com/Valdecy/pyDecision) | Sim | **Ambígua**: GitHub "NOASSERTION" / PyPI "GNU" | 5.1.8 em 2026-10-12; push 2026-10-15; 375 estrelas | `pip install pyDecision` | AHP, TOPSIS, PROMETHEE I a VI, ELECTRE (várias), VIKOR e outros; SMAA não aparece | Resumo menciona modelo de linguagem e GUI web: dependência pesada. Conferir licença antes de qualquer uso |
| **ProMCDA** (github.com/wetransform-os/ProMCDA) | Sim | EPL-2.0 | PyPI 1.0.8 em 2023-11-28; push GitHub 2026-11-03; 10 estrelas | `ProMCDA` | Monte Carlo sobre indicadores (distribuições) **ou** pesos | Doc inconsistente sobre distribuição dos pesos (normal vs uniforme) [LI]; EPL tem copyleft fraco |
| **objective-weighting** (github.com/energyinpython/objective-weighting) | Sim | MIT | 0.1.8 em 2022-05-29 | `objective-weighting` | Só `VIKOR_SMAA` | Parado desde 2022. Não usar |
| **smaa** (R, CRAN) | Sim | GPL-3 | 0.3-4 em 2026-08-21 | Não é Python | Implementação R de SMAA (Tervonen e Figueira, 2008) | Referência de correção, não para integrar |
| **Fruchtfolge** (github.com/fruchtfolge/client) | Sim | API do GitHub não informa licença | push 2026-06-09; 12 estrelas | Não (Node/Nuxt) | DSS aberto de planejamento de culturas por otimização, Univ. de Bonn | O README que li não menciona incerteza |

**JSMAA / smaa.fi:** tentei abrir; a página retornou erro de conexão. Não afirmo nada sobre ele.

**Minha avaliação [OPINIÃO]:** a conta SMAA é simples e o SULCO já tem a peça principal. Escrever 40 linhas próprias
(testadas contra `pysensmcda` em um teste) evita dependência com 2 estrelas e conflito de licença. Adicionar uma lib
só se o usuário quiser os índices exatos por programação linear.

---

## 8. Sistemas agrícolas parecidos e como mostram incerteza

- **Fruchtfolge** (acima): aberto, planeja culturas; não achei exibição de incerteza no README.
- **Htun et al. (2022), Agriculture 12(7):1027** (https://research-portal.uu.nl/en/publications/developing-visual-assisted-decision-support-systems-across-divers/)
  [LI]: afirmam que DSS agrícolas "raramente fornecem interatividade, visualizam incerteza e são avaliados com usuários";
  construíram 6 sistemas web, avaliados com especialistas do domínio (usabilidade, carga de trabalho, aceitação, confiança)
  e publicaram o código. O resumo não descreve como a incerteza é desenhada. Vale abrir o artigo completo antes de copiar.
- **Hansen et al. (2022), Frontiers in Climate** (https://www.frontiersin.org/articles/10.3389/fclim.2022.908661)
  [LI, primeiras 100 mil de 136 mil caracteres]: previsão sazonal em categorias (abaixo/normal/acima) é mal interpretada por agricultores
  (exemplos em Zimbábue, Namíbia, Austrália). A proposta "Flexible Forecast" mostra a **curva de probabilidade de excedência em
  unidades físicas (mm)**, e o treinamento parte de **frequências naturais** ("em quantos anos choveu mais que X") e de memória
  de safras passadas. Os próprios autores dizem que a evidência é limitada (piloto, amostras pequenas).
- **Aplicação ao SULCO [OPINIÃO]:** (a) trocar "score 88 ± 6" por "em 100 combinações de pesos plausíveis, esta cultura
  ficou entre as 3 primeiras em 54"; (b) usar anos reais ("em 18 dos 24 anos a chuva ficou dentro da faixa ótima"), que o
  projeto já tem; (c) mostrar cobertura e "sem dado de N/palha" em texto, não só cor; (d) validar a tela com técnicos
  antes do agricultor. Nenhuma das fontes provou qual formato funciona melhor para este caso.

---

## 9. Tabela de opções: custo x ganho

Custo: B = baixo (horas), M = médio (dias), A = alto (semanas ou envolve pessoas). Ganho para os 4 problemas (1 lacuna, 2 empate,
3 faixa, 4 pesos).

| # | Opção | Resolve | Custo | Ganho | Risco principal |
|---|---|---|---|---|---|
| 1 | Mostrar **cobertura** em cada score | 1 | B | Médio | Só informa, não corrige a ordem |
| 2 | Ranquear por **critérios comuns**; N/palha ao lado | 1 | B | Alto | Perde N/palha no ranking até haver dado |
| 3 | **Empate declarado** (sem alfabeto) por regra simples (faixa de posição sobreposta) | 2 | B | Alto | Define-se tolerância; melhor sair da simulação (#4) |
| 4 | **Monte Carlo (SMAA-2)** em pesos + lacuna [0,1] sem renormalizar; reportar P(top-3), faixa de score e de posição | 1, 2, 3 | M | **Muito alto** | Faixas largas; explicar que não é probabilidade de sucesso |
| 5 | Somar **ano do clima** sorteado (2001-2024) ao Monte Carlo | 3 | M | Médio-alto | Janela do ciclo ainda é suposição aberta |
| 6 | Pesos por **ordem/faixa** com 3 a 5 técnicos (A+B da seção 6) | 4 | B-M (depende de agendar) | Alto | Técnicos discordam; resultado vira faixa (é o desejado) |
| 7 | **AHP** com técnicos | 4 | M | Médio | Mais trabalho que A+B, mesma incerteza residual |
| 8 | **Delphi** completo | 4 | A | Médio | Tempo; consenso não é verdade |
| 9 | Preencher lacunas de N/palha com **fonte** (já pergunta 7 do doc 06) | 1 | M-A | Alto | Dados de poucos estudos, fora do semiárido |
| 10 | Pareto (eliminar dominadas) | 2 | B | Baixo-médio | Frente grande demais |
| 11 | PROMETHEE I (incomparável) / ELECTRE | 2 | M | Baixo | Limiares novos sem fonte |
| 12 | Trocar para TOPSIS | nenhum | M | Negativo | Inversão de ranking |
| 13 | Conformal / ranking bayesiano formal | 3 | A | Baixo agora | Sem dado observado para calibrar |

---

## 10. Recomendação (opinião minha, a decidir por você)

**Fase 1 (barata, faz sentido já):** itens 1, 2, 3 e 4 juntos. O 4 é o coração: um único Monte Carlo (10 mil sorteios,
semente fixa, tudo gravado no JSON) preenche `faixa_incerteza`, define empate pelos dados e impede o prêmio da lacuna.
Reimplementar em numpy e conferir o resultado com `pysensmcda` num teste.

**Fase 2:** item 6 (ordem/faixa de pesos com técnicos) e 5 (anos do clima) dentro do mesmo Monte Carlo.

**Fase 3:** item 9 (fonte para N/palha) reduz a faixa de quem hoje é "largo"; AHP/Delphi só se houver demanda institucional.

**Não fazer agora:** itens 11, 12, 13.

**Teste de aceitação que eu proporia:** (i) cultura com lacuna não pode ter score central maior que o equivalente com
dados iguais nos critérios comuns; (ii) trocar a ordem alfabética dos nomes não muda o resultado; (iii) `faixa_incerteza`
nunca vazia; (iv) mesma semente, mesmo resultado.

---

## 11. Perguntas para você

1. A lacuna deve virar **incerteza em [0,1]** (mais conservador) ou **faixa observada nas culturas com dado** (mais informativo, mas pressupõe que o que falta se parece com o que temos)?
2. Para o ranking principal: **só critérios comuns** (N/palha ao lado) ou **5 critérios com faixa larga** para quem tem lacuna? Ou os dois lado a lado?
3. Quem seriam os técnicos (Embrapa, Emater-CE, universidade?), quantos, e há tempo para uma conversa de 30 a 60 min? Prefere **ordem/faixa** ou **AHP**?
4. Como chamar "empate": regra pela simulação (ex.: faixas de posição que se sobrepõem) ou limite em pontos que você escolha?
5. A faixa de clima deve usar a **variação entre anos 2001-2024**? Isso depende de decidir a janela do ciclo (pergunta 3 do doc 06).
6. A tela do agricultor mostra "ficou entre as 3 primeiras em X de 100 simulações" ou só o técnico vê isso?
7. Aceita **código próprio** para o Monte Carlo (sugerido) em vez de dependência externa? Se preferir lib, `pysensmcda` (MIT) é a única que conferi com SMAA geral em Python, mas tem pouca adoção.
8. Lacunas de N/palha: quer priorizar a busca de fonte (item 9) antes de ligar os pesos?

---

## 12. O que eu não consegui abrir ou só vi em resumo de busca (não usado como base)

- JSMAA / smaa.fi: erro de conexão. Repositório que tentei no GitHub: 404.
- Springer (Schader também no Springer, SMAA-AD), Frontiers (Delphi de sistema alimentar), DOAJ (403), Bristol (league tables):
  não abriram.
- Embrapa Alice `Pereiraareasprioritarias2019.pdf`: era só uma figura, sem texto.
- Em resumos de busca, sem abrir: Topal et al. 2024 (Mathematics, imputação causa viés), Mazurek e Strzałka 2022 (PLOS ONE,
  pesos centrais), `mcdabench` (R), CSIRO Value-Ag, Pet-Edwards et al. 1996 (consistência de AHP em grupo), tabelas de
  índice aleatório do AHP, estudo SMAA-AD (valores uniformes quando há ignorância total). Podem valer leitura futura.
- `scikit-criteria`: não conferi a lista de métodos.
- Não existe aqui validação com dados do SULCO: a proposta de Monte Carlo é desenho, não resultado medido.
