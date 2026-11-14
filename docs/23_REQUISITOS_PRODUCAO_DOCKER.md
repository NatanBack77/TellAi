# 23. Requisitos para rodar o SULCO em produção, em Docker

Levantamento de 2026-11-14, feito lendo `requirements.txt`, `config.yaml`, `src/` e medindo a API aqui. **Ainda não existe `Dockerfile`, `docker-compose.yml` nem `.dockerignore`** (conferido): este documento é o insumo para criá-los.
Marcas: **[MEDIDO]** número que eu medi nesta máquina; **[LIDO]** visto no código ou na doc; **[A VERIFICAR]** não confirmei; **[DECISÃO]** depende de você.

## 1. O que roda (processos)
| Serviço | Comando | Porta | Observação |
|---|---|---|---|
| **App** (Streamlit) | `streamlit run src/app/app.py` | 8501 | Interface do agricultor. 1ª abertura ~10 s, depois 0,5–1,5 s por seleção (AppTest) |
| **API** (FastAPI + Uvicorn) | `uvicorn src.api.main:app --host 0.0.0.0 --port 8000` | 8000 | Docs em `/docs`. `GET /saude` serve de healthcheck [LIDO]. Pré-aquece RAG e previsão ao subir (`SULCO_PREAQUECER=0` desliga) |
Os dois leem os mesmos arquivos e importam o mesmo código (`src/`). O app não chama a API: são independentes. **[DECISÃO]** um contêiner com os dois, ou dois contêineres da mesma imagem (recomendado: dois, para escalar e reiniciar separado).

## 2. Stack necessária
**Resumo:** Python + Streamlit + FastAPI/Uvicorn + pandas/numpy/scikit-learn/XGBoost; dados em **arquivos** (Parquet, CSV, JSON); RAG em **arquivos** (sem banco vetorial); dois modelos de linguagem pequenos do Hugging Face (opcionais). **Não precisa de banco relacional, Redis, fila, GPU nem banco vetorial.**

### 2.1 Linguagem
- Python **3.14.7** é o que o projeto usa [LIDO]. **[A VERIFICAR]** se existe imagem Docker oficial `python:3.14-slim` e se todas as rodas (wheels) do `requirements.txt` existem para ela; se não, fixar uma versão menor (3.12/3.13) e **rodar a suíte de 395 testes** antes de aceitar.

### 2.2 Bibliotecas de execução (entram na imagem)
`numpy`, `pandas`, `pyarrow`, `scipy`, `scikit-learn`, `statsmodels`, `pymannkendall`, `xgboost`, `PyYAML`, `joblib` (vem com o scikit-learn), `streamlit`, `altair`, `pydeck`, `fpdf2` (PDF do cartão; opcional), `fastapi`, `uvicorn`, `pydantic`. Versões fixas em `requirements.txt`.
**RAG semântico (opcional):** `torch` (CPU) e `sentence-transformers`. Sem eles a busca cai para BM25 (acerto menor; ver `docs/21_resultados_fases/L_R.md`). **[DECISÃO]** imagem completa (RAG semântico) ou enxuta (só BM25).
**Não entram na imagem de produção:** `earthaccess`, `h5py`, `rasterio` (só coleta de dados), `pytest`, `httpx` (só testes). Recomendo separar `requirements.txt` em `requirements-runtime.txt`, `requirements-coleta.txt` e `requirements-dev.txt` (hoje há um arquivo só).

### 2.3 Pacotes do sistema operacional
- Em execução: nenhum obrigatório que eu tenha confirmado. **[A VERIFICAR]** `libgomp1` para o XGBoost em imagens `slim`.
- Só no estágio de build do índice do RAG e nos testes: `poppler-utils` (`pdftotext`).

### 2.4 Banco vetorial: **não é necessário**
O RAG do SULCO é feito de arquivos [LIDO: `src/rag/busca.py`, `indice/`]:
- `indice/embeddings.npy` (vetores de 384 dimensões), `indice/trechos.jsonl` (3.203 trechos), `indice/meta.json`: **7,1 MB** no total [MEDIDO].
- A busca é **BM25 próprio + similaridade em numpy + reranker**, tudo em memória. Com 3.203 vetores não há ganho em Chroma, FAISS, pgvector ou Qdrant.
- O `indice/` **não é versionado** (ignorado pelo git): tem de ser gerado no build (`python -m src.rag.rag_docs`, precisa de `pdftotext` e de baixar o modelo de embeddings) ou copiado como artefato.
- **Quando passaria a precisar:** acervo na casa de centenas de milhares de trechos, várias réplicas escrevendo no índice ou busca com filtros. Hoje nenhum se aplica. **[DECISÃO]** se quiser um banco vetorial mesmo assim (por exemplo pgvector), é uma troca da camada `src/rag/busca.py`, e isso exige reavaliar o acerto do RAG.

### 2.5 Modelos do Hugging Face (só para o RAG semântico)
`intfloat/multilingual-e5-small` (embeddings da pergunta) e `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (reranker) [LIDO: `busca.py`]. São baixados na **1ª chamada** de `/evidencias` (a 1ª pergunta nova leva ~28 s sem pré-aquecimento). **Em produção: embutir os dois na imagem** (baixar no build para um diretório de cache e apontar `HF_HOME`) para não depender de internet nem de uma cota externa, e para o contêiner subir sem rede. **[A VERIFICAR]** a variável de ambiente que desliga o acesso à rede do Hugging Face (`HF_HUB_OFFLINE`) na versão fixada.

## 3. Dados que a imagem (ou volume) precisa ter
Todo o runtime lê só arquivos locais (regra do projeto: **o app nunca chama API de dados ao vivo**).
| Caminho | Tamanho [MEDIDO] | Uso |
|---|---|---|
| `data/processed/` (clima, NDVI, solo, terreno, ZARC, PAM, diagnóstico, `mvp/`, `modelos/`, `cenarios/`, `pontos.csv`) | 34 MB (sem os arquivos 2025+, que são pequenos) | leitura |
| `data/culturas/` | 0,2 MB | tabela de culturas e matriz de rotação |
| `config.yaml` | pequeno | configuração |
| `indice/` | 7,1 MB | RAG (gerado no build) |
| `docs_rag/` | 141 MB (50 PDFs) | só para o build do índice e para testes de fidelidade; o texto devolvido vem de `trechos.jsonl`. **[A VERIFICAR]** se algum trecho de código abre o PDF em runtime |
| `data/raw/` (modis, power, smap, soilgrids, srtm…) | centenas de MB | **fora da imagem**: só coleta |
`.venv` local tem 2,4 GB (inclui coleta e testes); a imagem de runtime enxuta ficará bem menor (**não medido**).
**Atualização dos dados:** hoje é manual (scripts de `src/coleta/`) e fora do contêiner. **[DECISÃO]** processo de atualização (a cada ano? a cada composto de 16 dias?) e quem o executa.

## 4. Variáveis de ambiente e segredos [LIDO]
| Variável | Para quê | Em produção |
|---|---|---|
| `SULCO_LLM_MODO` | `template` (padrão), `offline` ou `online` | `template` até haver chave |
| `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | camada LLM | **segredo** (Docker secret/variável do orquestrador); nunca na imagem nem no git |
| `SULCO_PREAQUECER` | `0` desliga o pré-aquecimento da API | `1` |
| `SULCO_DADOS_DIR`, `SULCO_MVP_DIR`, `SULCO_CENARIOS_DIR`, `SULCO_DIAGNOSTICO`, `SULCO_DIAGNOSTICO_DIR`, `SULCO_RELATORIO` | trocam os caminhos dos dados | usar para montar volume |
| `SULCO_ABERTURA_ZOOM` | animação de zoom no mapa | `0` |
| `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` | **só coleta** | **não colocar na imagem de produção** |
O `.env` nunca vai para a imagem (`.dockerignore`).

## 5. Escrita em disco em execução (precisa de volume gravável) [LIDO]
- `data/processed/modelos/cache_api_previsao.joblib`: cache do modelo de previsão da API. Se não existir ou os dados mudarem, a API **retreina na 1ª chamada** (~20 s a mais). Recomendo gerá-lo no build ou num volume persistente.
- `data/processed/llm_cache/`: cache das respostas do LLM (só com LLM ligado).
- Pré-cálculos (`python -m src.app.precalculo ...`): rodar no build, não em execução.
Sistema de arquivos raiz pode ficar **somente leitura**, com um volume gravável só para esses dois caminhos.

## 6. Recursos (dimensionamento)
- **Memória:** a API com RAG semântico e previsão aquecidos usa **~2,0 GB de RSS (pico 2,19 GB)** [MEDIDO, 40 threads]. O Streamlit **não foi medido**. Planejar **no mínimo 4 GB** para os dois serviços; sem o RAG semântico, bem menos (**não medido**).
- **CPU:** 2 vCPU são suficientes para demo; sem GPU. O reranker é o gargalo.
- **Latências medidas na API** [MEDIDO, 1 requisição cada, máquina com outros processos]: `/saude` 18 ms; `/evidencias` 1,9 s (pergunta já vista) e 7,9 s (pergunta nova); `/modelo/previsao/{id}` 0,16 s com cache; `/cenarios` 3,1 s. Pré-aquecimento: RAG ~22 s e previsão ~10 s após subir; o contêiner deve esperar o `/saude` indicar `aquecimento` concluído antes de receber tráfego (readiness).
- **Concorrência:** não testei carga. O XGBoost e o Monte Carlo rodam no processo da API; muitas requisições simultâneas de `/cenarios` competem por CPU. **[A VERIFICAR]** com teste de carga antes de abrir ao público.

## 7. Rede e segurança
- **Saída de rede em execução:** nenhuma obrigatória. Opcional: DeepSeek (se `online`) e, só se os modelos do Hugging Face não forem embutidos, o próprio Hugging Face. Coleta de dados (POWER, ORNL, Earthdata, IBGE, SoilGrids) **não roda em produção**.
- **O mapa do app** usa a camada de fundo do navegador do usuário, que precisa de internet no cliente; sem ela só aparecem os pontos (há opção de fundo liso).
- **A API não tem autenticação, CORS configurado nem limite de taxa** (procurei no código: não achei). **[DECISÃO]** colocar atrás de proxy reverso com TLS (Nginx/Traefik/Caddy), limitar a taxa, restringir `/docs` e decidir quem pode chamar. O app Streamlit também não tem login.
- **LLM:** o que vai à API externa é nome do município e a pergunta (lat/lon e dados pessoais já são removidos). **[DECISÃO]** aceitável? (DU10 em `docs/15`.)
- Rodar o contêiner como usuário **não-root**; sem `.env`; imagem sem `earthaccess`.

## 8. Saúde, logs e observabilidade
- Healthcheck da API: `GET /saude` (arquivos presentes, n de pontos, estado do aquecimento, cache do modelo, latências). Todas as respostas trazem `X-Latencia-ms`.
- Healthcheck do Streamlit: **[A VERIFICAR]** o endpoint nativo (`/_stcore/health`) na versão 1.67.
- Logs: saída padrão (stdout) dos dois processos; não há logging estruturado. **[DECISÃO]** destino e retenção. Nenhuma métrica Prometheus existe.

## 9. Build e CI
1. Estágio de build: instalar dependências, baixar os 2 modelos, rodar `python -m src.rag.rag_docs` (exige `poppler-utils`), gerar o cache da previsão.
2. Estágio final: copiar só `src/`, `config.yaml`, `data/processed`, `data/culturas`, `indice/`, e (se necessário) `docs_rag/`.
3. CI: suíte por partes (395 testes passam hoje; `tests/test_rag.py` leva ~7 min e precisa de `indice/` e `pdftotext`; os testes de tempo são sensíveis à carga).
4. `.dockerignore`: `.git`, `.venv`, `.env`, `data/raw`, `experimentos`, `tests`, `*.pkl`, `*.pq`.

## 10. Riscos e lacunas para a produção
- Sem teste de carga, sem autenticação e sem monitoramento.
- Python 3.14: confirmar imagem e rodas.
- O produto **nunca foi validado com técnico/agricultor**; em produção pública, manter os avisos "a avaliar com técnico local" e a página "Limites dos dados".
- A camada LLM nunca chamou a API real; só ligar com a chave e o cache de demo pré-gerado.
- Os dados envelhecem: o clima vai até 2024-12 (e 2025+ em arquivos à parte), e o NDVI até 2026-10 em `ndvi_2025plus.parquet`; o modelo em produção usa treino até 2021 mais holdout 2022–24.

## 11. Próximos passos sugeridos
1. Separar o `requirements.txt` em runtime, coleta e dev.
2. Escrever `Dockerfile` (multi-stage), `.dockerignore` e `docker-compose.yml` (api + app + volume de cache) e **testar o build do zero**.
3. Medir memória do Streamlit e carga na API; ajustar o dimensionamento.
4. Decidir as **[DECISÃO]** acima (1 ou 2 contêineres, RAG semântico ou só BM25, proxy/TLS, LLM sim ou não).
