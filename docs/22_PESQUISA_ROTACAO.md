# 22. Pesquisa: como melhorar a qualidade e a confiabilidade da rotação (2026-11-13)

Pesquisa só de leitura (nenhum código foi alterado). Regra usada: **só entra aqui o que abri nesta sessão**. Cada fonte tem um rótulo:
**[LIDA]** = abri a página/PDF e li o conteúdo citado; **[RESUMO]** = só li o resumo ou um índice (não o texto completo); **[BUSCA]** = só vi o trecho que o buscador devolveu, sem abrir a página (não confiar em número); **[OPINIÃO]** = julgamento meu, não fato de fonte.
Cálculo de "custo" (pequeno/médio/grande) é estimativa minha.

## Resposta curta à pergunta "não há como melhorar mais?"

Há como melhorar, mas **não por fazer o empate técnico sumir**. [OPINIÃO] Três razões:
1. Um estudo grande com mapas de cultura e satélite (EUA e outros "celeiros", não semiárido) achou que passar de uma rotação simples de 2 culturas para uma mais diversa tem em geral efeito pequeno, às vezes negativo, e que o benefício muda com o clima ([Kluger et al., arXiv 2506.02384](https://arxiv.org/abs/2506.02384), [RESUMO]). Ou seja, parte do empate pode ser real.
2. Para desempatar de verdade falta dado que o projeto não tem (preço, custo, histórico de produtividade por cultura e por sequência).
3. Mais um "critério" sem fonte só troca o empate por um falso vencedor.

O que melhora a **confiabilidade**: (a) separar o que é regra dura do que é nota, (b) mostrar *o que separa* as alternativas em vez de um ranking, (c) trazer a matriz "o que vem depois de quê" de fonte brasileira, (d) incluir risco de renda com série oficial, (e) testes de consistência e revisão cega por técnicos.

---

## 1. O que o projeto já faz (lido do código e dos docs)

- **Motor de culturas** (`motor.py`, `ciclo.py`, `incerteza.py`): adequação por ciclo e por ano de clima (temperatura e chuva, EcoCrop, mínimo das duas notas), ZARC opcional, Monte Carlo estilo SMAA-2 (10.000 sorteios: pesos Dirichlet, ano de clima, lacuna = U[0,1], sem renormalizar). Empate técnico = faixas p10-p90 sobrepostas. Resultado conhecido: empate em 100% dos locais (docs 10, 15 C1).
- **Rotação de 3 safras** (`rotacao.py`): sequências (c1,c2,c3), c1 = cultura atual; 5 critérios (adequação ao clima, diversidade de família, leguminosa antes de não leguminosa, palha, água); renda = lacuna; pré-seleção das 80 melhores; SMAA sobre elas; ordem de critérios por prioridade do agricultor (suposição a validar, DU6).
- **MILP** (`rotacao_milp.py`): modelo de fluxo (Alfandari et al.), regras duras (não repetir em seguida, mínimo de leguminosas, máximo de repetições), CVaR dos 25% piores anos, e `otimizar_com_incerteza` (MILP repetido com pesos, ano e lacunas sorteados; devolve `p_otima`). Conferido contra enumeração exata em 15 casos. Rotulado "proposta".
- **Solver:** só `scipy.optimize.milp` (`scipy==1.18.1` no `requirements.txt`; PuLP, OR-Tools e Pyomo **não** são usados). A documentação do SciPy diz que `milp` é um *wrapper* do HiGHS ([docs SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html), [LIDA]).
- **Conferência externa:** SMAA-2 igual ao `pysensmcda` (diferença < 1e-12), teste pulado se o pacote não está instalado.
- **Achado do experimento MILP** (`experimentos/milp/RESULTADO.md`): o ótimo do MILP depende dos pesos e da palha (dado de poucos estudos), não de fato agronômico; não coincide com as alternativas do SMAA.

**Fragilidades que a pesquisa deve atacar** [OPINIÃO, lidas no código]: (1) "diversidade de família" e "leguminosa antes" são *proxies* sem matriz de efeito sucessor com fonte; (2) palha/N vêm de estudos de fora do semiárido; (3) mesmo ano de clima nas 3 safras (suposição declarada); (4) nenhuma validação contra prática publicada; (5) renda é lacuna.

---

## 2. Tabela de opções

Legenda de "ganho": o quanto melhora a *confiabilidade/honestidade* (não o "rende mais"). Risco de enganar: B = baixo, M = médio, A = alto.

| # | Opção | Ganho | Custo | Risco de enganar | O que validaria |
|---|---|---|---|---|---|
| 1 | Restrições do agricultor como regra **dura** (cultura que não planta, sem irrigação, área, mão de obra) antes de ranquear; mostrar "por que saiu" | Alto | Pequeno | B | Teste de propriedade: nenhuma saída viola a regra; caso do técnico |
| 2 | Mostrar "o que separa as alternativas" (dominância de Pareto + critério em que cada uma ganha/perde) em vez de ranking | Alto | Pequeno | B | Conferir que ninguém dominado é recomendado; revisão cega |
| 3 | Matriz "cultura anterior → seguinte" com fonte e grau de evidência, obtida do acervo Embrapa + Delphi curto com técnicos; substitui os proxies de família/leguminosa | Alto | Médio | M (se virar número sem fonte) | Concordância com o acervo; painel de técnicos (estilo Fenz) |
| 4 | Risco de renda: série de preço CONAB + produtividade PAM por município; comparar por CVaR/dominância estocástica | Alto | Médio | M-A (poucos anos; PAM é município, não talhão) | Backtest em anos passados; mostrar o n de anos |
| 5 | Testes de consistência (monotonia, sensibilidade, propriedade com Hypothesis) | Médio | Pequeno | B | Passam na suíte; falha = bug achado |
| 6 | Pareto multiobjetivo no MILP (varrer pesos ou ε-restrição), mostrando a curva diversidade x clima x palha | Médio | Pequeno-médio | B | Conferir contra enumeração (já existe) |
| 7 | SMAA com pesos *ordenados* (técnico só ordena) e SMAA-O para critérios que só têm nota ordinal | Médio | Pequeno | B | Igualdade com `pysensmcda` (já há teste) |
| 8 | Modelo de cultura (AquaCrop-OSPy) para produtividade limitada por água por cultura/data de plantio | Médio | Grande | A (parece "produtividade") | Comparar com PAM por município; calibração local |
| 9 | Estimar efeito da cultura anterior com NDVI de satélite do próprio local | Médio (se possível) | Grande | A | Precisa mapa de cultura por ano: **hoje inviável no Nordeste** (ver 3.4) |
| 10 | Programação dinâmica/MDP, Markov de rotação, aprendizado por reforço | Baixo agora | Grande | A | Precisam de transições observadas ou simulação que não temos |
| 11 | Otimização robusta/estocástica "completa" (distribucionalmente robusta etc.) | Baixo agora | Grande | A | Precisa de distribuição de preço/produtividade que não temos |
| 12 | Comunicação: mostrar P(top-3) e "empate" em palavras; lista "o que conferir com o técnico" por regra violada | Médio | Pequeno | B | Teste de leitura com 3-5 pessoas (agricultor/técnico) |

---

## 3. Detalhe por tema

### 3.1 (a) Formulações de otimização

**Solvers abertos (repositórios abertos por mim):**

| Projeto | Existe | Licença | Linguagem | Última atividade | Observação |
|---|---|---|---|---|---|
| [HiGHS](https://github.com/ERGO-Code/HiGHS) | Sim | MIT | C++ (algum C) | **Não confirmei data** (página mostra 17.536 commits; 1,9 mil estrelas; README cita v1.16.0, não confirmada como a última) | LP, QP convexo e MIP; é o que o SciPy usa por trás |
| [OR-Tools](https://github.com/google/or-tools) | Sim | Apache-2.0 | núcleo C++, interfaces Python/C#/Java | **Não confirmei data** (14,4 mil estrelas) | Tem CP-SAT; útil para regras combinatórias complexas |
| [PuLP](https://github.com/coin-or/pulp) | Sim | MIT | Python (com extensão Rust) | **Não confirmei data** | Solver padrão CBC |
| [Pyomo](https://github.com/Pyomo/pyomo) | Sim | BSD | Python | **Não confirmei data** | Cita programação estocástica mista e pacote `mpi-sppy` (este **não abri**) |

[OPINIÃO] Trocar de solver **não** melhora a confiabilidade: o HiGHS via SciPy já prova o ótimo em ~0,1 s (RESULTADO.md). Só valeria OR-Tools se as regras ficarem muito combinatórias, e Pyomo se for fazer programação estocástica de dois estágios. Nada disso é prioridade.

**Formulações lidas:**
- **MILP de fluxo** (Lemalade, Nagih, Plateau, Alfandari, *Annals of Operations Research* 190, 2011): rotação em vários períodos com demanda e regra "parcela em cultivo e em pousio ao mesmo tempo é proibida"; aplicado a fazendas de Madagascar ([página IAOR](https://iaorifors.com/paper/72605), [RESUMO]). Já é a base do projeto.
- **Multiobjetivo** (Pontes et al., *Agricultural Systems* 219, 2024, 104050): 4 modelos MILP, objetivos renda líquida, diversidade e uso da terra. Trechos do buscador falam em ~60% mais diversidade com perda de renda < 5% ([BUSCA]: não abri a página do periódico; **não usar o número**). Ideia útil: varrer o peso e mostrar a curva.
- **Robusta** ([Liu et al., arXiv 2512.10396](https://arxiv.org/abs/2512.10396), [RESUMO]): "estrutura robusta em camadas" com matriz de interação entre culturas e camada de otimização distribucionalmente robusta; dados do norte da China; o resumo **não traz números** nem diz se é MILP. Lição: tratar como ideia, não como evidência.
- **CVaR com simulador** ([Akhavizadegan et al., arXiv 2208.04840](https://arxiv.org/abs/2208.04840), [RESUMO]): CVaR no objetivo estocástico, APSIM simulando cada decisão, 25 locais do Corn Belt dos EUA; decide data de plantio, N, densidade, cultivar (não rotação). O projeto já usa CVaR sem simulador.
- **Programação dinâmica estocástica** ([Boussios et al., Frontiers Env. Sci. 2022](https://www.frontiersin.org/articles/10.3389/fenvs.2022.986816), [LIDA parcialmente: li 100 mil de 125 mil caracteres]): famílias de lavoura e pecuária em terras secas da Jordânia; APSIM em 500 anos de clima sintético; o próprio artigo diz que o modelo ficou **limitado a um ano** porque modelos dinâmicos maiores ficam grandes demais, e que **não** serve para política. Não traz resultado de rotação.
- **Aprendizado por reforço** ([Fenz et al., *Computers and Electronics in Agriculture* 212, 2023](https://publications.sba-research.org/publications/2023%20-%20Fenz%20-%20AI-%20and%20data-driven%20crop%20rotati_Stefan%20Fenz.pdf), [LIDA]): agente DQN usa **matriz de culturas sucessoras** (de longa duração e de NDVI) e margem de contribuição; validado com 1 especialista e 2 agricultores. Detalhes em 3.2.
- **Cadeias de Markov de rotação:** o exemplo aberto é um *blog* que estima transições dos mapas de cultura dos EUA (CDL) por máxima verossimilhança, supondo estacionariedade, independência entre pixels e primeira ordem, e admite ser um modelo ingênuo e sem validação ([R-bloggers](https://www.r-bloggers.com/2016/07/predicting-agriculture-poorly-part-i/), [LIDA]). Exige mapa de cultura por ano, que no Nordeste não existe (3.4).

**Restrições agronômicas** (intervalo de retorno da mesma família, leguminosa antes de gramínea, pousio, cobertura permanente): não achei, nas páginas que abri, uma tabela de intervalos de retorno com fonte brasileira para as 16 culturas. Os resumos do buscador sobre famílias e intervalos **não localizaram** esse conteúdo ([BUSCA]). O acervo do projeto (`docs_rag/manifesto.json`) já traz material de rotação e plantio direto da Embrapa (Bogiani, Debiasi et al., Pesagro-Rio, etc.), mas são de Cerrado/Sul/Sudeste na maioria; **eu não li esses PDFs de novo nesta pesquisa**.

### 3.2 (b) Como validar sem resultado de campo

1. **Painel de especialistas** (o que Fenz fez, [LIDA]): sequências geradas foram mostradas a 1 especialista em rotação e 2 agricultores com questionário (realismo, dado de entrada, o que falta). Resultado reportado: sequências de 5 passos e as de 7 passos com a matriz de NDVI foram consideradas "realistas" na maioria; as de 7 passos com a matriz da literatura foram "mal vistas". **Amostra de 3 pessoas**: serve para achar absurdos, não para provar acerto.
2. **Comparação com prática publicada**: ZARC e Embrapa dizem *quando* plantar, não a melhor sequência. [OPINIÃO] A checagem viável é: para cada sequência sugerida, listar quais regras do acervo (com trecho numerado) a apoiam e quais não têm apoio. Já existe RAG; falta usá-lo como auditor, não como explicador.
3. **Modelos de cultura:**
   - **AquaCrop-OSPy** ([repositório](https://github.com/aquacropos/aquacrop), [LIDA]): existe, licença Apache-2.0, Python, 173 estrelas, 526 commits, **data da última atividade não confirmada**. O README diz que espelha a maior parte do AquaCrop 7.1, **exceto salinidade, estresse de fertilidade, manejo de ervas daninhas e herbáceas perenes**, e que não é oficial da FAO. Entradas do exemplo: clima diário, solo, cultura com data de plantio e água inicial do solo. [OPINIÃO/inferência] Sem estresse de fertilidade, o modelo **não representa o benefício de nitrogênio de uma leguminosa**, que é o ganho central de uma rotação. Serve para produtividade limitada por água por cultura e data, não para "efeito da cultura anterior".
   - **DSSAT** ([dssat-csm-os](https://github.com/DSSAT/dssat-csm-os), [LIDA]): existe, BSD-3-Clause, 240 estrelas; linguagem e data não confirmadas na página (provável Fortran, **inferência**).
   - **APSIM** ([ApsimX](https://github.com/APSIMInitiative/ApsimX), [LIDA]): existe, 220 estrelas; licença e data **não confirmadas** (a página só liga um LICENSE.md); `APSIM/APSIMClassic` deu 404.
   - Limite comum [OPINIÃO]: todos pedem solo (perfil hídrico), parâmetros de cultivar e calibração local; sem isso, dão número bonito e errado. O exemplo de Gana (AquaCrop + dominância estocástica) **não diz como calibrou** ([Ahiamadia et al. 2024](https://mro.massey.ac.nz/handle/10179/72022), [LIDA]).
4. **Experimentos de campo no semiárido:** **não achei experimento de longa duração** de rotação milho/caupi no Nordeste. Achei uma tese de 2 anos em Quixadá-CE (Cysne, UFC, 2011; milho e feijão-caupi em duas sucessões, 5 coberturas, 2008 e 2009), cujo resumo diz que a produtividade do milho **não diferiu** entre coberturas e a do caupi foi **maior no plantio convencional** ([tese](https://repositorio.ufc.br/ri/bitstream/riufc/8611/1/2011_tese_jrbcysne.pdf), [LIDA: li o resumo]). É evidência local útil como *aviso* ("o efeito não é garantido"), mas curta demais para calibrar nada.
5. **Consistência (sem campo)** [OPINIÃO]: monotonia (mais chuva dentro da faixa não pode piorar a adequação; cultura viável não pode virar inviável ao relaxar `risco_max`), invariância (renomear culturas não muda o resultado, já testado), sensibilidade (mudar o ciclo muda mais que o município: já medido no doc 10), regra dura nunca violada, MILP = enumeração (já testado). Ferramenta: [Hypothesis](https://github.com/HypothesisWorks/hypothesis) ([LIDA]: existe, 9,2 mil estrelas, Python; licença e data não confirmadas) gera casos aleatórios e reduz ao menor que falha. Não é dependência do projeto hoje.
6. **Delphi/AHP:** busca por "Delphi + AHP + matriz de rotação, Brasil" **não achou** método pronto ([BUSCA]). Achei só uso de Markov+AHP para escolher cultura em Caxias do Sul e um sistema de rotação em Goiás com modelo Target MOTAD e dados CONAB (TCC, [BUSCA]). Então o Delphi curto seria desenho nosso (ver 3.5).

### 3.3 (c) Reduzir o empate de forma honesta

- **Mais critérios com fonte.** Só vale critério com fonte e que **varie entre as alternativas**; senão não separa nada. Candidatos: renda/risco (3.5-C), matriz sucessora (3.5-B), custo de implantação (não temos), mão de obra (ver abaixo).
- **Aviso de método:** o MILP/Pareto mostra o que é *possível*; a decisão entre empatadas pertence ao agricultor. Um achado citado no doc 16: restrições de **mão de obra** mudam mais a rotação que a aversão a risco ([INRAE, prodinra 275403](https://prodinra.inra.fr/record/275403), só o título veio via doc 16; **não abri**). Se for verdade, perguntar ao agricultor "quantas pessoas trabalham?" vale mais que refinar pesos. [OPINIÃO]
- **Informação do agricultor como restrição dura:** ver opção 1. Não adiciona dado externo, tira alternativas impossíveis e, portanto, reduz empate sem inventar nada.
- **SMAA-O:** o resumo que li ([Lahdelma, Salminen, Hokkanen 2002, EJOR 142](https://research.aalto.fi/en/publications/locating-a-waste-treatment-facility-by-using-stochastic-multicrit/), [RESUMO]) diz que SMAA-O trata **medidas de critério ordinais** (sorteia todas as escalas numéricas compatíveis com a ordem). **Atenção:** o `docs/08` fala em SMAA-O para "pesos ordinais"; pelo que li, SMAA-O é para **notas** ordinais. Pesos só ordenados se tratam sorteando o simplex ordenado (o projeto já tem `ordem_pesos`). Uso concreto de SMAA-O: critérios que um técnico só consegue classificar (ex.: "bom/médio/ruim" para efeito sobre a palha).
- **Dominância estocástica:** ordena opções pela distribuição completa de renda/produtividade, não só pela média ([Wageningen](https://edepot.wur.nl/670719), [BUSCA]; [Ahiamadia et al. 2024, Gana](https://mro.massey.ac.nz/handle/10179/72022), [LIDA]: dominância de 2ª ordem + AquaCrop para ranquear práticas em região semiárida). Em rotação: [Maynard, Harper e Hoffman 1997](https://econpapers.repec.org/RePEc:cup:agrerw:v:26:y:1997:i:01:p:106-114_00), dominância em 5 rotações com 21 anos de dados de experimento ([BUSCA]: só o resumo via buscador; a página do PDF deu 403). **Limite para o SULCO** [OPINIÃO]: precisa de uma série longa por cultura. O PAM do projeto cobre 2015-2023 (9 anos, 182 municípios, doc 16): serve para uma *faixa* por cultura, **não** para provar dominância; com 9 pontos, a maioria das comparações vai cruzar.
- **Dados de mercado:**
  - **CONAB:** a página de preços agropecuários diz que há pesquisa de mais de 112 produtos há mais de 30 anos e mais de 20 mil séries em todas as UFs; as consultas ("Preços de Mercado" etc.) estão ligadas na página, mas ela **não confirma** feijão/milho/mandioca, formato de download nem API; só cita um link "Dados Abertos" ([CONAB](https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/precos-agropecuarios), [LIDA parcial]). **Não consegui baixar nem verificar uma série.**
  - **CEPEA:** a página de feijão devolveu 403 ([tentativa](https://www.cepea.org.br/br/indicador/feijao.aspx)); **não verifiquei** termos de uso nem dados.
  - **PAM/IBGE:** já coletado (`pam_ce.parquet`); hoje só é contexto e, com `renda_por_cultura`, receita bruta/ha (não lucro).

### 3.4 (d) Benefício da rotação estimado com satélite do próprio local

- **O método existe e foi validado em outro contexto:** Peltonen-Sainio et al. (2019) estimaram "valor da cultura anterior" para pares cultura-anterior/cultura-seguinte a partir de NDVI Sentinel-2 em ~240 mil parcelas no sudoeste da Finlândia, 2016-2017, comparando cada parcela ao percentil 90 da mesma cultura; valores de -16% a +16%, com leguminosas de grão e colza como melhores antecessoras, "consistente com experimentos de campo" ([Frontiers Plant Sci.](https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2019.00462/full), [LIDA]). Limites que eles mesmos listam: NDVI não é produtividade; o produtor explica 61-76% da variação e os modelos explicam só ~34-50%; só 1 região e 2 anos. Fenz et al. (2023) usam NDVI perto da colheita por par de culturas, na Áustria (Fig. 3 de [Fenz, CEA](https://publications.sba-research.org/publications/2023%20-%20Fenz%20-%20AI-%20and%20data-driven%20crop%20rotati_Stefan%20Fenz.pdf), [LIDA]). Kluger et al. combinam mapas de cultura, "verdor" de satélite e *machine learning* causal ([RESUMO]).
- **O que todos exigem:** registro *por parcela* de qual cultura foi plantada em cada ano, com pelo menos ~20 casos por par de culturas. (Peltonen-Sainio, [LIDA].)
- **MapBiomas não fornece isso no Nordeste:** a legenda de agricultura da Coleção 10 separa só soja, cana, arroz, algodão, café, citros, dendê e **"outras lavouras temporárias"** (tabela do [factsheet de Agricultura C10](https://brasil.mapbiomas.org/wp-content/uploads/sites/4/2025/12/Factsheet-Agricultura_C10_10.12_v2.pdf), [LIDA]). Milho e feijão aparecem como classe **só no mapa de segunda safra, que é beta** e (pelo texto do factsheet) foca soja/milho/algodão de safrinha, sem o sertão. Pela busca, a Caatinga tem ~1,4 Mha de temporárias em 2024, quase todas em "outras" ([BUSCA]). Conclusão [OPINIÃO]: **não dá para identificar milho vs feijão-caupi vs mandioca por parcela e por ano**, logo não dá para estimar "efeito da cultura anterior" por par de culturas.
- **O que ainda dá para medir de satélite** [OPINIÃO]: "temporária (algo plantado) vs pousio" por ano; duração do solo nu e épocas de estresse (já feito no app); resposta do NDVI à chuva por local. Isso descreve o presente, não prova qual rotação funciona.
- **CONAB/IBGE LSPA:** não abri nenhuma página do LSPA nesta sessão; **sem conclusão**.

### 3.5 Opções recomendadas em detalhe

**A. Restrições do agricultor como regra dura + "por que saiu"**
- Ideia: antes do SMAA/MILP, excluir cultura/sequência que o agricultor não pode ou não quer (sem semente, sem irrigação, sem animal para palma, sem mão de obra). O MILP já tem regras duras; falta ligar ao formulário.
- No SULCO: campos opcionais no app → `regras` do MILP e filtro nas candidatas; lista "descartadas e por quê".
- Dado: do próprio usuário, nenhum dado externo. Custo: pequeno. Risco de enganar: baixo (menos alternativas, não mais confiança). Validação: teste de propriedade (nenhuma sequência viola) + 3 casos reais com técnico.

**B. Matriz "cultura anterior → seguinte" com fonte e grau de evidência**
- Ideia (Kolbe/Fenz): uma tabela de efeito sucessor (+, 0, −, sem dado) por par de culturas; hoje o projeto usa proxies (família diferente, leguminosa antes). [LIDA: Fenz Figs. 2-3]
- No SULCO: tabela no estilo `tabela_culturas.csv` (par, efeito qualitativo, fonte, página, nível de evidência); lacuna = "sem dado", nunca neutro. Entra como critério ordinal (SMAA-O) em vez de 0/1.
- Dado: **não temos**. Fontes prováveis: acervo Embrapa (já baixado), literatura do semiárido; Delphi curto (2 rodadas, 5-8 técnicos). Custo: médio (o trabalho é humano). Risco: médio se preenchida "de cabeça"; baixo se cada célula tiver fonte. Validação: concordância entre técnicos e com o acervo; células sem dado aparecem como lacuna.

**C. Risco de renda (CONAB + PAM)**
- Ideia: transformar a lacuna "renda" em faixa (P10-P90 de receita/ha por cultura no município) e comparar por CVaR ou dominância, dizendo o número de anos usado.
- Dado: PAM já temos (2015-2023, 9 anos); **preço CONAB não temos e não verifiquei como baixar**. Custo: médio. Risco: médio-alto (receita ≠ lucro; custos ausentes; PAM é município; 9 anos). Validação: teste retrospectivo (usar até 2020, comparar 2021-2023) e rótulo "receita bruta, não lucro".

---

## 4. As 3 melhorias que recomendo primeiro

1. **Regras duras do agricultor + "o que separa as alternativas"** (opções 1 e 2, mais teste de propriedade da opção 5). Sem dado novo, reduz alternativas impossíveis, torna a recomendação auditável e muda o texto de "ranking" para "estas diferem em X, empatam em Y". Exige: campos no formulário, `regras` do MILP ligado a eles, dominância de Pareto sobre os 5 critérios, e testes (monotonia, regra nunca violada). Um a dois dias de trabalho [estimativa].
2. **Matriz sucessora com fonte (opção 3)**. É a fraqueza científica mais clara do módulo (proxy de família e de leguminosa sem fonte). Exige: decidir quem são os técnicos (decisão sua), montar o questionário, extrair do acervo o que já há (com página), e aceitar que muitas células ficarão "sem dado". Sem isso o resto é refino de um critério fraco.
3. **Revisão cega por técnicos + risco de renda como faixa (opções 12 e 4)**, nessa ordem. A revisão (estilo Fenz: ~20 sequências, questionário curto) é a única validação possível sem campo e **dá a medida real** da confiabilidade; o risco de renda só entra quando a série de preço for verificada. Exige: agendar 3-5 técnicos/agricultores, 20 casos impressos com e sem rótulos, e confirmar com a CONAB (SIC) como obter série por UF.

## 5. O que NÃO vale fazer (e por quê)

- **Trocar o SMAA pelo MILP como "o ótimo"**: o MILP devolve um único ótimo para pesos fixos; o resultado já mostrou depender da palha. Manter como proposta/checagem.
- **Estimar efeito da cultura anterior por NDVI no Nordeste agora**: MapBiomas não separa milho/feijão/mandioca (3.4); sem registro por parcela, o método de Peltonen-Sainio/Fenz não roda.
- **Aprendizado por reforço, MDP, otimização distribucionalmente robusta**: exigem transições ou distribuições observadas que não temos; o artigo de PD estocástica que li cobre 1 ano e diz não servir para política; o robusto não traz números.
- **AquaCrop/APSIM/DSSAT completos agora**: custo grande, calibração local ausente, e o AquaCrop-OSPy não modela estresse de fertilidade (benefício N da leguminosa). Risco de parecer "previsão de produtividade", contra o objetivo do SULCO.
- **Cadeia de Markov com transições dos EUA (CDL)**: dado de outra região; o próprio exemplo aberto é um baseline sem validação.
- **Citar números de buscador** (ex.: "60% mais diversidade"): não abri a fonte.
- **Mais critérios sem fonte** só para quebrar o empate; e **medir "acerto" com bases tipo Kaggle**: os trechos de busca sobre recomendação de cultura com 99% de acerto falam de benchmark, não de campo ([BUSCA], não abri).

## 6. Incerteza e comunicação ao agricultor (e)

Busca por revisão sobre incerteza em sistemas de recomendação de cultura: só vieram artigos de ML (LIME/SHAP, Monte Carlo *dropout*), de benchmark; **não achei revisão específica sobre comunicar incerteza ao agricultor** ([BUSCA], nada aberto). Os dois achados úteis: Fenz validou com usuários reais com questionário; Gana usou dominância estocástica para tratar aversão a risco do pequeno agricultor. [OPINIÃO] O SULCO, com "empate técnico", lacunas e "o que conferir", já está à frente do que apareceu; o que falta é **testar a leitura** com pessoas reais (opção 12).

## 7. Decisões que ficam com você

1. Quem serão os técnicos para a matriz sucessora e a revisão cega (DU6/BL5)? Quantos? Há disponibilidade antes do pitch?
2. Aceita "sem dado" na matriz (lacuna visível) em vez de preencher tudo?
3. Quer que "renda" entre só como faixa de **receita bruta**, com o aviso de que não é lucro? Aceita esperar a verificação da série CONAB?
4. O ciclo real (DU1) continua sendo a maior fonte de variação; fechar antes de refinar rotação.
5. O MILP continua "proposta" (DU15) ou passa a "checagem de regras" (recomendação: checagem)?
6. Adotar o Hypothesis como dependência de teste (não de produção)?
7. Mudar a linguagem de "ranking de alternativas" para "alternativas que diferem em..." (opção 2)?
8. Corrigir no doc 08 a frase sobre SMAA-O para pesos (SMAA-O trata notas ordinais)?

## 8. O que não consegui abrir ou confirmar

- Essec (Alfandari) e SciTePress: 404/não abri; usei a página do IAOR (resumo).
- Pontes et al. 2024, CEPEA, página do periódico de Maynard et al.: bloqueio (403/WAF) ou só indexador.
- Artigo de Fenz et al. 2023 (EJA, AI4CROPR): domínio inacessível; só trecho de buscador.
- Sartore e Boryan (NASS, Markov de ordem alta): domínio inacessível.
- Vieira e Wander (revisão econômica de rotação, Embrapa) e a nota do ZARC (PDF): o texto não foi legível/ou o arquivo veio trocado; nada citado como fato.
- Datas de última atividade de HiGHS, OR-Tools, PuLP, Pyomo, AquaCrop-OSPy, DSSAT, APSIM, Hypothesis: a página não mostrou; licenças de APSIM e Hypothesis não confirmadas.
- `mpi-sppy`, LSPA/CONAB, INRAE (prodinra): não abertos.
