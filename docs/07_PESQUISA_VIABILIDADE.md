# 07. Pesquisa de viabilidade: como fazer o motor diferenciar os municípios

Data da pesquisa: 2026-11-12. Pesquisa somente de leitura: nenhum arquivo de `src/`, `data/` ou `.env` foi alterado.
Regra usada: só afirmo como **FATO** o que li na URL citada. O que é minha leitura vai marcado como **OPINIÃO**.
O que não consegui ler ou confirmar está na seção "O que NÃO consegui confirmar".

## 1. O problema, com o que vi no código e na tabela do projeto (FATO, arquivos locais)
- `src/culturas/motor.py`: o filtro de viabilidade usa a faixa **absoluta** do EcoCrop (`temp_min_abs`...`temp_max_abs`, `chuva_min_abs`...`chuva_max_abs`). O perfil traz `temp_media_c` e `chuva_ciclo_mm`.
- `data/culturas/tabela_culturas.csv` (16 culturas): as faixas absolutas são muito largas. Exemplos lidos: chuva máxima absoluta de mandioca 5000 mm, feijão-caupi 4100 mm, amendoim 4000 mm; chuva mínima de feijão-caupi 300 mm, milho 400 mm. Qualquer município do Ceará cai dentro desses limites, por isso quase tudo passa no filtro.
- A mesma tabela tem `ciclo_min_dias` / `ciclo_max_dias` para as 16 culturas, mas o intervalo é enorme (milho 65 a 365 dias, feijão-caupi 30 a 240, sorgo 90 a 300). Um "ciclo" único não sai desses números.
- `demanda_hidrica_mm_ciclo` só existe para 7 das 16 culturas (milho 500, feijão comum 300, sorgo 450, milheto 450, algodão 700, amendoim 500, girassol 600).
- Clima diário do projeto (`data/processed/clima_diario.parquet`, 1.709.370 linhas, 195 pontos): colunas `chuva_mm`, `tmax_c`, `tmin_c`, `radiacao`, `data`, `ponto_id`, `celula_power`. **Não há** umidade relativa nem vento (necessários para Penman-Monteith).
- `data/processed/pontos.csv`: colunas `ponto_id,lat,lon,celula_power`. **Não há código IBGE** do município (necessário para casar com o ZARC).

## 2. O que o ZARC é e como entra (item a)

### Fatos lidos
- **Portaria SPA/MAPA nº 121, de 20/05/2026** (feijão-caupi, Ceará, safra 2026/2027): https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/portarias/safra-vigente/ceara/PORTN121FEIJOCAUPICE.pdf
  - Identifica municípios aptos e períodos de semeadura em **3 níveis de risco: 20%, 30%, 40%**.
  - Usa **balanço hídrico da cultura**: exigência de água e temperatura, duração do ciclo, fases da cultura, reserva de água do solo, chuva e evapotranspiração de referência de séries de **no mínimo 15 anos de dados diários** em 3.750 estações pluviométricas.
  - Critérios: temperatura mínima média do decêndio acima de 18 °C em todo o ciclo; ciclo em 4 fases; **ISNA >= 0,6 na fase I (germinação) e >= 0,5 na fase III (floração/enchimento)**.
  - Solos: tipo 1 arenoso (31,5 mm de água disponível), tipo 2 médio (49,5 mm), tipo 3 argiloso (67,5 mm), raiz efetiva de 45 cm.
  - Grupos de cultivar pelo número de dias da emergência à maturação: Grupo I até 75 dias; II de 76 a 85; III acima de 85. No Ceará, todas as cultivares indicadas ficaram no Grupo I.
  - Mínimo de 300 mm de chuva no ciclo, mas o texto diz que a limitação é mais pela **distribuição** da chuva do que pelo total.
  - Município é "apto" se pelo menos 20% da área atende aos critérios.
  - Janela dada em **36 decêndios** (períodos de 10 dias, de 1 a 36).
  - O modelo supõe que não há limite de fertilidade nem dano de pragas.
  - Acesso: SISZARC, Painel de Indicação de Riscos e aplicativo Plantio Certo (o documento cita os três).
- **Nota Técnica 14/2026** (caupi e mamona 2026/2027, inclui Ceará): https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/notas-tecnicas-air/notas-tecnicas-2024/NotaTcnica14FeijoCaupieMamona.pdf
  - O ZARC é publicado por portarias da SPA/MAPA; indica a melhor época de plantio por município, ciclo da cultivar e tipo de solo, com séries de no mínimo 15 anos.
  - O ZARC é **obrigatório** para o enquadramento no Proagro (cita o Manual de Crédito Rural cap. 12, seção 2) e vincula a subvenção do seguro rural (PSR).
  - A atualização anual de caupi e mamona consiste na mudança do banco de cultivares.
- **Dados abertos "Tábua de Risco"** (CKAN do MAPA): https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f
  - Licença **CC BY**; 13 arquivos CSV, um por safra (2016/2017 até 2026/2027) mais um "Perene, Olerícola e Sem Safra"; a página diz atualização semanal (o dicionário diz diária); portal em CKAN. A página não lista endpoint de API específico do conjunto.
  - Um CSV por safra, com URL no padrão `.../resource/<id>/download/dados-abertos-tabua-de-risco-safra-2025-2026.csv` (ids de cada safra estão na página).
- **Dicionário de dados 2026** (lido em PDF): https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f/resource/bebb0ebb-bc75-460c-b900-a7a1ebd87bee/download/dicionario-de-dados-tabua-de-risco-2026.pdf
  - Colunas: `Nome_cultura`, `SafraIni`, `SafraFin`, `Cod_Cultura`, `Cod_Ciclo` (13 Perene, 19 Semiperene, 20 a 26 Grupos I a VI), `Cod_Solo` (1 Arenoso, 2 Textura Média, 3 Argiloso, 11 a 16 = AD1 a AD6), `geocodigo` (IBGE do município), `UF`, `municipio`, `Cod_Outros_Manejos` (1 Sequeiro, 2 Irrigado, 3 Irrigado com controle de geada), `Nome_Outros_Manejos`, `Cod_Clima` (inclui **4 = Semiárido**), `Nome_Clima`, `Cod_NM` (NM1 a NM4), `Produtividade`, `Cod_Munic` (SICOR), `Cod_Meso`, `Cod_Micro`, `Portaria`, `dec1` a `dec36`.
  - Os campos `dec1`..`dec36` guardam o risco por decêndio. O manual do painel diz que o risco é mostrado em 20% (verde), 30% (amarelo) e 40% (vermelho). Não vi o conteúdo exato das células (ex.: se vazio = não indicado) porque não consegui abrir um CSV; ver seção 7.
- **Manual do Painel ZARC**: https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/documentos/ManualdeInstruesdonovoPaineldoZarc.pdf
  - Filtros obrigatórios: Safra, Cultura, Grupo, Solo e UF; a aba "Dados" permite exportar tabela.
  - O mapa mostra o **menor risco por município entre os 36 decêndios**; o risco por decêndio só aparece na "Tábua de Risco".
  - Há "Zarc para validação" com a nova classificação de solo em 6 classes de água disponível (AD), iniciada com a soja 2023/2024.
- **Estudo Embrapa sobre o ZARCPro** (soja, Sul): https://apct.sede.embrapa.br/agrometeoros/article/download/26573/14591/127070
  - Confirma as classes de risco até 20%, 21 a 30%, 31 a 40% e acima de 40%, usadas pelo Proagro e pelo PSR; o risco é a probabilidade de a produtividade ficar abaixo de um nível esperado, medida por ISNA em série de 30 anos. É soja no Sul, não semiárido.
- Os nomes de arquivo das portarias do Ceará que apareceram na busca incluem caupi, girassol, mamona, sorgo granífero e sorgo forrageiro (por exemplo `.../portarias/safra-vigente/ceara/PORTN97GIRASSOLCE.pdf`). **Só abri a de caupi.** Não confirmei se milho, algodão, amendoim, gergelim, mandioca, feijão comum ou palma têm ZARC no Ceará.
- Nenhuma portaria que encontrei trata de crotalária, mucuna, feijão-de-porco ou guandu. **Não achei** ZARC para adubos verdes (ausência de resultado, não prova de que não existe).

### Como entraria no SULCO
1. Baixar os CSV da Tábua de Risco da safra vigente (e do arquivo "perene"), filtrar `UF == CE`, manejo = sequeiro (1), e guardar em `data/` (fora do repositório de código, com a licença CC BY citada).
2. Casar município com o ponto do SULCO. Falta o código IBGE em `pontos.csv`; seria preciso juntar por nome (risco de acento e grafia) ou adicionar o geocódigo de uma tabela do IBGE.
3. Usos possíveis, do mais simples ao mais forte:
   - **Filtro categórico**: a cultura só é candidata se o município tem alguma janela com risco <= 30% (ou o nível que o usuário escolher). Isto já diferencia municípios sem nenhum cálculo novo.
   - **Janela de plantio como entrada**: pegar os decêndios indicados e calcular chuva e temperatura do ciclo (início do decêndio + duração do ciclo) com o clima diário POWER já coletado. Resolve a "data de plantio desconhecida".
   - Mostrar na tela "janela ZARC: decêndios X a Y, risco Z%".
- **Custo**: baixo a médio (baixar, normalizar, juntar por município; ~1 a 3 dias de trabalho, **OPINIÃO**).
- **Riscos**: (i) cobertura por cultura no CE não confirmada; (ii) adubos verdes provavelmente sem ZARC; (iii) o ZARC é política de crédito/seguro (Proagro/PSR), mede risco de **perda de produtividade**, não "melhor cultura para rotação"; (iv) 3 tipos de solo (precisa de suposição ou dado de solo); (v) as portarias são anuais e mudam o banco de cultivares; (vi) a janela do ZARC é para cultivares específicas (caupi no CE: ciclo até 75 dias).

## 3. Balanço hídrico, ISNA, Kc, ETo (item b)

### Fatos lidos
- FAO-56, cap. 6 (tabelas 11 e 12), https://www.fao.org/4/x0490e/x0490e0b.htm (lido por extração automática; os valores de Kc ini das culturas estavam em imagem e **não vieram**): comprimentos de fase e Kc mid/end, por exemplo "Green gram, cowpeas" Kc mid 1,05, Kc end 0,60–0,35; maize grain Kc mid 1,20; sorghum grain Kc mid 1,00–1,10, Kc end 0,55; sunflower Kc mid 1,0–1,15; cotton Kc mid 1,15–1,20; groundnut Kc mid 1,15, Kc end 0,60; castorbean Kc mid 1,15, Kc end 0,55; cassava ano 1 Kc ini 0,3, mid 0,80, end 0,30. Comprimentos de fase (dias, Init/Dev/Mid/Late/Total) existem, por exemplo "Green gram, cowpeas (March; Mediterranean)" 20/30/30/20 = 110; "Sorghum (Mar/April; Arid Region)" 20/35/45/30 = 140. São de regiões fora do Nordeste; **não há Kc do FAO-56 para crotalária, mucuna, feijão-de-porco, guandu, gergelim, milheto ou palma** nesta página.
- FAO-56, cap. 4, https://www.fao.org/4/x0490e/x0490e07.htm: a equação de Penman-Monteith (Eq. 6) precisa de Tmax, Tmin, pressão de vapor (umidade), radiação líquida e vento a 2 m. Para quando só há temperatura, o texto dá Hargreaves (Eq. 52): `ETo = 0,0023 (Tmean + 17,8) (Tmax - Tmin)^0,5 Ra`, com Ra em mm/dia. O texto diz que esse uso "é menos recomendado", deve ser checado contra Penman-Monteith em cada região, pode ser calibrado por regressão, tende a **subestimar com vento alto (u2 > 3 m/s)** e **superestimar com umidade alta**.
- NASA POWER oferece RH2M (umidade relativa a 2 m) e WS2M (vento a 2 m), diários, na comunidade AG: https://power.larc.nasa.gov/api/system/manager/parameters/RH2M?community=ag&temporal=daily e https://power.larc.nasa.gov/api/system/manager/parameters/WS2M?community=ag&temporal=daily. O parâmetro EVPTRNS (https://power.larc.nasa.gov/api/system/manager/parameters/EVPTRNS?community=ag&temporal=daily) é "Evapotranspiration Energy Flux" (fluxo de energia da superfície), **não** é ETo de referência; não o recomendo como ETo (**OPINIÃO**).
- Biblioteca `pyet` (https://github.com/pyet-org/pyet): existe, licença MIT, Python, última atividade 2026-05-26 (via API do GitHub). A descrição diz que estima evaporação de referência e potencial. **Não li a lista de métodos**; não afirmo que traga Hargreaves.
- Biblioteca `pyfao56` (https://github.com/kthorp/pyfao56): existe, Python, 101 estrelas, última atividade 2026-10-21; a licença aparece como "other/NOASSERTION" na API e não consegui ler o arquivo de licença no caminho `LICENSE`. Descrição: implementação Python da abordagem de coeficiente de cultura dual do FAO-56 para uso de água. **Não li a documentação de entradas.** Pelo nome do que implementa (FAO-56 dual Kc), esperaria dados de umidade e vento (**OPINIÃO**, não confirmada).
- ISNA no ZARC: limiares ISNA >= 0,6 (fase I) e >= 0,5 (fase III) para o caupi, na portaria acima. **Não li a definição formal do ISNA** em nenhuma fonte desta pesquisa; a definição usual (água realmente usada / água demandada pela cultura) é da minha memória e precisa ser conferida antes de implementar.

### Como entraria no SULCO
- Para cada ponto, cada decêndio de plantio e cada cultura, rodar um balanço hídrico diário simples: `ETc = Kc x ETo`; balde de solo com reserva (usar 31,5 / 49,5 / 67,5 mm do ZARC como CAD de partida); déficit = ETc - consumo real; ISNA por fase. Dar nota por fase crítica. Isso é a versão "mini-ZARC" própria, calculada para qualquer cultura que tenha Kc e fases.
- ETo: Hargreaves com Tmax/Tmin que o projeto já tem, **sem coletar nada novo**; o valor de Ra vem de cálculo por latitude e dia do ano (a equação do Ra não foi lida nesta pesquisa). Ou coletar RH2M e WS2M no POWER para Penman-Monteith (mexe em `data/`, ver decisões).
- **Custo**: médio (3 a 7 dias, **OPINIÃO**), maior parte em reunir Kc e duração de fase por cultura com fonte.
- **Riscos**: Kc/fases sem fonte para ~9 das 16 culturas; Hargreaves tende a errar no litoral úmido e com vento forte; resolução da célula POWER (km); parâmetros viram "números inventados" se não tiverem fonte, o que viola o princípio do projeto (docs/01 seção 3).

## 4. Modelos simples de adequação (item c)

### Fatos lidos (repositórios abertos, via API do GitHub e leitura do README)
| Repositório | Existe | Licença | Última atividade | Linguagem | Roda em Python? |
|---|---|---|---|---|---|
| https://github.com/OpenCLIM/ecocrop | sim | **sem licença declarada** (campo vazio na API) | 2026-01-30 | Python (descrito como Scheme na busca; scripts `.py` no repo) | sim, mas pensado para grade/netCDF e HPC |
| https://github.com/cropmodels/Recocrop | sim | GPL-3.0 | 2026-08-01 | R (C++ no núcleo) | não (R) |
| https://github.com/flozabel/CropSuite | sim | CC-BY-4.0 | 2025-10-28 | Python | sim, mas por raster e GUI |
| https://github.com/aquacropos/aquacrop (AquaCrop-OSPy) | sim | Apache-2.0 | 2026-09-23; release v3.1.0 de 2026-06-22 | Python (`pip install aquacrop`) | sim |
| https://github.com/ajwdewit/pcse | sim | arquivo LICENSE cita EUPL 1.1 ("NOASSERTION" na API) | 2026-11-12 (tag mais recente listada 6.0.13) | Python | sim |

- **OpenCLIM EcoCrop** (lido o README): usa o banco FAO EcoCrop e calcula nota 0 a 100 de temperatura e de chuva **por dia**, olhando para a frente em janelas de duração `GTIME` entre `GMIN` e `GMAX` (passo de 10 dias). Para culturas anuais: soma dias com temperatura adequada; se atinge `GMIN` dentro de `GTIME`, nota = `100 x [1 - (GTIME - GMIN)/(GMAX - GMIN)]`; zera se a mínima ficar abaixo da temperatura letal `KTMP`; desconta dias acima de `TMAX`. A nota combinada é o **mínimo** entre temperatura e chuva (ideia de fator limitante). Insumos: temperatura média/mínima/máxima diária e chuva diária; no repositório vem `EcoCrop_DB.csv`. Conclusão do que li: **este modelo já resolve "data de plantio desconhecida" avaliando todas as datas de início e duração possíveis**. O README (que o `motor.py` já cita) não deixa claro o tratamento exato da chuva; não li o código `ecocrop_utils.py`.
  - Entraria no SULCO reimplementando a lógica (em pandas/numpy, para 195 pontos × ~36 inícios × 16 culturas) lendo o README, **sem copiar código**, por causa da ausência de licença. Custo médio (3 a 5 dias, **OPINIÃO**). Risco: ainda usa as faixas largas do EcoCrop; a nota "mínimo de temperatura e chuva" sem ISNA pouco diferencia chuva boa de chuva ruim no tempo; `GMIN/GMAX` do projeto são largos.
- **Recocrop (R)**: https://github.com/cropmodels/Recocrop, README mínimo ("implements the ecocrop algorithm", instalação via r-universe). Não roda em Python. Útil só como referência de comparação de resultados. Custo: baixo para comparar, mas exige R e GPL-3.0.
- **CropSuite**: https://github.com/flozabel/CropSuite. README cita o artigo "CropSuite v1.0 – a comprehensive open-source crop suitability model considering climate variability" (Zabel, Knüttel, Poschlod; DOI 10.5194/gmd-18-1067-2025). O repositório tem `CropSuite.py`, `CropSuite_GUI.py`, `plant_params/`, `data/`, manual em PDF. **Não li o artigo nem o manual**; a pasta `plant_params` contém `available` e `~template.txt` (não abri). Parece desenhado para mapas globais/regionais em raster. Custo alto para 195 pontos (montar rasters e parâmetros por cultura); só valeria como referência de método.
- **AquaCrop-OSPy** (README lido): `pip install aquacrop`; exemplo mostra `AquaCropModel(...weather_df, soil=Soil(soil_type='SandyLoam'), crop=Crop('Wheat', planting_date='10/01'), ...)`. O README diz que **não é a implementação oficial** da FAO e espelha a maioria das funções da versão 7.1 do AquaCrop (exceto parte da salinidade; texto cortado, não li o resto). No arquivo `crop_params.py` aparecem como culturas pré-definidas Maize, Sorghum, Sunflower, Cotton, Cassava, DryBean, Soybean, Wheat, Barley, Potato, Quinoa, Tomato, SugarBeet, SugarCane, PaddyRice (nomes lidos no código). **Não aparece feijão-caupi, amendoim, gergelim, mamona, mandioca-do-Nordeste calibrada nem adubos verdes**: seria preciso criar parâmetros próprios (modo "custom"), que precisam de fonte. Entra como modelo de produtividade por água (dá rendimento relativo, não só adequação). Custo alto (1 a 3 semanas, **OPINIÃO**); risco de parâmetros inventados e de falsa precisão.
- **PCSE**: https://github.com/ajwdewit/pcse. Estrutura Wageningen (WOFOST etc.), exige arquivos de parâmetros de cultura, solo e manejo; README lido descreve o framework. **Não vi lista de culturas suportadas.** Custo alto, mesma limitação de parâmetros. Não recomendo para esta fase (**OPINIÃO**).
- Lógica fuzzy / Liebig: o próprio EcoCrop do OpenCLIM usa o **mínimo** entre notas. O documento FAO 1976 "A framework for land evaluation" (https://www.fao.org/4/x5310e/x5310e00.htm) foi aberto, mas a página só trouxe o sumário (classes de adequação no capítulo 3, seção 3.2 "Structure of the suitability classification"); **não li o texto** que confirma a regra do fator mais limitante. Qualquer afirmação além disso seria de memória.
- Banco EcoCrop da FAO (https://gaez.fao.org/pages/ecocrop): a página abriu sem conteúdo; **não confirmei** o texto de licença nem o número de espécies.

## 5. Dados abertos úteis (item d)
- **SoilGrids (ISRIC)**: https://docs.isric.org/globaldata/soilgrids/index.html. Resolução de 250 m, propriedades pH, carbono orgânico, densidade, fragmentos grossos, areia, silte, argila, CTC, nitrogênio total, estoque de carbono; 6 profundidades; licença CC-BY 4.0. A **API REST está pausada** ("não podemos estimar prazo") e a página diz que é beta, sem garantia de funcionamento. Acesso por WCS e WebDAV (VRT) segue anunciado. Entraria como textura (areia/silte/argila) para escolher solo tipo 1/2/3 do ZARC por ponto. Custo médio; risco: estimativa global de 250 m, pouco dado de campo no semiárido (**OPINIÃO**).
- **MapBiomas**: uso e cobertura em GeoTIFF por ano (site oficial e Coleção 10 1985-2024 citados em resultados de busca; apêndice ATBD da Caatinga existe). A licença CC-BY-4.0 vista foi da página do Earth Engine para a versão V1.0 e **não confirmei para a coleção atual**. Serviria para mascarar pixel agrícola/caatinga em torno do ponto. Ganho baixo para a rotação, custo médio.
- **FUNCEME**: não achei documentação oficial de API ou dados abertos. Achei só o uso por um pacote R de terceiros (código lido em https://rdrr.io/github/jmigueldelgado/valbuhayra/src/R/getAPIdata.r) que consulta `http://api.funceme.br/rest/pluvio/pluviometria-funceme-normalizada` e `rest/pluvio/posto` (campos `codigo`, `nome`, `latit`, `longit`, `municipio`). **Não testei os endpoints** e o repositório de origem não foi encontrado pela API do GitHub, então não o cito como repositório confirmado. Série de postos serviria para checar a chuva do POWER (que é grade). Risco: acesso não oficial, sem termos de uso confirmados.
- **INMET**: a página do catálogo de estações automáticas (https://portal.inmet.gov.br/paginas/catalogoaut) abriu sem lista de estações e com botão "Download CSV" sem destino visível; menciona BDMEP. **Não confirmei** API nem termos.
- **Embrapa / solos do Brasil**: não pesquisei uma fonte específica nesta rodada. Sem fato lido, não recomendo nenhuma.

## 6. Tabela de opções (ordenada de maior ganho por custo para menor)
Custo e ganho abaixo são **OPINIÃO** minha, a partir dos fatos acima. "Muda o resultado entre municípios?" é a pergunta central do problema.

| # | Opção | Custo | Ganho | Muda por município? | Principal risco |
|---|---|---|---|---|---|
| 1 | **Chuva e temperatura dentro de janela de ciclo** calculadas do POWER, com todos os inícios de plantio e ciclo da cultura (lógica estilo OpenCLIM, reimplementada) em vez da chuva anual | Baixo | Alto | Sim (a chuva da estação varia muito) | Ciclos do EcoCrop são largos; precisa definir ciclo por cultura com fonte |
| 2 | **Filtro por ZARC** (município tem janela com risco <= 30%) usando a Tábua de Risco | Baixo a médio | Alto para as culturas zoneadas | Sim, direto (lista de municípios aptos por cultura) | Cobertura por cultura no CE não confirmada; sem ZARC para adubos verdes; falta código IBGE em `pontos.csv` |
| 3 | **Janela do ZARC como entrada** da opção 1 (início = decêndios indicados; fim = início + ciclo) | Médio | Alto | Sim | Soma os riscos das opções 1 e 2 |
| 4 | **Faixas estreitas**: trocar a faixa absoluta pela ótima como filtro "forte" e por uma nota que penaliza, e marcar "indeterminado" quando falta ciclo | Baixo | Médio | Pouco sozinho | A faixa ótima também é genérica por espécie |
| 5 | **Balanço hídrico simples (ISNA próprio)** com Kc e ETo Hargreaves | Médio a alto | Alto | Sim (déficit e distribuição da chuva) | Kc/fases sem fonte para parte das culturas; Hargreaves tem viés |
| 6 | **Solo por ponto** (SoilGrids textura -> solo tipo 1/2/3 do ZARC) para a reserva de água | Médio | Médio | Sim, mas pouco no semiárido | API pausada; estimativa de 250 m |
| 7 | AquaCrop-OSPy | Alto | Médio (produtividade, não rotação) | Sim | Sem parâmetros para caupi/adubos verdes; falsa precisão |
| 8 | CropSuite / PCSE | Muito alto | Baixo para o escopo atual | Sim | Raster e parâmetros; fora do porte do projeto |

Observação separada (do `docs/06`): as **lacunas** (culturas com 3 critérios ganham nota maior que as com 5) são um problema de método do score, não de clima. Nenhuma das opções acima corrige isso; a proposta de ranquear só pelos critérios comuns e mostrar N/palha ao lado continua valendo.

## 7. O que NÃO consegui confirmar (importante)
- **Conteúdo real do CSV da Tábua de Risco.** O arquivo da safra 2025/2026 passa de 10 MB (a ferramenta de leitura recusou) e o download direto por `curl` falhou neste ambiente. Portanto não vi nenhuma linha de Ceará, não sei se há linhas para cada uma das 16 culturas, nem como as colunas `dec1`..`dec36` representam "sem indicação". Primeiro passo na implementação: baixar o CSV fora deste ambiente e inspecionar.
- Que a API do CKAN do MAPA responde: a chamada `datastore_search` da safra 2025/2026 retornou erro HTTP 400. O conjunto parece ser só de arquivos para baixar, não de consulta por API.
- Definição formal do ISNA e do Kc por fase para cada cultura do projeto (só li os limiares do caupi e as Kc mid/end da tabela do FAO-56 para algumas).
- Licença do `pyfao56` e do `pcse` com precisão (a API do GitHub devolve "outra/NOASSERTION"; li só o cabeçalho "EUPL" do LICENSE do PCSE).
- Se a FUNCEME e o INMET oferecem acesso aberto e estável (não achei documentação oficial).
- Dados do Embrapa sobre solos: não pesquisei fonte específica.
- Artigos do CropSuite e do OpenCLIM (só li os README).

## 8. Recomendação (OPINIÃO justificada)
Fazer em duas etapas, nessa ordem, sem usar modelo de cultura pesado:

**Etapa A (baixo custo, resolve a causa raiz):** opções 1 e 4.
Motivo: o problema descrito (mesmo score em todo o Ceará) vem de três coisas que li no código e na tabela: faixa absoluta larga, chuva anual no lugar de chuva do ciclo e ciclo desconhecido. A opção 1 troca a chuva anual por chuva do ciclo para todos os inícios possíveis e usa o **melhor início viável** (ou a mediana entre os inícios viáveis), e o EcoCrop já foi pensado assim (README do OpenCLIM). Usa só dados que o projeto já tem (`chuva_mm`, `tmax_c`, `tmin_c`).

**Etapa B (médio custo, dá credibilidade):** opção 2 (ZARC) como filtro e como janela.
Motivo: é uma fonte oficial, aberta (CC BY), já diferencia municípios e é a referência que o Proagro/seguro exige, o que ajuda na defesa do resultado. Só vale depois de baixar e inspecionar o CSV (item 7). Para culturas sem ZARC (adubos verdes, palma etc.), o motor deve mostrar "sem ZARC" em vez de tratar como inapto ou apto.

**Etapa C (só se A+B não separarem bem):** opção 5 (ISNA próprio com Hargreaves), com Kc só para as culturas que têm fonte. Opções 7 e 8 não recomendadas agora.

## 9. O que depende de decisão do usuário
1. **Nível de risco do ZARC** a aceitar como "viável": 20% (conservador), 30% ou 40%?
2. **Culturas sem ZARC no CE** (provável para adubos verdes): ficam no ranking com aviso "sem ZARC", ficam fora, ou entram num ranking separado?
3. **Duração do ciclo** por cultura: usar o grupo do ZARC (ex.: caupi no CE, até 75 dias) quando houver, e o que fazer quando não houver (o intervalo EcoCrop é muito largo)?
4. **Regra para o início do plantio** sem ZARC: melhor início do ano, mediana dos inícios viáveis, ou início da estação chuvosa que você defina?
5. **Tipo de solo** padrão (1 arenoso, 2 médio ou 3 argiloso) enquanto não há dado de solo por ponto; aceita usar SoilGrids depois?
6. **Coletar mais variáveis do POWER** (umidade relativa e vento) para Penman-Monteith? Isso altera `data/` e exige nova coleta; ou aceita Hargreaves?
7. **Código IBGE nos pontos**: posso adicionar o geocódigo a partir de uma tabela do IBGE (a fonte ainda precisa ser escolhida e lida)?
8. **Reimplementar a lógica do EcoCrop** do OpenCLIM (o repositório não declara licença; só a ideia descrita no README seria usada, sem copiar código) — aceitável?
9. Aceitar o uso do ZARC como evidência no `trechos`/contrato JSON (cada nota precisa de fonte+URL+página, conforme `validar_cenario`).

## 10. Fontes abertas e lidas (resumo de URLs)
- ZARC: Portaria 121/2026 (caupi CE), Nota Técnica 14/2026, Manual do Painel, dataset "Tábua de Risco" e dicionário (URLs na seção 2).
- Estudo ZARCPro: https://apct.sede.embrapa.br/agrometeoros/article/download/26573/14591/127070
- FAO-56: https://www.fao.org/4/x0490e/x0490e0b.htm e https://www.fao.org/4/x0490e/x0490e07.htm
- NASA POWER parâmetros: URLs na seção 3.
- Repositórios (todos confirmados via API do GitHub): OpenCLIM/ecocrop, cropmodels/Recocrop, flozabel/CropSuite, aquacropos/aquacrop, ajwdewit/pcse, kthorp/pyfao56, pyet-org/pyet.
- SoilGrids: https://docs.isric.org/globaldata/soilgrids/index.html
- FAO 1976: https://www.fao.org/4/x5310e/x5310e00.htm (só sumário)
- FUNCEME (indireto): https://rdrr.io/github/jmigueldelgado/valbuhayra/src/R/getAPIdata.r
- INMET: https://portal.inmet.gov.br/paginas/catalogoaut
- MapBiomas (apenas resultados de busca, não abri): https://brasil.mapbiomas.org/en/colecoes-mapbiomas
