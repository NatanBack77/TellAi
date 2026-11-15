# 11. MVP demonstrável do SULCO

Atualizado em 2026-11-12. App Streamlit offline (`src/app/app.py`) que lê só arquivos locais: 195 pontos (184 municípios do Ceará).
Os números citados abaixo vêm de código rodado nesta data (tela, `data/processed/mvp/*.json`, `RESULTADO.md`); na demo, leia-os da tela.

## 1. Como rodar

```
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run src/app/app.py            # abre em http://localhost:8501
.venv/bin/python -m pytest tests -W error -q       # inclui o teste de tela (AppTest) e de tempo de resposta
```

Arquivos que o app lê (todos locais):

| Arquivo | O que é | Como regerar |
|---|---|---|
| `data/processed/pontos.csv`, `clima_diario.parquet` | 195 pontos e clima NASA POWER 2001-2024 | coleta (docs/04) |
| `data/processed/diagnostico/diagnostico.json`, `anomalias.parquet` | diagnóstico REAL dos 195 pontos (~80 s) | ver abaixo |
| `data/processed/mvp/evidencias_rag.json` | trechos do acervo por cultura e critério (~9 min, carrega modelo de embeddings) | `python -m src.app.precalculo evidencias` |
| `data/processed/mvp/auditoria_alternativas.json` | roda o motor nos 195 pontos (milho; 3 prioridades) e mede empates (~2,5 min) | `python -m src.app.precalculo auditoria` |
| `data/culturas/tabela_culturas.csv` | 16 culturas com fonte | `src/culturas` |

O diagnóstico foi gravado fora de `data/processed/modelos/` (outro agente regrava `metricas.json` lá):

```
.venv/bin/python -W ignore -c "
from src.modelos.entrada import RAIZ, carregar_config, carregar_entradas
from src.modelos.diagnostico import diagnosticar_todos, salvar_diagnostico
cfg = carregar_config(); res, anom = diagnosticar_todos(carregar_entradas(cfg), cfg)
salvar_diagnostico(res, anom, RAIZ / 'data/processed/diagnostico')"
```

Se faltar algum arquivo o app mostra `LACUNA: ...` em vez de quebrar. Sem internet o mapa pode ficar sem fundo (os 195 pontos aparecem
e são clicáveis); a lista de municípios funciona sempre.

## 2. O que o app faz (4 passos na página "Meu local")

1. **Entrada.** Mapa (pydeck, clique escolhe o ponto) ou lista; cultura atual (16 da tabela); prioridade. Aviso fixo: o satélite enxerga
   de ~250 m a ~50 km, não o talhão.
2. **Diagnóstico do local** (dados reais): quando o campo costuma ficar nu, quando a vegetação mais sofre, estação chuvosa e veranicos,
   quando a cultura atual é mais vulnerável (adequação por data de plantio e cruzamento do ciclo com solo nu/estresse), tendências, confiança e
   lacunas do diagnóstico.
3. **Três estratégias** (atual + 2 alternativas) pelo motor `src/culturas` (ciclo + Monte Carlo): por quê (cada critério com dado e fonte),
   benefícios (só critério com dado), lacunas, riscos para revisão local, evidência do acervo (ou "sem evidência"), melhor época, faixa,
   empate técnico e cobertura de critérios. Quando há empate técnico, o app diz que não há 1º/2º e lista as empatadas.
4. **Cenário de clima**: controles de chuva (70% a 130%) e temperatura (0 a +3 °C) recalculam o motor de ciclo com o clima alterado e mostram
   as mesmas 3 estratégias lado a lado, com aviso de EXTRAPOLAÇÃO quando o ciclo sai do intervalo já visto no local (2001-2024).

Páginas "Glossário" (NDVI, solo nu, anomalia, SMAP, evapotranspiração, veranico, empate técnico, faixa de incerteza) e "Limites dos dados"
(números lidos de `experimentos/avaliacao_195/RESULTADO.md`, `relatorio_modelos.md`, `auditoria_alternativas.json`, `docs/04_RETOMADA.md`).

## 3. Prioridade do agricultor: regra (SUPOSIÇÃO a validar com técnico)

Cada prioridade vira uma **ordem de importância** entre critérios (faixa ordinal, sem pesos exatos): o motor sorteia pesos que respeitam a ordem
(`Parametros.ordem_pesos`, estilo SMAA-O). Definição em `src/app/mvp.py`, `PRIORIDADES`.

| Prioridade | Ordem (maior para menor) | Bloco que escolhe as alternativas |
|---|---|---|
| Sem prioridade | pesos livres | principal (critérios que todas as culturas têm: temperatura, chuva, família) |
| Economizar água | chuva > temperatura > família | principal |
| Proteger o solo | palha > nitrogênio na biomassa > família > chuva > temperatura | completo (5 critérios; dado ausente de N/palha = incerteza U[0,1], sem prêmio nem castigo) |
| Renda extra | **nenhuma** | igual a "sem prioridade". **LACUNA**: não há dado de preço, custo nem mercado; não altera o ranking nem gera número |

Mudança pequena no motor para isso: `Parametros.bloco_ranking` (padrão `"principal"`, comportamento antigo) e `motor.gerar_cenarios` escolhe as alternativas
pelo bloco pedido. "Economizar água" NÃO mede consumo de água: só prioriza o encaixe da chuva do ciclo na faixa da cultura; a demanda hídrica do
ciclo aparece onde a tabela tem (7 de 16 culturas).

## 4. Roteiro de demo (2 minutos)

Local: **Quixadá (CE)**; cultura atual: **Milho**; prioridade: **Proteger o solo**; depois trocar para **Renda extra**.

| Tempo | Ação | O que dizer |
|---|---|---|
| 0:00 | Abrir; apontar o aviso de "km, não o talhão". Clicar em Quixadá no mapa. | "O agricultor marca a área e diz o que planta e o que importa. Não fingimos certeza: o satélite vê pixels de centenas de metros a dezenas de km, não o seu talhão." |
| 0:20 | Seção 2: gráfico de solo nu e frase de estresse. | "Nos dados de 2001-2024, o verdor de Quixadá fica no seu patamar mais baixo, em pelo menos metade dos anos, de outubro a dezembro. 'Solo nu' aqui é relativo ao próprio local. A confiança é *média*: só 18 anos de NDVI aproveitáveis." |
| 0:45 | Gráfico de adequação por data de plantio da cultura atual. | "Para o milho, o motor acha o melhor início por volta de 17/12; maio é o pior. O ciclo é uma suposição, e o app mostra isso." |
| 1:00 | Seção 3: tabela e as 3 colunas. Ler o aviso de empate técnico. | "Três caminhos: o atual e duas alternativas. Cada critério vem com dado e fonte; o que falta aparece como lacuna. Onde os dados não separam as opções, o app não inventa 1º e 2º." |
| 1:20 | Trocar a prioridade para **Renda extra**. | "Renda não muda nada, e o app diz por quê: não temos preço nem mercado. Preferimos mostrar a lacuna a inventar um número." |
| 1:35 | Seção 4: chuva 70%, temperatura +3 °C. | "Isto não é previsão: é um teste de sensibilidade. Quando o clima sai do que já aconteceu no local, o app avisa 'extrapolação'." |
| 1:50 | Abrir "Limites dos dados". | "O modelo preditivo de NDVI só ganha com a memória do próprio NDVI (+0,24 na confirmação selada); o clima sozinho não supera a média histórica. Por isso ele não dá nota. O app apoia a conversa com o técnico; não substitui." |

Segundo local (se sobrar tempo): **Limoeiro do Norte (CE)** com a mesma cultura: diagnóstico com confiança *alta*, mais seco, pontuação do milho menor.

## 5. Perguntas prováveis dos jurados (respostas honestas)

- **"Qual rotação rende mais?"** Nenhuma ferramenta prova isso. O app compara adequação ao clima e dados de cobertura/nitrogênio com fonte, mostra as lacunas e diz que a decisão é do agricultor com o técnico.
- **"Por que as alternativas são quase sempre as mesmas?"** É um limite real. Na auditoria com milho nos 195 locais, guandu e feijão-caupi aparecem na maioria dos locais com prioridade livre ou de água, e em 100% dessas alternativas há empate técnico (muitas candidatas empatadas). Detalhe e números exatos: página "Limites dos dados". Com "Proteger o solo" a escolha passa a depender das notas de palha e nitrogênio, que vêm de poucos estudos fora do semiárido.
- **"A previsão de NDVI funciona?"** A persistência (verdor da quinzena anterior) dá skill de +0,24 sobre a média histórica na confirmação selada 2022-2024; o clima sozinho não supera a média histórica; a faixa de incerteza cobre menos do que promete. Por isso não entra na nota.
- **"Qual a resolução?"** NDVI 250 m (MODIS), clima ~50 km (POWER), umidade do solo ~9 km (SMAP). São 195 pontos, mas só 59 células de clima: pontos na mesma célula têm o mesmo clima.
- **"As citações do acervo provam os números?"** Não necessariamente. Os valores vêm da tabela de culturas (EcoCrop e estudos citados com fonte). Os trechos do acervo são achados por busca automática e podem não confirmar o valor; o acerto top-5 do RAG é de 54% numa avaliação de 13 perguntas (meta era 80%), e a página "Limites" mostra isso.
- **"E a renda?"** Lacuna declarada: sem dado de preço/custo/mercado.
- **"Por que o ciclo da cultura é 'suposto'?"** O EcoCrop dá faixas largas; o app usa o ponto médio e mostra a sensibilidade (ciclo mínimo/máximo está no JSON de cada estratégia). Decisão pendente do usuário.
- **"Vocês usam IA generativa?"** Não: as explicações são templates sobre números de arquivos.

## 6. Limites e pontos fracos conhecidos (para decisão)

1. Alternativas sem separação: ver pergunta acima; é consequência de notas climáticas que saturam em 1 e de 5 culturas com todos os critérios.
2. Prioridade "solo": palma forrageira é escolhida como alternativa em todos os 194 locais em que o motor devolve alternativas (auditoria, milho), por ter os maiores valores de palha e nitrogênio na tabela (estudos diferentes, min-max entre 10 culturas). O app avisa, mas o resultado reflete o dado, não a cultura.
3. Nomes dos municípios saem do identificador (sem acentos); `pontos.csv` não guarda o nome oficial.
4. O cenário de clima aplica variação uniforme (todos os dias); não representa veranicos nem início da estação. O módulo `src/modelos/cenarios.py` não alimenta o cenário do app (reage pouco ao clima: o ganho do modelo vem da persistência do NDVI); desde a Fase 5 ele é usado só pela API em `GET /modelo/previsao/{ponto_id}` (1 composto à frente, faixa ACI; ver docs/12_API.md).
5. Ciclo, risco aceitável, pesos-base e mapeamento das prioridades são suposições do projeto (docs/06, docs/10).
6. Diagnóstico com confiança *baixa* em 14 locais; o app mostra um alerta.
7. Primeira abertura (carregar clima e bibliotecas) é mais lenta que as seleções seguintes: abra o app antes da demo.
8. (Fase 5, 2026-11-13) ZARC vem LIGADO por padrão no app (`mvp.ZARC_PADRAO = True`, decisão do usuário); no motor (`Parametros.usar_zarc`) o padrão continua desligado. Culturas sem ZARC no município (adubação verde, sorgo) não são restringidas: viés a favor delas, registrado em `experimentos/zarc/RESULTADO.md`. `sobral_ce` não tem código IBGE (sem ZARC, lacuna explícita).
9. (Fase 5) Contagens de nitrogênio na tabela de culturas (conferidas no CSV): N na biomassa em 10 das 16 culturas; N fixado medido em 3 (amendoim, crotalária, mucuna). Textos antigos que diziam 4 e 11 estavam errados e foram corrigidos em `src/culturas/rotacao.py`.

## 7. Estado ao encerrar (2026-11-12, ~21:15)

**Pronto e testado** (`tests/test_mvp.py` + `tests/test_app.py`: 24 passam com `-W error`; app abre sem exceção em AppTest e em servidor headless, health `ok`, HTTP 200):
mapa clicável + lista, cultura atual, prioridade (com renda como lacuna), diagnóstico real dos 195 pontos, 3 estratégias com empate técnico explícito,
cenário de chuva/temperatura com aviso de extrapolação, glossário, limites com números lidos de arquivo.

**Tempos medidos (AppTest, esta máquina, outros processos rodando):** primeira abertura ~6 s (carrega clima e bibliotecas); trocar local ~1,2 s;
trocar cultura ~1,0 s; trocar prioridade ~0,9 s; mover slider ~0,6 s. Motor sozinho: 0,25 a 0,55 s por seleção. O teste exige < 5 s por seleção.

**Parcial / fraco:** acerto do RAG 54% (meta 80%; 43 de 80 pares cultura-critério têm algum trecho); alternativas sem separação (100% em empate técnico
com prioridade livre/água); prioridade "solo" dominada por palma forrageira (dado de poucos estudos); nomes sem acento; mapa sem fundo offline;
`src/modelos/cenarios.py` não usado.

**Suíte completa:** a execução de `pytest tests -W error` inteira foi interrompida ao encerrar (processos de outros agentes disputavam CPU e um `pkill`
meu pode ter encerrado execuções deles). Antes da interrupção, 114 passavam e a única falha era um erro do meu próprio teste, já corrigido.
Rode a suíte inteira de novo antes do commit.

**Decisões pendentes do usuário:** ciclo real das culturas; pesos-base; mapeamento prioridade -> ordem de critérios (seção 3) e validação com técnico;
fonte de preço/mercado para "renda"; incluir mais culturas; aceitar `bloco_ranking` no motor (mudança pequena em `src/culturas/motor.py` e `parametros.py`);
`altair` e `pydeck` fixados em `requirements.txt`.

**Atualização Fase 5 (2026-11-13):** o que o app calcula agora também está na API (`docs/12_API.md`): rotação de 3 safras (`POST /rotacao`), cenário de clima
(`POST /cenarios/clima`), plano MILP como proposta (`POST /plano`), solo estimado SoilGrids (`GET /solo/{id}`), ZARC (`GET /zarc/{id}/{cultura}`) e previsão de 1 composto
(`GET /modelo/previsao/{id}`), todos por import de `src/app/mvp.py` e `src/culturas`. Testes: `tests/test_api.py` (13 passam com `-W error`). Teste de equivalência
app x API não existe; as duas camadas chamam as mesmas funções.

## 8. Próximos passos (em ordem)

1. Rodar a suíte inteira (`.venv/bin/python -m pytest tests -W error -q`) e commitar (inclui `data/processed/diagnostico/` e `data/processed/mvp/`).
2. Ensaiar o roteiro de 2 min no navegador, com internet, e conferir o mapa.
3. Validar com técnico a ordem de critérios por prioridade e o ciclo das culturas.
4. Melhorar a separação das alternativas (mais critérios com dado: demanda hídrica, palha/N com fonte do semiárido).
5. Melhorar o RAG (mais fontes em português sobre rotação/palhada) e regerar `evidencias_rag.json`.
6. Nomes oficiais dos municípios (IBGE) em `pontos.csv`; opção de rodar a auditoria com outras culturas atuais.
7. Quando a persistência entrar em `src/modelos`, avaliar um cenário de NDVI separado do cenário do motor de ciclo.


## 9. Atualização 2026-11-13: seções 2b e 3b da página "Meu local"
- **2b. Chuva da quadra (fev–mai):** média, variabilidade e anos secos do local (clima POWER 2001–2024); relação com o rendimento municipal do IBGE (PAM 2015–2023)
  em quadra seca/úmida e R²; aviso de que é associação histórica, de que o rendimento do IBGE é estimado e de que a previsão da próxima quadra é da FUNCEME.
  Código: `src/app/quadra.py`; testes: `tests/test_quadra.py`.
- **3b. Rotação em 3 safras:** sequências de 3 safras (uma por ano) partindo da cultura atual, com a rotação do agricultor (opcional), textura e matéria orgânica
  do solo (avisos de risco, não alteram nota) e ZARC opcional. Critérios: adequação ao clima do ciclo, diversidade de famílias (proxy de pragas), leguminosa antes de
  não leguminosa (regra a validar), palha e demanda hídrica (lacuna quando falta). Só as 80 sequências de maior nota média entram na simulação de incerteza (tempo).
  Empate técnico entre alternativas continua; separa bem rotação x repetir a mesma cultura. Código: `src/culturas/rotacao.py`; testes: `tests/test_rotacao.py`.

## 10. Atualização 2026-11-14: "Seu perfil" no topo (substitui a entrada do item 2.1)
- **Sem cultura padrão.** O campo "Culturas que eu planto ou penso em plantar" (multisseleção, 0 a N) começa VAZIO; a primeira cultura é a base dos três caminhos, as demais ficam no perfil ("também considero") e no chat. Há também "Ainda não sei / quero conversar". Sem cultura, "Meu local" mostra só o retrato do local (satélite, quadra, risco de solo, extremos, balanço) e o convite "Conte no chat o que você planta...". Três caminhos, rotação de 3 safras, cenário de clima, renda e cartão só aparecem com ao menos uma cultura.
- **Seção única recolhível** (abre sozinha enquanto não há cultura): município, culturas, prioridade, manejo e água, textura, matéria orgânica, safras 2 e 3 da rotação atual, equipamento e mercado (filtros que só consultam), **regras do agricultor** e **campos que só registram**. Os campos antes espalhados (3b e "Condições da sua área") foram para cá, com as mesmas chaves.
- **Regras** (ligadas a `src/culturas/regras_duras.py`): "não quero plantar", "preciso incluir", "máximo de safras seguidas da mesma cultura" (vazio = sem regra), "aceito pousio" (só registra). A tela diz quantas alternativas foram descartadas, por quê, e se foram todas; a rotação atual dele nunca some (aviso se violar).
- **Só registram** (nunca entram na conta): área (ha), mês em que costuma plantar (só comparado com a melhor época já calculada), declive percebido, acesso a mercado/transporte.
- **Guardar sem servidor:** "Baixar meu perfil (JSON)" e "Carregar perfil" (validado por schema, nada executado). O perfil entra no cartão ("O que você informou"), nos fatos do chat (sem nome, ponto_id, lat, lon) e na API (`regras` em `/cenarios` e `/rotacao`; `perfil` em `/chat`).
- **Conversa consultiva:** `src/app/ligacao_conversa.py` é o ponto de ligação (chips de resposta rápida + estado `{culturas_citadas, foco}`); a seção aparece em "Pergunte ao Sulco" só quando `src/llm/conversa.py` existir.
- Detalhes, schema e testes: `docs/21_resultados_fases/PERFIL_AGRICULTOR.md`.
