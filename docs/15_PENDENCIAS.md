# Pendências do SULCO (lista completa e organizada)

Reescrito em 2026-11-13 consolidando a versão de 2026-11-12 (21h20) e o que foi feito depois. Nenhum item anterior foi removido: os já feitos estão em "Concluído (com data)" no fim; o mapa "item antigo → novo ID" está no final.
Marcas: **[DECISÃO SUA]** precisa de você; **[FAZER]** trabalho técnico; **[VERIFICAR]** conferir antes de afirmar; **[BLOQUEADO]** depende de algo externo.
Princípio: o produto é apoio à decisão do agricultor (marcar a área, cultura atual, prioridade; épocas de solo nu e de estresse; 3 caminhos com lacunas; sem fingir certeza). A previsão do NDVI é módulo de apoio.
Contexto: `docs/18_ARQUITETURA_TECNICA.md` (como tudo funciona), `docs/04_RETOMADA.md` (por onde começar), `docs/19_ALINHAMENTO_AO_DESAFIO.md` (lacunas frente ao desafio).

## 1. Bloqueios

- **BL1 [BLOQUEADO] Chave DeepSeek** (antigo 19). Sem `DEEPSEEK_API_KEY` no `.env` a camada LLM nunca foi chamada de verdade. Código: `src/llm/provedores.py`. Próximo passo: criar a chave em platform.deepseek.com/api_keys, pôr no `.env`, rodar 5 cenários reais e contar rejeições do verificador (`docs/14_LLM.md` seção 7). Ligado a DU9.
- **BL2 [FAZER, urgente] Trocar a senha do Earthdata** (antigo 28). Foi digitada numa conversa com o assistente. Próximo passo: trocar no site do Earthdata e atualizar o `.env` (nunca commitar).
- **BL3 [BLOQUEADO] ERA5-Land / GLDAS / FLDAS** (antigo 3). Earth Engine e CDS exigem cadastro novo; GLDAS/FLDAS via Earthdata é possível. Scripts iniciais em `experimentos/previsao_doc09/t3_*.py` (download não concluído). Ver M3.
- **BL4 [BLOQUEADO] FUNCEME** (antigo 26). Rede de ~500 pluviômetros sem API oficial confirmada; o certificado do site foi bloqueado na pesquisa (`docs/09`). Próximo passo: pedir acesso/dados à FUNCEME ou desistir; enquanto isso o app aponta para a previsão sazonal da FUNCEME sem reproduzi-la.
- **BL5 [BLOQUEADO] Validação com técnico local**. Várias suposições só fecham com um técnico: ordem de critérios por prioridade (DU6), ciclo real (DU1), pesos (DU4), regra "leguminosa antes de não leguminosa" (`rotacao.py`), valores de palha/N de estudos fora do semiárido. Próximo passo: agendar uma conversa e levar a lista `docs/11_MVP.md` seção 3 e `docs/10` seção 6.

## 2. Decisões do usuário

- **DU1 [DECISÃO SUA] Ciclo real das culturas e data de início** (antigo 7). Hoje: ponto médio do EcoCrop (`Parametros.ciclo_modo="medio"`), início a cada 10 dias. O ciclo escolhido pesa mais que o município (`docs/10` seção 4). Próximo passo: definir por cultura (ou regra mín/médio/máx, ou ciclo de cultivar do ZARC) e a data de início.
- **DU2 [DECISÃO SUA] `risco_max`** (antigo 8; hoje 0,30; `src/culturas/parametros.py`). Fração de anos que pode falhar para a cultura seguir "viável". Não é o risco do ZARC.
- **DU3 [DECISÃO SUA] Definição de "empate técnico" e percentis da faixa** (antigo 8; hoje intervalos p10–p90 que se sobrepõem). Também: como desempatar (doc 06 pergunta 4: mostrar empatadas, como hoje, ou regra sua).
- **DU4 [DECISÃO SUA] Pesos-base** (antigo 8; hoje 0,25/0,25/0,20/0,15/0,15 em `motor.PESOS`, sem fonte). O Monte Carlo sorteia pesos, mas o score central usa estes. `Parametros.ordem_pesos` aceita ordem; faixas min-max não foram implementadas.
- **DU5 [DECISÃO SUA] Lista de culturas** (antigo 8): hoje 16. Faltam, sem valor nenhum acrescentado: melancia, abóbora, quiabo, maxixe, leucena, gliricídia, sisal, cebola, capins forrageiros. Cobertura/adubação verde (crotalária, mucuna, feijão-de-porco) e comerciais na mesma lista ou em rankings separados? Preencher N e palha com fonte antes de pesar esses critérios (doc 10 item 8).
- **DU6 [DECISÃO SUA] Mapeamento prioridade → ordem de critérios** (antigo 9). SUPOSIÇÃO a validar com técnico (`mvp.PRIORIDADES`, `rotacao.ORDEM_PRIORIDADE`, `docs/11_MVP.md`). "Renda" é lacuna hoje (ver C9).
- **DU7 [DECISÃO SUA] ZARC** (antigo 14, parte aberta). Já decidido: ligado por padrão no app. Em aberto: nível de risco (padrão 30; opções 20/30/40), solo ("qualquer" x "todos"; no app o solo vem da textura), mapeamento de feijão comum → "Feijão 2ª Safra", sorgo sem ZARC (granífero x forrageiro ambíguo) e janela aproximada das culturas sem ZARC (união das anuais).
- **DU8 [DECISÃO SUA] `sobral_ce`** (antigo 15). A coordenada cai fora do polígono de Sobral; fica sem código IBGE (183 códigos únicos no CE, não 184) e sem ZARC. Corrigir a coordenada (e o clima associado) ou aceitar o código 2312908?
- **DU9 [DECISÃO SUA] Chave DeepSeek e modelo** (antigo 19): ver BL1. Os IDs `deepseek-flash` e `deepseek-v4-pro` foram lidos por ferramenta que resume a página: **[VERIFICAR]** antes de ligar.
- **DU10 [DECISÃO SUA] Camada LLM** (antigo 20): (a) enviar nome do município e a pergunta a uma API externa é aceitável (lat/lon e dados pessoais já são removidos)? (b) embeddings no `responder` ou só BM25? (c) recusar "qual rotação devo escolher" é a leitura certa da regra 3? (d) "garante"/"lucro" barrados mesmo em negação.
- **DU11 [DECISÃO SUA] `pers_lags4`** (antigo A-nota "decisão sobre pers_lags4"): ganho marginal (+0,005), não integrado. Integrar ou não.
- **DU12 [DECISÃO SUA] Regras do motor** (docs `10` seção 6 e `06`): o mínimo (temperatura, chuva) deve entrar no score em vez de só escolher a janela? `demanda_hidrica_mm_ciclo` (7 culturas) vira filtro ou fica informativa? Vale ranquear só pelos critérios comuns, com N e palha à parte (já implementado assim; confirmar)?
- **DU13 [DECISÃO SUA] Como usar o valor da produção do IBGE** como critério de renda (ver C9): receita bruta por hectare não é lucro; escolher o recorte (cultura, ano, município) e o texto de aviso.
- **DU14 [DECISÃO SUA] Pontos do demo (S2)** (antigo 10): a lista é proposta; os 195 pontos e os do demo precisam de revisão sua. Perguntas antigas ainda abertas (`docs/03`): escala/valores de `confiabilidade` do NDVI e quais descartar (hoje 0 e 1 aceitos).
- **DU15 [DECISÃO SUA] Plano de várias safras (MILP)**: manter como "proposta" no expander (hoje) ou promover? Recomendação do experimento: rotular como proposta e não substituir o SMAA (`experimentos/milp/RESULTADO.md`).

## 3. Técnico por área

### 3.1 Modelos (`src/modelos/`)
- **M1 [FAZER] Teste de horizonte e estação** (antigo 2): +1 a +4 compostos e chuvosa/seca para `base`, `persistencia`, `pers_lags4`, só 2010–2021. Parcial em `experimentos/previsao_doc09/` (`t1_*.py`; `t1_linhas.pkl` é ignorado pelo git; o placebo foi interrompido). Mostra onde o clima pode ajudar (a literatura indica R² 0,69 → 0,35 → 0,16 em 1, 2, 3 meses). Próximo passo: rodar `t1_horizonte.py` e `t1_placebo` com N declarado.
- **M2 [VERIFICAR] Grade do SMAP** (antigo 4): catálogo do Earth Engine diz 11 km, nossa doc diz 9 km. Conferir nos metadados do arquivo HDF5.
- **M3 [FAZER] Fonte nova de chuva/umidade com série longa** (antigo 3): ERA5-Land ou GLDAS/FLDAS. Testar pelo protocolo (só 2010–2021, N no Bonferroni, placebo, pareado contra `pers_lags4`). Depende de BL3.
- **M4 [FAZER] SMAP como feature** (antigo 5): só vale com mais anos (série desde 2015; seleção só 2018–2021, IC pouco confiável). Ganho ~+0,006 a +0,007; desligado por padrão.
- **M5 [VERIFICAR] Amostra efetiva** (antigo 6): só 59 células de clima para 195 pontos; confirmação com 3 anos; mais pontos melhoram pouco o poder (a unidade independente é o ano, antigo 27).
- **M6 [FAZER] EVI/SAVI** (antigo 26 parcial): agente interrompido, sem resultado; cache parcial em `experimentos/expB_indices/` (`baixar.py` é idempotente; depois `montar.py` + `rodar.py`). A literatura sugere SAVI em vegetação esparsa.
- **M7 [FAZER] CHIRPS**: concluído sem ganho em 13 pontos (poder baixo). Reabrir só se houver motivo novo; `experimentos/expA_chirps/RESULTADO.md`.
- **M8 [FAZER] Cobertura por ano do conformal**: o ACI cobre 80,9% / 90,6% na média, mas o pior ano (2022) cobriu 71,7% / 84,8% (`metricas.json`). Garantia é de longo prazo. EnbPI não foi testado (ver seção 4).
- **M9 [VERIFICAR] `confianca` e semântica da `pixel_reliability` (0–3)**: ainda "a conferir" na doc oficial (`config.yaml`).
- **M10 [FAZER] `src/modelos/cenarios.py` fora do app**: o app usa o motor de ciclo para os cenários; a faixa ACI de `cenarios.py` não é mostrada. Decidir se o NDVI previsto aparece em alguma tela (hoje só na página "Limites").
- **M11 [FAZER] `shap`**: não instalado (sem wheel confirmada para Python 3.14); a explicação usa `pred_contribs`.
- **M12 [FAZER] Relatório da raiz desatualizado**: a página "Limites dos dados" lê `relatorio_modelos.md` da raiz (`src/app/logica.py: caminho_relatorio`), que é o relatório antigo de 13 pontos (Ridge, skill -0,021); a API lê `data/processed/modelos/relatorio_modelos.md` (atual). Próximo passo: apontar `caminho_relatorio` para `data/processed/modelos/relatorio_modelos.md` (ou copiar o arquivo) e ajustar `test_mvp.py: test_relatorio_real_do_projeto_nao_supera` se necessário.
- **M13 [FAZER] CLI do walk-forward imprime 2022–2024**: `python -m src.modelos.walkforward` avalia 2010–2024 de uma vez e mostra a confirmação (viola "só olhar uma vez"); `experimentos/avaliacao_195/avaliar.py` foi o desvio usado. Próximo passo: opção `--so-selecao` na CLI.

### 3.2 Motor de culturas e rotação (`src/culturas/`)
- **C1 [FAZER] Empate técnico entre alternativas** (antigo 25 e 5e): em 100% dos locais testados (388/388 com milho) e na rotação de 3 safras; separa bem rotação x repetir a mesma cultura. Depende de dado novo e das decisões DU1–DU6. Mostrar honestamente (já mostrado).
- **C2 [FAZER] Lacunas da tabela de culturas** (antigo 10 e 3): 34 lacunas em 240 linhas (demanda hídrica 9 culturas sem dado, N acumulado 6, palha 6, N fixado 13), `data/culturas/tabela_culturas.csv`. N fixado tem dado só para 3 culturas na tabela (amendoim, crotalária, mucuna); `docs/19` e `rotacao.py` dizem 4 e N na biomassa "11" (tabela: 10): **[VERIFICAR]** e corrigir o texto. Palma domina a prioridade "solo" no motor de 3 estratégias nos 194 locais com alternativas (maiores valores de palha/N, estudos diferentes). Próximo passo: achar fonte do semiárido para as lacunas (acervo, Embrapa Semiárido), com trecho e página. **Contagem confirmada em 2026-11-13 pela tabela (`tabela_culturas.csv`): N fixado em 3 culturas (amendoim, crotalária juncea, mucuna); N na biomassa em 10; os comentários de `src/culturas/rotacao.py` e o texto de testes ainda dizem 4 e 11 (corrigir quando for autorizado mexer em código).**
- **C3 [VERIFICAR] Faixa de chuva do EcoCrop anual ou do ciclo?** (antigo 11). Divergências EcoCrop x FAO (girassol, amendoim, algodão, milho) em `docs/06`. EcoCrop veio de espelho do GitHub (OpenCLIM, commit ea43ecd), não do site da FAO.
- **C4 [FAZER] `sensibilidade.py` e `docs/06` descrevem o motor antigo** (antigo 12): perfil anual, desempate alfabético. No ciclo só entram 23 anos de clima (a janela de 2024 passa do fim da série).
- **C5 [VERIFICAR] Casos extremos** (antigo 13): Petrolina-PE tem milho inviável e o motor não devolve alternativas (a tela mostra lacuna); a pontuação central pode cair fora de p10–p90 (ex.: Caridade).
- **C6 [FAZER] Renda e preço**: ver C9 (valor da produção) e dado de preço/mercado (CONAB, CEPEA) ainda sem fonte.
- **C7 [FAZER] Pragas e doenças**: lacuna declarada; só proxy (diversidade de famílias). Sem dado no projeto.
- **C8 [FAZER] PAM cobre só lavouras temporárias (tabela 1612)**: palma e outras perenes ficam sem contexto de município (`rotacao.PAM_PRODUTO` não tem palma); feijão caupi e comum não se separam. **[VERIFICAR]**.
- **C9 [FAZER] Renda na prioridade "renda"** (item 1 dos itens do usuário): `valor_producao_mil_reais` (variável 215 do IBGE) já está em `data/processed/pam_ce.parquet` e não entra em nenhuma nota. Próximo passo: receita bruta por hectare = valor da produção ÷ área colhida, por cultura e município (último ano e mediana), como critério da prioridade "renda" com aviso de que não é lucro. É o mesmo item A3 da seção 3.9.
- **C10 [FAZER] Plano MILP**: `otimizar_com_incerteza` (novo) não está descrito em `experimentos/milp/RESULTADO.md`; `experimentos/milp/incerteza.py` é o script. Atualizar o resultado com os números. O MILP não reduz o empate (ver DU15).

### 3.3 Dados
- **D1 [FAZER] Terreno SRTM fora do app** (antigo 2 do pedido): `data/processed/terreno.parquet` (altitude, declive) coletado e testado como feature (não ajuda o NDVI), mas não aparece no app. Ver A1 (erosão) na seção 3.9.
- **D2 [FAZER] Uso do solo (MapBiomas), INMET**: não feitos (antigo 26).
- **D3 [FAZER] Tarefa AppEEARS antiga** (`data/raw/modis/tarefa.json`, estado `done`, não baixada): descartar ou baixar.
- **D4 [FAZER] Nomes oficiais dos municípios** (antigo 18): `pontos.csv` só tem `ponto_id` sem acento; o nome na tela deriva do id (`mvp.nome_do_ponto`). Próximo passo: coluna `nome` oficial vinda do IBGE.
- **D5 [FAZER] `pontos.csv` é sobrescrito por `python -m src.coleta.power`** (perde a coluna `ibge`). Próximo passo: o coletor deve preservar `ibge`; até lá, rodar `python -m src.coleta.ibge_codigos` depois.
- **D6 [VERIFICAR] SoilGrids**: 181 de 195 pontos com pixel central válido (os demais usam mediana da janela de ~2 km); é modelagem global, não análise de solo.
- **D7 [FAZER] Fontes brasileiras de solo alternativas** (BDiA/Embrapa) para validar o SoilGrids.
- **D8 [FAZER] Índices NOAA em `data/raw/indices/`**: não há módulo de coleta em `src/coleta`; documentar/criar o coletor se for reusar.

### 3.4 ZARC
- **Z1 [VERIFICAR] Significado de `decN`** (0 sem indicação; 20/30/40 risco máximo): leitura observada; o dicionário oficial não descreve (`src/coleta/zarc.py`). Confirmar nas portarias.
- **Z2 [FAZER] Portarias do ZARC no acervo RAG**: faltam (ver R1).
- **Z3 [FAZER] 11 pontos fora do Ceará sem ZARC** e `sobral_ce` sem código (DU8): o app só aplica ZARC ao CE; para os demais usa o clima. Próximo passo: coletar UF dos 11 pontos (`coletar(uf=...)` aceita UF) ou declarar.
- **Z4 [FAZER] Validação das janelas** com ciclo real e técnico (`experimentos/zarc/RESULTADO.md`: "não há validação com ciclo real ainda").
- **Z5 [FAZER] Manejo irrigado do ZARC**: só sequeiro é usado; ver A6.

### 3.5 API (`src/api/main.py`, `docs/12_API.md`)
- **P1 [FAZER] `GET /modelo/previsao/{ponto_id}` responde 501** (antigo 16): treinar/carregar o modelo com persistência via `cenarios.treinar_para_cenarios`, cachear em disco e devolver anomalia prevista + faixa ACI + limites. Sem clima futuro só há retrospectiva do último composto (decidir o que mostrar).
- **P2 [FAZER] `/evidencias` lento** (antigo 17): ~28 s na 1ª chamada (embeddings e reranker) e ~8 s depois. Próximo passo: pré-aquecer na subida e cachear respostas.
- **P3 [FAZER] Cenário de clima só no app** (antigo 17): não exposto em `/cenarios`. Rotação de 3 safras, plano MILP e ZARC também não estão na API (`/cenarios` usa `Parametros()` com ZARC desligado).
- **P4 [FAZER] Testes que faltam**: `/evidencias` com acervo real (aceita 200 ou 503) e 404 de ponto sem diagnóstico (`docs/12`).
- **P5 [FAZER] `src/llm` não integrado à API** (ver L2).

### 3.6 Camada LLM (`src/llm/`)
- **L1 [FAZER] Nunca chamou a API real**: ver BL1/DU9.
- **L2 [FAZER] Integrar ao app e à API** (antigo 21): `servico.reescrever(cenario, provedor=obter(), cache=Cache(), offline=True)` com o template como padrão.
- **L3 [FAZER] Cache do demo** (`data/processed/llm_cache/`) pré-gerado e versionado; sem cache o modo offline cai no template.
- **L4 [FAZER] Avaliação das 20 perguntas** estilo agricultor com LLM real; medir citações corretas, latência e custo (estimativa de US$ 0,00108 por chamada é cálculo nosso, com tamanhos de token supostos).
- **L5 [VERIFICAR] IDs de modelo** (`deepseek-flash`, `deepseek-v4-pro`) e formato do corpo de erro (não está na doc).
- **L6 [VERIFICAR] Limite do verificador**: valida forma e números, não a fidelidade semântica; `responder` com embeddings não foi reavaliado; `responder` não foi rodado contra o índice real.

### 3.7 RAG (`src/rag/`)
- **R1 [FAZER] Acerto de 54%** (meta 80%) numa avaliação de 13 perguntas; 80% em 25 perguntas de teste (frágil); 57% no DEV (antigo 22). Faltam documentos: Emater, INSA, portarias do ZARC, EcoCrop paginado, cartilha de palma. `www.infoteca.cnptia.embrapa.br` resolve; sem `www` não.
- **R2 [FAZER] Perguntas em português sobre documentos em inglês (FAO): 0%.** Próximo passo: traduzir a pergunta (expansão de consulta já existe em `busca.expandir_consulta`, desligada por padrão).
- **R3 [VERIFICAR] Trechos x valor da tabela** (antigo 23): só 43 de 80 pares cultura-critério têm algum trecho, e nem sempre confirmam o valor; a tela avisa.
- **R4 [VERIFICAR] Limiar do portão** (cosseno 0,87, 60% dos termos): calibrado com poucas perguntas negativas (margem pequena).
- **R5 [FAZER] `indice/` não é versionado**: reconstruir com `python -m src.rag.rag_docs` (precisa de `pdftotext`).

### 3.8 App (`src/app/`, `docs/11_MVP.md`)
- **AP1 [FAZER] Cartão de uma página do município (PDF) e zoom órbita → município** (antigo 24): propostos e NÃO construídos.
- **AP2 [FAZER] Mapa sem fundo offline** (antigo 24): pydeck precisa de internet para o fundo; os pontos aparecem.
- **AP3 [FAZER] Texto desatualizado em "Limites dos dados"**: diz "Não há dado de ... solo ... nem zoneamento (ZARC)" (`app.py`), mas ZARC e solo estimado já entram. Corrigir o texto e ver M12.
- **AP4 [FAZER] Teste com agricultor/técnico**: nunca feito (`docs/19` item 35).
- **AP5 [FAZER] Docs do app**: `docs/11_MVP.md` seções 6 e 7 (limites e estado) estão defasadas (ex.: cenarios.py, ZARC, solo).

### 3.9 Lacunas frente ao desafio da NASA (`docs/19_ALINHAMENTO_AO_DESAFIO.md`, "Maiores lacunas", em ordem)
- **A1 [FAZER] Erosão e infiltração** (itens 21, 29b, 33): indicador de risco combinando declive SRTM (`data/processed/terreno.parquet`) com textura e carbono do SoilGrids (`data/processed/solo.parquet`), como camada no mapa. Declive é indicador de risco, não modelo de erosão.
- **A2 [FAZER] Evapotranspiração e balanço hídrico** (itens 12, 20, 23): ETo por Hargreaves-Samani (Tmax, Tmin, radiação do POWER) e saldo chuva − ETo por quinzena.
- **A3 [FAZER] Renda** (itens 5, 22, 29e): receita bruta por hectare a partir do valor da produção do IBGE (`data/processed/pam_ce.parquet`, variável `valor_producao_mil_reais`) na prioridade "renda". (Mesma questão de C9 e DU13.)
- **A4 [FAZER] Calor e chuva extrema** (itens 9, 14): dias com Tmax acima de um limiar e índice de chuva extrema a partir do POWER diário (ou GPM/IMERG para nomear a base). O limiar de calor é decisão (DU) sua ou do técnico.
- **A5 [FAZER] Mapa com camadas coloridas por indicador e linha do tempo** (itens 32, 34a, 34b): colorir os pontos por solo nu, declive, variabilidade da quadra, tendência e adicionar controle de ano.
- **A6 [FAZER] Entradas do agricultor** (item 36): irrigado ou sequeiro (o ZARC tem manejo irrigado: `Cod_Outros_Manejos` 2 e 3 em `zarc_ce.parquet`), água disponível, equipamento e preferência de mercado, como filtros. Próximo passo: adicionar o campo manejo ao `Parametros`/`zarc.py` e à tela 1.
- **A7 [FAZER] Explicações curtas no glossário** (itens 23, 31): fixadoras de N, adubação verde, raízes profundas, ET e balanço hídrico, com trecho do acervo. Hoje o glossário tem 8 termos (`mvp.GLOSSARIO`).
- **A8 [FAZER] Valor forrageiro** (item 29d): palma, sorgo e milheto, com os PDFs do MAPA já no acervo (`mapa_2021_forrageiras_semiarido.pdf`, `mapa_2021_forragem_semiarido_ajustes.pdf`, `embrapa_caprinos_cardapio_forrageiro.pdf`); entrar na tabela de culturas com fonte, página e trecho.
- **A9 [FAZER] Registrar por que ECOSTRESS, GPM, GRACE e GEDI foram usados ou descartados** (itens 9, 14, 16, 28): escrever uma seção em `docs/16_PESQUISA.md` ou `docs/19`. Não aplicável: geada (13); GEDI em caatinga baixa e GRACE em escala de município têm baixo retorno.

### 3.10 Repositório e infraestrutura
- **I1 [FAZER] Segredos**: `.env` fora do git; trocar a senha do Earthdata (BL2).
- **I2 [VERIFICAR] Pastas pesadas**: `experimentos/previsao_doc09/t1_linhas.pkl` (46 MB) é ignorada (`experimentos/**/*.pkl`); `indice/` também; `data/raw/*` ignorado exceto `modis_ornl/` e `indices/` (os caches de POWER e SMAP vão como `.tar.gz`; `data/raw/smap/` não está extraído nesta máquina).
- **I3 [FAZER] Suíte pesada**: `tests/test_rag.py` (~7 min) e testes de API/app carregam embeddings; foram rodados em separado, nunca juntos com `-W error` em uma execução só nesta rodada. Próximo passo: rodar por partes antes do commit (ver `docs/04_RETOMADA.md`).
- **I4 [FAZER] `scripts/setup.sh` é bash** e usa `.venv/bin/python`; no Windows precisa de Git Bash/WSL ou comandos manuais.
- **I5 [FAZER] Docs defasados**: `docs/13_ZARC.md` (plano original; cabeçalho já avisa), `docs/12_API.md` ("ZARC não integrado"), `docs/17_PITCH.md` (tabela diz "mapa de solo em coleta"; agora está coletado e no app), `docs/06` (motor antigo), `docs/01_VISAO_GERAL.md` (SoilGrids como "plano B do SMAP").
- **I6 [VERIFICAR] Contagem de testes**: 324 coletados em 2026-11-13; os números "35 testes"/"16 testes" de docs 14 e experimentos/milp mudaram com parametrização.

## 4. Ideias pesquisadas e não testadas
- **EnbPI** (conformal para séries sem divisão de dados; Xu e Xie, ICML 2021): não testado (`docs/16` B).
- **SAVI/MSAVI** em vegetação esparsa (ver M6); **GLDAS/ERA5-Land** (BL3/M3); **uso do solo MapBiomas** (D2); **SMAP defasado** com mais anos (M4).
- **MILP multiobjetivo/estocástico** (CVaR com APSIM, planejamento robusto; `docs/16` F): só a versão CVaR simples foi implementada; não achei MILP específico para pequenos agricultores do semiárido.
- **Rotações com leguminosas retêm mais água do solo** (campo na Etiópia; `docs/16` F): não usado como critério.
- **Preço/mercado** (CONAB, CEPEA) para a prioridade renda (C6).
- **Pluviômetros FUNCEME** (BL4) e INMET (D2).
- **Teste de previsão sazonal da quadra**: índices de out–jan não anteciparam fev–mai (skill -0,05, só 2 janelas testadas, sem varredura); modelos dinâmicos são da FUNCEME.
- **Ensembles**: sem ganho sobre o XGBoost (`experimentos/ensemble/RESULTADO.md`); não repetir.
- **Mais variáveis de pesquisas** (`docs/07`, `docs/08`, `docs/09`): balanço hídrico, SMAA-O com faixas, modelos de fundação (proibidos no escopo do módulo de modelos).

## 5. Riscos e limites conhecidos
- **Resolução**: NDVI 250 m, clima ~50 km (59 células para 195 pontos), SMAP ~9 km, solo ~2 km; o talhão pode diferir do pixel. Pontos da mesma célula têm o mesmo clima.
- **NDVI não é produtividade**: R² 0,03–0,10 contra rendimento do IBGE; a chuva da quadra explica mais (milho 0,31). Rendimento do PAM é estimado, não medido; no máximo 9 anos por município.
- **O ganho do modelo é persistência**: o clima sozinho não supera a climatologia (confirmação −0,044); cenários de clima reagem pouco no preditivo (por isso o app usa o motor de ciclo).
- **Conformal**: cobertura média 80,9% / 90,6%, mas por ano varia (2022: 71,7%); a garantia é de longo prazo.
- **Confirmação com 3 anos** (2022–2024) e IC sobre anos: pouco poder; o Bonferroni é conservador.
- **Suposições do motor** (ciclo, `risco_max`, pesos, ordem das prioridades, regra de leguminosas, mesmo ano de clima nas 3 safras) não validadas com técnico.
- **Empate técnico** em todos os locais testados: nenhuma alternativa tem "percentual de acerto".
- **Valores de palha/N** vêm de poucos estudos fora do semiárido (comparação indicativa); notas por min-max entre as candidatas que têm dado.
- **ZARC**: mede risco climático por município; janela aproximada para culturas sem ZARC é suposição; só Ceará.
- **Solo**: estimativa de mapa global; o aviso de risco de solo não altera nota.
- **MILP**: ótimo para pesos fixos; esconde o empate se mostrado sozinho (por isso roda com sorteios e é rotulado proposta).
- **LLM**: nunca testado com API real; o verificador não garante fidelidade semântica; nome do município iria à API externa.
- **Máquina limitada**: 7 GB de RAM na máquina anterior; não rodar mais de 2 processos pesados (walk-forward, reranker, preditivo) ao mesmo tempo.

## 6. Concluído (com data)

| Data | O que | Onde |
|---|---|---|
| 2026-11-09 | Esqueleto, `config.yaml`, validador de entrada, gerador sintético, diagnóstico, features, preditivo, conformal split, decisão XGBoost x Ridge, `cenarios.py`, `relatorio.py` (passos 1–12) | `src/modelos/`, `docs/02`, `docs/03` |
| 2026-11-11 | Coleta POWER; MODIS via ORNL; walk-forward com placebo/Bonferroni/confirmação selada; persistência validada; Ceará completo (184 municípios) | `src/coleta/`, `docs/05` |
| 2026-11-11 | CHIRPS testado: sem ganho | `experimentos/expA_chirps/RESULTADO.md` |
| 2026-11-12 | NDVI e SMAP completos para 195 pontos; avaliação com 195 pontos; persistência integrada ao preditivo (D52) | `experimentos/avaliacao_195/RESULTADO.md`, `docs/03` D52 |
| 2026-11-12 | Motor de ciclo + Monte Carlo SMAA-2 (empate técnico, lacuna = incerteza, sem desempate alfabético) | `src/culturas/`, `docs/10` |
| 2026-11-12 | MVP Streamlit, API FastAPI (6 de 7 endpoints), RAG (31 PDFs), camada LLM com verificador (testada sem chave), códigos IBGE em `pontos.csv` | `src/app`, `src/api`, `src/rag`, `src/llm`, `src/coleta/ibge_codigos.py` |
| 2026-11-13 | Cobertura do conformal (antigo item 1): ACI por estação, gamma 0,05, integrado a `cenarios.py` e ao preditivo: 80,9% / 90,6% no holdout (antes 76,0% / 87,2%) | `src/modelos/conformal_aci.py`, `experimentos/conformal_A1/RESULTADO.md` |
| 2026-11-13 | Outros algoritmos e ensembles (12 candidatos): XGBoost já em produção, ensemble não acrescenta | `experimentos/ensemble/RESULTADO.md` |
| 2026-11-13 | Diagnóstico de overfitting/underfitting: sem evidência de nenhum | `experimentos/overfit_underfit/RESULTADO.md` |
| 2026-11-13 | Terreno (SRTM) e índices Niño/Atlântico como features: não melhoram; NDVI x rendimento do IBGE (R² 0,03–0,10); índices não anteciparam a quadra | `experimentos/novas_fontes/RESULTADO.md` |
| 2026-11-13 | Rotação em 3 safras no app (seção 3b) | `src/culturas/rotacao.py`, `tests/test_rotacao.py` |
| 2026-11-13 | Indicador da chuva da quadra (seção 2b) | `src/app/quadra.py`, `tests/test_quadra.py` |
| 2026-11-13 | ZARC baixado (CE, 108.818 linhas), integrado ao motor; ZARC por solo e janela aproximada para culturas sem ZARC (corrige o viés); **ligado por padrão no app** (decisão sua) | `src/coleta/zarc.py`, `src/culturas/zarc.py`, `experimentos/zarc/RESULTADO.md` |
| 2026-11-13 | PAM/IBGE coletado (inclui valor da produção, variável 215) e SRTM coletado | `src/coleta/sidra.py`, `src/coleta/srtm.py` |
| 2026-11-13 | Solo (SoilGrids) coletado por `rasterio` (`rasterio==1.5.2` em `requirements.txt`; o bloqueio de instalação foi resolvido) e usado no app como solo estimado (textura, avisos de risco, solo do ZARC) | `src/coleta/solo.py`, `src/app/mvp.py: solo_estimado` |
| 2026-11-13 | MILP (`rotacao_milp.py`): modelo de fluxo, regras duras, CVaR, MILP com incerteza e plano de várias safras no app | `experimentos/milp/RESULTADO.md`, `tests/test_rotacao_milp.py` |
| 2026-11-13 | Pitch e avaliação honesta; alinhamento ao desafio | `docs/17_PITCH.md`, `docs/19_ALINHAMENTO_AO_DESAFIO.md` |
| 2026-11-13 | Documentação técnica completa e retomada | `docs/18_ARQUITETURA_TECNICA.md`, `docs/04_RETOMADA.md` |

## 7. Mapa dos itens antigos (versão de 2026-11-12) para os novos IDs

| Antigo | Novo | Antigo | Novo |
|---|---|---|---|
| A1 | Concluído (ACI) | E19 | BL1 / DU9 |
| A2 | M1 | E20 | DU10 |
| A3 | M3 / BL3 | E21 | L2, L3, L4 |
| A4 | M2 | F22 | R1, R2 |
| A5 | M4 | F23 | R3 |
| A5b, 5c, 5d, 5e, 5f | Concluído | G24 | AP1, AP2 |
| A5g (SoilGrids) | Concluído (rasterio autorizado e solo coletado) | G25 | C1 |
| A6 | M5 | H26 | D2, D3, M6, BL4 |
| B7 | DU1 | H27 | M5 |
| B8 | DU2, DU3, DU4, DU5 | I28 | BL2 / I1 |
| B9 | DU6 | I29 | I2, R5 |
| B10 | C2 | D16 | P1 |
| B11 | C3 | D17 | P2, P3 |
| B12 | C4 | D18 | D4 |
| B13 | C5 | C14 | Concluído + DU7 |
| C15 | DU8 | | |
