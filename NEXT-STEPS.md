# 🧭 NEXT-STEPS — Panorama Estratégico e Roadmap do SULCO

Documento consolidado de próximos passos, pendências técnicas e evolução estratégica do projeto **SULCO — da órbita ao sulco** (NASA Space Apps Challenge 2026 • Equipe **Big Space Creative**, Juazeiro do Norte - CE).

Elaborado em consonância com as diretrizes de governança técnica, os 34 documentos de arquitetura (`docs/`), os 6 Agentes Especializados e as 6 Skills de automação em `.ai/`.

---

## 📍 1. Estado Atual do Projeto (Onde Estamos)

* **Motor Preditivo & Dados:** 195 locais (184 no Ceará) com 24 anos de séries da NASA (POWER, MODIS, SMAP, SRTM) e estatísticas oficiais (IBGE PAM, ZARC). Modelo XGBoost/ACI com **28% menos erro** que a climatologia histórica.
* **Aplicações:** 
  1. Painel Streamlit (`src/app/app.py`) na porta `8501`.
  2. API REST FastAPI (`src/api/main.py`) na porta `8000` com IA DeepSeek online e verificador de fatos.
  3. Frontend React + Vite da assistente Maíra (`frontend/`) na porta `5173`.
* **Portais Visuais & Apresentação (`assets/`):**
  - `assets/index.html`: Portal executivo com briefing da equipe e simulador interativo de LER.
  - `assets/kpis.html`: Painel de métricas quantitativas de impacto agronômico, hídrico e socioeconômico.
  - `assets/ods-policultura.html`: Estudo técnico aprofundado sobre a aplicação dos ODS da ONU.
* **Documentação Técnica Recente:** `docs/34_ODS_E_IMPACTO_SUSTENTAVEL.md` na branch `feat/ods-impacto-sustentavel`.
* **Ambiente de Desenvolvimento:** Python 3.14 via `uv` em `.venv/` e dependências npm instaladas.

---

## 🎯 2. Matriz de Priorização (Framework MoSCoW)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ROADMAP DE EVOLUÇÃO DO SULCO                          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
     ┌───────────────────┬─────────────┴─────┬───────────────────┐
     ▼                   ▼                   ▼                   ▼
 [FASE 1: MUST]    [FASE 2: SHOULD]    [FASE 3: COULD]     [FASE 4: WON'T]
  Pitch & Demo      Modelos & Renda     SRE & GitOps        Campo & 2027
  (Próx. 24h)       (Pós-Hackathon)     (Infra Nuvem)       (Longo Prazo)
```

---

### 🔴 FASE 1: Prioridade Máxima • Submissão & Pitch (Must Have - Próximas 24 Horas)

| # | Tarefa | Módulo / Arquivo | Agente / Skill Responsável | Impacto no Julgamento |
|---|---|---|---|---|
| **1.1** | **Implementar Prioridade "Alimento" (ODS 2)** | `src/app/mvp.py`<br>`src/app/perfil.py` | `@agro-polyculture-ods-expert`<br>`crop-rotation-recommender` | **Crucial:** Responde diretamente ao desafio da NASA, focando em segurança alimentar familiar e quebra de monocultura. |
| **1.2** | **Ativar LER no App como Evidência** | `src/culturas/consorcio.py`<br>`src/app/mvp.py` | `@agro-polyculture-ods-expert` | Conecta os 8 estudos científicos de consórcios pareados do Semiárido (LER 1,05 a 1,82) na tela do agricultor. |
| **1.3** | **Gravar o Pitch de 240 Segundos (4 min)** | `docs/17_PITCH.md`<br>`assets/index.html` | `@space-apps-pitch-strategist`<br>`space-apps-pitch-builder` | Cumpre rigorosamente as 5 rubricas oficiais da NASA (*Impact, Creativity, Validity, Relevance, Presentation*). |
| **1.4** | **Auditoria Pré-Voo GitOps** | `scripts/validate_preflight.cjs` | `@gitops-release-engineer`<br>`sulco-gitops-deploy` | Garante que nenhum token/chave suba ao GitHub e valida a autoria oficial `Antenor Pires <contato@antenorpires.eng.br>`. |
| **1.5** | **Preencher Página Oficial do Space Apps** | Formulário de Submissão | `@space-apps-pitch-strategist` | Tradução de impacto, links de demonstração, dados da NASA utilizados e repositório. |

---

### 🟡 FASE 2: Engenharia de Modelos & Agronomia (Should Have - MVP v1.1)

| # | Tarefa | Módulo / Arquivo | Agente / Skill Responsável | Descrição Técnica |
|---|---|---|---|---|
| **2.1** | **Integrar Dados 2025+ no Modelo Preditivo** | `src/coleta/unir_2025.py`<br>`src/modelos/previsao.py` | `@nasa-earthdata-agent`<br>`nasa-agro-data` | Atualmente a previsão do app projeta a partir do final de 2024; ligar os Parquets `2025plus` para atualizar a inferência até o presente. |
| **2.2** | **Renda Real por Hectare com Base no IBGE** | `src/culturas/renda.py`<br>`data/processed/pam_ce.parquet` | `@ibge-agro-data-expert`<br>`ibge-data-fetcher` | Utilizar a variável 215 (Valor da produção) do IBGE dividida pela área colhida para calcular a receita bruta/ha e mitigar a lacuna da prioridade "renda". |
| **2.3** | **Ativação Plena do Índice RAG Agronômico** | `indice_agronomia/`<br>`src/rag/agronomia.py` | `@sre-platform-engineer`<br>`sre-ops` | Avaliar os 8.849 trechos gerados, calibrar o limiar de similaridade (`LIM_COS = 0.86`) e ligar na busca semântica da Maíra. |
| **2.4** | **Correção de Coordenada de Sobral (DU8)** | `data/processed/pontos.csv` | `@ibge-agro-data-expert` | Corrigir a coordenada para que o ponto caia no polígono municipal e receba o código IBGE 2312908 e os dados do ZARC. |
| **2.5** | **Inserir Glossário Climático Didático** | `src/app/mvp.py`<br>`docs/35_CLIMA.md` | `@nasa-earthdata-agent` | Adicionar conceitos de Clima Semiárido (BSh), Fatores de Altitude (SRTM) e Campo Nu (NASA POWER) no menu do app. |

---

### 🔵 FASE 3: Infraestrutura, SRE & GitOps (Could Have - Nuvem & Produção)

| # | Tarefa | Módulo / Arquivo | Agente / Skill Responsável | Descrição Técnica |
|---|---|---|---|---|
| **3.1** | **Deploy Híbrido: Frontend na Vercel** | `frontend/`<br>`vercel.json` | `@gitops-release-engineer`<br>`sulco-gitops-deploy` | Publicar o app React da Maíra na Vercel conectado à API backend pública para que jurados acessem instantaneamente pelo celular. |
| **3.2** | **Containerização Otimizada com Docker** | `Dockerfile`<br>`docker-compose.yml` | `@sre-platform-engineer`<br>`sulco-sre-ops` | Subir o contêiner de produção (`sulco:latest`) em VPS/Render/Railway, validando os 3 GB de RAM da API e 2 GB do Streamlit. |
| **3.3** | **Pipeline de CI com GitHub Actions** | `.github/workflows/ci.yml` | `@gitops-release-engineer`<br>`sulco-gitops-deploy` | Automação de testes rápidos (`pytest`) e build de contêiner a cada Pull Request aberto. |
| **3.4** | **Proxy Reverso & Blindagem TLS (HTTPS)** | `docker/nginx.conf` | `@sre-platform-engineer` | Configurar terminação SSL/TLS com Let's Encrypt e rate-limiting para proteger as rotas da API contra abusos. |
| **3.5** | **Telemetria e Métricas Prometheus** | `src/api/metricas.py` | `@sre-platform-engineer`<br>`sulco-sre-ops` | Instrumentar o endpoint `/saude` para exportar métricas de latência (`X-Latencia-ms`) e taxa de uso de tokens do DeepSeek. |

---

### ⚪ FASE 4: Extensão de Campo & Ciência Cidadã (Won't Have Now - Roadmap 2027)

| # | Tarefa | Módulo / Arquivo | Descrição |
|---|---|---|---|
| **4.1** | **Validação Cega com Técnicos da EMATERCE** | `docs/11_MVP.md` | Apresentar os cenários gerados para agrônomos de campo do Cariri para calibrar suposições de ciclo e manejo. |
| **4.2** | **Integração de Pluviômetros da FUNCEME** | `src/coleta/funceme.py` | Estabelecer convênio de dados para incorporar a rede de 500 postos pluviométricos do Ceará. |
| **4.3** | **Cálculo Físico de Perda de Solo (RUSLE)** | `src/modelos/erosao.py` | Evoluir o indicador relativo de erosão para uma estimativa em toneladas de solo perdidas por hectare/ano. |

---

## 🛠️ 3. Matriz de Atribuição: Agentes e Skills

Para manter a separação de responsabilidades e evitar ineficiência de contexto:

| Agente Especializado | Quando Invocar (`invoke_agent`) | Skill Associada |
|---|---|---|
| **`@agro-polyculture-ods-expert`** | Modelagem de consórcios, LER, ODS 2, 6, 12, 13, 15 e fitossanidade. | `crop-rotation-recommender` |
| **`@nasa-earthdata-agent`** | Consultas a APIs da NASA (POWER, SMAP, ECOSTRESS, MODIS) e clima. | `nasa-agro-data` |
| **`@ibge-agro-data-expert`** | Dados do PAM, rendimento médio municipal (kg/ha) e agricultura familiar. | `ibge-data-fetcher` |
| **`@space-apps-pitch-strategist`** | Storytelling, roteiro de pitch em vídeo, submissão e rubricas da NASA. | `space-apps-pitch-builder` |
| **`@sre-platform-engineer`** | Docker, dimensionamento de RAM/CPU, healthchecks e estabilidade do SULCO. | `sulco-sre-ops` |
| **`@gitops-release-engineer`** | Higienização de commits, branch isolation, CI/CD e deploy híbrido Vercel. | `sulco-gitops-deploy` |

---

## ⚡ 4. Guia Rápido de Comandos para o Time

```bash
# Auditar saúde dos serviços ativos (FastAPI, Streamlit, Frontend):
node .ai/skills/sulco-sre-ops/scripts/healthcheck_sulco.cjs

# Validar integridade e segredos antes de commitar ou fazer push:
node .ai/skills/sulco-gitops-deploy/scripts/validate_preflight.cjs --repo-dir ./sulco-nasa

# Rodar testes automatizados do backend:
cd sulco-nasa && .venv/bin/python -m pytest tests/test_consorcio.py tests/test_features.py -q

# Gerar documento oficial de submissão do pitch:
node .ai/skills/space-apps-pitch-builder/scripts/generate_pitch.cjs --title "SULCO: Da Órbita ao Sulco"
```

---

*Documento mantido pela equipe Big Space Creative. Apoia, não decide.*
