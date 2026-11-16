# SULCO — da órbita ao sulco

MVP (NASA Space Apps Challenge 2026 • Juazeiro do Norte, Brasil) de **apoio à decisão sobre rotação de culturas e saúde do solo no semiárido do Nordeste**.  
A ferramenta **apoia, não decide**: todo cenário é "a avaliar com técnico local". Nenhum número é inventado; o que falta aparece como **lacuna**.

---

## 👥 Equipe & Informações do Evento
- **Equipe:** Big Space Creative
- **Instagram Oficial:** `@bigspacecreative`
- **Polo Local:** Juazeiro do Norte, Ceará, Brasil
- **Período do Hackathon:** Dias 14 (das 9h às 17h) e 15 (das 9h às 14h)
- **Líder:** Nathanael Ferreira Bueno
- **Membros:**
  - Natanael Marcelino da Silva Vieira
  - Enzo Almino de Lima
  - Arthur de Araujo Neves
  - Antenor Pires de Lima Neto

### 🎯 Desafio Oficial
**Field Shift: Adapting Farms with NASA Data**  
*Farmers around the world navigate shifting temperatures, changing rainfall patterns, water shortages, extreme weather, and declining soil health. These pressures make it difficult to choose crop rotations that protect fields, conserve water, and support long‑term resilience. Your challenge is to create a decision‑support tool that uses NASA Earth observations along with local soil information, crop characteristics, and farmer priorities to help farmers explore rotation strategies that could strengthen soil health and adapt their farms to changing conditions.*

### 🔬 Tópicos Centrais de Pesquisa da Equipe
- **Agricultura Familiar:** Responsável por mais de 70% dos alimentos no Brasil e com apenas 8,2% de assistência técnica no Semiárido (Censo IBGE 2017).
- **ODS da ONU na Policultura:** Onde se aplicam as metas da Agenda 2030 (especialmente ODS 2, 6, 12, 13 e 15) no consórcio e rotação de culturas.
- **Ambiente Ceará & Quadra Chuvosa:** Dinâmica de chuvas concentradas (fevereiro a maio) e o fenômeno do **Campo Nu** (segundo semestre com céu sem nuvens, alta insolação e dessecação do solo).
- **Edafologia do Semiárido:** Tipos de solo (Neossolos rasos, Latossolos profundos, Vertissolos), verificação de pH e descompactação biológica de solo por raízes.

---

## 📊 Portais Visuais e Assets (`assets/`)
O projeto conta com interfaces visuais complementares dedicadas para apresentação e auditoria da banca de jurados:
- **`assets/index.html`**: Portal executivo de briefing, apresentação da equipe e simulador interativo de LER.
- **`assets/kpis.html`**: Painel executivo com os principais KPIs e métricas (LER > 1.4, eficiência hídrica WUE, retenção radicular SMAP e estabilidade de renda IBGE).
- **`assets/ods-policultura.html`**: Documento aprofundado sobre os mecanismos agronômicos e ecológicos de aplicação dos ODS da ONU na policultura.

---

## 🛰️ O que o sistema faz hoje (2026-11-15)
- **195 locais** (184 municípios do Ceará e 11 de outros estados) com 24 anos (2001–2024) de dados da NASA: chuva e temperatura (POWER), vegetação (MODIS), mais umidade do solo (SMAP), relevo (SRTM) e solo estimado (SoilGrids); produção agrícola do IBGE (PAM) e zoneamento agrícola de risco climático (ZARC, Ceará).
- **App Streamlit** (`src/app/app.py`): o agricultor escolhe o local, a cultura atual e a prioridade (água ou solo); opcionalmente informa a rotação atual e a textura do solo. Vê: o que a terra costuma fazer (campo nu, estresse, veranicos), a chuva da quadra e o que significou para o rendimento, **3 estratégias** (atual + 2 alternativas), **rotação de 3 safras**, plano de várias safras (MILP) e cenários de chuva e temperatura.
- **Previsão da vegetação** (anomalia de NDVI): 28% menos erro que a média histórica no holdout 2022–2024 (skill +0,28, XGBoost); faixa de incerteza adaptativa (ACI) cobre 80,9% / 90,6% para metas de 80% / 90%. O ganho vem da persistência do NDVI, não do clima. Não prevê produtividade.
- **API** FastAPI (`src/api`), **camada LLM** com verificador (`src/llm`, integrada via DeepSeek) e **RAG** sobre 31 PDFs (`src/rag`).
- **Rigor:** validação walk-forward ano a ano com placebo, correção por número de testes e confirmação selada em 2022–2024 (`docs/05_EXPERIMENTOS.md`).

---

## ⚠️ Limites que o app declara
Resolução de município (não de talhão); NDVI não é produtividade (explica só 3% a 10% do rendimento municipal); as alternativas de rotação ficam em **empate técnico** (os dados não separam as melhores); renda, mercado, pragas e erosão ainda são lacunas.
Alinhamento ao desafio: ~61% dos pontos do texto (núcleo obrigatório 86%): [`docs/19_ALINHAMENTO_AO_DESAFIO.md`](docs/19_ALINHAMENTO_AO_DESAFIO.md).

---

## 📚 Documentação (comece por aqui)
| Para… | Leia |
|---|---|
| continuar em outro computador e saber por onde começar | [`docs/04_RETOMADA.md`](docs/04_RETOMADA.md) |
| ver tudo o que está pendente | [`docs/15_PENDENCIAS.md`](docs/15_PENDENCIAS.md) |
| entender o sistema das bases ao resultado | [`docs/18_ARQUITETURA_TECNICA.md`](docs/18_ARQUITETURA_TECNICA.md) |
| apresentar a solução (pitch e avaliação honesta) | [`docs/17_PITCH.md`](docs/17_PITCH.md) |
| comparar com o desafio da NASA | [`docs/19_ALINHAMENTO_AO_DESAFIO.md`](docs/19_ALINHAMENTO_AO_DESAFIO.md) |
| **entender o impacto direto nos ODS da ONU** | [`docs/34_ODS_E_IMPACTO_SUSTENTAVEL.md`](docs/34_ODS_E_IMPACTO_SUSTENTAVEL.md) |
| ver LER e consórcios com base científica no Semiárido | [`docs/29_LER_CONSORCIO.md`](docs/29_LER_CONSORCIO.md) |
| planejar as próximas fases em outro computador | [`docs/20_PLANO_PROXIMAS_FASES.md`](docs/20_PLANO_PROXIMAS_FASES.md) |
| saber o estado e o histórico | [`docs/00_STATUS.md`](docs/00_STATUS.md), [`docs/03_SUPOSICOES_E_DECISOES.md`](docs/03_SUPOSICOES_E_DECISOES.md) |
| ver os experimentos e a pesquisa | [`docs/05_EXPERIMENTOS.md`](docs/05_EXPERIMENTOS.md), [`docs/16_PESQUISA.md`](docs/16_PESQUISA.md) |
Índice completo de todos os 34 documentos: [`docs/README.md`](docs/README.md).

---

## 💻 Como rodar

```bash
# 1. Ativar o ambiente virtual existente ou criar com uv:
uv venv .venv --python 3.14
source .venv/bin/activate
uv pip install -r requirements-runtime.txt

# 2. Iniciar o Painel Streamlit do Agricultor:
.venv/bin/python -m streamlit run src/app/app.py             # app em http://localhost:8501

# 3. Iniciar a API FastAPI:
.venv/bin/uvicorn src.api.main:app --port 8000              # API em http://localhost:8000/docs

# 4. Rodar a suíte de testes automatizados:
.venv/bin/python -m pytest -q

# 5. Executar o pipeline de previsão e métricas:
.venv/bin/python -m src.modelos.preditivo
```

---

## 💬 Front-end React da conversa Maíra
O front-end React usa a conversa com estado da API (`POST /conversa`) e fica em [`frontend/`](frontend/README.md).  
Para rodar em desenvolvimento:
```bash
cd frontend
npm install
npm run dev                                                 # interface em http://localhost:5173
```
O Vite encaminha automaticamente as requisições de API para `127.0.0.1:8000`.

---

## 🔒 Segurança
O arquivo `.env` guarda chaves de API (`DEEPSEEK_API_KEY`, etc.) e **nunca** é commitado no git.
