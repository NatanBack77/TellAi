# Fase 5: consistência API x app, D5, M13, C2 (2026-11-13)

## O que mudou
- **API (`src/api/main.py`, v0.2.0)**: novos `POST /rotacao`, `POST /cenarios/clima`, `POST /plano`, `GET /solo/{id}`, `GET /zarc/{id}/{cultura}`; `/modelo/previsao/{id}` implementado (era 501); `/municipios` ganhou `nome` e `ibge`; `/cenarios` ganhou `usar_zarc` (padrão = app, ligado) e usa `mvp.PRIORIDADES` (cópia local removida); `/saude` mostra `aquecimento` e `cache_modelo_previsao`. Tudo chama `src/app/mvp.py`, `src/culturas`, `src/modelos` por import.
- **Previsão**: novo `src/modelos/previsao.py` (modelo de `metricas.json`, cache em `data/processed/modelos/cache_api_previsao.joblib`, gitignored, impressão digital dos insumos). 1 composto à frente, faixa ACI, lacuna explícita quando falta persistência/clima/feature.
- **`/evidencias`**: cache de respostas + pré-aquecimento em thread (RAG e previsão) ao subir; `SULCO_PREAQUECER=0` desliga. Medido: 1ª pergunta 32,7 s sem aquecimento; 7,1 s com; repetida 10 ms; pergunta nova ~5–7 s (rerank, não reduzido).
- **D5**: `src/coleta/power.py` ganhou `gravar_pontos`, que preserva colunas extras de `pontos.csv` (ex.: `ibge`) por `ponto_id`; ponto novo fica com a coluna vazia. Teste: `tests/test_coleta_power.py` (2).
- **M13**: `src/modelos/walkforward.py`: `anos_da_execucao`; CLI avalia por padrão só 2010–2021 (`--so-selecao` explícito, equivale ao padrão); `--incluir-confirmacao` é a única forma de tocar 2022–2024 (imprime ATENÇÃO). O cálculo (`walk_forward`, `resumir`) não mudou. Testes novos em `tests/test_walkforward.py` (2). Observação: isto muda o comportamento padrão da CLI (antes avaliava tudo); confirme que é o que você quer.
- **C2**: contado no CSV: 16 culturas; N acumulado na biomassa = 10; N fixado = 3 (amendoim, crotalária, mucuna). `src/culturas/rotacao.py` dizia "4 culturas" para N fixado: corrigido. Não achei "11" em src/tests (só em docs que não posso editar, ver abaixo). Teste: `test_contagens_de_n_na_tabela_batem_com_o_texto_do_modulo` em `tests/test_rotacao.py`.
- **Docs**: `docs/11_MVP.md` (seções 6, 7), `docs/12_API.md` (reescrito), `docs/13_ZARC.md` (cabeçalho de estado real).

## Como testar
```
.venv/bin/python -m pytest tests/test_api.py tests/test_coleta_power.py tests/test_walkforward.py tests/test_rotacao.py -q -W error   # 38 passaram em 70 s
.venv/bin/python -m src.modelos.walkforward --variantes base,persistencia            # só 2010-2021 (padrão)
.venv/bin/python -m src.modelos.walkforward --incluir-confirmacao                    # inclui 2022-2024 (uso único, ao final)
SULCO_PREAQUECER=1 .venv/bin/uvicorn src.api.main:app --port 8000 && curl localhost:8000/saude
```
Não rodei a suíte do RAG nem `pytest tests` inteiro; `test_mvp.py`/`test_app.py` (dono: outro agente) não foram executados por mim.

## Para quem edita docs 00/15/19/20 (não editei)
- doc 15 / 20: D5, M13, C2 e a previsão da API estão resolvidos conforme acima; o risco do `python -m src.coleta.power` apagar `ibge` deixou de existir.
- Qualquer texto que ainda diga "N fixado em 4 culturas" ou "N na biomassa em 11" deve passar a 3 e 10 (fonte: `data/culturas/tabela_culturas.csv`).

## Limites e lacunas
- Previsão: 1 composto; `fortaleza_ce` (e outros com compostos anteriores não consecutivos) devolvem lacuna, sem número. Faixa ACI = cobertura média, não por ponto; calibrada com resíduos do Ridge aplicada ao xgboost (como em `treinar_para_cenarios`).
- `/zarc` e culturas sem ZARC: `motivo` explícito; sem IBGE (`sobral_ce`) = sem janela.
- Cache do modelo muda se os parquets/config mudarem (retreina ~20 s na 1ª chamada ou no pré-aquecimento).
- Sem teste de equivalência numérica app x API (mesmas funções, mesmos parâmetros padrão exceto `n_sorteios` da rotação: API 1000, app 3000).
