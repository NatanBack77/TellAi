# 12. API (back-end offline)

Código: `src/api/main.py` (FastAPI 0.162.5, pydantic 2.14.3, uvicorn 0.54.0, httpx 0.28.1 para os testes; fixados em `requirements.txt`).
Só lê arquivos locais. Lacuna = campo `lacuna`/lista `lacunas`/valor `null` com motivo, nunca valor padrão inventado. Texto fixo: "avaliar com técnico local".
A API NÃO copia lógica: chama por import `src/app/mvp.py` (rotação, plano, cenário de clima, solo estimado, prioridades), `src/culturas` (motor, ZARC) e `src/modelos` (previsão).

```
.venv/bin/uvicorn src.api.main:app --port 8000      # docs interativas em /docs
SULCO_PREAQUECER=0 ...                              # desliga o pré-aquecimento (padrão: ligado)
.venv/bin/python -m src.modelos.previsao            # (opcional) gera o cache do modelo de previsão antes de subir o servidor
.venv/bin/python -m pytest tests/test_api.py -q -W error   # 13 testes, ~1 min (não roda a suíte do RAG)
```

## Endpoints

| Endpoint | Estado |
|---|---|
| `GET /saude` | arquivos presentes, latências por rota (memória), estado do pré-aquecimento (`aquecimento`) e se o cache do modelo existe; header `X-Latencia-ms` em toda resposta |
| `GET /municipios` | 195 pontos: `ponto_id`, `nome` (derivado do id, sem acentos), `lat`, `lon`, `celula_power`, `ibge` (`null` = lacuna, ex.: `sobral_ce`) |
| `GET /diagnostico/{ponto_id}` | solo nu, estresse (anomalias de NDVI), estação chuvosa, veranicos, tendência, confiança, lacunas, limites |
| `POST /cenarios` | atual + 2 alternativas (motor de ciclo + Monte Carlo), contrato do doc 01 seção 7, evidências do cache; `usar_zarc` (padrão = o do app: ligado) |
| `POST /cenarios/clima` | **novo.** "E se chover X% menos / +Y °C?": `fator_chuva` 0,7–1,3 e `delta_t` 0–3 °C (mesmos limites de apresentação do app; fora = 422). Compara as MESMAS estratégias e marca `extrapolacao` quando o cenário sai do já visto (2001–2024). Não é previsão |
| `POST /rotacao` | **novo.** Rotação de 3 safras (`calcular_rotacao`): `rotacao_atual` (3 culturas, 1ª = atual), `textura`, `materia_organica`, `usar_zarc`, `n_sorteios` 100–5000 (padrão 1000; o app usa 3000). Solo informado só gera avisos; sem textura informada usa a estimada (rotulada) |
| `POST /plano` | **novo.** Plano de 2–8 safras por MILP com regras duras, repetido sob incerteza (`calcular_plano`). `status` = `proposta` (nunca decisão) ou `sem_plano` (+ `lacuna`). `top[].p_otima` = fração dos sorteios em que a sequência foi a ótima |
| `GET /solo/{ponto_id}` | **novo.** Solo ESTIMADO pelo SoilGrids (argila/areia/silte, carbono orgânico, pH; textura por argila: <15 arenoso, 15–35 médio, >35 argiloso). `estimado: null` + `lacuna` se não há dado. Não é análise de solo |
| `GET /zarc/{ponto_id}/{cultura_id}` | **novo.** Janela do ZARC: `risco` 20/30/40, `solo`. 36 decêndios, IBGE, safra usada, `motivo` se não houver janela. Detalhes em docs/13_ZARC.md |
| `GET /evidencias?q=&k=` | busca no acervo (`src.rag.busca.buscar`); cache de respostas por (q, k); `sem_evidencia: true` quando vazio; 503 com LACUNA se índice/modelo ausente |
| `GET /limites` | números lidos de `data/processed/modelos/metricas.json` e da tabela "Holdout temporal" do relatório |
| `GET /modelo/previsao/{ponto_id}` | **implementado** (antes 501); ver abaixo |

Prioridades (`sem`, `agua`, `solo`, `renda`) vêm de `mvp.PRIORIDADES` (uma só definição, a do app): faixas ordinais, SUPOSIÇÃO a validar com técnico; `renda` = lacuna (sem dado de mercado), resultado igual a `sem`.
Schemas de entrada estritos (`extra="forbid"`): campo desconhecido, cultura fora da tabela (16) ou valor fora dos limites = 422; ponto inexistente = 404.

## `/modelo/previsao/{ponto_id}`

Modelo de `metricas.json` (`decisao.modelo`; hoje xgboost com persistência), treinado uma vez (anos 2001–2021) e guardado em `data/processed/modelos/cache_api_previsao.joblib` (ignorado pelo git, regenerável).
O cache leva uma impressão digital dos arquivos de entrada e do `preditivo` do config: se mudarem, retreina (nunca usa modelo velho em silêncio). Código: `src/modelos/previsao.py`.

- Devolve a anomalia de NDVI prevista para o composto SEGUINTE ao último válido do ponto (2026-11-01 para quem tem 2026-10-16 como último; a data sai dos dados, não é constante; ver `docs/21_resultados_fases/DADOS_2025_NA_PREVISAO.md`), com faixa ACI 80%/90% de `treinar_para_cenarios` (mesmo código dos cenários).
- **Só vale 1 composto à frente.** As features do composto t usam clima até t-1 e a anomalia dos 2 compostos anteriores; sem clima futuro, t+2 em diante não tem features. O clima observado vai até o último dia com chuva e tmax não vazios dos arquivos *atuais* (2026-11-10); `clima_ate` = dia anterior ao alvo, `clima_disponivel_ate` = fim do clima. O modelo é treinado só com os originais (até 2024); original + 2025+ só alimentam a inferência (`python -m src.coleta.unir_2025`).
- Lacuna explícita (`anomalia_ndvi_prevista: null`, `lacuna` com o motivo) quando: os 2 compostos anteriores não são consecutivos (ex.: `fortaleza_ce`), o clima necessário não existe, falta feature, ou o cenário extrapola a faixa do treino. Nada é preenchido.
- `limites_declarados` na resposta: horizonte de 1 composto; ganho vem da persistência (o clima contribui pouco); a faixa ACI calibra cobertura média por estação, não garante um ponto isolado (a calibração usa resíduos do Ridge); NDVI 250 m / clima ~50 km não enxergam o talhão; não é produtividade. Métricas do holdout: `GET /limites`.

## Exemplos

```
curl localhost:8000/municipios
curl localhost:8000/diagnostico/quixada_ce
curl -X POST localhost:8000/cenarios -H 'content-type: application/json' \
  -d '{"ponto_id":"quixada_ce","cultura_atual":"milho","prioridade":"solo","ciclo_modo":"medio","n_sorteios":10000}'
curl -X POST localhost:8000/rotacao -H 'content-type: application/json' \
  -d '{"ponto_id":"quixada_ce","cultura_atual":"milho","prioridade":"solo","textura":"médio"}'
curl -X POST localhost:8000/cenarios/clima -H 'content-type: application/json' \
  -d '{"ponto_id":"quixada_ce","cultura_atual":"milho","fator_chuva":0.8,"delta_t":1.0}'
curl -X POST localhost:8000/plano -H 'content-type: application/json' \
  -d '{"ponto_id":"quixada_ce","cultura_atual":"milho","prioridade":"solo","horizonte":5}'
curl localhost:8000/solo/quixada_ce
curl 'localhost:8000/zarc/quixada_ce/milho?risco=30&solo=medio'
curl 'localhost:8000/evidencias?q=feijao%20caupi%20palha&k=3'
curl localhost:8000/limites
curl localhost:8000/modelo/previsao/quixada_ce
```

## Latências medidas (TestClient, máquina local, 2026-11-13, 1 núcleo livre parcial)

| Rota | 1ª chamada | seguintes |
|---|---|---|
| /saude, /municipios, /solo | < 70 ms | |
| /diagnostico/{id} | ~100 ms (carrega JSON de 4 MB) | |
| /zarc/{id}/{cultura} | 4,6 s (carrega o índice do ZARC) | ms |
| /cenarios/clima | 0,26 s | |
| /rotacao (300–1000 sorteios) | 0,26 s (300 sorteios; medido) | |
| /plano (20 sorteios) | 0,7 s | |
| /modelo/previsao/{id} | 11,6 s (monta o dataset e lê o modelo do cache em disco; sem o cache: ~20 s a mais para treinar) | 0,04–0,25 s |
| /evidencias | 32,7 s (embeddings + reranker, sem aquecimento) | ~4,8–7 s por pergunta NOVA (o reranker domina); pergunta repetida ~10 ms (cache de respostas) |

Pré-aquecimento (`lifespan`, thread em segundo plano ao subir o servidor; desligue com `SULCO_PREAQUECER=0`): carrega o RAG com uma consulta real e o contexto da previsão. Medido: RAG 27,1 s e previsão 14,3 s em paralelo com o servidor já aceitando requisições
(`/saude` mostra `aquecimento`). Depois disso, a 1ª pergunta nova ao `/evidencias` custou 7,1 s (rerank), não 32 s; a repetida, 10 ms. O custo do rerank por pergunta nova NÃO foi reduzido.

## Pendências

1. `/evidencias`: reduzir o rerank (~5–7 s por pergunta nova), p.ex. menos candidatos ou cache em disco das perguntas frequentes (decisão do usuário: pode afetar a qualidade da busca).
2. Previsão: só 1 composto; para mais seria preciso previsão de clima (fora do escopo). Faixa ACI cobre ~81%/91% no holdout em média, não por ponto.
3. `src/llm` não integrado (não existe na API).
4. Nomes oficiais dos municípios (pontos.csv só tem o ponto_id; `nome` é derivado sem acento).
5. Decisões do usuário (docs 10 e 11): ciclo real, risco_max, definição de empate, pesos por prioridade com técnicos.
6. Não há teste de equivalência numérica app x API (ambos chamam as mesmas funções de `mvp.py`).
