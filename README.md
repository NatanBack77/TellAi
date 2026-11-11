# SULCO — da órbita ao sulco

MVP (NASA Space Apps 2026) de apoio à decisão sobre rotação de culturas e saúde do solo no semiárido do Nordeste.
A ferramenta **apoia**, não decide: todo cenário é "a avaliar com técnico local".

## Documentação
- [`docs/01_VISAO_GERAL.md`](docs/01_VISAO_GERAL.md) — problema, arquitetura, regras, bases de dados
- [`docs/02_MODULO_MODELOS.md`](docs/02_MODULO_MODELOS.md) — módulo de séries temporais e preditivo
- [`docs/00_STATUS.md`](docs/00_STATUS.md) — feito, falta e achados
- [`docs/03_SUPOSICOES_E_DECISOES.md`](docs/03_SUPOSICOES_E_DECISOES.md) — suposições, pendências, decisões

## Estado
- Passo 1 concluído (2026-11-09): esqueleto, `config.yaml`, `requirements.txt`, validador de entrada, gerador sintético, 7 testes passando.
- Passo 4 concluído: `diagnostico.py` (STL, anomalias, solo nu, tendências, veranicos), 20 testes passando.
- Passo 5 concluído: `features.py` (janelas anteriores, dias secos, sazonalidade, alvo = anomalia), 37 testes passando.
- Passo 6 concluído: `preditivo.py` (climatologia, Ridge, XGBoost; GroupKFold por célula + holdout temporal), 54 testes passando.
- Passos 7–12 concluídos no código: conformal + cobertura, decisão XGBoost vs. Ridge, explicação (`pred_contribs`), `cenarios.py`, `relatorio.py`, 71 testes passando.
- Coleta POWER feita (13 pontos, 2001–2024): `python -m src.coleta.power`. Faltam MODIS e SMAP (Earthdata).
- NDVI (MODIS) em coleta parcial; para continuar em outro PC veja [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md).
- Próximo: dados reais geração do `relatorio_modelos.md` real.

## Como rodar
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.modelos.sintetico   # gera data/processed/sintetico/SINTETICO_*.parquet
.venv/bin/python -m src.modelos.diagnostico --sintetico   # diagnóstico dos pontos sintéticos
.venv/bin/python -m src.modelos.preditivo --sintetico     # só testa o fluxo; não imprime métricas
.venv/bin/python -m pytest -q
.venv/bin/python -m src.modelos.preditivo   # com dados reais: grava metricas.json e relatorio_modelos.md
```
(No Windows use `.venv/Scripts/python`.)
Dados `SINTETICO_*` servem só para testar formato e fluxo; nenhuma métrica deles é resultado do projeto.

## Segurança
`.env` guarda chaves e nunca é commitado.
