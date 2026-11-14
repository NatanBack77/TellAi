# Como retomar o trabalho em outro computador

> **Nota 2026-11-13 (noite):** tudo da rodada está commitado e no GitHub. Para o estado atual e o que falta, leia `docs/00_STATUS.md` e `docs/15_PENDENCIAS.md` (nota de topo); resultados por fase em `docs/21_resultados_fases/`. Arquivos que NÃO vêm no clone: `.env`, `.venv/`, `indice/` (reconstruir: `python -m src.rag.rag_docs`), `experimentos/**/*.pkl` e `*.pq`. O cache do ERA5 vem como `data/raw/era5land_cache.tar.gz` (extrair: `tar xzf data/raw/era5land_cache.tar.gz -C data/raw`); os caches brutos de 2025+ (`data/raw/modis_ornl_2025plus/`, `power_2025plus/`) não vão ao git (os parquets processados vão).

Atualizado em 2026-11-13. Nada fica rodando em segundo plano. Leia junto: `docs/18_ARQUITETURA_TECNICA.md` (como tudo funciona), `docs/15_PENDENCIAS.md` (o que falta), `docs/00_STATUS.md` (estado), `docs/19_ALINHAMENTO_AO_DESAFIO.md` (lacunas frente ao desafio).

## 1. Pré-requisitos
- **Python 3.14** foi o usado (3.14.7); 3.11+ deve servir (não verificado nas versões intermediárias). Os pacotes têm versão fixa em `requirements.txt` e podem não ter wheel para outros Pythons.
- **`pdftotext` (poppler)**: só para reconstruir o índice do RAG (`python -m src.rag.rag_docs`). Windows: instalar o poppler e pôr no PATH; Linux: `apt install poppler-utils`; Mac: `brew install poppler`.
- **`rasterio==1.5.2`** já está em `requirements.txt` (usado só pela coleta de solo, `src/coleta/solo.py`).
- `torch==2.15.0` e `sentence-transformers` são só para o RAG semântico; sem eles a busca cai para BM25. Para CPU: `--index-url https://download.pytorch.org/whl/cpu`.
- Conta Earthdata **só** se for recoletar SMAP (`src/coleta/smap.py`). POWER, ORNL (NDVI), SIDRA, SRTM, SoilGrids, ZARC e IBGE são públicos.
- Máquina da rodada anterior: 7 GB de RAM; não rode mais de 2 processos pesados (walk-forward, reranker, preditivo) ao mesmo tempo.

## 2. Clonar e preparar
```
git clone git@github.com:NatanBack77/sulco-nasa.git && cd sulco-nasa
python -m venv .venv
# Linux/Mac:  .venv/bin/python -m pip install -r requirements.txt
# Windows:    .venv/Scripts/python -m pip install -r requirements.txt
```
Atalho (Linux/Mac, ou Git Bash/WSL no Windows): `bash scripts/setup.sh` cria o venv, instala, extrai os caches `.tar.gz` e confere o ambiente; `--rag` reconstrói o índice do RAG; `--testes` roda a suíte. O script usa `.venv/bin/python`; no Windows puro faça os passos à mão.
Conferir o ambiente (só lê): `python scripts/verificar_ambiente.py`.

**`.env` NÃO está no repositório** (nunca commitar). Crie na raiz só o que for usar:
```
EARTHDATA_USERNAME=<usuario>
EARTHDATA_PASSWORD='<senha>'
DEEPSEEK_API_KEY=<chave>      # só quando for ligar a camada LLM
```
A senha do Earthdata foi digitada numa conversa com o assistente: **troque-a** no site do Earthdata antes de usar.

## 3. O que vem no git e o que NÃO vem
| Vem no git | NÃO vem (e como refazer) |
|---|---|
| Código, `config.yaml`, `requirements.txt`, `docs/`, `tests/`, `experimentos/` (scripts e `RESULTADO.md`) | `.env` (criar à mão) |
| `data/processed/`: `clima_diario`, `ndvi_16d`, `umidade_solo`, `pam_ce`, `solo`, `terreno`, `zarc_ce` (parquet), `zarc_manifesto.json`, `pontos.csv`, `sensibilidade_pesos.json`, `diagnostico/`, `mvp/`, `cenarios/`, `modelos/metricas.json` e `modelos/relatorio_modelos.md` | outros arquivos de `data/processed/modelos/` (`anomalias.parquet`, `diagnostico.json`): regerar com `python -m src.modelos.preditivo` / `diagnostico` |
| `data/raw/modis_ornl/` (21.840 JSON, ~97 MB), `data/raw/indices/` (Niño 3.4, TNA, TSA), `data/raw/power/`, `data/raw/soilgrids/`, `data/raw/zarc/` (dicionário) e **`data/raw/srtm_tiles.tar.gz.part-00..02`** (28 tiles SRTM, 709 MB compactados em 231 MB; restaurar com `cat data/raw/srtm_tiles.tar.gz.part-* | tar -xz -C data/raw`) | `data/raw/smap/` e `data/raw/modis/` (a tarefa antiga do AppEEARS); `.venv/`, `.env`, `indice/` e `data/processed/sintetico/` |
| `data/raw/power_cache.tar.gz` (27 MB) e `data/raw/smap_cache.tar.gz` (61 MB); `scripts/setup.sh` extrai | `indice/` do RAG (ignorado): `python -m src.rag.rag_docs` (precisa de `pdftotext`; baixa o modelo de embeddings na 1ª vez; a suíte do RAG leva ~7 min) |
| `data/culturas/tabela_culturas.csv`, `docs_rag/` (31 PDFs + `manifesto.json`) | `experimentos/**/*.pkl` (ex.: `t1_linhas.pkl`, 46 MB), `coleta_*.log`, `data/processed/sintetico/` |

Como refazer os caches ignorados (tempos só quando documentados): POWER `python -m src.coleta.power` (cache em `data/raw/power/`, ou extraia `power_cache.tar.gz`); NDVI `python -m src.coleta.modis_ornl --workers 16` (já vem no git; a coleta de 195 pontos teve fase de listagem de ~10 min e ~190 a 250 janelas/min; para 59 pontos estimou-se 35 a 60 min); SMAP extraia `smap_cache.tar.gz` (recoletar exige Earthdata; tempo não documentado); SRTM `python -m src.coleta.srtm` e SoilGrids `python -m src.coleta.solo` (tempos não documentados; os `.parquet` já vêm no git, então só refaça se precisar); ZARC `python -m src.coleta.zarc` (o parquet já vem no git).

## 3b. Inventário dos dados no repositório (conferido em 2026-11-13, arquivo por arquivo contra o git)
Conferência feita com `git ls-files` contra o disco do computador onde o push foi feito (commit `ed5af7df`). Contagens iguais = tudo enviado.

**Enviado ao GitHub (disco = git):**
| Pasta ou arquivo | Arquivos | O que é |
|---|---|---|
| `data/processed/clima_diario.parquet` | 1 | clima POWER diário, 195 pontos, 2001–2024 |
| `data/processed/ndvi_16d.parquet` | 1 | NDVI MODIS 16 dias, 195 pontos |
| `data/processed/umidade_solo.parquet` | 1 | SMAP, 195 pontos |
| `data/processed/solo.parquet` | 1 | SoilGrids por ponto (areia, silte, argila, carbono orgânico, pH; 3 camadas até 30 cm) |
| `data/processed/terreno.parquet` | 1 | SRTM: altitude e declive por ponto |
| `data/processed/pam_ce.parquet` | 1 | IBGE PAM 2015–2023 (área, quantidade, rendimento, valor da produção) |
| `data/processed/zarc_ce.parquet`, `zarc_manifesto.json` | 2 | ZARC do Ceará e manifesto (URLs, sha256) |
| `data/processed/pontos.csv`, `sensibilidade_pesos.json` | 2 | pontos (com `ibge`) e sensibilidade dos pesos |
| `data/processed/cenarios/`, `diagnostico/`, `modelos/`, `mvp/` | 10, 2, 4, 2 | saídas lidas pelo app e pela API |
| `data/raw/modis_ornl/` | 21.840 | NDVI bruto (respostas do ORNL DAAC) |
| `data/raw/soilgrids/` | 15 | solo bruto, uma camada por arquivo |
| `data/raw/power/` | 59 | clima bruto do POWER (cache por ponto) |
| `data/raw/indices/` | 3 | Niño 3.4, TNA, TSA (NOAA) |
| `data/raw/zarc/` | 1 | dicionário de dados do ZARC (PDF) |
| `data/raw/srtm_tiles.tar.gz.part-00..02` | 3 | 28 tiles SRTM (709 MB) compactados em 231 MB; restaurar: `cat data/raw/srtm_tiles.tar.gz.part-* \| tar -xz -C data/raw` (testado: idêntico ao original) |
| `data/raw/power_cache.tar.gz`, `smap_cache.tar.gz` | 2 | caches compactados da rodada anterior (`scripts/setup.sh` extrai) |
| `data/culturas/tabela_culturas.csv` | 1 | tabela de culturas com fonte |
| `docs_rag/` | 31 PDFs + `manifesto.json` | acervo do RAG |

**Não enviado, de propósito (e como refazer):**
| Item | Motivo | Como refazer |
|---|---|---|
| `.env` | tem senha e chaves; nunca vai ao repositório | criar à mão (seção 2) |
| `.venv/` | 1,7 GB; é o ambiente Python | `python -m venv .venv` e `pip install -r requirements.txt` |
| `data/raw/srtm/` (28 `.hgt` soltos) | duplicado das 3 partes compactadas | comando de restauração acima |
| `data/processed/sintetico/` | dados de teste, não são resultado | `python -m src.modelos.sintetico` |
| `data/raw/modis/` | só o id de uma tarefa antiga do AppEEARS, sem uso | descartar |
| `__pycache__/`, `.pytest_cache/`, `coleta_*.log` | lixo local | não precisa |

**Não existiam no computador do push (portanto NÃO estão no GitHub):** conferir no outro computador, que fez a rodada anterior.
| Item | Para que serve | O que fazer lá |
|---|---|---|
| `indice/` (índice do RAG: embeddings e BM25) | busca nos PDFs | não precisa subir; reconstruir com `python -m src.rag.rag_docs` (precisa de `pdftotext`) |
| `experimentos/previsao_doc09/t1_linhas.pkl` (46 MB) | intermediário do teste de horizonte e estação, interrompido | só subir se quiser retomar M1 (`docs/15`); é regerável pelos scripts `t1_*.py` |
| `data/raw/smap/` (HDF5 brutos do SMAP) | origem de `umidade_solo.parquet` | não precisa subir: o resultado processado e o cache compactado já estão no git |
| qualquer coleta feita depois do último push de lá | | rodar `git status` e `git ls-files` lá |

**Como conferir e completar a partir do outro computador (antes de trabalhar):**
```
git pull --rebase origin main                      # traz tudo o que está acima
git status --short                                 # o que existe lá e ainda não foi versionado
git status --ignored --short | grep '^!!'          # o que existe lá e é ignorado de propósito
du -sh data/raw/* data/processed/* 2>/dev/null     # tamanhos
```
Se algo valioso aparecer em `git status` ou na lista de ignorados (e tiver menos de 100 MB por arquivo), adicione, comite e envie; acima de 100 MB, compacte e divida como foi feito com o SRTM: `tar -czf - -C data/raw <pasta> | split -b 90M -d - data/raw/<nome>.tar.gz.part-` (e acrescente a exceção em `.gitignore`). O GitHub avisou (GH001) que há arquivos grandes; nada passou do limite, mas, se os dados crescerem muito, considerar Git LFS ou guardar os dados fora do git.

## 4. Rodar o que existe
```
streamlit run src/app/app.py                 # MVP (abra uma vez antes da demo: a 1ª abertura leva ~6 s)
uvicorn src.api.main:app --port 8000         # back-end; docs em /docs (ver docs/12_API.md)
python -m src.modelos.diagnostico            # diagnóstico (CLI grava em data/processed/modelos/; o app lê data/processed/diagnostico/)
python -m src.modelos.preditivo              # grava metricas.json e relatorio_modelos.md (faça backup antes)
python -m src.modelos.walkforward --variantes base,persistencia [--placebo]   # ATENÇÃO: imprime também 2022-2024
```
(prefixe com `.venv/bin/python -m` ou `.venv/Scripts/python -m`; para `streamlit`/`uvicorn` use `python -m streamlit ...` / `python -m uvicorn ...`.)

Regerar pré-cálculos do app (só se mudar motor, tabela ou RAG; gravam em `data/processed/mvp/`):
```
python -m src.app.precalculo evidencias      # ~9 min (carrega embeddings)
python -m src.app.precalculo auditoria       # ~2,5 min
python -m src.app.precalculo tudo
```
Diagnóstico do app (~80 s): trecho de `docs/11_MVP.md` seção 1.

### Coletas (fase A, com internet)
```
python -m src.coleta.power                       # clima. ATENÇÃO: regrava pontos.csv e perde a coluna ibge -> rode ibge_codigos depois
python -m src.coleta.modis_ornl --workers 16     # NDVI (--status mostra o progresso)
python -m src.coleta.smap                        # umidade do solo (Earthdata no .env; --limite N, --parcial)
python -m src.coleta.ibge_codigos                # código IBGE nos pontos (--dry-run)
python -m src.coleta.sidra                       # PAM/IBGE (inclui valor da produção, variável 215)
python -m src.coleta.zarc                        # ZARC do CE
python -m src.coleta.solo                        # SoilGrids (rasterio)
python -m src.coleta.srtm                        # terreno (baixa ~700 MB)
```

### Testes
```
python -m pytest --collect-only -q | tail -3     # 324 testes coletados em 2026-11-13
python -m pytest -q -W error --ignore=tests/test_rag.py     # suíte sem a parte pesada
python -m pytest tests/test_rag.py -q -W error               # ~7 min; precisa do índice (indice/)
python -m pytest tests/test_api.py -q                        # ~15 s
```
Pesados: `tests/test_rag.py` (~7 min), testes da API que chamam `/evidencias` (carregam embeddings e reranker) e `tests/test_mvp.py` (AppTest e tempo de resposta). Nesta rodada a suíte do RAG e do LLM foi rodada separadamente. Reporte falhas, não as esconda.

## 5. Estado dos dados (2026-11-13)
| Base | Estado | Onde |
|---|---|---|
| Pontos | **completo**: 195 (184 do CE + 11 de outros estados); `ibge` em 194 (falta `sobral_ce`) | `data/processed/pontos.csv`, `config.yaml` |
| Clima POWER 2001–2024 | **completo**: 0 ausentes; 59 células distintas | `clima_diario.parquet` |
| NDVI MODIS (ORNL) | **completo**: 107.583 linhas, 195 pontos, 2001-01-01 a 2024-12-18; 83,2% confiáveis (0 ou 1); 0,05% ausente | `ndvi_16d.parquet` |
| SMAP SPL4SMGP v008 | **completo**: 195 x 3.564 dias, 0% NaN; fora do modelo por padrão | `umidade_solo.parquet` |
| Diagnóstico real | **completo** para os 195 | `data/processed/diagnostico/` |
| Métricas do preditivo | **completo** (com persistência; XGBoost escolhido) | `data/processed/modelos/` |
| Tabela de culturas | 16 culturas, **34 lacunas** de 240 linhas (parcial por natureza) | `data/culturas/tabela_culturas.csv` |
| Acervo RAG | 31 PDFs, 2.689 trechos; índice a reconstruir; acerto 54% (meta 80%) | `docs_rag/` |
| ZARC (CE) | **completo**: 108.818 linhas; ligado por padrão no app; só CE | `zarc_ce.parquet` |
| Solo (SoilGrids) | **completo**: 195 pontos (181 com pixel central válido); entra no app como estimativa | `solo.parquet` |
| PAM/IBGE | **completo**: 2015–2023, 184 municípios, 4 variáveis; valor da produção ainda sem uso | `pam_ce.parquet` |
| Terreno SRTM | **coletado**; **fora do app** | `terreno.parquet` |
| Índices NOAA | coletados à mão; só experimentos | `data/raw/indices/` |
| ERA5-Land/GLDAS, EVI/SAVI, CHIRPS (parcial) | **pendente / interrompido** | `experimentos/previsao_doc09/`, `expB_indices/`, `expA_chirps/` |
| LLM (DeepSeek) | código pronto; **nunca chamou a API real**; não integrado | `src/llm/` |
| API | 6 de 7 endpoints; `/modelo/previsao` responde 501 | `src/api/main.py` |

## 6. Resultados principais (todos de código rodado; documentos citados)
- **Persistência do NDVI** (anomalia dos 2 compostos anteriores): confirmação selada 2022–2024 skill +0,239 Ridge / +0,264 XGBoost; seleção +0,309; placebo ≈ 0 (`experimentos/avaliacao_195/RESULTADO.md`). Em produção, holdout 2022–2024: XGBoost RMSE 0,0719 contra 0,1004 da climatologia, skill +0,284 (`data/processed/modelos/metricas.json`).
- **Clima sozinho não supera a climatologia** (confirmação −0,044 Ridge). CHIRPS, terreno e índices Niño/Atlântico: sem ganho. SMAP: +0,006 a +0,007, poder baixo. Ensembles: não superam o XGBoost.
- **Conformal**: ACI por estação cobre 80,9% / 90,6% no holdout (metas 80% / 90%); pior ano (2022) 71,7% / 84,8%.
- **NDVI x rendimento (IBGE)**: R² 0,03–0,10; chuva de fev–mai explica mais (milho 0,31) (`experimentos/novas_fontes/RESULTADO.md`).
- **Motor de culturas**: municípios diferem, mas as alternativas seguem em **empate técnico** (mediana de 12 a 13 candidatas empatadas); o ciclo escolhido pesa mais que o município (`docs/10`, `docs/11`). Rotação x repetir a mesma cultura separa bem.
- **ZARC** muda as janelas de plantio de nov–dez para jan–mar em 10 municípios do CE (`experimentos/zarc/RESULTADO.md`). **MILP** não reduz o empate (`experimentos/milp/RESULTADO.md`).
- **RAG**: acerto top-5 de 54% numa avaliação de 13 perguntas; 0% em perguntas PT sobre documentos EN.

## 7. POR ONDE COMEÇAR (em ordem de prioridade; detalhes e IDs em `docs/15_PENDENCIAS.md`)
Antes de tudo: **(0)** trocar a senha do Earthdata (BL2) e rodar `python -m pytest --collect-only -q` e a suíte por partes (seção 4) para confirmar que o outro computador reproduz o estado.

1. **Erosão e infiltração como camada no mapa (A1)**: combinar declive do SRTM (`data/processed/terreno.parquet`) com textura e carbono do SoilGrids (`data/processed/solo.parquet`) em um indicador de risco por local. É o principal vazio de "saúde do solo" frente ao desafio (itens 21, 29b, 33 de `docs/19`).
2. **Evapotranspiração e balanço hídrico (A2)**: ETo por Hargreaves-Samani com Tmax, Tmin e radiação do POWER (já em `clima_diario.parquet`) e saldo chuva − ETo por quinzena; depois explicar ET e balanço no glossário (A7).
3. **Renda (A3/C9)**: receita bruta por hectare = valor da produção ÷ área colhida do IBGE (`pam_ce.parquet`, `valor_producao_mil_reais`) na prioridade "renda", com aviso de que não é lucro. Decida o recorte antes (DU13).
4. **Calor e chuva extrema (A4)**: dias com Tmax acima de um limiar e índice de chuva extrema a partir do POWER diário; o limiar é decisão sua ou de um técnico.
5. **Mapa com camadas coloridas por indicador e linha do tempo (A5)** e **entradas do agricultor: irrigado/sequeiro, água disponível, equipamento, mercado (A6)**.
6. **Decisões suas abertas (DU1–DU15)**, em especial: ciclo real e data de início, `risco_max` (0,30), pesos-base, ordem de critérios por prioridade, lista de culturas, nível de risco do ZARC (padrão 30) e mapeamento feijão comum → "Feijão 2ª Safra", `sobral_ce`, enviar o nome do município a API externa, chave DeepSeek. Elas mudam o ranking mais do que qualquer ajuste de modelo.
7. **Corrigir o que engana na tela**: `relatorio_modelos.md` da raiz está desatualizado e a página "Limites" ainda diz que não há solo nem ZARC (M12, AP3); depois valor forrageiro (A8), explicações no glossário (A7) e o registro de por que ECOSTRESS, GPM, GRACE e GEDI foram usados ou descartados (A9).
8. **Camada LLM e RAG**: com a chave, integrar `src/llm` ao app/API com cache de demo e avaliar 20 perguntas (BL1, L1–L4); melhorar o RAG (documentos Emater/INSA/portarias, tradução da pergunta) e regerar `evidencias_rag.json` (R1, R2). Depois: horizonte/estação e ERA5-Land/GLDAS (M1, M3), `/modelo/previsao` (P1).

## 8. Texto para colar no início da sessão do assistente no outro computador
> Projeto SULCO ("da órbita ao sulco"), MVP do NASA Space Apps 2026: apoio à decisão de rotação de culturas e saúde do solo no semiárido do Ceará (195 pontos, 184 municípios). Leia, nesta ordem: `docs/18_ARQUITETURA_TECNICA.md`, `docs/15_PENDENCIAS.md`, `docs/04_RETOMADA.md`, `docs/00_STATUS.md`, `docs/19_ALINHAMENTO_AO_DESAFIO.md`, `docs/05_EXPERIMENTOS.md`.
> O SULCO APOIA a conversa do agricultor com o técnico; não decide e nunca promete que a rotação rende mais. A previsão do NDVI é módulo de apoio e não dá nota às rotações.
> Regras: nenhum número sem fonte lida ou código rodado; dado ausente vira lacuna visível; resultado negativo é reportado como está; dados SINTETICO nunca são resultado; NUNCA usar 2022–2024 para escolher variantes (seleção só 2010–2021; a confirmação selada é olhada uma vez); contar o N total de variantes testadas (inclusive as descartadas) no Bonferroni e rodar o placebo; hiperparâmetros nunca ajustados olhando o teste; não commitar `.env`; não fazer commit nem push sem eu pedir; repasse estas regras a todo subagente.
> Comece pelo item 0 e depois pelo item 1 de "POR ONDE COMEÇAR" em `docs/04_RETOMADA.md`, e pergunte antes de decidir qualquer item marcado [DECISÃO SUA].

## 9. Cuidados conhecidos
- `pkill -f pytest` dentro de um comando que contém "pytest" mata o próprio shell; use `pgrep` + `kill <pid>`.
- O `ls` do usuário pode estar aliasado (use `\command ls` em scripts).
- O ORNL satura em ~230 janelas/min (64 workers); mais workers não ajudam; a fase de listar datas leva ~9 a 10 min sem log.
- `python -m src.coleta.power` sobrescreve `pontos.csv` (perde `ibge`): rode `python -m src.coleta.ibge_codigos` em seguida.
- Rodar `python -m src.modelos.preditivo` regrava `data/processed/modelos/metricas.json` e `relatorio_modelos.md` (a API e o app leem esses arquivos): faça backup antes.
