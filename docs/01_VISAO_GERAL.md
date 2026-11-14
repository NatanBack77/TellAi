# SULCO — Visão geral ("da órbita ao sulco")

NASA Space Apps Challenge 2026 · MVP em 48h · Última atualização: 2026-11-09; seção 5 revisada em 2026-11-14 (estado das bases)

## 1. Problema
Agricultores do semiárido do Nordeste decidem o que plantar após a safra sem ver o que clima,
umidade do solo e vegetação dizem sobre a terra. Só 8,2% dos estabelecimentos do Nordeste têm
assistência técnica (Censo Agropecuário 2017, via Ipea).

## 2. O que a ferramenta deve fazer
- Comparar no mínimo 3 estratégias de rotação, incluindo a atual.
- Para cada uma: por que foi sugerida, evidência citada, benefícios, **lacunas** e **riscos para revisão local**.
- Apoiar, nunca decidir ("cenário a avaliar com técnico local").
- Linguagem simples; mostrar incerteza e o que o satélite não enxerga (pixel de km vs. talhão).

## 3. Regras inegociáveis
1. Nenhum número, nota ou fonte inventados.
2. Dado ausente vira "lacuna" visível.
3. O LLM nunca calcula, escolhe rotação nem prevê clima; só reescreve JSON + trechos [n].
4. Busca de evidências vazia => resposta "sem evidência".
5. O app nunca chama API de dados ao vivo (demo roda offline, do cache).
6. Nenhum dado sensível/empresarial enviado a API externa.

## 4. Arquitetura em duas fases
**Fase A (offline, gera arquivos locais):** A1 coleta por local → A2 diagnóstico → A3 XGBoost (opcional)
→ A4 tabela de culturas → A5 acervo + índice híbrido → A6 pré-geração de cenários/explicações (cache).

**Fase B (Streamlit):** entrada → perfil do local → filtro de viabilidade (EcoCrop) → pontuação
ponderada → seleção (atual + 2 melhores) → incerteza → busca de evidências → explicação → tela.

**Núcleo obrigatório:** passos 1–7 da Fase B + tela com explicação em template.
**Extras (só depois):** LLM, XGBoost, chat, voz.

## 5. Bases de dados
| Base | Uso | Acesso |
|---|---|---|
| NASA POWER | chuva, temperatura, radiação | API REST por ponto |
| MODIS MOD13Q1 v061 | NDVI + confiabilidade | Earthdata + earthaccess |
| SMAP L4 SPL4SMGP | umidade do solo (~9 km); coletado, só informativo | Earthdata + earthaccess |
| FAO EcoCrop | faixas climáticas por cultura | CSV exportado |
| Tabela de culturas (própria) | N fixado, palha, demanda hídrica, família | CSV com fonte e página |
| Acervo (Embrapa, FAO, ZARC) | evidência citada | pasta local |

**Estado das bases em 2026-11-14** (fontes: `docs/18_ARQUITETURA_TECNICA.md` seção de bases, `docs/19_ALINHAMENTO_AO_DESAFIO.md`, `docs/21_resultados_fases/`):
- Em uso no app: NASA POWER (clima, ~50 km, 2001-2024 + 2025+), MODIS MOD13Q1 (NDVI, 250 m, 2001-2024 + 2025+), SRTM (declive, entra no risco de erosão), SoilGrids (solo estimado, 250 m, mediana ~2 km), ZARC do Ceará (MAPA), IBGE PAM (receita bruta), EcoCrop + tabela própria de 16 culturas, acervo RAG (50 PDFs no manifesto, 3.203 trechos).
- SMAP: coletado (2015-2024), **informativo**: não melhorou o modelo (ganho ~+0,006 a +0,007 de skill, poder baixo); desligado por padrão.
- **SoilGrids não é "plano B do SMAP"** (redação antiga, errada): são coisas diferentes (SoilGrids é solo estimado por mapa global, não umidade). Foi coletado para a textura/solo do local e para o risco de erosão; como feature do modelo de NDVI NÃO deu ganho (`experimentos/soilgrids/RESULTADO.md`).
- Não usadas: IMERG/GPM, Landsat/HLS, GRACE, ECOSTRESS, GEDI. Motivo de cada uma: `docs/16_PESQUISA.md` seção G.

## 6. Ordem de trabalho
1 Earthdata/POWER/MODIS (1 ponto) → 2 diagnóstico mínimo → 3 tabela de culturas + motor → 4 Streamlit
(**ponto de corte**) → 5 RAG + LLM + cache → 6 incerteza + página de limites → 7 pré-gerar demo → 8 extras.

## 7. Contrato de dados (JSON do cenário)
Campos: `local`, `cultura_atual`, `rotacao`, `score`, `faixa_incerteza`, `criterios{valor, unidade, nota, fonte, pagina}`,
`lacunas`, `riscos_revisao_local`, `trechos[{n, arquivo, pagina, texto}]`.

## 8. Critérios de aceite globais
- 20 perguntas estilo agricultor: português puro, citações [n] corretas, "sem evidência" quando falta base, JSON válido.
- RAG: trecho certo no top 5 em ≥80% das perguntas.
- Toda nota tem valor bruto, fonte, página e URL (validador).
- Demo roda offline a partir do cache.

## 9. Não fazer
LangChain; API de dados ao vivo no demo; notas "de cabeça"; prometer que a rotação "rende mais";
XGBoost sem baseline; enviar dado sensível a API externa.

## 10. Estrutura do repositório
`data/{raw,processed}`, `docs/`, `docs_rag/`, `indice/`, `notebooks/`, `src/{coleta,diagnostico,cenarios,rag,llm,app,modelos}`,
`tests/`, `.env` (nunca commitar), `README.md`.
