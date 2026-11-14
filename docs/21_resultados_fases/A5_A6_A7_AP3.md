# A5, A6, A7 e AP3: mapa com camadas, entradas do agricultor, glossário e página "Limites dos dados"

Data: 2026-11-13. Arquivos: `src/app/app.py`, `src/app/mvp.py`, `src/app/logica.py` (alterados); `src/app/camadas.py`, `src/app/filtros.py` (novos);
testes em `tests/test_app.py` e `tests/test_mvp.py`. Sem commit.

## AP3 / M12: página "Limites dos dados"
- `logica.caminho_relatorio()` agora aponta para `data/processed/modelos/relatorio_modelos.md` (era `relatorio_modelos.md` da raiz, de 13 pontos).
  A variável de ambiente `SULCO_RELATORIO` continua valendo (testes).
- O texto "Não há dado de ... solo ... nem zoneamento (ZARC)" foi trocado por frases que dizem o que entra: solo ESTIMADO (SoilGrids, 0 a 30 cm,
  não é análise), ZARC como filtro das datas de sequeiro (risco até 30%), ZARC irrigado só consultado nos filtros, equipamento e mercado sem dado.
- Com o relatório novo, o holdout 2022-2024 mostra ridge e xgboost com skill acima de zero (0,257 e 0,284 no arquivo de hoje), então a faixa
  vermelha "NÃO supera" só aparece se o arquivo disser isso. A tela avisa, lendo o arquivo, que o relatório usa a persistência (verdor da quinzena
  anterior) e que o ganho vem dela, não do clima sozinho. O teste `test_relatorio_real_do_projeto_e_o_de_data_processed_modelos` confere a
  coerência (modelo em `sem_ganho_no_holdout` se e só se skill <= 0), sem número fixo.
- Evapotranspiração/balanço hídrico: com a integração final (abaixo), `mvp.BALANCO_NA_TELA = True` e a página manda ver a seção própria, dizendo que só há ETo de referência e chuva menos ETo.

## A5: mapa com camadas e linha do tempo
Tela 1, acima do mapa: "Colorir os pontos por" e "Ano (linha do tempo)". Todas as camadas vêm de arquivo; ponto sem dado fica cinza (nunca valor inventado).

| Camada | Sem ano (todos os anos) | Com ano | Fonte |
|---|---|---|---|
| Solo nu | nº de quinzenas (de 24) com campo nu típico (NDVI < percentil 20 do próprio local em pelo menos metade dos anos) | % das quinzenas do ano com NDVI < percentil 20 do local (exige 12+ quinzenas com dado) | `data/processed/diagnostico/` (`diagnostico.json`, `anomalias.parquet`) |
| Declive | declive médio em 1 km (%) | não muda por ano (o controle avisa) | `data/processed/terreno.parquet` (SRTM) |
| Variabilidade da quadra | coeficiente de variação da chuva de fev-mai | chuva de fev-mai do ano em % da média do local | `clima_diario.parquet` via `src/app/quadra.py` |
| Risco de erosão | soma de 4 notas (0 a 8), de `src/culturas/risco_solo.py` | não muda por ano | módulo A1 (opcional: sem ele, "ainda sem dado" e pontos cinza) |

- Cor: rampa amarelo-claro a marrom, cortada nos percentis 5 e 95 (valor extremo não apaga o resto); legenda com mínimo, máximo e nº de pontos cinza.
- O ponto escolhido tem contorno vermelho; o clique continua escolhendo o local. O tooltip mostra nome e valor.
- Sem internet o mapa fica sem fundo (só os pontos); o aviso está sob o mapa. O resto do app não depende da internet.
- Limites: a chuva vem de 59 células de ~50 km (locais vizinhos repetem a cor); "solo nu" é relativo a cada local; o declive é indicador de terreno,
  não de erosão; o risco de erosão usa notas e cortes que o próprio módulo declara como suposição.

## A6: entradas do agricultor como filtros
Tela 1, expansor "Condições da sua área (opcional)". Chaves de sessão: `manejo`, `agua_irrig`, `equip`, `mercado`. Os filtros só MARCAM
("atende", "NÃO atende", LACUNA); não mudam pontuação, ranking nem empate técnico e não removem alternativas.
- Manejo: sequeiro consulta o ZARC sequeiro (como o motor). Irrigado consulta o ZARC irrigado (`Cod_Outros_Manejos` = 2). O código 3 não existe nos
  dados do Ceará (só 1 e 2). Das culturas da tabela, só `feijao_comum` ("Feijão") tem ZARC irrigado; as demais ficam em LACUNA, que não quer dizer
  "irrigar é proibido". `zarc.py` NÃO foi alterado: o motor continua com ZARC e chuva de sequeiro, e a tela avisa que o efeito da irrigação sobre a
  nota não é modelado (LACUNA).
- Água disponível (só irrigado): irrigação informada (mm por ciclo) + chuva média do ciclo (do motor) comparada com a demanda de água da tabela de
  culturas (limite inferior da faixa FAO, referência global). Sem demanda na tabela: LACUNA.
- Equipamento: a tabela de culturas não tem exigência de máquina ou mão de obra: sempre LACUNA; a resposta vai para a conversa com o técnico.
- Preferência de mercado: sem preço nem demanda. O único dado real é a área colhida da cultura no município (IBGE/PAM), usada como proxy de
  escoamento local e rotulada assim; cultura sem correspondência no PAM: LACUNA.
- Onde aparece: tabela "Seus filtros sobre os três caminhos" (tela 3) e uma linha por safra nas rotações de 3 safras (3b, sem o filtro de água).
- Limite: o filtro marca as alternativas que o motor já escolheu; não busca outras que passariam (isso exigiria mudar o motor).

## A7: glossário
Novos termos: fixadoras de nitrogênio, adubação verde, raízes profundas, balanço hídrico, risco de erosão (evapotranspiração já existia). Cada um tem
trecho do acervo em `mvp.TRECHOS_GLOSSARIO` (arquivo e página do PDF), lido com `pdftotext`:
- Fixadoras de N: `embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf`, p. 97.
- Adubação verde: `embrapa_semiarido_biomassa_leguminosas_milheto.pdf`, p. 1.
- Raízes profundas: `embrapa_debiasi_diversificacao_especies.pdf`, p. 9.
- Evapotranspiração: `embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf`, p. 27. Balanço hídrico: mesmo arquivo, p. 28.
- Risco de erosão: `embrapa_cap3_sistema_plantio_direto.pdf`, p. 2.
"Página" é a posição no arquivo PDF (a primeira página é 1), não o número impresso. O teste `test_glossario_novos_termos_e_trechos_verdadeiros_do_acervo`
confere cada trecho na página citada (se `pdftotext` existir) e que o glossário não diz que o app calcula ET enquanto `mvp.BALANCO_NA_TELA` for False.
Texto de ET e balanço: `mvp.glossario_atual()` usa a frase de "ainda não calcula" quando `BALANCO_NA_TELA` é False e, quando é True (hoje), diz que o app mostra só a ETo de REFERÊNCIA (Kc é lacuna) e `chuva menos ETo`, que não é o balanço do solo.

## Integração final (seções dos outros módulos), 2026-11-13
Desenhadas em "Meu local", depois do cenário (cada uma dentro de try: erro vira LACUNA, e módulo ausente faz a seção sumir):
- **5. Risco de erosão** (`secao_risco_solo`): classe e soma de notas, tabela com valor de entrada, classe, nota, corte e fonte de cada componente,
  fontes das faixas, lacunas e avisos. Aviso fixo: os cortes de carbono e de dias de chuva erosiva são RELATIVOS entre os 195 pontos (tercis), não risco absoluto.
- **5b. Calor e chuva extrema** (`secao_extremos`): barras por ano, definições com limiares e fonte (ETCCDI), tendências (Mann-Kendall) e avisos (células de ~50 km, série curta).
- **5c. Chuva menos ETo** (`secao_balanco_hidrico`): linha com faixa p10-p90 entre os anos, aviso de que ETo não é consumo da cultura, Kc e Penman-Monteith como lacuna.
  O clima é lido só do ponto (filtro no parquet) e passado à seção.
- **5d. Receita bruta por hectare** (`secao_renda`): tabela por cultura com anos usados e lacunas; NÃO é lucro, valores correntes, não é previsão.
- **Forragem** (`secao_forragem`): só um expansor com a lacuna declarada e os trechos lidos.
- **Prioridade 'renda'**: `mvp.calcular_rotacao` busca `secao_renda(...)['renda_por_cultura']` e passa a `gerar_rotacoes` (só na rotação 3b; sem o módulo, vira lacuna). Nos três caminhos (seção 3) 'renda' continua sem efeito
  (texto da prioridade ajustado). O teste antigo "renda não altera" foi trocado por: `usa_renda` só na prioridade renda.
- **Textura (item 4)**: mantive o rótulo do app (argila < 15%, 15 a 35%, > 35%, usado para escolher o solo do ZARC; a fonte desses cortes NÃO foi achada no acervo) e declarei a divergência na tela,
  mostrando também a classe do SiBCS de `risco_solo.classe_textura` para o mesmo ponto.
- `mvp.BALANCO_NA_TELA = True`; glossário e "Limites dos dados" ajustados. `app.secoes_opcionais` continua para futuras seções que desenhem com Streamlit (`desenha_streamlit = True`).

## Tempos medidos (AppTest, esta máquina, `-W error`, depois da integração)
Abertura do app: 12,7 s (primeira carga). Por seleção, depois de aberto: local 1,9 a 2,9 s; cultura 2,5 s; prioridade renda 2,2 s; prioridade solo 2,7 s;
camada do mapa 0,5 a 0,7 s; manejo irrigado 0,45 s. Todas < 5 s (testes `test_resposta_por_selecao_abaixo_de_5_segundos` e `test_mapa_troca_de_camada_e_ano_sem_excecao_e_rapido`).
Testes (`-W error`): `test_app`, `test_mvp`, `test_risco_solo`, `test_extremos`, `test_balanco_hidrico`, `test_renda`, `test_rotacao`: 80 passaram.
Também troquei `use_container_width` (descontinuado) por `width="stretch"` em `app.py`.

## Limites e pendências
- A seção de risco usa notas e cortes que o módulo declara como suposição; o balanço é só `chuva - ETo` (sem Kc).
- Filtros não trocam as alternativas; efeito da irrigação na nota continua LACUNA.
- Não rodei a suíte do RAG nem o precálculo de evidências (RAM).
