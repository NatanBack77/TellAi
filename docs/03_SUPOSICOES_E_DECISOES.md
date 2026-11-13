# Suposições, decisões e pendências

Registro vivo. Atualizar a cada decisão. Última atualização: 2026-11-09.

## Suposições (aprovadas pelo usuário em 2026-11-09)
| # | Suposição | Status |
|---|---|---|
| S1 | Python 3.11+, `venv`, sem LangChain | aprovada |
| S2 | Região do demo: semiárido do Nordeste; pontos a definir | pendente (pontos) |
| S3 | Dados reais ainda não existem localmente; desenvolvimento só com `SINTETICO_*` | aprovada |
| S4 | Features de chuva usam apenas dados até o início do período t (sem vazamento do futuro) | aprovada |
| S5 | NDVI 16 d alinhado ao clima diário pela data de início do composto | **a confirmar** que `data` = início |
| S6 | Caminhos em `data/processed/`, configuráveis em `config.yaml` | aprovada |
| S7 | "Estação chuvosa" = quinzenas de maior chuva na climatologia do ponto (em `config.yaml`) | aprovada |
| S8 | Mann-Kendall com poucos anos => lacuna explícita (mínimo configurável) | aprovada |
| S9 | Holdout temporal é a avaliação final; `GroupKFold` roda dentro do período de treino | aprovada |
| S10 | `tabela_culturas.py` e `rag_docs.py` não foram fornecidos; serão criados do zero | aprovada |
| S11 | Valores da tabela de culturas só com fonte lida; sem fonte => lacuna | aprovada |

## Itens a verificar na documentação oficial (não adivinhar)
- Nomes de parâmetros do NASA POWER (ex.: `PRECTOTCORR`, `T2M_MAX`, `T2M_MIN`, radiação).
- Camadas do MOD13Q1 v061 e semântica do *pixel reliability*.
- Variáveis e versão mais recente do SPL4SMGP.
- ID do modelo DeepSeek (`deepseek-flash` não confirmado).
- `intfloat/multilingual-e5-small` (validar uso para PT).
- Link do desafio (Resources tab): **não informado**.

## Perguntas em aberto ao usuário
1. Lat/lon no diagnóstico (descritivo) e fora das features — confirmar.
2. Escala/valores de `confiabilidade` do `ndvi_16d` e qual descartar.
3. Quantos anos de dados reais esperados (decide limiar de "poucos anos").
4. Permitir bloco "teste de fumaça" marcado como sintético no relatório (sem tratá-lo como resultado).
5. Lista dos 10–20 pontos do demo (ou aceitar proposta).
6. Contas/chaves: Earthdata, DeepSeek/Gemini (via `.env`; nunca lidas nem commitadas).

## Decisões
- D1 (2026-11-09): este ciclo implementa só `src/modelos/`; coleta, RAG, LLM e app ficam para outras tarefas.
- D2 (2026-11-09): documentação criada antes de qualquer código (`docs/01..03`).
- D3 (2026-11-09): Python 3.14.7 no ambiente. `shap` não foi instalado ainda (dependência pesada/numba); instalar no passo 9 e, se não houver wheel para 3.14, usar `TreeExplainer` alternativo ou `xgboost` `pred_contribs` e registrar aqui.
- D4 (2026-11-09): "instalar as bases" = dados sintéticos aleatórios por ora. Dados reais (POWER, MODIS, SMAP) não são baixados neste módulo; exigem Earthdata e ficam na etapa de coleta (`src/coleta`).

## Progresso
- [x] Passo 1: esqueleto, config, requirements (fixados), sementes
- [x] Passo 2: gerador `SINTETICO_*` (6 células x 2 pontos, 2010–2023, clima/NDVI/umidade)
- [x] Passo 3: validador de entrada (`entrada.py`), falha explícita
- [x] Passo 4: `diagnostico.py` + `tests/test_diagnostico.py` (20 testes no total passando)
- [x] Passo 5: `features.py` + `tests/test_features.py` (37 testes no total passando)
- [x] Passo 6: `preditivo.py` + `tests/test_preditivo.py` (54 testes no total passando)
- [x] Passos 7–12 (código e testes; 71 testes passando). Falta rodar com dados reais.

## Decisões do diagnóstico (passo 4)
- D5: grade do NDVI = 23 slots por ano pela regra `(dia_do_ano-1)//16`; o gerador sintético agora segue a grade MODIS (DOY 1, 17, ..., 353).
  **Pendente de confirmar com dado real**: a `data` do MOD13Q1 ser o início do composto (S5).
- D6: interpolação só em buracos internos de até 2 observações seguidas; buracos maiores ficam NaN e viram lacuna. Interpoladas são marcadas (`interpolado`).
- D7: STL roda no maior trecho contínuo sem NaN (mínimo 2 períodos = 46 obs); se não houver, não roda e registra lacuna.
- D8: ano de NDVI só conta se tiver >= 16 observações válidas originais (antes da interpolação).
- D9: períodos (quinzena/ano/estação) com cobertura de dias < 90% viram NaN, nunca são preenchidos.
- D10: solo nu padrão = percentil 20 do próprio ponto. Por construção todo ponto terá "solo nu"; o limiar é relativo ao local. Aviso fixo em `lacunas`. Quinzena é "típica" se solo nu em >= 50% dos anos e >= 3 anos de dados.
- D11: estação chuvosa = janela circular de `n_quinzenas` (padrão 8) consecutivas com maior chuva média; ano da estação desloca -1 quando a janela cruza o fim do ano.
- D12: z-score só com >= 3 anos na quinzena e desvio > 0.
- D13: `confianca` (alta/media/baixa) = heurística: anos válidos (>=15 alta, >=8 media), -1 nível se >10% do NDVI interpolado, -1 nível se faltar veranico ou NDVI. **Não é probabilidade.**
- D14: `n_anos_validos` é dicionário por variável (ndvi, chuva, umidade_solo).
- D15: toda saída carrega `limites` (resolução 250 m / 50 km / 9 km, NDVI não é produtividade, não prevê).

## Como rodar o diagnóstico
`.venv/bin/python -m src.modelos.diagnostico --sintetico` grava `diagnostico.json` e `anomalias.parquet` em `data/processed/sintetico/modelos/`.
Sem `--sintetico`, usa os caminhos reais do `config.yaml`. Resultados de dados sintéticos não são resultado do projeto.

## Decisões das features (passo 5)
- D16: unidade de linha = (ponto, período t de NDVI observado). `data` = início do composto (grade 23 slots). Só NDVI original e confiável vira linha; interpolados nunca são alvo.
- D17: toda feature usa só dias em [t-W, t-1]. Teste de vazamento: alterar clima a partir de D não muda nenhuma feature de t <= D.
- D18: janelas de soma (chuva 30/60/90 d) exigem cobertura 100%; janelas de média (tmax 30 d, umidade 15 d) exigem >= 90% (`cobertura_minima_dados`). Faltou => NaN, sem preencher. Linhas com NaN ficam com `completo = False` e fora do treino.
- D19: `dias_secos_consecutivos` conta dias com chuva < 1 mm terminando em t-1, teto de 90 dias; NaN se a sequência toca dado ausente ou o início da série.
- D20: sazonalidade como `quinzena_sin`/`quinzena_cos` (circular); a quinzena crua fica só como metadado, não é feature.
- D21: umidade do solo = média de `sm_superficie` e `sm_raiz` nos 15 dias antes de t (defasada por construção). Sem umidade, essas features não existem e isso vira lacuna.
- D22: alvo = NDVI - média do slot por ponto, calculada SÓ nos `anos_referencia` informados (`adicionar_anomalia`). Slot com < 3 anos de referência => NaN. **O preditivo deve passar só anos de TREINO no holdout temporal.** Limite conhecido: no GroupKFold por célula a climatologia do ponto de teste usa os anos do próprio ponto; é padrão em anomalias, mas fica registrado.
- D23: `resumir_dataset` devolve contagens e lacunas, incluindo o aviso de < 15 células POWER distintas.

## Decisões do preditivo (passo 6)
- D24: modelos comparados em todo esquema: climatologia (anomalia = 0), Ridge (StandardScaler + Ridge) e XGBoost. Skill = 1 - RMSE_modelo/RMSE_baseline; baseline principal = climatologia, e o XGBoost também reporta `skill_vs_ridge`.
- D25: divisão: holdout = últimos `holdout_anos` (3) anos presentes; `GroupKFold` por `celula_power` roda só nas linhas do período de treino. Cada célula valida em exatamente um fold. `n_folds = min(config, células de treino)` e a redução vira lacuna.
- D26: Ridge escolhe `alpha` (grade em `config.yaml`) por `GroupKFold` interno de 3 folds usando só dados de treino de cada ajuste; com < 3 células no treino, alpha fixo 1.0 + aviso. XGBoost usa parâmetros fixos a priori (`preditivo.xgboost` no config), NUNCA ajustados olhando teste. Sementes fixas, `n_jobs=1`.
- D27: um teste lê o código-fonte e falha se aparecer `KFold(` sem Group, `ShuffleSplit`, `train_test_split` ou `cross_val_score` (CV aleatória proibida).
- D28: métricas por fold com média e desvio (ddof=1); holdout com métricas pooled. R² pode ser instável em folds pequenos; reportado como está.
- D29: `confianca` do preditivo = "baixa" se < 15 células POWER distintas, senão "media" (heurística, não probabilidade). Toda saída traz `lacunas`, `confianca` e o aviso de que é associação histórica, não causalidade nem previsão do clima.
- D30: com `--sintetico` a CLI grava `SINTETICO_metricas.json`, marca `dados_sinteticos: true` na primeira lacuna e **não imprime métricas**. Um teste de fluxo checa só que o Ridge supera a climatologia no sintético (o NDVI sintético depende da chuva por construção); isso valida o encanamento, não é resultado.
- **A decidir no passo 8**: critério de "XGBoost supera o Ridge de forma consistente" (proposta: skill_vs_ridge > 0 na média dos folds E na maioria dos folds E no holdout; caso contrário, Ridge). Pendente de aprovação antes de olhar dados reais.

## Decisões dos passos 7–12
- D31: critério XGBoost vs. Ridge implementado como proposto (skill_vs_ridge > 0 na média dos folds, no holdout e em mais da metade dos folds; senão Ridge). **Aprovado pelo usuário em 2026-11-11**; a saída traz `criterio_aprovado_pelo_usuario: true`. Se o modelo escolhido não superar a climatologia no holdout, há aviso explícito.
- D32: conformal split por CÉLULA: das células do treino, `conformal_fracao_calibracao` (0.25) vão à calibração; o modelo é ajustado nas demais; quantil com correção de amostra finita ceil((n+1)(1-α))/n (inf => sem faixa, vira lacuna). Cobertura medida nas células de validação (CV) e nos anos de holdout. Limite: no holdout as células de teste coincidem com as de treino (a separação é temporal).
- D33: SHAP: `shap` não instalado; usa-se `pred_contribs` do XGBoost (valores de Shapley de árvore). Só explicativo.
- D34: cenários: `chuva_ac_*` × fator, `tmax_media_*` + delta; dias secos, sazonalidade e umidade não mudam (declarado em `limites`). Qualquer feature fora de [min, max] do treino => `extrapolacao: true`, sem número e sem faixa.
- D35: com dados sintéticos o relatório e a CLI não mostram métricas nem a decisão.
- D36 (2026-11-11): coleta POWER via API REST (`urllib`, sem dependência nova). Parâmetros confirmados na resposta da API: PRECTOTCORR (mm/dia), T2M_MAX, T2M_MIN (°C), ALLSKY_SFC_SW_DWN (MJ/m²/dia); fill_value -999 vira NaN. Comunidade AG. `celula_power` = índice aproximado da grade 0,5° x 0,625° (`round(lat/0.5)_round(lon/0.625)`), não o ID oficial.
- D38: NDVI via ORNL DAAC subset (10 datas/chamada, ~8 chamadas/min), porque o AppEEARS não saiu da fila. `modis_date` AYYYYDDD = início do composto (S5 confirmada para esta fonte); NDVI inteiro x 0,0001, preenchimento -3000; reliability fill -1.
- D37: lista de 13 pontos em `config.yaml` é PROPOSTA minha (um por célula, semiárido do NE); S2 segue pendente de revisão do usuário.
- D39 (2026-11-11): primeira rodada com dados reais. `ndvi.confiabilidade_aceita: [0, 1]` mantido: valores observados 0, 1 e 3 (sem 2); 3 (nuvem) é descartado. Semântica 0–3 segue a conferir na doc oficial. Resultado: ver `relatorio_modelos.md`.
- D40 (2026-11-11): validação de melhorias por walk-forward (`walkforward.py`); anos 2010–2021 decidem, 2022–2024 selados para confirmação; Bonferroni pelo nº de variantes; placebo obrigatório (docs/05).
- D41: **persistência** (anomalia dos 2 compostos anteriores, só se consecutivos ≤ 17 d) validada: +0,23 vs. +0,06. Ressalva: ganho vem da autocorrelação do NDVI, não do clima; cenários de chuva ficam pouco sensíveis.
- D42: Ceará ampliado: 1 município por célula POWER (centroide IBGE API v1 + malhas v3). 59 pontos / 59 células no total. Lista é proposta a revisar (S2).
- D43: NDVI via ORNL com 16 downloads em paralelo (~100 janelas/min); com 4–8 era ~8/min.
- D44: experimentos dos agentes ficam em `experimentos/` (scripts + caches parciais + `dados13/` com o instantâneo dos 13 pontos).

## Decisões da rodada de 2026-11-11 (noite)
- D45: Ceará inteiro: 184 municípios (IBGE localidades v1 + malhas v3, centroide). 195 pontos com os 11 de outros estados. Clima por município (POWER); só 59 células distintas.
- D46: NDVI via ORNL com 64 workers (satura perto de ~230 janelas/min).
- D47: SMAP SPL4SMGP v008 via OPeNDAP (subset por caixa, 1 pedido/granulo); `sm_surface`→`sm_superficie` (0–5 cm), `sm_rootzone`→`sm_raiz` (0–100 cm), m3/m3, fill −9999→NaN (variáveis lidas dos atributos HDF5). Pixel EASE2 mais próximo (≤ 6,2 km); média diária UTC com ≥ 6/8 granulos, senão NaN. 44 granulos falharam (HTTP 502 do servidor).
- D48: CHIRPS descartado (sem ganho validado).
- D49: `src/culturas/`: valores só com fonte lida (validador exige fonte, URL, página e trecho contendo o número); sem fonte = lacuna. EcoCrop via espelho OpenCLIM (não conferido com a FAO). Pesos do score e lista de culturas: **proposta pendente de aprovação**.
- D50: `src/rag/`: texto indexado é o `pdftotext` de cada página e testado como substring; limiar de relevância (60% dos termos ou cosseno ≥ 0,87) calibrado com poucas perguntas negativas.
- D51: caches pesados (SMAP, POWER) versionados como `.tar.gz` em `data/raw/` para retomar em outro PC; `.env` nunca.
- D52 (2026-11-12): **persistência integrada à produção** (`preditivo.py`, `cenarios.py`, `relatorio.py`). Usa a MESMA função validada em `walkforward.py` (`features.adicionar_persistencia`; `walkforward.extra_persistencia` é alias), `anom_lag1/2` = anomalia dos 2 compostos anteriores só se consecutivos (≤ 17 d; `persistencia_max_gap_dias`), com a climatologia só dos anos de treino (D22); lag ausente/não consecutivo => NaN e a linha sai do treino e do teste (nunca preenchida). Padrão `preditivo.usar_persistencia: true`; `false` (ou `--sem-persistencia`) devolve o modelo só-clima, que continua como linha de comparação no relatório (mesmas linhas e todas as linhas). NÃO usa `pers_lags4` (ganho marginal) nem SMAP: `preditivo.usar_umidade_solo: false` por padrão (ganho ~+0,007 sobre a persistência, poder baixo, perde ~60% das linhas por começar em 2015); `construir_dataset` ignora o SMAP se a opção estiver desligada (antes ele entrava sozinho quando o arquivo existia). Cenários: `anom_lag*` não mudam sob cenário de chuva/temperatura, declarado em `limites`; a regra "fora de [min, max] do treino => sem número" vale também para `anom_lag*`; sensibilidade medida com e sem persistência em `cenarios.sensibilidade_comparada`. Conformal recalibrado por célula como antes; a cobertura real no holdout continua abaixo da meta e é reportada (não ajustada). Nada novo foi escolhido com 2022–2024.
- S5 confirmada (D38). Pendentes: S2 (pontos), semântica da `confiabilidade`.

## Decisões de 2026-11-12 (adicionais; D45–D51 acima)
- D52: persistência integrada ao preditivo/cenários (função única `adicionar_persistencia`, mesma da validação); SMAP desligado por padrão (`usar_umidade_solo: false`); `pers_lags4` não integrado.
- D53: motor de culturas com ciclo de plantio (36 inícios/ano, nota = mínimo entre temperatura e chuva) e Monte Carlo estilo SMAA-2; lacunas de N e palha viram incerteza em [0,1], sem renormalizar; ranking principal por critérios comuns; sem desempate alfabético. Parâmetros em `src/culturas/parametros.py` (todos SUPOSIÇÃO).
- D54: prioridade do agricultor (água/solo/renda) = ordem ordinal de critérios, SUPOSIÇÃO a validar com técnico; renda sem dado = lacuna.
- D55: camada LLM só reescreve JSON + trechos; verificador determinístico (números, [n], promessas, aviso de técnico); sem chave o app usa o template.
- D56: back-end FastAPI offline (`src/api`); `/modelo/previsao` pendente (501).
- D57: códigos IBGE em `pontos.csv` (`ibge`), aceitos só com nome único + coordenada dentro do polígono; `sobral_ce` fica sem código.
- D58: caches pesados versionados como `.tar.gz` (SMAP, POWER); `scripts/setup.sh` extrai.
