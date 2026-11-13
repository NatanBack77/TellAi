# SULCO — da órbita ao sulco

MVP (NASA Space Apps 2026) de apoio à decisão sobre rotação de culturas e saúde do solo no semiárido do Nordeste.
A ferramenta **apoia**, não decide: todo cenário é "a avaliar com técnico local".

## Documentação
- **Comece por** [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md) (como continuar em outro computador) e [`docs/15_PENDENCIAS.md`](docs/15_PENDENCIAS.md) (o que falta). Índice completo: [`docs/README.md`](docs/README.md).
- [`docs/01_VISAO_GERAL.md`](docs/01_VISAO_GERAL.md) — problema, arquitetura, regras, bases de dados
- [`docs/02_MODULO_MODELOS.md`](docs/02_MODULO_MODELOS.md) — módulo de séries temporais e preditivo
- [`docs/00_STATUS.md`](docs/00_STATUS.md) — feito, falta e achados
- [`docs/03_SUPOSICOES_E_DECISOES.md`](docs/03_SUPOSICOES_E_DECISOES.md) — suposições, pendências, decisões

## Estado
- Passo 1 concluído (2026-11-09): esqueleto, `config.yaml`, `requirements.txt`, validador de entrada, gerador sintético, 7 testes passando.
- Passo 4 concluído: `diagnostico.py` (STL, anomalias, solo nu, tendências, veranicos), 20 testes passando.
- Passo 5 concluído: `features.py` (janelas anteriores, dias secos, sazonalidade, alvo = anomalia), 37 testes passando.
- Passo 6 concluído: `preditivo.py` (climatologia, Ridge, XGBoost; GroupKFold por célula + holdout temporal), 54 testes passando.
- Passos 7–12 concluídos no código: conformal + cobertura, decisão XGBoost vs. Ridge, explicação (`pred_contribs`), `cenarios.py`, `relatorio.py`, 81 testes passando (inclui walk-forward).
- Coleta POWER feita (13 pontos, 2001–2024): `python -m src.coleta.power`. Faltam MODIS e SMAP (Earthdata).
- **Estado (2026-11-11):** clima POWER de 59 pontos (Ceará + outros) completo; NDVI MODIS em 34/59 pontos (cache). Walk-forward implementado: a persistência da anomalia de NDVI é a única melhoria validada até agora. Ver [`docs/05_EXPERIMENTOS.md`](docs/05_EXPERIMENTOS.md) e [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md).
- NDVI (MODIS) coletado para os 13 primeiros pontos; diagnóstico e preditivo rodados com dados reais (ver `relatorio_modelos.md`: o modelo não supera a climatologia no holdout). Retomada em outro PC: [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md).
- **Estado (2026-11-12):** dados completos para 195 pontos; MVP, API, RAG, motor de culturas e camada LLM prontos (ver `docs/00_STATUS.md`). Antes:  195 pontos (Ceará inteiro); clima e SMAP coletados; NDVI em 85%; novos `src/culturas`, `src/rag`, `src/app`. Para continuar em outro PC: [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md).
- **Estado (2026-11-12, D52):** `persistencia` (anomalia dos 2 compostos anteriores, validada em walk-forward) integrada a `preditivo.py`/`cenarios.py`/`relatorio.py` e ligada por padrão (`preditivo.usar_persistencia`). Holdout 2022–2024, 195 pontos: skill vs. climatologia Ridge +0,257 / XGBoost +0,284 (só clima, mesmas linhas: −0,025 / +0,003). O relatório mostra as duas linhas lado a lado. O ganho vem da memória do NDVI; cenários de clima reagem pouco (medido em `relatorio_modelos.md`). SMAP fica desligado por padrão (`usar_umidade_solo: false`). Opções de CLI: `--sem-persistencia`, `--com-smap`.
- Próximo: opções de uso do solo/FUNCEME, decisão do usuário sobre `pers_lags4` (ganho marginal) e sobre a faixa conformal (cobertura real abaixo da meta).

## Como rodar
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.modelos.sintetico   # gera data/processed/sintetico/SINTETICO_*.parquet
.venv/bin/python -m src.modelos.diagnostico --sintetico   # diagnóstico dos pontos sintéticos
.venv/bin/python -m src.modelos.preditivo --sintetico     # só testa o fluxo; não imprime métricas
.venv/bin/python -m pytest -q
# validação walk-forward de variantes (ver docs/05_EXPERIMENTOS.md)
.venv/bin/python -m src.modelos.walkforward --variantes base,persistencia
.venv/bin/python -m src.modelos.preditivo   # com dados reais: grava metricas.json e relatorio_modelos.md (com persistência)
.venv/bin/python -m src.modelos.preditivo --sem-persistencia   # modelo só-clima (comportamento anterior)
.venv/bin/python -m src.modelos.preditivo --com-smap           # opção desligada por padrão (D52)
```
(No Windows use `.venv/Scripts/python`.)
Dados `SINTETICO_*` servem só para testar formato e fluxo; nenhuma métrica deles é resultado do projeto.

## Segurança
`.env` guarda chaves e nunca é commitado.
