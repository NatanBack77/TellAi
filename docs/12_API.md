# 12. API (back-end offline)

Código: `src/api/main.py` (FastAPI 0.162.5, pydantic 2.14.3, uvicorn 0.54.0, httpx 0.28.1 para os testes; fixados em `requirements.txt`).
Só lê arquivos locais. Lacuna = campo `lacuna`/lista `lacunas`, nunca valor padrão inventado. Texto fixo: "avaliar com técnico local".

```
.venv/bin/uvicorn src.api.main:app --port 8000      # docs interativas em /docs
.venv/bin/python -m pytest tests/test_api.py -q      # 6 testes, ~15 s (não roda a suíte do RAG)
```

## Estado dos endpoints

| Endpoint | Estado |
|---|---|
| `GET /saude` | pronto (arquivos presentes + latências medidas por rota em memória; header `X-Latencia-ms` em toda resposta) |
| `GET /municipios` | pronto (195 pontos: ponto_id, lat, lon, celula_power) |
| `GET /diagnostico/{ponto_id}` | pronto (solo_nu, estresse = resumo de anomalias de NDVI, estação chuvosa, veranicos, tendência, confiança, lacunas, limites) |
| `POST /cenarios` | pronto (motor de ciclo + Monte Carlo; contrato seção 7 do doc 01 + janela_plantio; evidências do cache `data/processed/mvp/evidencias_rag.json`) |
| `GET /evidencias?q=` | pronto, parcial: usa `src.rag.busca.buscar`; devolve `sem_evidencia: true` quando vazio; 503 com LACUNA se índice/modelo ausente |
| `GET /limites` | pronto (números lidos de `data/processed/modelos/metricas.json` e da tabela "Holdout temporal" do relatório) |
| `GET /modelo/previsao/{ponto_id}` | **NÃO implementado**: responde 501 com `lacuna` explícita |

Prioridade em `/cenarios` (faixas ordinais, SUPOSIÇÃO a validar com técnico): `sem` (pesos livres), `agua` (chuva > temperatura > família), `solo` (palha > N > família > chuva > temperatura; bloco completo), `renda` (LACUNA: sem dado de mercado; resultado idêntico a `sem`, teste cobre). A regra aplicada volta em `regra_prioridade`.
Schema de entrada estrito (`extra="forbid"`): campo desconhecido = 422.

## Exemplos

```
curl localhost:8000/municipios
curl localhost:8000/diagnostico/quixada_ce
curl -X POST localhost:8000/cenarios -H 'content-type: application/json' \
  -d '{"ponto_id":"quixada_ce","cultura_atual":"milho","prioridade":"solo","ciclo_modo":"medio","n_sorteios":10000}'
curl 'localhost:8000/evidencias?q=feijao%20caupi%20palha&k=3'
curl localhost:8000/limites
curl -i localhost:8000/modelo/previsao/quixada_ce     # 501
```

## Latências medidas (TestClient, máquina local, 2026-11-12)

| Rota | 1ª chamada | seguintes |
|---|---|---|
| /saude | 56 ms | |
| /municipios | 9 ms | |
| /diagnostico/{id} | 101 ms (carrega JSON de 4 MB) | |
| /limites | 8 ms | |
| /cenarios (solo, 10 000 sorteios) | 286 ms (carrega clima) | 136 ms |
| /evidencias | 27,7 s (carrega embeddings + reranker) | 7,9 s (a medir de novo: rerank domina) |

O modelo do RAG carrega uma vez (cache em `src.rag.busca`). Pré-aquecer o `/evidencias` na subida ainda não foi feito.

## Pendências e próximos passos (em ordem)

1. `/modelo/previsao/{id}`: treinar (ou carregar) o modelo com persistência via `src.modelos.cenarios.treinar_para_cenarios`, cachear em disco e devolver anomalia prevista + faixa conformal 80/90 + limites. Atenção: o modelo precisa de clima até a data do composto; sem clima futuro só há retrospectiva do último composto, não previsão de futuro (decidir o que mostrar).
2. Pré-aquecimento/lazy-load seguro do RAG e cache de respostas de `/evidencias`; reduzir 7,9 s.
3. Cenário de clima (fator de chuva/temperatura) em `/cenarios`: o app já faz; não exposto.
4. `src/llm` e ZARC não integrados (não existem ainda).
5. Nomes dos municípios: `pontos.csv` não tem nome oficial (só ponto_id).
6. Decisões do usuário (docs 10 e 11): ciclo real, risco_max, definição de empate, pesos por prioridade com técnicos.
7. Testes ainda não cobrem: `/evidencias` com acervo real (aceita 200 ou 503), 404 de ponto sem diagnóstico.
