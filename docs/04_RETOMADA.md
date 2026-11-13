# Como retomar o trabalho em outro computador

Atualizado em 2026-11-12 (21h20). Tudo foi parado de propósito e commitado. **Nada fica rodando em segundo plano.**
Leia também: `docs/15_PENDENCIAS.md` (o que falta, em ordem) e `docs/00_STATUS.md` (estado).

## 1. Preparar o ambiente (5 a 15 min)
```
git clone git@github.com:NatanBack77/sulco-nasa.git && cd sulco-nasa
bash scripts/setup.sh              # cria .venv, instala requirements.txt, extrai os caches, confere o ambiente
bash scripts/setup.sh --rag        # (opcional) reconstrói o índice do RAG; precisa de pdftotext (poppler)
bash scripts/setup.sh --testes     # (opcional) roda a suíte inteira (a parte do RAG leva ~7 min)
.venv/bin/python scripts/verificar_ambiente.py   # só confere; diz o que falta
```
Windows: use Git Bash ou WSL (o script é bash). Python 3.14 foi o usado; 3.11+ deve servir.
- `torch==2.15.0` é só para o RAG semântico; sem ele a busca cai para BM25. Para CPU: `--index-url https://download.pytorch.org/whl/cpu`.
- **`.env` NÃO está no repositório.** Crie na raiz:
  ```
  EARTHDATA_USERNAME=<usuario>
  EARTHDATA_PASSWORD='<senha>'
  DEEPSEEK_API_KEY=<chave>      # só quando for ligar a camada LLM
  ```
  A senha do Earthdata foi digitada numa conversa com o assistente: **troque-a** no site do Earthdata.
- Caches versionados como `.tar.gz`: `data/raw/smap_cache.tar.gz` (61 MB) e `data/raw/power_cache.tar.gz` (27 MB); o `setup.sh` extrai.
  O cache do NDVI (`data/raw/modis_ornl/`, 21.840 arquivos) já vem como arquivos comuns.

## 2. Rodar o que existe
```
.venv/bin/streamlit run src/app/app.py        # MVP (abra uma vez antes da demo: a 1ª abertura leva ~6 s)
.venv/bin/uvicorn src.api.main:app --port 8000 # back-end (ver docs/12_API.md)
.venv/bin/python -m pytest -q -W error        # suíte; tests/test_rag.py sozinho leva ~7 min
```
Pré-cálculos do MVP (já gravados em `data/processed/mvp/`; regerar só se mudar motor/tabela/RAG):
`python -m src.app.precalculo evidencias` (~9 min), `auditoria` (~2,5 min). Diagnóstico real: `data/processed/diagnostico/`.

## 3. Estado dos dados (2026-11-12)
| Dado | Estado | Onde |
|---|---|---|
| Pontos | **195** (184 municípios do CE + 11 de outros estados), coluna `ibge` em 194 | `data/processed/pontos.csv`, `config.yaml` |
| Clima POWER 2001–2024 | completo, 0 ausentes, 59 `celula_power` distintas | `data/processed/clima_diario.parquet` |
| NDVI MODIS (ORNL) | **completo**: 107.583 linhas, 195 pontos, 2001-01-01 a 2024-12-18; 83,2% confiáveis (conf. 0 ou 1); ausente 0,05% | `data/processed/ndvi_16d.parquet` |
| SMAP SPL4SMGP v008 | completo: 195 pontos × 3.564 dias (2015-03-31 a 2024-12-31), 0% NaN | `data/processed/umidade_solo.parquet` |
| Diagnóstico real (solo nu, estresse, estação chuvosa, veranicos, tendência) | gerado para os 195 | `data/processed/diagnostico/` |
| Métricas do preditivo (com persistência) | gravadas; backups `*.bak_pre_D52` | `data/processed/modelos/` |
| Tabela de culturas | 16 culturas, 34 lacunas (de 53) | `data/culturas/tabela_culturas.csv` |
| Acervo RAG | 31 PDFs reais, 2.689 trechos | `docs_rag/` (índice em `indice/`, reconstruir) |
| ZARC | **não baixado** | — (ver `docs/13_ZARC.md`) |

## 4. Resultados principais (todos de código rodado; detalhes nos docs citados)
- **Persistência do NDVI** (anomalia dos 2 compostos anteriores): confirmação selada 2022–2024 skill +0,239 Ridge / +0,264 XGBoost; seleção +0,309. Placebo ≈ 0. Em produção: holdout +0,257 / +0,284 (`docs/05`, `experimentos/avaliacao_195/RESULTADO.md`, `docs/03` D52).
- **Clima sozinho não supera a climatologia** (confirmação −0,044 Ridge). CHIRPS: sem ganho. SMAP: +0,007, poder baixo (seleção só 2018–2021). `pers_lags4`: ganho marginal (+0,005), não integrado.
- **Cenários de chuva/temperatura reagem pouco no preditivo** (variação ~0,002 contra RMSE ~0,07): o ganho é memória do NDVI.
- **Conformal abaixo da meta**: 76% / 87% para 80% / 90% (a própria climatologia cobre 76% / 87,5%).
- **Motor de culturas** (ciclo + Monte Carlo): municípios agora diferem, mas as alternativas seguem em **empate técnico** (mediana de 12 a 13 candidatas empatadas); o ciclo escolhido pesa mais que o município (`docs/10`, `docs/11`).
- **RAG**: top-5 80% em 25 perguntas de teste (margem grande); 0% em perguntas PT sobre documentos EN (`docs/03` D50, relatório do agente em `docs/15`).

## 5. Módulos criados nesta rodada
| Módulo | Doc | Estado |
|---|---|---|
| `src/modelos/` (persistência integrada) | `docs/02`, `docs/03` D52 | pronto; SMAP desligado por padrão (`--com-smap`) |
| `src/culturas/` (ciclo, incerteza, sensibilidade, parâmetros) | `docs/06`, `docs/10` | pronto; parâmetros são SUPOSIÇÕES |
| `src/rag/` | `docs/03` D50 | pronto; reranker (~470 MB baixados na 1ª vez) |
| `src/pipeline/` (gerar cenários) | `docs/10` | pronto |
| `src/app/` (MVP Streamlit) | `docs/11_MVP.md` | pronto; roteiro de demo dentro |
| `src/api/` (FastAPI) | `docs/12_API.md` | 6 de 7 endpoints; `/modelo/previsao` responde 501 |
| `src/llm/` (DeepSeek + verificador) | `docs/14_LLM.md` | pronto e testado com provedor falso; **nunca chamou a API real**; não integrado ao app/API |
| `src/coleta/ibge_codigos.py` | `docs/13_ZARC.md` | pronto; só a parte IBGE do ZARC |

## 6. O que fazer primeiro no outro PC
1. `bash scripts/setup.sh --testes` e confira que a suíte passa (reporte falhas, não as esconda).
2. Leia `docs/15_PENDENCIAS.md` e decida as perguntas marcadas "DECISÃO SUA".
3. Ordem sugerida: (a) ZARC (`docs/13_ZARC.md`), (b) corrigir a cobertura conformal e rodar horizonte/estação (`experimentos/previsao_doc09/`), (c) integrar `src/llm` ao app/API com a chave, (d) fonte nova de chuva/umidade (ERA5-Land/GLDAS), (e) polimento do MVP.

## 7. Contexto para o assistente (cole no início da sessão)
> Leia `docs/15_PENDENCIAS.md`, `docs/00_STATUS.md`, `docs/04_RETOMADA.md`, `docs/05_EXPERIMENTOS.md` e a memória do projeto (objetivo do SULCO e regras anti-alucinação).
> O SULCO apoia a decisão de rotação do agricultor do semiárido, não finge certeza e mostra lacunas. A previsão do NDVI é módulo de apoio.
> Regras: nenhum número sem fonte lida ou código rodado; dado ausente vira lacuna visível; resultado negativo reportado como está;
> protocolo anti-overfitting (seleção 2010–2021, confirmação selada 2022–2024 uma vez, placebo, Bonferroni com N total);
> SINTETICO nunca é resultado; nunca prometer que a rotação "rende mais"; `.env` nunca commitado; repasse as regras a todo subagente.

## 8. Cuidados conhecidos
- `pkill -f pytest` dentro de um comando que contém "pytest" mata o próprio shell; use `pgrep` + `kill <pid>`.
- Máquina de 7 GB: não rode mais de 2 processos pesados (walk-forward, reranker, preditivo) ao mesmo tempo.
- O `ls` do usuário pode estar aliasado (use `\command ls` em scripts).
- O ORNL satura em ~230 janelas/min (64 workers); mais workers não ajudam. A fase de listar datas leva ~9 min sem log.
