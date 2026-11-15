# Ciclo FAO-56 e chuva anual como padrão do motor

Data: 2026-11-14. Código: `src/culturas/ciclo_fao.py` (novo), `ciclo.py`, `motor.py`, `parametros.py`. Experimento: `experimentos/fao_melhorias/exp5_antes_depois.py` (saídas em `experimentos/fao_melhorias/saida/exp5_*`). Testes: `tests/test_ciclo_fao.py`. Pesquisa de origem: `docs/25_PESQUISA_FAO.md`, `experimentos/fao_melhorias/RESULTADO.md`.

## 1. Decisões do usuário (2026-11-14)

- **(A) Chuva anual.** A faixa de chuva do EcoCrop é comparada à chuva dos 365 dias desde o início do plantio (`Parametros.chuva_modo="anual"`, novo padrão). Base: a descrição oficial do EcoCrop (https://gaez.fao.org/pages/ecocrop) fala em "annual precipitation". A ficha oficial da espécie não foi aberta (login Google/503): a leitura "anual" vem da descrição da base, não da ficha. A temperatura continua sendo a média do ciclo, e a janela de plantio continua sendo o início escolhido na grade de 10 dias. O atendimento hídrico do ciclo (chuva do ciclo sobre a demanda da tabela, `chuva_sobre_demanda_hidrica`) fica só como informação (`janela_plantio.atendimento_hidrico_nota`), fora do ranking. **ETc = Kc x ETo NÃO foi levado ao motor** (precisa de ETo e latitude; segue só no experimento `exp2_etc.py`).
- **(B) Ciclo FAO.** `Parametros.ciclo_fonte="fao"` (novo padrão): as 11 culturas da Tabela 11 usam a soma dos 4 estágios; guandu, palma forrageira, crotalária juncea, feijão-de-porco e mucuna (sem dado FAO, lacuna em `fao_staging.csv`) mantêm o ponto médio do EcoCrop. O ciclo FAO entra por `ciclo.duracao_efetiva` (prioridade: `ciclo_override` > FAO > EcoCrop), com o staging validado por `fao_staging.carregar` (fonte, URL, trecho contendo o valor). Cada cenário traz aviso em `lacunas` e em `suposicoes`: "ciclo de referência de outras regiões" (FAO) ou "ciclo do EcoCrop, sem dado FAO" (as 5). `tabela_culturas.csv` NÃO foi alterado: o ciclo da tabela (EcoCrop) e o da FAO divergem de propósito, e a divergência aparece no aviso (e em `janela_plantio.ciclo_ecocrop_min_max`).
- **Opção anterior preservada:** `Parametros(chuva_modo="ciclo", ciclo_fonte="ecocrop")` (CLI: `--chuva-modo ciclo --ciclo-fonte ecocrop`). Verificado: regenerar os 10 `cenarios/*.json` com ela reproduz os arquivos antigos (rotação, score, P(top-3), melhor início, adequação, chuva do ciclo, empate: 0 divergências em 10 arquivos); teste `test_opcao_anterior_reproduz_o_cenario_antigo`.

## 2. Regra única para escolher a linha da Tabela 11 (fixada antes de olhar o ranking)

Fonte: FAO-56 (Allen et al. 1998), cap. 6, Tabela 11, https://www.fao.org/4/x0490e/x0490e0b.htm; trechos literais em `data/culturas/fao_staging.csv` (coluna `trecho`, formato "Crop | Init | Dev | Mid | Late | Total | Plant Date | Region :: Maize (grain) | 25 | 40 | 45 | 30 | 140 | Dec/Jan | Arid Climate").

1. Mandioca: só a linha "ano 1" (210 d); o "ano 2" (360 d) é cultivo de 2 anos.
2. Se a FAO rotula alguma linha da cultura como "Arid" (aparece em "Arid Climate", "Arid Region", "(Semi) Arid Climates"), vale essa linha: é a mais próxima do semiárido segundo a própria classificação da FAO. Só o rótulo impresso é usado, nenhum julgamento nosso de similaridade.
3. Sem rótulo árido: mediana inferior das linhas ordenadas pela soma dos estágios. Com uma só linha, é ela.
Duração = soma dos 4 estágios. A faixa mín–máx das linhas vai no aviso e define `ciclo_modo` "min"/"max" nas culturas FAO.

| cultura | dias | regra | linha escolhida (região, plantio) | faixa nas linhas | total impresso pela FAO |
|---|---|---|---|---|---|
| milho | 140 | rótulo árido | Arid Climate, Dec/Jan | 125–180 (6 linhas) | 140 |
| sorgo | 130 | rótulo árido | Arid Region, Mar/April | 125–130 | **140** (a soma dos estágios é 130; usada a soma) |
| mamona | 180 | rótulo árido | (Semi) Arid Climates, March | 135–180 | 180 |
| feijão-caupi | 100 | linha única | Mediterranean, March | 100 | **110** (soma 100) |
| girassol | 130 | linha única | Medit.; California, April/May | 130 | 130 |
| gergelim | 110 | linha única | China, June | 110 | **100** (soma 110) |
| mandioca | 210 | linha única (ano 1) | Tropical regions, estação chuvosa | 210 | 210 |
| feijão comum | 100 | mediana inferior | Idaho, USA, June | 95–110 | 100 |
| milheto | 105 | mediana inferior | Pakistan, June | 105–140 | 105 |
| algodão | 195 | mediana inferior | Egypt; Pakistan; Calif., Mar-May | 180–225 | 195 |
| amendoim | 140 | mediana inferior | Mediterranean, May/June | 130–140 | 140 |

Nenhuma linha é do semiárido brasileiro. Sorgo, caupi e gergelim têm inconsistência da própria tabela da FAO (soma dos estágios x total impresso), registrada no aviso.

## 3. Mudanças no código (resumo)

- `ciclo.py`: `duracao_efetiva`; `notas_ciclo` devolve `chuva` (soma do CICLO, informação) e `chuva_comparada` (a que entra na nota: 365 dias no modo anual) e `ciclo_info`; a validade da janela exige o ciclo e os 365 dias sem dado faltante (dado faltante continua descartando o ano, nunca é preenchido; teste `test_janela_com_dado_faltante_continua_descartada`). `resumir` devolve `chuva_ciclo_mm` (do ciclo) e `chuva_comparada_mm`.
- `motor.py`: suposições dependem dos parâmetros; avisos de ciclo por cultura em `lacunas` e `suposicoes`; `janela_plantio` ganha `chuva_comparada_mm`, `chuva_comparada_janela_dias`, `ciclo_fonte`, `ciclo_referencia`, `ciclo_ecocrop_min_max`, `atendimento_hidrico_nota`. `janela_plantio.chuva_ciclo_mm` continua sendo a chuva do ciclo (o app usa esse campo contra a demanda de água); `criterios.chuva.valor.perfil` é a chuva efetivamente comparada.
- Rotação de 3 safras e MILP: usam `avaliar_local`/adequações por ano, que já refletem o novo ciclo e a nova chuva; testes de regras duras, Pareto, rotação, MILP, renda e matriz passam com `-W error` (298 testes, mais `test_mvp.py` e `test_api.py`: 38 passam). Verificação em um município real (barbalha_ce, milho): 3 estratégias, P(top) e empate técnico calculados.

## 4. Antes x depois (15 municípios do CE, 655 a 1134 mm/ano, escolhidos por quantis de chuva anual; 10 000 sorteios, semente fixa, 23 anos de clima)

Colunas "só ..." separam o efeito de cada decisão.

**Cultura atual: milho**

| métrica | ANTES | DEPOIS | só chuva anual | só ciclo FAO |
|---|---|---|---|---|
| adeq. média da cultura atual | 0.853 | 0.909 | 0.909 | 0.751 |
| desvio-padrão da adequação entre municípios | 0.097 | 0.056 | 0.056 | 0.135 |
| inícios de plantio distintos (de 15) | 7 | 7 | 7 | 7 |
| fração dos 36 inícios a ≤0,05 da melhor adequação | 0.261 | 0.739 | 0.739 | 0.13 |
| culturas viáveis (média) | 15.067 | 14.933 | 14.933 | 15.267 |
| P(top-3) médio das 2 alternativas | 0.459 | 0.429 | 0.435 | 0.462 |
| taxa de empate técnico | 1.0 | 1.0 | 1.0 | 1.0 |
| nº médio de empatadas por alternativa | 11.933 | 11.533 | 11.5 | 12.3 |
| conjuntos de alternativas distintos (de 15) | 3 | 4 | 2 | 2 |
| mudou a melhor época (de 15) | - | 15 | 15 | 13 |
| deslocamento médio da melhor época (dias) | - | 150.7 | 150.7 | 30.7 |
| mudou o conjunto de viáveis (de 15) | - | 15 | 15 | 3 |
| mudou o conjunto de alternativas (de 15) | - | 15 | 15 | 11 |

**Cultura atual: feijao_caupi**

| métrica | ANTES | DEPOIS | só chuva anual | só ciclo FAO |
|---|---|---|---|---|
| adeq. média da cultura atual | 0.869 | 0.974 | 0.974 | 0.741 |
| desvio-padrão da adequação entre municípios | 0.098 | 0.034 | 0.033 | 0.134 |
| inícios de plantio distintos (de 15) | 4 | 9 | 9 | 5 |
| fração dos 36 inícios a ≤0,05 da melhor adequação | 0.166 | 0.921 | 0.933 | 0.101 |
| culturas viáveis (média) | 15.067 | 14.933 | 14.933 | 15.267 |
| P(top-3) médio das 2 alternativas | 0.517 | 0.557 | 0.557 | 0.53 |
| taxa de empate técnico | 1.0 | 1.0 | 1.0 | 1.0 |
| nº médio de empatadas por alternativa | 11.067 | 9.9 | 9.667 | 11.067 |
| conjuntos de alternativas distintos (de 15) | 6 | 7 | 6 | 5 |
| mudou a melhor época (de 15) | - | 15 | 15 | 15 |
| deslocamento médio da melhor época (dias) | - | 141.3 | 154.3 | 18.3 |
| mudou o conjunto de viáveis (de 15) | - | 15 | 15 | 3 |
| mudou o conjunto de alternativas (de 15) | - | 13 | 13 | 12 |

Pontos de dados:
- Alternativas escolhidas para milho (frequência nos 15): ANTES guandu 15, caupi 9, crotalária 5, feijão comum 1; DEPOIS crotalária 15, caupi 11, gergelim 2, feijão comum 1, feijão-de-porco 1. Para caupi: ANTES milho 12, milheto 8, gergelim 5, sorgo 3, girassol 1, mamona 1; DEPOIS milho 11, gergelim 10, algodão 3, milheto 2, girassol 2, palma 1, mandioca 1.
- Viabilidade (milho como atual, igual com caupi): **sorgo passa a inviável em 15 de 15 municípios** (a faixa absoluta de chuva do sorgo no EcoCrop é 300–700 mm; os 15 municípios têm 655 a 1134 mm/ano em média, e o filtro exige a cultura dentro da faixa em ao menos 70% dos anos; a contagem de anos por município não foi detalhada); amendoim e mandioca passam a viáveis em 3 e feijão-de-porco em 7. A cultura atual (milho e caupi) continua viável nos 15.
- Auditoria nos 195 pontos (milho atual, `auditoria_alternativas.json`, prioridade "água"): empate técnico 100% antes e depois; mediana de empatadas 13 -> 11; P(top-3) de 0,372–1,0 para 0,322–0,874; mais escolhidas: ANTES guandu 188, caupi 135, crotalária 54; DEPOIS crotalária 194, caupi 96, gergelim 45, guandu 29, feijão-de-porco 16. Prioridade "solo": empate técnico 50% nos dois, alternativas crotalária e palma (194–195 pontos).
- Os 10 `data/processed/cenarios/*.json` e `auditoria_alternativas.json` foram regerados; `evidencias_rag.json` não.

## 5. O que NÃO melhorou e riscos novos

1. **Empate técnico continua em 100%** (milho e caupi, 15 municípios e auditoria de 195 pontos para água/sem). Ciclo FAO e chuva anual não separam as alternativas; guandu/crotalária/caupi seguem sendo escolhidas entre ~11 candidatas empatadas.
2. **A "melhor época" perdeu poder de informação com a chuva anual.** Como a chuva de 365 dias é quase a mesma para qualquer início, só a temperatura do ciclo discrimina: a fração dos 36 inícios a até 0,05 da melhor adequação sobe de 26% para 74% (milho) e de 17% para 92% (caupi). O início "melhor" passa a ser decidido em grande parte pelo desempate (centro do platô) e se desloca em média 150 dias (milho: antes quase sempre dezembro, depois abril a julho). **Início em julho para milho no Ceará não é recomendação agronômica**; o motor com chuva anual não "vê" a estação chuvosa. A janela de plantio fiel à chuva sazonal exige o ZARC (`usar_zarc=True`, hoje desligado por padrão) ou uma decisão do usuário sobre usar o atendimento hídrico do ciclo para escolher o início (sem entrar no ranking entre culturas). Pendente de decisão; o app que mostra "melhor época" deve levar esse aviso.
3. Ciclo FAO não validado no semiárido (regiões de outros climas); o ciclo da cultivar local pode diferir 30–50 dias. Caupi, girassol e gergelim têm uma só linha FAO. Nas 5 culturas sem FAO o ciclo EcoCrop (60–365 d, extremos largos) segue, então esse grupo e as 11 de FAO usam fontes diferentes e ficam comparados entre si.
4. Chuva anual: a faixa do EcoCrop do sorgo (máx. absoluto 700 mm) elimina o sorgo em todo o Ceará amostrado, o que contradiz a prática local; é limite do dado da espelho OpenCLIM (não comparável com a ficha oficial, inacessível). Registrar para revisão técnica.
5. Janela anual de 365 dias desde o início passa para o ano seguinte: o último ano da série (2024) fica fora (23 anos usados, igual ao antes).
6. P(top-3) não melhorou de forma geral (milho 0,459 -> 0,429; caupi 0,517 -> 0,557): varia com o conjunto de candidatas.
7. ETc = Kc x ETo não está em produção; Kc de clima sub-úmido não ajustado ao semiárido.

## 6. Como voltar à opção anterior

`Parametros(chuva_modo="ciclo", ciclo_fonte="ecocrop")`; CLI: `python -m src.pipeline.gerar_cenarios --cultura-atual milho --chuva-modo ciclo --ciclo-fonte ecocrop --saida <pasta>`.
