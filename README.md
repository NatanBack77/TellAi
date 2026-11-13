# SULCO — da órbita ao sulco

MVP (NASA Space Apps 2026) de **apoio à decisão sobre rotação de culturas e saúde do solo no semiárido do Nordeste**.
A ferramenta **apoia, não decide**: todo cenário é "a avaliar com técnico local". Nenhum número é inventado; o que falta aparece como **lacuna**.

## O que o sistema faz hoje (2026-11-13)
- **195 locais** (184 municípios do Ceará e 11 de outros estados) com 24 anos (2001–2024) de dados da NASA: chuva e temperatura (POWER), vegetação (MODIS), mais umidade do solo (SMAP), relevo (SRTM) e solo estimado (SoilGrids); produção agrícola do IBGE (PAM) e zoneamento agrícola de risco climático (ZARC, Ceará).
- **App Streamlit** (`src/app/app.py`): o agricultor escolhe o local, a cultura atual e a prioridade (água ou solo); opcionalmente informa a rotação atual e a textura do solo. Vê: o que a terra costuma fazer (campo nu, estresse, veranicos), a chuva da quadra e o que significou para o rendimento, **3 estratégias** (atual + 2 alternativas), **rotação de 3 safras**, plano de várias safras (MILP) e cenários de chuva e temperatura.
- **Previsão da vegetação** (anomalia de NDVI): 28% menos erro que a média histórica no holdout 2022–2024 (skill +0,28, XGBoost); faixa de incerteza adaptativa (ACI) cobre 80,9% / 90,6% para metas de 80% / 90%. O ganho vem da persistência do NDVI, não do clima. Não prevê produtividade.
- **API** FastAPI (`src/api`), **camada LLM** com verificador (`src/llm`, sem chave ainda) e **RAG** sobre 31 PDFs (`src/rag`).
- **Rigor:** validação walk-forward ano a ano com placebo, correção por número de testes e confirmação selada em 2022–2024 (`docs/05_EXPERIMENTOS.md`).

## Limites que o app declara
Resolução de município (não de talhão); NDVI não é produtividade (explica só 3% a 10% do rendimento municipal); as alternativas de rotação ficam em **empate técnico** (os dados não separam as melhores); renda, mercado, pragas e erosão ainda são lacunas.
Alinhamento ao desafio: ~61% dos pontos do texto (núcleo obrigatório 86%): [`docs/19_ALINHAMENTO_AO_DESAFIO.md`](docs/19_ALINHAMENTO_AO_DESAFIO.md).

## Documentação (comece por aqui)
| Para… | Leia |
|---|---|
| continuar em outro computador e saber por onde começar | [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md) |
| ver tudo o que está pendente | [`docs/15_PENDENCIAS.md`](docs/15_PENDENCIAS.md) |
| entender o sistema das bases ao resultado | [`docs/18_ARQUITETURA_TECNICA.md`](docs/18_ARQUITETURA_TECNICA.md) |
| apresentar a solução (pitch e avaliação honesta) | [`docs/17_PITCH.md`](docs/17_PITCH.md) |
| comparar com o desafio da NASA | [`docs/19_ALINHAMENTO_AO_DESAFIO.md`](docs/19_ALINHAMENTO_AO_DESAFIO.md) |
| **planejar as próximas fases em outro computador** | [`docs/20_PLANO_PROXIMAS_FASES.md`](docs/20_PLANO_PROXIMAS_FASES.md) |
| saber o estado e o histórico | [`docs/00_STATUS.md`](docs/00_STATUS.md), [`docs/03_SUPOSICOES_E_DECISOES.md`](docs/03_SUPOSICOES_E_DECISOES.md) |
| ver os experimentos e a pesquisa | [`docs/05_EXPERIMENTOS.md`](docs/05_EXPERIMENTOS.md), [`docs/16_PESQUISA.md`](docs/16_PESQUISA.md), `experimentos/*/RESULTADO.md` |
Índice completo: [`docs/README.md`](docs/README.md).

## Como rodar
```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt          # Linux/Mac: .venv/bin/python
.venv/Scripts/python -m streamlit run src/app/app.py             # app em http://localhost:8501
.venv/Scripts/python -m pytest -q                                # suíte completa (324 testes coletados; RAG e LLM são pesados)
.venv/Scripts/python -m src.modelos.preditivo                    # previsão com dados reais: metricas.json e relatorio_modelos.md
.venv/Scripts/python -m src.modelos.walkforward --variantes base,persistencia   # validação de variantes
```
Coletas (idempotentes, com cache): `python -m src.coleta.power | modis_ornl --workers 16 | zarc | solo | sidra | srtm`. Detalhes e ordem em [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md).
Dados `SINTETICO_*` servem só para testar formato e fluxo; nenhuma métrica deles é resultado do projeto.

## Segurança
`.env` guarda chaves (Earthdata, DeepSeek) e **nunca** é commitado.
