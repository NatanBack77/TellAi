# 18. Arquitetura técnica do SULCO: das bases de dados ao resultado final

Atualizado em 2026-11-13. Escrito para quem vai continuar o trabalho em outro computador e para jurados técnicos.
Tudo aqui foi conferido no código (`src/`, `config.yaml`, `tests/`) e nos documentos do repositório. Números têm o arquivo de origem entre parênteses.
O que não pôde ser confirmado está marcado "não verificado". Estado do que falta: `docs/15_PENDENCIAS.md`. Como retomar: `docs/04_RETOMADA.md`.

## (a) Visão geral e diagrama do fluxo

O SULCO ("da órbita ao sulco") é uma ferramenta de **apoio** à conversa do agricultor do semiárido com o técnico: mostra o que o clima e a vegetação do município
dizem sobre a terra e compara três caminhos de rotação (a atual e duas alternativas), com incerteza, lacunas e riscos. Não decide e não promete que a rotação rende mais.
Escopo: 195 pontos (184 municípios do Ceará mais 11 de outros estados), 2001–2024.

```
FASE A (offline, com internet: coleta e pré-cálculo)                       FASE B (offline: o app só lê arquivos locais)
-----------------------------------------------------------------         -----------------------------------------------------------
NASA POWER ------------> clima_diario.parquet ---+
MODIS (ORNL DAAC) -----> ndvi_16d.parquet -------+--> src/modelos:         Streamlit (src/app/app.py)  /  API (src/api/main.py)
SMAP (Earthdata) ------> umidade_solo.parquet ---+    diagnostico ------> data/processed/diagnostico/  --> "O que os satélites mostram"
                                                       features +          data/processed/modelos/        --> página "Limites dos dados"
                                                       preditivo +         (metricas.json, relatorio)         (o NDVI NÃO dá nota às rotações)
                                                       walk-forward +
                                                       conformal ACI
IBGE malhas/localidades -> pontos.csv (coluna ibge) --+
IBGE PAM (SIDRA) -------> pam_ce.parquet --------------+--> src/app/quadra.py --> "2b. Chuva da quadra e rendimento"
SoilGrids (ISRIC) ------> solo.parquet ----------------+--> solo estimado (textura) --> avisos de risco + solo do ZARC
SRTM (AWS) -------------> terreno.parquet (coletado; AINDA FORA do app)
ZARC (MAPA) ------------> zarc_ce.parquet ------------+
EcoCrop/FAO + estudos --> data/culturas/tabela_culturas.csv (16 culturas, cada valor com fonte)
                                       |
                                       v
                          src/culturas (motor):  ciclo (temperatura e chuva no ciclo, 36 inícios x 24 anos)
                                       -> filtro de viabilidade (risco_max) -> ZARC (janela de plantio)
                                       -> critérios -> Monte Carlo estilo SMAA-2 (pesos Dirichlet, lacuna = incerteza)
                                       -> faixa, posição, P(top-3), empate técnico
                                       -> rotação em 3 safras (rotacao.py) e plano de várias safras (MILP, rotacao_milp.py)
                                       v
PDFs do acervo (31) -> src/rag (BM25 + embeddings, portão lexical) -> data/processed/mvp/evidencias_rag.json (trechos por cultura e critério)
                                       v
                          src/app/mvp.py (lógica) -> telas 1, 2, 2b, 3, 3b, 4 (templates em português; sem LLM no app hoje)

src/llm (DeepSeek ou Stub): só REESCREVE o JSON do cenário + trechos [n]; verificador barra qualquer número/promessa inventado.
        Pronto e testado com provedor falso; NÃO integrado ao app nem à API (ver docs/14_LLM.md e docs/15_PENDENCIAS.md).
```

Princípios que atravessam tudo: nenhum número inventado; dado ausente vira lacuna visível; o resultado é cenário "a avaliar com técnico local"; o app não chama API de dados ao vivo.
Detalhes das regras de ouro e dos testes que as protegem: seção (h).

## (b) Bases de dados

Legenda "versionado": o que está no git. `data/raw/*` é ignorado pelo `.gitignore`, **exceto** `data/raw/indices/` e `data/raw/modis_ornl/`; os caches de POWER e SMAP entram como `.tar.gz`.
`data/processed/*.parquet`, `pontos.csv`, `zarc_manifesto.json`, `diagnostico/`, `mvp/` e `cenarios/` são versionados; `data/processed/modelos/*` só `metricas.json` e `relatorio_modelos.md`; `data/processed/sintetico/` é ignorado.

| Base | O que é | Resolução / período | Como coletar (módulo e comando) | Onde fica | Versionado? | Limites |
|---|---|---|---|---|---|---|
| NASA POWER (diário) | chuva (PRECTOTCORR), Tmax (T2M_MAX), Tmin (T2M_MIN), radiação (ALLSKY_SFC_SW_DWN); comunidade AG | grade 0,5° x 0,625° (~50 km, `config.yaml` `coleta.power`); 2001-01-01 a 2024-12-31 | `python -m src.coleta.power [--forcar]` (API REST, sem login, idempotente) | bruto `data/raw/power/<ponto>.json` (59 arquivos nesta máquina); processado `data/processed/clima_diario.parquet` (1.709.370 linhas, `docs/00_STATUS.md`) | parquet sim; bruto só como `data/raw/power_cache.tar.gz` (27 MB) | 195 pontos mas só **59 células distintas**: pontos da mesma célula têm o mesmo clima e contam como UMA amostra efetiva. `celula_power` é índice aproximado (`round(lat/0,5)_round(lon/0,625)`), não o ID oficial. O comando também regrava `pontos.csv` (ver aviso em (j)). |
| MODIS MOD13Q1 v061 (NDVI) via ORNL DAAC | NDVI e `pixel_reliability` por pixel | 250 m, composto de 16 dias; 2001-01-01 a 2024-12-18; 107.583 linhas, 195 pontos x 552 datas (`experimentos/avaliacao_195/RESULTADO.md`) | `python -m src.coleta.modis_ornl --workers 16` (público, sem login; `--status` mostra o progresso; retomável pelo cache) | bruto `data/raw/modis_ornl/` (21.840 JSON, 97 MB nesta máquina); processado `data/processed/ndvi_16d.parquet` | ambos sim | NDVI x 0,0001, preenchimento -3000. Confiabilidade observada 0, 1 e 3 (não existe 2); `config.yaml` aceita 0 e 1 (83,2% das linhas); a semântica 0–3 segue "a conferir" na doc oficial. Faltam 57 linhas em 2005-08-29 (0,05%); nada é preenchido. `src/coleta/modis.py` (AppEEARS) ficou preso na fila e não é o caminho em uso. |
| SMAP L4 SPL4SMGP v008 | umidade do solo `sm_surface` (0–5 cm) e `sm_rootzone` (0–100 cm), m3/m3 | grade EASE-Grid 2.0 (~9 km; a doc do projeto diz 9 km e o catálogo do Earth Engine diz 11 km: **a verificar**); granulos de 3 h viram média diária (exige ≥ 6 de 8); 2015-03-31 a 2024-12-31; 195 x 3.564 dias = 694.980 linhas | `python -m src.coleta.smap [--limite N] [--parcial]`; exige Earthdata no `.env` (OPeNDAP via `earthaccess`, 1 pedido por granulo com a caixa dos pontos) | bruto `data/raw/smap/granulos/` (28.524 granulos); processado `data/processed/umidade_solo.parquet` | parquet sim; bruto só como `data/raw/smap_cache.tar.gz` (61 MB; não está extraído nesta máquina) | Série curta (desde 2015). **Desligado por padrão** no preditivo (`usar_umidade_solo: false`): ganho de ~+0,006 a +0,007 de skill, poder baixo. Pixel EASE2 mais próximo (≤ 6,2 km). |
| SRTM (terreno) | altitude e declive (pixel e raio de ~1 km; média e p90) | tiles HGT de 1 arco-segundo (~30 m) em `s3://elevation-tiles-prod/skadi`, sem login | `python -m src.coleta.srtm` | bruto `data/raw/srtm/*.hgt` (693 MB); processado `data/processed/terreno.parquet` (195 pontos, 0 sem altitude) | parquet sim; tiles não | Coletado e testado como feature (não ajuda a prever NDVI), mas **ainda não aparece no app** (declive/erosão). É terreno do pixel e da vizinhança, não do talhão. |
| SoilGrids v2.0 (ISRIC) | areia, silte, argila, carbono orgânico (soc) e pH em água; camadas 0–5, 5–15 e 15–30 cm | 250 m, CC BY 4.0; mediana dos pixels válidos numa janela de 9x9 (~2 km) | `python -m src.coleta.solo` (exige `rasterio==1.5.2`; lê VRT por `/vsicurl` de `files.isric.org`; a API REST `rest.isric.org` estava fora do ar em 2026-11-13) | bruto `data/raw/soilgrids/*.json` (15 arquivos); processado `data/processed/solo.parquet` (195 pontos; 195 com argila 0–5 cm; 181 com pixel central válido) | parquet sim; bruto não | Modelagem global, não análise de solo; ~2 km. No app a textura vem da argila média 0–30 cm (< 15% arenoso, 15 a 35% médio, > 35% argiloso; `mvp.solo_estimado`). Tempo de coleta: não documentado. |
| IBGE PAM (SIDRA, tabela 1612) | lavouras temporárias do CE: área colhida (216), quantidade produzida (214), rendimento (112), **valor da produção (215, mil reais correntes)** | municipal; 2015–2023; 298.080 linhas, 184 municípios | `python -m src.coleta.sidra` (API pública) | `data/processed/pam_ce.parquet` | sim | Rendimento é estimado por agentes do IBGE, não medido. O valor da produção (215) já está no arquivo mas **não é usado em nenhuma nota**. |
| IBGE localidades e malhas | código IBGE de 7 dígitos por ponto | municipal | `python -m src.coleta.ibge_codigos [--dry-run]` | coluna `ibge` de `data/processed/pontos.csv` (194 de 195) | sim | Só aceita o código se o nome casa com 1 município da UF E a coordenada cai no polígono. `sobral_ce` fica sem código (coordenada fora do polígono): 183 códigos únicos no CE. |
| ZARC (MAPA, Tábua de Risco) | decêndios de plantio indicados por município, cultura, solo e nível de risco | município; safras 2024/25, 2025/26, 2026/27 e "perene, olerícola e sem safra"; CC BY; 108.818 linhas do CE, 184 municípios, 53 culturas | `python -m src.coleta.zarc` (streaming, filtra `UF == CE`; não guarda o CSV bruto) | `data/processed/zarc_ce.parquet` e `zarc_manifesto.json` (URLs, sha256, data) | sim | Só Ceará (11 pontos de fora ficam sem ZARC). Significado de `decN` (0 sem indicação; 20/30/40 risco máximo) é leitura observada nas linhas: o dicionário oficial não descreve. Mede risco climático de perda, não substitui técnico. |
| FAO EcoCrop (via espelho OpenCLIM) e estudos | faixas de temperatura e chuva, ciclo e família botânica (EcoCrop); N na biomassa, palha, N fixado (estudos Embrapa e revistas); demanda hídrica (Brouwer e Heibloem 1986) | por espécie, genérico | `python -m src.culturas.construir_tabela --ecocrop <EcoCrop_DB.csv>` (gera a tabela; cada valor copiado do arquivo/PDF com trecho) | `data/culturas/tabela_culturas.csv`: 240 linhas = 16 culturas x 15 atributos, **34 lacunas** (demanda hídrica 9, N acumulado 6, N fixado 13, palha 6) | sim | EcoCrop veio do espelho do GitHub (commit ea43ecd), **não** do site da FAO (pediu login/503). Não se sabe se a faixa de chuva é anual ou do ciclo (verificar). |
| Índices NOAA PSL (Niño 3.4, TNA, TSA) | índices mensais do Pacífico e do Atlântico | mensal | sem módulo em `src/coleta`: os `.txt` foram colocados à mão (como foram baixados: não verificado) | `data/raw/indices/{nino34,tna,tsa}.txt` | sim | Só usados em experimentos (`experimentos/novas_fontes/`): não ajudaram. Não entram no app. |
| Acervo RAG (31 PDFs) | Embrapa, FAO, MAPA etc. sobre rotação, plantio direto, adubação verde, ZARC | 2.689 trechos (`docs/04_RETOMADA.md`) | PDFs em `docs_rag/` com `manifesto.json` (URL, data, sha256); índice por `python -m src.rag.rag_docs` (precisa de `pdftotext`) | `docs_rag/` (PDFs); índice em `indice/` | PDFs sim; `indice/` **não** (reconstruir) | Perguntas em português sobre documentos em inglês não acham (0%). Faltam Emater, INSA, portarias do ZARC. |

Resolução resumida: NDVI 250 m, clima ~50 km, umidade do solo ~9 km, solo 250 m (mediana ~2 km), terreno ~30 m. O app avisa que o satélite não enxerga o talhão (`AVISO_KM` em `src/app/app.py`).

## (c) Coleta (`src/coleta/`)

| Arquivo | O que faz |
|---|---|
| `power.py` | Baixa o diário do POWER por ponto (4 tentativas, espera crescente), converte `-999` em NaN, grava `clima_diario.parquet` e `pontos.csv` (que ganha `celula_power`). Cache por ponto em `data/raw/power/`. |
| `modis_ornl.py` | Para cada ponto lista as datas do MOD13Q1 e baixa janelas de até 10 datas, para as bandas NDVI e `pixel_reliability`; descarta arquivo truncado; monta `ndvi_16d.parquet` (NDVI x 0,0001; fora de [-0,2; 1,0] vira NaN). Confirmou que `modis_date` = início do composto (S5 resolvida). Ritmo observado: ~190 a 250 janelas/min; fase de listar datas ~10 min (`experimentos/avaliacao_195/RESULTADO.md`); mais de 64 workers não ajudam (`docs/03` D46). |
| `modis.py` | Alternativa via AppEEARS (login Earthdata). Ficou presa na fila; mantida só por histórico (tarefa antiga em `data/raw/modis/tarefa.json`, não baixada). |
| `smap.py` | OPeNDAP do Earthdata (subset no servidor, ~100 KB por granulo em vez de 139 MB). Grava um JSON por granulo (retomável), agrega para dia e só grava o parquet se a coleta estiver completa (ou com `--parcial`). |
| `sidra.py` | PAM/IBGE (SIDRA 1612), 2015–2023, 4 variáveis; valores não numéricos viram NaN. |
| `srtm.py` | Lê tiles HGT, calcula altitude e declive por diferenças centrais (espaçamento de ~30 m corrigido pela latitude). Um tile por vez na memória. |
| `solo.py` | Lê os mapas do SoilGrids por janela (rasterio), 5 propriedades x 3 camadas; guarda fração de pixels válidos e se o pixel central era válido. |
| `zarc.py` | Baixa em streaming os 4 recursos do ZARC, filtra o CE, registra sha256 e data no manifesto, grava o parquet. Exige `User-Agent` de navegador (CKAN). |
| `ibge_codigos.py` | Casa nome e coordenada com a API de localidades e as malhas do IBGE e acrescenta `ibge` a `pontos.csv`. |

Credenciais: `EARTHDATA_USERNAME` e `EARTHDATA_PASSWORD` vêm de `.env` (lido por `smap.py` e `modis.py`; nunca impressas nem versionadas). POWER, ORNL, SIDRA, SRTM, SoilGrids, ZARC e IBGE são públicos.
Nenhum código de produção (app, API, modelos) chama essas APIs: a coleta é a fase A.

## (d) Camada de modelos (`src/modelos/`)

Papel: **diagnosticar o passado** e **medir** o quanto o clima e a memória do NDVI explicam a anomalia da vegetação. O modelo preditivo sustenta o diagnóstico e a página "Limites dos dados"; **não dá nota às rotações**.

### d.1 Diagnóstico por local (`diagnostico.py`)
- NDVI na grade de 23 compostos por ano (`(dia_do_ano-1)//16`); descarta baixa confiabilidade; interpola só buracos internos de até 2 observações (marcados como `interpolado`); ano só conta com ≥ 16 observações originais válidas.
- **STL** (período 23; só no maior trecho contínuo, mínimo 2 períodos), climatologia por quinzena e z-score (só com ≥ 3 anos na quinzena).
- **Solo nu**: NDVI abaixo do percentil 20 do próprio ponto (`config.yaml` `solo_nu`). É relativo ao local: todo ponto terá "solo nu" por construção (aviso fixo em `lacunas`). Quinzena "típica" = solo nu em ≥ 50% dos anos (e ≥ 3 anos).
- **Estresse**: quinzenas com z ≤ -1 ("abaixo do normal"; convenção de apresentação do app, `mvp.LIMIAR_Z_ESTRESSE`, não é limiar agronômico).
- **Estação chuvosa**: janela circular das 8 quinzenas de maior chuva na climatologia do ponto. **Veranicos**: maior sequência de dias com chuva < 1 mm dentro da estação chuvosa, e a distribuição.
- **Tendência**: Theil-Sen + Mann-Kendall em chuva anual, temperatura média e NDVI de pico; abaixo de 10 anos (`tendencia.min_anos`) vira lacuna.
- Toda saída traz `n_anos_validos` (por variável), `lacunas`, `limites` e `confianca` ("alta" ≥ 15 anos, "media" ≥ 8, com rebaixamento por interpolação alta ou faltas). **A confiança é heurística de cobertura de dados, não probabilidade.**
- Gera `diagnostico.json` e `anomalias.parquet`; o app lê os de `data/processed/diagnostico/` (o CLI padrão grava em `data/processed/modelos/`, ver (j)).

### d.2 Features e persistência (`features.py`)
- Uma linha por (ponto, composto de NDVI observado e confiável). Toda feature usa só dias **estritamente anteriores** ao composto (janela [t-W, t-1]): chuva acumulada 30/60/90 d, Tmax média 30 d, dias secos consecutivos (teto 90), `quinzena_sin/cos`. Janelas de soma exigem cobertura 100%; de média, ≥ 90%; faltou, NaN (a linha sai do treino).
- Latitude, longitude e identificadores **não** são features.
- **Alvo** = anomalia do NDVI = NDVI menos a média do slot do ponto, com climatologia só dos anos de treino (`adicionar_anomalia`).
- **Persistência** (`adicionar_persistencia`): `anom_lag1` e `anom_lag2` = anomalia dos 2 compostos anteriores, só se consecutivos (≤ 17 dias, `persistencia_max_gap_dias`). Ligada por padrão (`preditivo.usar_persistencia: true`). É a MESMA função usada na validação (`walkforward.extra_persistencia` é alias), para a produção não divergir do que foi validado.

### d.3 Preditivo (`preditivo.py`)
- Modelos comparados: climatologia (anomalia = 0), Ridge (padronização + Ridge; alpha escolhido por validação interna agrupada só com dados de treino) e XGBoost (200 árvores, profundidade 3, taxa 0,05, parâmetros fixos a priori em `config.yaml`, **nunca ajustados olhando o teste**).
- Validação: `GroupKFold` por `celula_power` (5 folds, dentro do treino 2001–2021) e holdout temporal (últimos 3 anos: 2022–2024). CV aleatória é proibida e um teste lê o código-fonte e falha se aparecer `KFold(` sem grupo, `ShuffleSplit`, `train_test_split` ou `cross_val_score`.
- Métricas: MAE, RMSE, R², **skill = 1 - RMSE_modelo / RMSE_climatologia**.
- Decisão XGBoost x Ridge: XGBoost só vence se `skill_vs_ridge` > 0 na média dos folds, no holdout e em mais da metade dos folds (critério aprovado pelo usuário em 2026-11-11).
- Explicação: `pred_contribs` do XGBoost (valores de Shapley de árvore; `shap` não foi instalado). Só explicativa.
- Resultado em produção (`data/processed/modelos/metricas.json`, holdout 2022–2024, 8.052 linhas): climatologia RMSE 0,1004; Ridge 0,0746 (skill +0,257); **XGBoost 0,0719 (skill +0,284, R² 0,355)**; modelo escolhido: xgboost. SMAP desligado.
- Opções de CLI: `--sem-persistencia` (só clima) e `--com-smap`.

### d.4 Validação walk-forward (`walkforward.py`, protocolo em `docs/05_EXPERIMENTOS.md`)
- Ano de teste Y: treino só com anos < Y; climatologia só com anos < Y; 1 ano à frente, treino expansivo (mínimo 8 anos).
- Todas as variantes são avaliadas nas **mesmas linhas de teste** (interseção); métricas sempre na escala original da anomalia.
- **Seleção 2010–2021 decide**; **confirmação selada 2022–2024** só é olhada no fim, uma vez, para finalistas.
- **Bonferroni**: limite inferior do IC bootstrap sobre ANOS usa alpha/N, com N = número TOTAL de variantes testadas (inclusive as descartadas).
- **Placebo**: embaralha as features entre anos dentro de (ponto, slot); a skill tem de ficar ≤ 0; se não, há vazamento.
- Melhoria válida = skill > 0 com IC corrigido > 0, ≥ 60% dos anos positivos, melhor que a base pareado por ano e skill > 0 na confirmação.
- Variantes registradas: `base`, `persistencia`, `so_persistencia`, `janelas_longas`, `alvo_z`, `persistencia_z`. Resultados-chave (195 pontos, Ridge, seleção / confirmação): base +0,066 / -0,044; **persistência +0,309 / +0,239 (XGBoost +0,264)**; placebo ≈ 0 (`experimentos/avaliacao_195/RESULTADO.md`).
- O ganho vem da **memória do NDVI**, não do clima. CHIRPS, terreno, índices Niño/Atlântico, janelas longas, SPI e outras features não ajudaram (`docs/05`, `docs/16`, `experimentos/*`). Ensembles não superam o XGBoost sozinho (`experimentos/ensemble/RESULTADO.md`). Sem sinal de overfitting/underfitting (`experimentos/overfit_underfit/RESULTADO.md`).

### d.5 Incerteza: conformal split e ACI por estação
- **Split conformal por células** (`preditivo.conformal_split`): treino, calibração e teste em grupos de células distintos; quantil com correção de amostra finita `ceil((n+1)(1-alpha))/n`. Cobre ~76% / 87% para metas 80% / 90% (abaixo da meta: anos secos/úmidos deslocam os resíduos de todos os pontos juntos).
- **ACI por estação** (`conformal_aci.py`; Gibbs e Candès, NeurIPS 2021): `alpha_{t+1} = alpha_t + gamma (alpha - err_t)` a cada composto, um alpha por faixa de estação (4 faixas de 6 slots), gamma 0,05 fixado a priori, resíduos de calibração = 3 anos anteriores, aquecimento desde 2009. Em produção (`metricas.json`, holdout 2022–2024): **80,9% / 90,6%** (pior ano 2022: 71,7% / 84,8%; pior estação 77,3% / 88,9%). A garantia é de longo prazo, não de cada ano. `config.yaml: conformal_aci.ligado: true`.
- Decisão do método: `experimentos/conformal_A1/RESULTADO.md` (6 métodos, N = 6; confirmação selada 79,9% / 90,0%).

### d.6 Cenários de sensibilidade (`cenarios.py`)
- `treinar_para_cenarios`, `aplicar_cenario`, `simular`: multiplica `chuva_ac_*` por um fator e soma um delta à `tmax_media_*`. `dias_secos`, sazonalidade e `anom_lag*` não mudam (declarado em `limites`). Feature fora de [min, max] do treino => `extrapolacao: true`, **sem número e sem faixa**.
- A faixa usa o ACI por estação por padrão (`metodo_faixa="aci"`); `"split"` mantém o método antigo. `sensibilidade_comparada` mede a variação do cenário com e sem persistência (≈ 0,18 a 0,54 da variação só-clima; ambas pequenas frente ao RMSE de ~0,07, `docs/00_STATUS.md`).
- **O app NÃO usa `cenarios.py`**: o seletor de chuva/temperatura da tela 4 recalcula o motor de ciclo (seção e.9). Motivo: a previsão de NDVI quase não reage ao clima.

### d.7 Relatório (`relatorio.py`) e arquivos de apoio
`relatorio.py` gera `relatorio_modelos.md` a partir de `metricas.json` (com a tabela lado a lado: só clima em todas as linhas, só clima nas mesmas linhas, com persistência). `entrada.py` carrega `config.yaml` e valida arquivos/colunas (falta => erro explícito). `sintetico.py` gera dados `SINTETICO_*` só para testar fluxo (nunca são resultado).

## (e) Motor de culturas (`src/culturas/`)

### e.1 Tabela de culturas (`tabela_culturas.py`, `data/culturas/tabela_culturas.csv`)
Formato longo (cultura, atributo). 16 culturas: milho, feijão-caupi, feijão comum, sorgo, milheto, mandioca, algodão, amendoim, girassol, mamona, gergelim, guandu, palma forrageira, crotalária juncea, feijão-de-porco, mucuna.
O **validador** falha se um valor "verificado" não tiver fonte, URL, página e trecho, se o número não aparecer no trecho citado, se uma lacuna tiver valor ou não tiver motivo, ou se as faixas EcoCrop estiverem fora de ordem. Valor ausente é `lacuna` com motivo, nunca estimado.
Fontes: EcoCrop (temperatura, chuva, ciclo, família; via espelho OpenCLIM, `docs/03` D49), estudos citados com página (N e palha), Brouwer e Heibloem 1986 (demanda hídrica). Lacunas: 34 de 240 linhas.

### e.2 Ciclo e adequação climática (`ciclo.py`, `parametros.py`)
- Para cada **início de plantio** (a cada 10 dias desde 1º/jan = 36 inícios, `passo_inicio_dias`) e cada **ano** (2001–2024), calcula a temperatura média e a chuva acumulada **dentro do ciclo** da cultura (duração = ponto médio de `ciclo_min_dias`/`ciclo_max_dias` do EcoCrop; opções `min` e `max`).
- Nota trapezoidal 0–1 (0 fora da faixa absoluta, 1 na ótima) para temperatura e para chuva; **adequação = mínimo das duas** (ideia do EcoCrop, reimplementada sem copiar código). Melhor janela = início com maior adequação média entre anos (desempate pela fração de anos viáveis e depois pelo centro do platô; nunca por nome).
- Janela com dia faltante ou que passa do fim da série é descartada (nunca preenchida). Só entram anos em que **todos** os ciclos avaliados estão completos (23 de 24 com os ciclos médios atuais; aparece em `lacunas`).
- **Filtro de viabilidade**: existe algum início em que a cultura fica dentro das faixas absolutas em pelo menos `1 - risco_max` dos anos (`risco_max = 0,30`, SUPOSIÇÃO; não é o risco do ZARC). Cultura sem faixa completa ou sem ciclo é `indeterminada`, listada e fora do ranking.
- Todo parâmetro dependente de decisão do usuário está em `parametros.py` (dataclass `Parametros`) e é escrito em `suposicoes` de cada cenário.

### e.3 ZARC e janela aproximada (`zarc.py`; `Parametros.usar_zarc`)
- Com ZARC ligado, início de plantio fora dos decêndios permitidos recebe **nota 0** (NaN segue NaN). Decêndio permitido ao risco r se `0 < decN <= r` (padrão r = 30, `zarc_risco`). Só manejo sequeiro (`Cod_Outros_Manejos = 1`). Safra mais recente com a cultura (2026/27, 2025/26, 2024/25, depois perene).
- Solo (`zarc_solo`): `qualquer` (algum solo indica; permissivo), `todos` (conservador) ou `arenoso`/`medio`/`argiloso` (Cod_Solo 1, 2, 3). No app, o solo vem da textura informada pelo agricultor ou, na falta, da estimada pelo SoilGrids.
- Culturas mapeadas (nome claro): algodão, amendoim, feijão-caupi, feijão comum (mapeado a "Feijão 2ª Safra": suposição), gergelim, girassol, mamona, mandioca, milheto, milho (1ª safra), palma. **Sem ZARC**: crotalária, feijão-de-porco, guandu, mucuna e sorgo.
- **Janela aproximada** (`janela_aproximada_anuais`): para as culturas sem ZARC, usa a **união** dos decêndios das culturas anuais (algodão, amendoim, caupi, feijão comum, gergelim, girassol, mamona, milho, milheto) com ZARC no município. Corrige o viés registrado em `experimentos/zarc/RESULTADO.md` (sem isso, as culturas sem ZARC ficavam sem restrição e levavam vantagem). Sem ZARC de anuais no município: lacuna e nenhuma restrição.
- Efeito medido (`experimentos/zarc/RESULTADO.md`, 10 municípios): janelas de plantio passam de nov–dez para jan–mar (coerente com a quadra do CE); a viabilidade quase não muda.
- **No app o ZARC vem LIGADO por padrão** (`mvp.ZARC_PADRAO = True`, decisão do usuário em 2026-11-13); só se aplica a municípios do CE com código IBGE. A API e o CLI `gerar_cenarios` usam `Parametros()` padrão (`usar_zarc=False`).

### e.4 Critérios e pontuação (`motor.py`)
Cinco critérios com pesos-base de projeto (SUPOSIÇÃO, sem fonte): temperatura 0,25; chuva 0,25; N na biomassa 0,20; palha 0,15; família diferente da atual 0,15.
- **Ranking principal**: só os critérios que TODAS as candidatas têm (hoje temperatura, chuva, família; calculado dos dados). Cobertura 0,65 do peso total, igual para todas.
- **Complemento**: os 5 critérios, com lacuna de N/palha tratada como incerteza; fica à parte (`faixa_incerteza.complemento_n_palha`).
- Score central = pesos-base renormalizados só entre os critérios comuns, média dos anos; por isso pode cair fora de [p10, p90].

### e.5 Incerteza: Monte Carlo estilo SMAA-2 (`incerteza.py`)
- 10.000 sorteios (semente 20241112). Cada sorteio escolhe: **pesos** (Dirichlet(1), uniforme no simplex; com `ordem_pesos`, os pesos respeitam a ordem de importância, estilo SMAA-O), **o ano do clima** (o mesmo para todas as culturas do ponto) e, para cada nota ausente, **um valor U[0,1]** (a lacuna é incerteza: não é removida nem premiada; o score não é renormalizado).
- Saídas por cultura: faixa p10–p90 de score, posição p10/p90 e média, índice de aceitabilidade de posição, `p_top3`, `p_1o`, cobertura.
- **Empate técnico** = intervalos p10–p90 de score que se sobrepõem (SUPOSIÇÃO de definição; relação não transitiva). Empate exato divide a posição igualmente; **sem desempate alfabético**. As 2 alternativas são escolhidas por maior P(top-3), depois menor posição média; empate exato restante por sorteio com semente fixa (e avisa em `lacunas`).
- A faixa **não** é intervalo de confiança nem chance de a rotação dar certo: é sensibilidade a pesos, lacunas e anos de clima. Conferido contra o pacote `pysensmcda` (diferença < 1e-12; teste pulado se o pacote não está instalado).
- Achado central: as alternativas ficam em **empate técnico** (mediana de 12 a 13 candidatas empatadas; em 100% dos locais testados com milho, `docs/04_RETOMADA.md` e `docs/15_PENDENCIAS.md`). O ciclo escolhido pesa mais que o município (`docs/10`).

### e.6 Rotação em 3 safras (`rotacao.py`)
- Sequências (c1, c2, c3) com c1 = cultura atual (uma safra por ano). A rotação do agricultor (opcional) é a "atual"; sem informação, é a repetição da cultura atual. Candidatas = produto das culturas viáveis; só as **80 de maior nota média** (pesos iguais nos critérios com dado) entram na simulação (custo); a seleção das duas alternativas evita a mesma combinação em ordem trocada.
- Critérios (nota 0–1): `adeq_clima` (média da adequação das 3 culturas, mesmo ano de clima nas 3 safras: suposição), `diversidade_familia` (fração de transições com família diferente; **proxy** de pragas, que não têm dado), `leguminosa_antes` (leguminosa antes de não leguminosa; regra agronômica geral, SUPOSIÇÃO a validar), `palha` e `agua` (1 - demanda hídrica; min-max; lacuna quando falta dado). Principais: os três primeiros.
- Prioridade → ordem de critérios (SUPOSIÇÃO a validar com técnico): `agua` = água > clima > diversidade > leguminosa > palha; `solo` = palha > leguminosa > diversidade > clima > água (bloco completo); `sem` e `renda` = sem ordem (**renda é lacuna**: sem dado de preço/custo/mercado).
- Solo informado/estimado só gera **avisos de risco** (arenoso, argiloso, matéria orgânica baixa); não altera nota (a textura estimada ou informada altera só o solo do ZARC). Contexto do município: área colhida (PAM) do último ano, só informativa.
- Saída traz `empate_tecnico_todos` e o app mostra o aviso quando as duas alternativas empatam com muitas outras.

### e.7 MILP e plano de várias safras (`rotacao_milp.py`)
- `scipy.optimize.milp` (sem dependência nova). Variáveis `x[t,c]` (cultura c na safra t, safra 1 = atual) e `z` de transição ligadas por restrições de **fluxo** (Alfandari et al., 2011; resolve 10 safras com 16 culturas em ~0,1 s, `experimentos/milp/RESULTADO.md`). Regras duras opcionais: nunca repetir a mesma cultura em seguida, mínimo de leguminosas, máximo de repetições. Versão robusta (CVaR dos 25% piores anos) disponível em `otimizar(robusto_beta=...)`.
- `otimizar_com_incerteza`: roda o MILP `n` vezes sorteando pesos, ano de clima e lacunas (palha ~ U[0,1]) e conta com que frequência cada sequência é a ótima (`p_otima`). É o que o app usa no expander "Plano de várias safras" (3 a 8 safras, 150 sorteios; `mvp.calcular_plano`).
- Leitura honesta (`experimentos/milp/RESULTADO.md`): o MILP **não reduz o empate técnico** e não prova que a sequência é melhor na prática; o ótimo depende dos pesos e das lacunas (a palha domina a nota). Serve para horizonte longo, regras duras e checagem de viabilidade. Rotulado como proposta.

### e.8 Indicador da chuva da quadra (`src/app/quadra.py`)
Chuva de fev–mai por ano (exige ≥ 100 dias com dado), média, desvio, anos secos (< 80% da média do local) e úmidos (> 120%). Relação com o rendimento municipal do IBGE (PAM 2015–2023; milho, feijão, mandioca; municípios com ≥ 5 anos): variação do rendimento em quadra seca/úmida e R². Milho: R² 0,31 (`experimentos/novas_fontes/RESULTADO.md`). É associação histórica, não previsão da próxima quadra (a previsão sazonal oficial é da FUNCEME).

### e.9 Cenário de clima (tela 4, `mvp.cenario_clima`)
Variação uniforme (chuva 70% a 130%, temperatura +0 a +3 °C, todos os dias) aplicada à série diária e **recalcula o motor de ciclo**; compara adequação, anos viáveis, melhor início e situação (histórico → cenário) das 3 estratégias, e avisa **extrapolação** quando o ciclo sai do intervalo visto no local. Não é previsão de clima nem usa o modelo de NDVI.

### e.10 Solo estimado
`mvp.solo_estimado` lê `solo.parquet` e devolve argila, areia, silte, carbono orgânico, pH e a classe de textura (média das 3 camadas, 0–30 cm), com aviso de que é estimativa de mapa global. Sem pixel válido: lacuna. A textura informada pelo agricultor prevalece (testado).

### e.11 Outros arquivos de `src/culturas/`
`sensibilidade.py` (material de apoio sobre pesos; **descreve o motor antigo**, perfil anual e desempate alfabético; resultado em `data/processed/sensibilidade_pesos.json` e `docs/06`); `construir_tabela.py` (gera a tabela de culturas).

## (f) RAG e camada LLM

### f.1 RAG (`src/rag/`)
- `rag_docs.py`: extrai o texto de cada PDF por `pdftotext` (poppler), página a página, com **uma** normalização (espaços e quebras viram um espaço). Trechos de ~600 caracteres (máx. 1.000; mínimo 120; descarta tabelas numéricas por fração de letras < 0,65). Cada trecho é **substring verificável** da página (`pagina` 1-based = página física). Recusa PDF cujo sha256 difere do `manifesto.json`. Grava `indice/trechos.jsonl`, `meta.json` e, se possível, `embeddings.npy`.
- `busca.py`: **BM25 próprio** + embeddings `intfloat/multilingual-e5-small`, fundidos por RRF; reranking opcional por cross-encoder multilingue (`mmarco-mMiniLMv2-L12-H384-v1`, ~470 MB na 1ª vez). **Portão lexical**: um trecho só sai se ≥ 60% dos radicais da pergunta aparecem nele, ou cosseno ≥ 0,87; nada passa => `sem evidência`. Sem embeddings, cai para BM25 puro.
- `src/pipeline/gerar_cenarios.py` (`evidencias`): consulta o RAG por cultura e critério e só mantém o trecho que cita a cultura e um termo do critério. O app **não** consulta o RAG ao vivo: lê `data/processed/mvp/evidencias_rag.json` (pré-calculado, ~9 min).
- Qualidade (declarada na tela e em `docs/11`, `docs/15`): acerto top-5 de 54% numa avaliação de 13 perguntas (meta 80%); 80% em 25 perguntas de teste (frágil); 0% em perguntas PT sobre documentos EN; só 43 de 80 pares cultura-critério têm algum trecho. Os trechos podem não confirmar o valor da tabela: a tela avisa.

### f.2 Camada LLM (`src/llm/`)
- **O LLM nunca calcula, escolhe rotação nem prevê clima**: só reescreve em português simples o JSON do cenário + trechos numerados `[n]`. Sem LangChain.
- `provedores.py`: interface `gerar(sistema, usuario)`; `Stub` (determinístico, para teste) e `DeepSeek` (`deepseek-flash` por padrão, `DEEPSEEK_MODEL` sobrescreve; `temperature=0`, `thinking` desligado, `max_tokens=900`; sem `DEEPSEEK_API_KEY` => `ProvedorIndisponivel` e o serviço usa o template). Escolha por `SULCO_LLM`.
- `servico.py`: `reescrever(cenario, trechos)` e `responder(pergunta)`; saída `{texto, origem: llm|template|sem_evidencia|recusa, motivos, provedor, em_cache}`. Prompt de sistema fixo; trechos e pergunta entram em blocos delimitados como DADOS; sem trechos => não chama o LLM e responde `sem evidência`.
- `verificador.py` (sem LLM): barra o texto se algum número não aparece **exatamente** na fonte (tolera `0,35`/`0.35`; arredondamento só com casas decimais), se número por extenso não está na fonte, se `[n]` não existe, se falta citação, se há promessa proibida (rende mais, garante, lucro, aumenta a renda, 100%...), se falta "a avaliar com técnico local" ou se passa de 3.000 caracteres. Falhou: **descarta e devolve o template** (`src.app.logica.explicar`). Limite: não verifica a verdade semântica de uma frase.
- `seguranca.py`: recusa pedido com padrão de injeção ou de previsão de clima/escolha de rotação sem chamar o LLM; remove delimitadores; descarta trecho de PDF com cara de instrução; remove lat/lon e identificação do JSON e redige e-mail/CPF/telefone da pergunta. O nome do município e a pergunta ainda iriam à API externa (decisão do usuário aberta).
- `cache.py`: cache em disco por hash (`data/processed/llm_cache/`) para o demo offline (`offline=True` só lê o cache).
- **Estado**: pronto e testado com provedor falso; nunca chamou a API real; não integrado ao app/API; sem cache de demo; IDs de modelo a verificar (`docs/14_LLM.md`). Hoje o texto da tela vem de **templates** sobre números de arquivos (`src/app/logica.py`).

## (g) API FastAPI e app Streamlit

### g.1 API (`src/api/main.py`, `docs/12_API.md`)
Só lê arquivos locais; lacuna = campo `lacuna`/`lacunas`; schema de entrada estrito (`extra="forbid"`: campo desconhecido = 422); header `X-Latencia-ms` em toda resposta.
| Endpoint | Estado |
|---|---|
| `GET /saude` | pronto (arquivos presentes e latências por rota) |
| `GET /municipios` | pronto (195 pontos) |
| `GET /diagnostico/{ponto_id}` | pronto |
| `POST /cenarios` | pronto (motor de ciclo + Monte Carlo; prioridade `sem/agua/solo/renda`; evidências do cache) |
| `GET /evidencias?q=` | pronto, lento na 1ª chamada (~28 s: carrega embeddings e reranker; depois ~8 s); 503 com LACUNA se índice ausente |
| `GET /limites` | pronto (lê `data/processed/modelos/metricas.json` e `relatorio_modelos.md`) |
| `GET /modelo/previsao/{ponto_id}` | **501** (não implementado; resposta traz `lacuna`) |
Não inclui: cenário de clima, rotação em 3 safras, plano MILP, ZARC (o `POST /cenarios` usa o motor com ZARC desligado), LLM.

### g.2 App Streamlit (`src/app/app.py`, lógica em `mvp.py`/`logica.py`/`quadra.py`; roteiro de demo em `docs/11_MVP.md`)
Páginas: **Meu local**, **Glossário**, **Limites dos dados**. Seções da página "Meu local":
1. **Entradas**: mapa clicável (pydeck) ou lista de 195 locais; cultura atual (16); prioridade (sem, economizar água, proteger o solo, renda extra [lacuna]). Aviso fixo de que o satélite não enxerga o talhão.
2. **O que os satélites mostram** (diagnóstico real pré-calculado): quando o campo costuma ficar nu, quando a vegetação mais sofre, estação chuvosa e veranicos, vulnerabilidade da cultura atual (ciclo cruzado com solo nu/estresse), tendências, confiança e lacunas.
2b. **Chuva da quadra (fev–mai) e rendimento** (IBGE).
3. **Três caminhos** (atual + 2 alternativas) do motor: por quê (cada critério com dado e fonte), benefícios, lacunas, riscos, evidência do acervo (ou "sem evidência"), melhor época, faixa, P(top-3), empate técnico e cobertura.
3b. **Rotação em 3 safras**: entradas opcionais do agricultor (2ª e 3ª safra da rotação atual, textura e matéria orgânica; se não informar a textura, usa a estimada pelo SoilGrids), caixa "Usar as datas do ZARC" (ligada por padrão) e, em expander, o **plano de várias safras (MILP)** com botão "Calcular o plano".
4. **E se a chuva ou a temperatura forem diferentes?**: dois controles; recalcula o motor.

**Calculado ao vivo** (cache `st.cache_resource` por seleção): motor de ciclo + Monte Carlo (~0,25 a 0,55 s), rotação de 3 safras (3.000 sorteios), plano MILP (sob demanda), cenário de clima. Tempos medidos: 1ª abertura ~6 s; trocar local ~1,2 s; o teste exige < 5 s por seleção (`docs/11`).
**Pré-calculado e lido de arquivo**: diagnóstico (`data/processed/diagnostico/`), evidências do RAG e auditoria das alternativas (`data/processed/mvp/`), métricas e relatório (`data/processed/modelos/` e `relatorio_modelos.md` da raiz), solo, PAM, ZARC, clima.
Sem internet o mapa pode ficar sem fundo (os pontos aparecem e são clicáveis; a lista funciona sempre).

## (h) Regras de ouro e como cada uma é garantida

| Regra | Como é garantida (código e testes) |
|---|---|
| **Nenhum número inventado** | A tabela de culturas só aceita valor com fonte, URL, página e trecho que contém o número (`tabela_culturas.validar`; `tests/test_culturas.py`: `test_todo_valor_verificado_tem_fonte_url_pagina_trecho`, `test_valor_do_estudo_aparece_na_tabela`, `test_nenhum_numero_hardcoded_de_cultura_no_motor`). A explicação da tela usa só valores do JSON (`test_app.py: test_explicacao_so_com_valores_do_json`; `test_mvp.py: test_numeros_de_limites_vem_do_arquivo`). O RAG devolve só substring verificável da página (`test_rag.py: test_todo_trecho_e_substring_da_pagina_correta`). O LLM passa por verificador de números (`test_llm.py`). `validar_cenario` exige fonte+URL+página em toda nota. Métricas de dados sintéticos nunca saem (`test_cenarios.py: test_relatorio_sintetico_nao_tem_metricas`). |
| **Lacuna visível** | Dado ausente vira `lacuna` (nunca preenchido): `test_janela_com_dado_faltante_e_descartada_nao_preenchida`, `test_indeterminada_sem_ciclo_ou_sem_faixa_fica_visivel`, `test_lacuna_nao_e_removida_nem_premiada` (`test_incerteza.py`), `test_sem_dado_vira_lacuna` (`test_app.py`), `test_sem_cache_de_evidencias_vira_lacuna` e `test_renda_nao_altera_o_ranking_e_vira_lacuna` (`test_mvp.py`), `test_calibracao_insuficiente_vira_lacuna_sem_numero` (`test_cenarios.py`). Extrapolação não devolve número (`test_extrapolacao_nao_devolve_numero`). |
| **Apoio, não decisão** | Texto fixo "Cenário a avaliar com técnico local" em todo cenário (`validar_cenario` falha sem ele), na tela, na API e no verificador do LLM. Empate técnico é declarado em vez de inventar 1º e 2º (`test_tres_estrategias_atual_primeiro_e_empate_sem_posicao_falsa`, `test_empate_nao_e_alfabetico_renomear_ids_nao_muda_escolha`). O LLM recusa pedido de "qual rotação devo escolher" (`test_fora_de_escopo`). |
| **Sem vazamento do futuro** | Features só com dias anteriores (`test_features.py`), alteração do NDVI do holdout não muda o treino (`test_cenarios.py: test_mudar_ndvi_do_holdout_nao_altera_metricas_do_treino`), placebo e walk-forward (`test_walkforward.py`), igualdade produção x validação (`test_persistencia.py`), ACI sem anos futuros (`test_cenarios.py: test_faixa_aci_nao_depende_de_anos_futuros_ao_de_referencia`). CV aleatória barrada por teste que lê o código. |
| **App offline** | O app e a API só leem arquivos locais; nenhuma chamada a API de dados em `src/app` nem `src/api` (a coleta é fase A). Teste de tela sem exceção e de tempo de resposta (`test_mvp.py: test_app_fluxo_completo_sem_excecao`, `test_resposta_por_selecao_abaixo_de_5_segundos`). O LLM tem modo `offline=True` (só cache). |
| **Nenhum dado sensível a API externa** | `seguranca.sanear_json` e `redigir_pergunta` (`test_llm.py: test_dados_sensiveis_nao_vao_na_requisicao`, `test_redigir_pergunta`). Aberto: nome do município ainda iria à API (decisão do usuário). |
| **Reprodutibilidade** | Sementes fixas (`config.yaml: semente 42`; Monte Carlo 20241112), `n_jobs=1`; testes de reprodutibilidade de conformal, SMAA e ACI. |
| **`.env` nunca commitado** | `.gitignore`; `test_llm.py: test_chave_lida_do_env_arquivo` usa arquivo temporário. |

Contagem de testes: 324 coletados em 2026-11-13 (`.venv/Scripts/python -m pytest --collect-only -q`). `tests/test_rag.py` e parte de `tests/test_app.py`/`test_api.py` são pesados (modelos de embeddings); ver (j).

## (i) Mapa de arquivos

### Raiz
`config.yaml` (parâmetros de modelos, coleta, 195 pontos, walk-forward); `requirements.txt` (versões fixas); `relatorio_modelos.md` (relatório da raiz; **desatualizado**, ver (j)); `README.md`; `docs_rag/` (31 PDFs + `manifesto.json`); `scripts/setup.sh` (prepara ambiente em Linux/Mac/Git Bash) e `scripts/verificar_ambiente.py` (só confere o que falta); `coleta_*.log` (ignorados); `tests/`; `experimentos/`; `data/`.

### `src/coleta/`
`power.py` clima; `modis_ornl.py` NDVI (em uso); `modis.py` NDVI via AppEEARS (abandonado); `smap.py` umidade do solo; `sidra.py` PAM/IBGE; `srtm.py` terreno; `solo.py` SoilGrids; `zarc.py` ZARC do CE; `ibge_codigos.py` código IBGE dos pontos.

### `src/modelos/`
`entrada.py` config e validação; `sintetico.py` dados de teste; `diagnostico.py` diagnóstico por local; `features.py` features, alvo e persistência; `preditivo.py` Ridge/XGBoost/conformal split/decisão; `conformal_aci.py` ACI por estação; `cenarios.py` sensibilidade (não usado pelo app); `walkforward.py` validação com placebo, Bonferroni e confirmação selada; `relatorio.py` gera `relatorio_modelos.md`.

### `src/culturas/`
`tabela_culturas.py` leitura e validação da tabela; `construir_tabela.py` gera a tabela; `parametros.py` suposições (`Parametros`); `ciclo.py` adequação no ciclo; `zarc.py` janela ZARC e janela aproximada; `motor.py` viabilidade, critérios, ranking, cenários; `incerteza.py` Monte Carlo SMAA-2; `rotacao.py` rotação em 3 safras; `rotacao_milp.py` MILP e MILP com incerteza; `sensibilidade.py` sensibilidade dos pesos (motor antigo).

### `src/rag/`, `src/llm/`, `src/pipeline/`, `src/api/`, `src/app/`
`rag/rag_docs.py` extração e índice; `rag/busca.py` BM25+embeddings+portão+reranker. `llm/provedores.py`, `servico.py`, `verificador.py`, `seguranca.py`, `cache.py`. `pipeline/gerar_cenarios.py` gera cenários JSON em `data/processed/cenarios/` (CLI com `--cultura-atual`, `--ciclo-modo`, `--chuva-modo`, `--risco-max`, `--passo-inicio`, `--n-sorteios`, `--semente`) e contém a função `evidencias`; `pipeline/comparar_cenarios.py` compara os JSON entre locais. `api/main.py` FastAPI. `app/app.py` telas; `app/mvp.py` lógica do MVP; `app/logica.py` leitura de cenários/relatório e templates de explicação; `app/quadra.py` indicador da quadra; `app/precalculo.py` pré-cálculos (`evidencias`, `auditoria`, `tudo`).

### `data/`
`data/culturas/tabela_culturas.csv`; `data/processed/` (clima_diario, ndvi_16d, umidade_solo, pam_ce, solo, terreno, zarc_ce, zarc_manifesto, pontos.csv, sensibilidade_pesos.json, `diagnostico/`, `modelos/`, `mvp/`, `cenarios/`); `data/raw/` (ver (b)).

### `experimentos/`
Cada pasta tem scripts e, quando concluída, `RESULTADO.md`: `avaliacao_195` (avaliação com 195 pontos), `conformal_A1` (cobertura, ACI), `ensemble`, `expA_chirps` (CHIRPS, sem ganho), `expB_indices` (EVI/SAVI, interrompido), `expC_features` (16 variantes de features), `milp`, `novas_fontes` (terreno, índices, NDVI x PAM), `overfit_underfit`, `previsao_doc09` (horizonte e ERA5-Land, interrompidos), `zarc`, `ceara_selecao` (como os pontos do CE foram escolhidos), `dados13` (instantâneo dos 13 pontos antigos).

### `docs/`
`00_STATUS` estado; `01_VISAO_GERAL` problema e regras; `02_MODULO_MODELOS`; `03_SUPOSICOES_E_DECISOES` (D1–D58); `04_RETOMADA`; `05_EXPERIMENTOS`; `06_PESOS_E_CULTURAS` (motor antigo); `07`–`09` pesquisas; `10_MOTOR_CICLO_E_INCERTEZA`; `11_MVP`; `12_API`; `13_ZARC`; `14_LLM`; `15_PENDENCIAS`; `16_PESQUISA`; `17_PITCH`; **`18_ARQUITETURA_TECNICA` (este arquivo)**.

## (j) Como reproduzir cada etapa

Use `.venv/bin/python` (Linux/Mac) ou `.venv/Scripts/python` (Windows). Todos os comandos rodam da raiz do repositório.

| Etapa | Comando | Notas |
|---|---|---|
| Ambiente | `python -m venv .venv` e `.venv/.../python -m pip install -r requirements.txt` (ou `bash scripts/setup.sh`) | Python 3.14 foi o usado. `torch` só para o RAG semântico. `setup.sh` usa `.venv/bin/`: no Windows rode os passos à mão ou use Git Bash/WSL. |
| Coleta de clima | `python -m src.coleta.power` | Idempotente. **Atenção**: regrava `data/processed/pontos.csv` sem a coluna `ibge`; depois rode `python -m src.coleta.ibge_codigos`. |
| Coleta de NDVI | `python -m src.coleta.modis_ornl --workers 16` (progresso: `--status`) | Retoma do cache; grava `ndvi_16d.parquet`. |
| Coleta de SMAP | `python -m src.coleta.smap` (`--limite N`, `--parcial`) | Exige Earthdata no `.env`. |
| Códigos IBGE | `python -m src.coleta.ibge_codigos` (`--dry-run`) | |
| PAM/IBGE | `python -m src.coleta.sidra` | |
| ZARC | `python -m src.coleta.zarc` | |
| Solo | `python -m src.coleta.solo` | Precisa de `rasterio`. |
| Terreno | `python -m src.coleta.srtm` | Baixa ~700 MB de tiles. |
| Tabela de culturas | `python -m src.culturas.tabela_culturas` (valida) | Gerar de novo: `python -m src.culturas.construir_tabela --ecocrop <EcoCrop_DB.csv>`. |
| Diagnóstico real | `python -m src.modelos.diagnostico` | O CLI grava em `data/processed/modelos/`; o app lê `data/processed/diagnostico/`. Para regerar o do app use o trecho de `docs/11_MVP.md` seção 1 (~80 s). |
| Preditivo | `python -m src.modelos.preditivo` (`--sem-persistencia`, `--com-smap`) | Grava `metricas.json` e `relatorio_modelos.md` em `data/processed/modelos/`. Faça backup antes (ficou `*.bak_pre_D52` no passado). |
| Walk-forward | `python -m src.modelos.walkforward --variantes base,persistencia [--placebo]` | **Imprime também 2022–2024**: para escolher variantes novas, siga a regra de só olhar 2010–2021 (como fez `experimentos/avaliacao_195/avaliar.py`). |
| Cenários em JSON | `python -m src.pipeline.gerar_cenarios --cultura-atual milho` e `python -m src.pipeline.comparar_cenarios` | |
| Índice do RAG | `python -m src.rag.rag_docs` | Precisa de `pdftotext`; baixa o modelo de embeddings na 1ª vez. |
| Pré-cálculos do app | `python -m src.app.precalculo evidencias` (~9 min), `auditoria` (~2,5 min), `tudo` | Só regerar se mudar motor, tabela ou RAG. |
| Sensibilidade dos pesos | `python -m src.culturas.sensibilidade` | Descreve o motor antigo. |
| App | `streamlit run src/app/app.py` | Abrir uma vez antes da demo. |
| API | `uvicorn src.api.main:app --port 8000` | Docs em `/docs`. |
| Testes | `python -m pytest -q -W error` | `tests/test_rag.py` leva ~7 min; `tests/test_api.py` ~15 s; rodar por partes. |
| Conferir ambiente | `python scripts/verificar_ambiente.py` | Só lê. |

## Limites e inconsistências conhecidas da implementação (para não surpreender ninguém)
- A página "Limites dos dados" lê `relatorio_modelos.md` **da raiz** (`logica.caminho_relatorio`), que é o relatório antigo de 13 pontos (Ridge sem persistência, skill -0,021 no holdout). A API lê `data/processed/modelos/relatorio_modelos.md` (atual: persistência, XGBoost +0,284). Os dois arquivos diferem; a tela pode mostrar o número velho. Ver `docs/15_PENDENCIAS.md`.
- A mesma página afirma que "não há dado de ... solo ... nem zoneamento (ZARC)": desatualizado, pois ZARC e solo estimado já entram no app.
- `docs/06_PESOS_E_CULTURAS.md` e `src/culturas/sensibilidade.py` descrevem o motor antigo.
- O valor da produção do IBGE (variável 215) e o terreno SRTM estão nos dados e fora das notas e do app.
