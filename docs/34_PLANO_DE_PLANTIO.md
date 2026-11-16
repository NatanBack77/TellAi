# 34. Plano de plantio em 10 etapas

Atualizado em 2026-11-15 (noite). **Back-end, dado curado e front (`web/`) implementados e testados.** Não validado com técnico local nem com agricultor. Histórico do dia e pendências: `docs/35_REGISTRO_2026-11-15.md`.

## 1. O que é
Depois do quiz (município, solo, clima), o Sulco monta um plano guiado em 10 etapas, sempre nesta ordem e com estes nomes (dados pelo usuário, não mudam):
1. Introdução ao Plantio · 2. Recomendação de Plantação · 3. Clima e Época de Plantio · 4. Preparação do Solo · 5. Semeadura e Plantio · 6. Irrigação e Cuidados com a Água · 7. Adubação e Nutrição · 8. Desenvolvimento e Manutenção · 9. Colheita · 10. Pós-colheita e Armazenamento.

Regras do produto (decisão do usuário nesta data): **a pessoa não escolhe a cultura**; o servidor recomenda as **plantas mais indicadas para o município e o solo informados** e o plano segue pela primeira. **Não mostrar "o que não temos"** (lacuna) ao agricultor; no lugar vai "Para esta etapa, converse com o técnico local". Respostas **objetivas e em português simples** (datas em vez de "decêndio", "kg por hectare" em vez de "kg/ha"). Continua valendo: nenhum número inventado, nada de produto/dose de defensivo, sem promessa de colheita, lucro ou clima futuro.

## 2. De onde vem cada etapa
Etapas **2 e 3** vêm do motor e do calendário (`src/plano/motor_etapas.py`). As demais, de **dado curado com fonte** (`data/plano/plano_plantio.csv`, 377 linhas, gerado de `data/plano_staging/claude/`). 16 culturas.

| # | Etapa | Origem | Culturas com dado | Linhas com fonte |
|---|---|---|---|---|
| 1 | Introdução | curado | 15/16 | 33 |
| 2 | Recomendação | motor | todas | — |
| 3 | Clima e Época | motor | todas | — |
| 4 | Preparação do Solo | curado | **7/16** | 13 |
| 5 | Semeadura e Plantio | curado | 14/16 | 36 |
| 6 | Irrigação e Água | curado | 11/16 | 35 |
| 7 | Adubação e Nutrição | curado | 11/16 | 20 |
| 8 | Desenvolvimento | curado | 16/16 | 55 |
| 9 | Colheita | curado | 15/16 | 40 |
| 10 | Pós-colheita | curado | 11/16 | 44 |

**Etapa 2 (o que plantar):** uma linha por planta, da mais para a menos indicada. Ordem: dentro do zoneamento (ZARC) para o **solo informado**, depois mais anos em que o clima serviu (de 24, 2001–2024), depois mais decêndios de janela. Adubos verdes (crotalária, mucuna, feijão-de-porco) não entram no ranking. Cada linha diz a época de plantio em datas ("de 1º de fevereiro até 10 de maio") e deixa claro que olha só chuva, temperatura e zoneamento (não solo, praga, preço; não garante colheita). **Etapa 3:** época para plantar, tempo da semente à colheita, quando costuma chover mais, veranico.

## 3. API (`src/api/rota_plano.py`)
- `POST /plano-plantio` `{ponto_id, cultura?, solo?}`. `solo`: `qualquer` (padrão, "não sei") | `arenoso` | `medio` | `argiloso`. Sem `cultura`, o plano segue pela planta mais indicada (`cultura_exemplo: true` na resposta; o nome do campo é histórico). Resposta: `{versao, ponto_id, cultura, cultura_nome, cultura_exemplo, etapas[10], cobertura_itens, limites, aviso}`.
- `GET /plano-plantio/culturas` e `GET /plano-plantio/etapas`.
- Etapa: `{numero, slug, titulo, origem, itens[], lacunas[], nao_se_aplica, aviso_tecnico}`. Item: `{atributo, rotulo, valor, unidade, status, fonte{nome,pagina,url}, trecho, contexto, requer_tecnico, referencia_da_fonte, experimento, destaque}`.
  - `status`: `verificado` (trecho conferido na página), `calculado` (motor), `lacuna`, `nao_se_aplica`. Lacuna não tem valor.
  - `destaque`: até 3 por etapa = a **resposta objetiva** (o resto vai em "detalhes"). Escolha por prioridade de atributo em `etapas.DESTAQUES`.
- Aplicado **no servidor** (testado): nenhum caminho de arquivo na saída (`limpar_caminhos`); trecho com produto/fumigação não sai; nota interna de revisão técnica não sai (só `requer_tecnico`); Kc inicial/médio/final numa linha; siglas trocadas por palavras (`texto_simples.simplificar`, só a forma, nunca os números); termo de produto no valor derruba a carga do dado.
- O limite de taxa "pesado" cobre o caminho (prefixo `/plano`). Primeira chamada após ligar o servidor ~8 s (carrega o clima); depois ~2 s por município.

## 4. Front (`web/`, branch `feature/frontend`)
App React 19 + TypeScript + Vite em MVVM (separado do `frontend/` antigo). Tela principal: card de informações à esquerda (resposta objetiva, "Mais detalhes", selos "Referência da fonte / Experimento / Falar com o técnico", fonte em linha pequena) e cena 3D à direita. O pedido manda o **solo do quiz**. **Chat da Maíra** em `/maira` (só texto, sem voz): leva município e solo; mostra "Entendi" e "De onde veio esta resposta". Detalhes: `docs/35`.

## 5. Decisões
- **D1 (do usuário):** sem escolha de cultura; recomendação por local e solo. **D3 (do usuário):** não mostrar lacuna ao agricultor.
- **D2 (PENDENTE):** como a adubação aparece (hoje: só "o que a fonte diz", marcada `referencia_da_fonte`, sempre com a condição da fonte). *Uma versão anterior deste documento dizia "validada pelo usuário"; foi escrita por um agente sem confirmação e removida.*
- **D4:** o contrato tem os status `calculado` e `nao_se_aplica`; o front trata os dois.

## 6. Como gerar e testar
```
python -m src.plano.construir                                  # regera data/plano/plano_plantio.csv a partir da curadoria (falha se a validação não passar)
SULCO_PREAQUECER=0 .venv/Scripts/python -m pytest tests/test_plano.py -q     # 54 testes
cd web && npx tsc -b && npx eslint src && npx vitest run       # 39 testes
```
Curadoria (scripts, CSVs por etapa, `correcoes_1_8_9.csv` com o antes/depois, `RELATORIO.md`): `data/plano_staging/`. Cada linha `verificado` só entrou depois de o trecho existir **literalmente** na página citada (`scripts/curar.py`).

## 7. O que falta
1. **Ligar o dado curado à Maíra** (hoje o chat não conhece pragas, adubação, colheita, armazenamento) e o índice agronômico (`docs/33`).
2. Reescrever em português simples os **valores** das etapas 4 a 10 (hoje só títulos e siglas foram simplificados).
3. Fechar dado: etapa 4 (7/16 culturas), 7, culturas de cobertura, palma e guandu; preço e comercialização (sem fonte).
4. Calcular ETc no motor (Kc por fase) para a etapa 6 dizer quando e quanto irrigar; campo de análise de solo do agricultor.
5. **Validar com técnico local**; decisão D2.
6. Textos de abertura das etapas em `web/.../topicos.model.ts` ainda dizem "a melhor janela" e "sem perder produção".
