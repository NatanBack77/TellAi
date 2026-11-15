# 34. Plano de plantio em 10 etapas

Atualizado em 2026-11-15 (noite). **O back-end está implementado e testado** (dado curado + rota `POST /plano-plantio` + 34 testes). **Ainda não existem as telas** (`frontend/`) nem a Maíra no contexto da etapa. Nada aqui foi validado com técnico local nem com agricultor.

## 1. O que é
Depois que o agricultor escolhe o local e a cultura, o Sulco monta um plano guiado em 10 etapas, sempre nesta ordem e com estes nomes (dados pelo usuário, não mudam):

1. Introdução ao Plantio
2. Recomendação de Plantação
3. Clima e Época de Plantio
4. Preparação do Solo
5. Semeadura e Plantio
6. Irrigação e Cuidados com a Água
7. Adubação e Nutrição
8. Desenvolvimento e Manutenção
9. Colheita
10. Pós-colheita e Armazenamento

Regras do produto que valem em todas as etapas (`docs/32`): nenhum número inventado; lacuna aparece como "sem dado"; não prometer lucro, colheita nem clima futuro; não dizer qual rotação é melhor (comparar e dizer "empate técnico" quando for); "converse com o técnico" sempre à vista; linguagem simples.

## 2. De onde vem cada etapa e o que existe hoje
Etapas **2 e 3** vêm do motor e do calendário que já existiam (`src/plano/motor_etapas.py`, nada novo é calculado). As demais vêm de **dado curado com fonte** (`data/plano/plano_plantio.csv`, 377 linhas, gerado de `data/plano_staging/claude/`). Culturas = as 16 da tabela de culturas.

| # | Etapa | Origem | Culturas com dado | Linhas com fonte | O que a etapa entrega |
|---|---|---|---|---|---|
| 1 | Introdução | curado | 15 de 16 | 33 | finalidade, importância e limitação da cultura |
| 2 | Recomendação | motor | todas | — | a cultura no local (viabilidade, anos em que o clima comportou o ciclo) e os caminhos comparados, **com "empate técnico"**; sem renda |
| 3 | Clima e Época | motor | todas | — | janela do zoneamento (ZARC, risco até 30%), duração do ciclo, quando costuma chover, maior período seco |
| 4 | Preparação do Solo | curado | **7 de 16** | 13 | solo que a cultura pede, preparo, pH, análise de solo e calagem |
| 5 | Semeadura e Plantio | curado | 14 de 16 | 36 | espaçamento, densidade, semente por hectare, profundidade, inoculação, consórcio |
| 6 | Irrigação e Água | curado | 11 de 16 | 35 | Kc por fase (FAO-56, clima sub-úmido) e fase mais sensível à falta de água; **sem método, lâmina nem turno** |
| 7 | Adubação e Nutrição | curado | 11 de 16 | 20 | **referência da fonte** (nunca prescrição): base na análise de solo, calagem, fósforo, esterco |
| 8 | Desenvolvimento | curado | 16 de 16 | 55 | fases, capina, período crítico do mato, pragas e doenças (ocorrência, sintoma, manejo cultural) |
| 9 | Colheita | curado | 15 de 16 | 40 | como saber que é hora, método, umidade, dias até a colheita, perdas |
| 10 | Pós-colheita | curado | 11 de 16 | 44 | secagem, armazenamento, embalagem, pragas de grão guardado; **sem preço nem comercialização** |

Lacunas conhecidas: faltam dado nas etapas 4, 6, 7 e 10 para várias culturas (principalmente milho, sorgo, caupi, feijão-comum e palma na etapa 4; palma, guandu e adubos verdes no Kc e no pós-colheita). Crotalária, mucuna e feijão-de-porco **não se aplicam** ao pós-colheita de grão. Detalhe por cultura: `GET /plano-plantio/culturas`.

## 3. Contrato da API (`src/api/rota_plano.py`)
- `POST /plano-plantio` `{ponto_id, cultura}` → `{versao, ponto_id, cultura, cultura_nome, etapas[10], cobertura_itens, limites, aviso}`.
- `GET /plano-plantio/culturas` → culturas com plano e itens por etapa. `GET /plano-plantio/etapas` → o contrato das etapas.
- Cada etapa: `{numero, slug, titulo, origem: dado_curado|motor, itens[], lacunas[], nao_se_aplica, aviso_tecnico}`.
- Cada item: `{atributo, rotulo, valor, unidade, status, fonte{nome, pagina, url}, trecho, contexto, requer_tecnico, referencia_da_fonte, experimento}`.
  - `status`: `verificado` (trecho de publicação conferido na página), `calculado` (vem do motor), `lacuna`, `nao_se_aplica`. Lacuna não tem valor; **o front nunca preenche**.
  - `requer_tecnico`: mostrar "converse com o técnico antes de aplicar" junto do item. `referencia_da_fonte`: é o que a fonte diz, **não** recomendação para o terreno. `experimento`: valor de parcela de experimento, não recomendação de plantio. `contexto`: de onde vem (região da fonte); mostrar junto do valor.
- Regras aplicadas **no servidor** (testadas), que o front não precisa lembrar: nenhum caminho de arquivo na saída; trecho que cita produto ou fumigação não sai (`trecho: null`); a nota interna de revisão técnica não sai (só `requer_tecnico`); termo de produto/defensivo no valor ou contexto derruba a carga do dado.
- O limite de taxa "pesado" já cobre o caminho (prefixo `/plano`). Primeira chamada ~3 s (motor); depois ~0,2 s.

## 4. Suposições e decisões
- **D1 (suposição aplicada).** O agricultor **escolhe a cultura**; o sistema não escolhe por ele. Cada plano é de uma cultura.
- **D2 (PENDENTE de confirmação do usuário).** Como a adubação aparece ao agricultor. O que foi implementado: doses só como "o que a fonte diz" (`referencia_da_fonte`, sempre com a condição da fonte, ex.: análise de solo), nunca como instrução; nenhum produto nem dose de agrotóxico. *Nota: uma versão anterior deste documento dizia "VALIDADA pelo usuário em 15/11". Isso foi escrito por um agente sem confirmação do usuário e foi removido.*
- **D3 (aplicada).** Etapa sem dado mostra a lacuna e o que falta, em vez de sumir.
- **D4 (novo, precisa do front).** O contrato ganhou os status `calculado` e `nao_se_aplica`, além de `verificado` e `lacuna`.

## 5. Como gerar e testar
```
python -m src.plano.construir            # regera data/plano/plano_plantio.csv e o manifesto a partir de data/plano_staging/claude/ (falha se a validação não passar)
SULCO_PREAQUECER=0 .venv/Scripts/python -m pytest tests/test_plano.py -q     # 34 testes
```
A curadoria (scripts e fontes) está em `data/plano_staging/claude/` (`scripts/`, `RELATORIO.md`, `correcoes_1_8_9.csv` com o antes/depois de cada correção) e `data/plano_staging/fontes_op/` (PDFs baixados). Cada linha `verificado` só entrou depois de o trecho existir **literalmente** na página citada (`scripts/curar.py`). Isso prova que o trecho existe; não prova que serve ao local do agricultor.

## 6. O que falta
1. **Telas** no front (`frontend/`): uma por etapa, navegação entre elas, botões grandes, `lacunas` sempre visíveis, `requer_tecnico`/`referencia_da_fonte`/`experimento` como avisos junto do item. Tratar os status `calculado` e `nao_se_aplica`.
2. **Maíra** responder no contexto da etapa em que a pessoa está; ligar o índice agronômico (`docs/33`).
3. Fechar o dado: etapa 4 (7 de 16 culturas) e 7 (adubação), culturas de cobertura, palma e guandu no pós-colheita; preço e comercialização (sem fonte estruturada).
4. Calcular ETc no motor (Kc por fase) para a etapa 6 dizer quando e quanto irrigar.
5. **Validar com técnico local** (BL5): espaçamentos, referências de adubação e pragas hoje são "o que a fonte diz".
6. Campo opcional "análise de solo do agricultor" (pH, fósforo, potássio, matéria orgânica) para a etapa 7 deixar de ser só referência geral.
7. Decisão do usuário sobre a D2.
