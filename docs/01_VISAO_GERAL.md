# SULCO — Visão geral ("da órbita ao sulco")

NASA Space Apps Challenge 2026 · MVP em 48h · Última atualização: 2026-11-09

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
| SMAP L4 SPL4SMGP | umidade do solo (~9 km) | Earthdata + earthaccess |
| FAO EcoCrop | faixas climáticas por cultura | CSV exportado |
| Tabela de culturas (própria) | N fixado, palha, demanda hídrica, família | CSV com fonte e página |
| Acervo (Embrapa, FAO, ZARC) | evidência citada | pasta local |

Plano B do SMAP: SoilGrids (baixar uma vez). Fora do MVP: IMERG, SRTM, Landsat/HLS, GRACE, ECOSTRESS, GEDI.

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
