# Pesquisa: como melhorar a previsão da anomalia de NDVI (Caatinga e semiárido)

Data da pesquisa: 2026-11-12. Tarefa só de leitura: nenhum código, dado, `.env` ou commit foi tocado.

## 0. Como ler este documento

- **"Lido"** = abri a página ou o PDF e li o trecho citado. Só citei números do que li.
- **"Só resumo"** = li apenas o resumo (abstract) do artigo; não li métodos nem tabelas.
- **"Não conferi"** = não consegui abrir. Isso está listado na seção 8 e **não** entrou em nenhuma conclusão.
- Para repositórios, "última atividade" = campo `pushed_at` da API do GitHub, consultado em 2026-11-12.
- Frases marcadas **[inferência]** são raciocínio meu, não resultado de estudo.
- A rede da máquina bloqueou vários sites (FUNCEME por certificado, INMET, CDS, NOAA PSL/CPC, gloh2o). Não contornei o bloqueio de certificado.

## 1. O que a literatura lida diz (resumo em 8 pontos)

1. **A memória do próprio índice de vegetação é o que mais explica a previsão a curto prazo.** Em Gallear et al. (NHESS 2025), a nota de saúde da vegetação (VHI) do mês atual entra como atributo, e a versão preliminar (SSRN 5655758) diz que o VHI defasado "domina" a contribuição nos modelos de todos os biomas. Isso bate com o nosso resultado (persistência = +0,23 / +0,10). Nenhum dos dois compara com persistência pura, então não dá para saber quanto o clima soma por cima dela.
2. **O clima ajuda pouco quando já se usa o índice defasado.** Barrett et al. (Quênia, arXiv 1911.10339) escrevem que "observações atuais de precipitação e temperatura tiveram pouco impacto" e sugerem ENSO/TSM como próximo passo. É o mesmo padrão que vimos.
3. **A habilidade cai rápido com o horizonte.** Gallear 2025: R² mediano do melhor modelo 0,69 (1 mês), 0,35 (2 meses), 0,16 (3 meses). **[inferência]** Se o nosso alvo é o próximo composto de 16 dias, estamos no horizonte onde a persistência é quase imbatível; o clima tende a aparecer em horizontes de 1 a 3 meses.
4. **Defasagem chuva para NDVI na Caatinga: 2 meses (ciclo médio), 1 a 3 meses (revisão).** Barbosa et al. 2011 (lido): resposta defasada de **dois meses** nos quatro tipos de Caatinga, mas com séries mensais AVHRR de 1981-2001 e chuva climatológica de 1961-1990, ou seja, **ciclo sazonal médio, não anomalias**. A defasagem do ciclo médio não prova a mesma defasagem nas anomalias de ano a ano.
5. **Ordem de poder preditivo das variáveis hidrológicas:** a tese de Rebello (UFRJ 2019, resumo lido) diz que precipitação, umidade do solo e evapotranspiração, **nessa ordem**, têm capacidade preditiva sobre anomalias de vegetação, e que a Caatinga é o bioma mais suscetível e com maior potencial de predição. Só resumo.
6. **Umidade do solo de satélite ajuda onde a água limita.** Le et al. (GRL 2024): modelo com NDVI defasado + umidade da zona radicular do SMAP supera a previsão por climatologia, com maior ganho em regiões limitadas por água (resumo lido; suplemento lido: defasagens de até 3 passos de 16 dias, anomalias padronizadas por rank, regressão com 2 preditores, SMAP 2015-2021). Os números de ganho estão no texto principal, que não consegui abrir (403).
7. **Oceano e sazonalidade longa:** Hounsou-Gbo et al. (Atmosphere 2019, resumo lido): TSM do Atlântico Niño (3S-3N, 20W-0) no verão boreal anterior se relaciona com a chuva de fev-abr no norte do Nordeste, com cerca de **6 meses** de antecedência; o resumo não traz números de habilidade. Erasmi et al. (Remote Sensing 2014, resumo lido): eventos El Niño e NDVI anual reduzido com **defasagem de 12 meses**, e a Caatinga é mais sensível que os outros biomas; nem todo El Niño aparece como anomalia negativa. NDVI anual, não de 16 dias.
8. **Chuva de satélite:** no semiárido brasileiro, um estudo na Int. J. Climatology de 2020 (resumo lido; autores não conferidos) acharam o CHIRPS o melhor entre sete métodos em escala mensal, e o pior desempenho no leste do semiárido. **[inferência]** Como o CHIRPS não ajudou no nosso teste, o gargalo provavelmente não é a qualidade da chuva, e sim que a informação de chuva já está dentro da persistência do NDVI.

## 2. Lista ordenada por (chance de ganho x facilidade)

Chance e facilidade: A = alta, M = média, B = baixa. É minha avaliação, justificada em cada ficha.

| # | Ideia | Chance | Facilidade | Custo de dados |
|---|---|---|---|---|
| 1 | Anomalia de umidade do solo SMAP (já coletado) como atributo | M | A | zero (já coletado) |
| 2 | Medir a habilidade por horizonte (1 a 4 compostos) e por estação do ano | A (para achar onde olhar) | A | zero |
| 3 | ERA5-Land (0,1 grau): umidade do solo em 4 camadas, chuva, evaporação, de 2001 em diante | M | M | conta (GEE ou CDS) |
| 4 | MapBiomas: fração de caatinga nativa, pastagem, lavoura por ponto; filtrar ou estratificar | M | M | conta GEE |
| 5 | Índices oceânicos (Atlântico Niño ATL3, TSA, Niño) para alvo sazonal/horizonte longo | B-M | A | arquivos de texto |
| 6 | SPI/SPEI de verdade (pacote pronto) com chuva e PET do ERA5-Land | B-M | M | depende do item 3 |
| 7 | Evapotranspiração: GLEAM (E, estresse) ou ERA5-Land; MOD16 só com cautela | B-M | M | cadastro (GLEAM) |
| 8 | Pluviômetros (FUNCEME/INMET/ANA) como verdade de campo | B-M | B | acesso incerto |
| 9 | IMERG ou MSWEP no lugar do POWER | B | M | cadastro (IMERG) |
| 10 | LSTM, transformer, Prophet | B | B | zero |

### Ficha 1. SMAP como atributo (já coletado)
- **Fonte lida:** https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008 (bandas `sm_rootzone` 0-100 cm, `sm_surface` 0-5 cm, `sm_profile`, e percentis; pixel de 11 km; passo de 3 h; desde 2015-03-31; domínio público). Le et al. 2024, https://doi.org/10.1029/2024GL111187 (resumo via Crossref) e suplemento https://ntrs.nasa.gov/api/citations/20240012812/downloads/2024_Le_GRL_SuppInfo.pdf. Resumo da página de síntese: https://smap.jpl.nasa.gov/internal_resources/866/Le_2024.pdf.
- **Resultado reportado:** "superioridade do DAPI sobre a previsão por climatologia, com maior ganho em regiões limitadas por água". Número exato: não li (texto principal 403). No SSRN 5655758, correlação espacial de -0,606 entre RZSM e probabilidade de seca na Caatinga (preprint, não revisado por pares).
- **Como testar no nosso protocolo:** reproduzir o desenho de Le: anomalia de NDVI defasada + anomalia de SMAP defasada (0, 1, 2 compostos), alvo = anomalia no composto seguinte. Variantes pré-registradas (no máx. 2): `pers_lags4 + sm_rootzone_anom` e `pers_lags4 + sm_surface_anom`. A anomalia do SMAP deve usar climatologia só de anos < Y (como já fazem com o alvo). Comparar com `pers_lags4` pareado por ano.
- **Limite sério:** a série começa em 2015. Climatologia do SMAP com 4 a 5 anos é ruidosa e só sobram ~2019-2021 para seleção e 2022-2024 para confirmação (poucos anos, baixo poder). Tratar como **teste de sinal**: se a direção for positiva em quase todos os anos, vale buscar uma série longa (item 3). O placebo continua obrigatório.
- **Custo e acesso:** zero, os dados já estão em `data/`. Observação: nossa documentação diz "9 km"; o catálogo do GEE lista pixel de 11 km (versão reamostrada) **[não conferi qual é a grade do arquivo que vocês baixaram]**.

### Ficha 2. Habilidade por horizonte e por estação
- **Fonte lida:** Gallear et al. 2025, https://nhess.copernicus.org/articles/25/1521/2025/ (R² mediano 0,69 / 0,35 / 0,16 para 1, 2, 3 meses); Barrett et al., https://arxiv.org/pdf/1911.10339 (modelo auto-regressivo com RMSE aproximadamente metade da persistência a 4 semanas; acerto de ~89% e falso alarme ~4% para o alerta de seca a 4 semanas; 81% e 6% a 6 semanas; o VCI3M é suavizado em 3 meses, o que infla a habilidade e o texto avisa que não é comparável a previsões puras).
- **Como testar:** sem coletar nada. Rodar `base`, `persistencia`, `pers_lags4` e as variantes de clima já existentes com alvo a +1, +2, +3, +4 compostos, e reportar skill separado para (a) estação chuvosa (fev-mai no Ceará) e resto do ano, (b) início da estação (primeiros compostos após a primeira chuva forte). Isso **não** é uma variante nova de modelo; conta como descritivo e deve ser declarado como tal. **[inferência]** O clima deve acrescentar mais onde a persistência perde força (horizontes longos e viradas de estação), o que o teste de +1 composto esconde.
- **Custo e acesso:** zero. Pré-requisito: o `ndvi_16d.parquet` com 195 pontos.

### Ficha 3. ERA5-Land
- **Fonte lida:** https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR (pixel de 11 132 m; 1950 até ~3 meses atrás; `volumetric_soil_water_layer_1..4` de 0-7, 7-28, 28-100, 100-289 cm; evaporação por componente; licença Copernicus com aviso obrigatório). **Atenção do próprio catálogo:** as bandas de evaporação de solo nu, água aberta e transpiração têm rótulos trocados por erro conhecido do ECMWF; validar antes de usar.
- **Resultado reportado:** nenhum estudo lido usou ERA5-Land para prever NDVI na Caatinga. Gallear usa ERA5 mensal (temperatura, evaporação potencial, radiação) mais SPEI/SPI e RZSM, com GBM como melhor modelo. Rezende et al. 2023 (https://www.frontiersin.org/articles/10.3389/frwa.2023.1295286) usam GLEAM v3.6a no semiárido, mas para estudo de tendência de LAI/GPP, não previsão.
- **Como testar:** trocar a chuva do POWER (0,5 grau) por chuva do ERA5-Land e acrescentar anomalia de umidade das camadas 1-3, tudo em anomalia padronizada com climatologia só de anos < Y. Série longa (2001-2024) mantém os 12 anos de seleção. Máx. 3 variantes: (a) chuva ERA5-Land no lugar do POWER, (b) + umidade camada 1-2, (c) + camada 3. Esse item resolve também o problema de 184 municípios compartilhando 59 células: 0,1 grau separa muito mais pontos **[inferência; não calculei quantas células ERA5-Land distintas os 195 pontos ocupam]**.
- **Custo e acesso:** Earth Engine exige conta cadastrada (não verifiquei regras de cota/uso). A página do CDS (Copernicus) não abriu na minha rede, então não sei descrever o cadastro de lá.

### Ficha 4. MapBiomas (separar caatinga, pastagem, lavoura)
- **Fonte lida:** https://developers.google.com/earth-engine/datasets/catalog/projects_mapbiomas-public_assets_brazil_lulc_v1 (ativo `projects/mapbiomas-public/assets/brazil/lulc/v1`, Coleção 10, 1985-2024, 30 m, banda `classification`, ano na propriedade `year`, licença CC-BY-4.0). Legenda lida em https://brasil.mapbiomas.org/wp-content/uploads/sites/4/2025/08/Legenda-Colecao-10-Legend-Code.pdf: Formação Florestal 3, Formação Savânica 4, Formação Campestre 12, Pastagem 15, Agricultura 18 (lavoura temporária 19, perene 36), Mosaico de Usos 21, Área urbanizada 24, Água 26. Documento do bioma: https://brasil.mapbiomas.org/wp-content/uploads/sites/4/2025/08/Caatinga-Appendix-ATBD-Collection-10-v1.pdf.
- **Resultado reportado:** nenhum estudo lido mede o ganho de estratificar por uso do solo na previsão. Le 2024 selecionou células com uma única cultura e separou irrigado/sequeiro (suplemento, Fig. S6 e S7 existem; resultados não lidos). A legenda não tem classe "Caatinga": o bioma é definido pelo mapa de biomas, e a vegetação nativa aparece como classes 3, 4, 12 **[inferência: confirmar com o mapa de biomas do IBGE]**.
- **Como testar:** para cada um dos 195 pontos, calcular a fração de cada classe dentro do pixel MODIS de 250 m (e num raio de ~1 km) no ano do alvo. Três usos, em ordem de custo: (1) só diagnóstico: skill separado por pontos "nativa > 70%" e "pastagem/lavoura/mosaico > 30%"; (2) filtrar pontos de baixa pureza; (3) interação persistência x fração de uso. Só (1) é descritivo; (2) e (3) contam como variantes no N de Bonferroni. **[inferência]** Pastagem e lavoura têm NDVI dependente de manejo e irrigação; a persistência deve valer por motivos diferentes lá.
- **Custo e acesso:** conta Earth Engine (a mesma do item 3). A API pública do MapBiomas fora do GEE: não conferi.

### Ficha 5. Índices oceânicos (ENSO e Atlântico)
- **Fonte lida:** Hounsou-Gbo 2019 https://doi.org/10.3390/atmos10060335 (resumo); Erasmi 2014 https://doi.org/10.3390/rs6043041 (resumo); página PSL do TSA https://psl.noaa.gov/data/timeseries/month/TSA (média de TSM em Eq-20S, 10E-30W; de 1948 até o presente; arquivos `/data/correlation/tsa.data`, `.csv`, `.nc`; fonte HadISST1.1); página CPC do ATL3 https://cpc.ncep.noaa.gov/products/international/ocean_monitoring/IODMI/ATL3_month.html (caixa 20W-0, 2.5S-2.5N; ERSST v6; desde 1950; arquivo de texto mensal).
- **Resultado reportado:** defasagens de ~6 meses (chuva fev-abr) e 12 meses (NDVI anual). Não achei número de habilidade lido para NDVI de 16 dias. Gallear 2025 testou o SOI e **o excluiu** do modelo final; Barrett cita ENSO/TSM como possível melhoria, sem testar.
- **Como testar:** no máximo 2 variantes, só em horizonte longo (ficha 2): `pers_lags4 + ATL3(jun-ago do ano anterior)` e `+ Niño3.4`. Só existe um valor por ano e por índice (24 valores no total): risco de overfitting alto, então o placebo (embaralhar o índice entre anos) é imprescindível. Como o índice é igual para todos os pontos, ele só pode entrar como interação com a época do ano. Se não houver ganho no horizonte longo, descartar.
- **Custo e acesso:** arquivos de texto públicos (sem cadastro nas páginas lidas). Não consegui abrir as páginas do ONI/Niño3.4 do CPC nem a do TNA.

### Ficha 6. SPI/SPEI "de verdade"
- **Fonte lida:** https://github.com/monocongo/climate_indices (SPI, SPEI, PET por Thornthwaite/Hargreaves/FAO-56, PDSI; BSD-3-Clause; Python; 463 estrelas; última atividade 2026-11-11; o README diz que a versão 3.2.0 descrita ainda não está no PyPI, a publicada é a 3.0.0). Resultado em estudo: Gallear 2025 acha SPEI/SPI entre os atributos mais importantes, e na versão SSRN os períodos de 30 e 90 dias aparecem, conforme o bioma.
- **Como testar:** nossas variantes "SPI simplificado" e "déficit hídrico Hargreaves" já falharam (seção 2 de `05_EXPERIMENTOS.md`) com POWER 0,5 grau. Só vale refazer com chuva e PET do ERA5-Land (item 3), calculando SPI/SPEI de 1, 2 e 3 meses com calibração só em anos < Y. Máx. 2 variantes.
- **Custo:** baixo depois do item 3. O pacote `xclim` (Apache-2.0, Python, última atividade 2026-11-12) existe, mas o README que li não cita SPI/SPEI; não confirmei.

### Ficha 7. Evapotranspiração (MOD16, GLEAM, ERA5-Land)
- **Fonte lida:** MOD16A2GF v061 https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD16A2GF (500 m, 8 dias, 2000 a 2025, bandas ET e PET em kg/m2/8 dias, escala 0,1, sem restrição de uso). GLEAM https://www.gleam.eu/ (versão 4.3; grade 0,1 grau, diária; 4.3a: 1980-2024; 4.3b: 2003-2024; variáveis incluem E, estresse evaporativo, umidade do solo da zona radicular e da superfície; **exige cadastro** com nome e e-mail, entrega por SFTP na porta 2225; uso comercial só com aprovação).
- **Resultado reportado:** Rebello 2019 (só resumo) coloca ET por último na ordem preditiva. Nada lido mede ganho de MOD16 ou GLEAM em previsão de NDVI.
- **Cuidado [inferência, não li a documentação do algoritmo]:** o MOD16 parte de produtos MODIS de vegetação (LAI/FPAR) como entrada, então pode ser quase uma cópia do NDVI. Prefira o estresse evaporativo (S) ou E do GLEAM, ou a evaporação do ERA5-Land. Confirmar a dependência antes de gastar tempo.
- **Como testar:** razão ET/PET (ou o estresse S do GLEAM) em anomalia, defasada 1-2 compostos, como atributo sobre `pers_lags4`. Essa razão faz o papel do que o Embrapa chama de ISNA (água consumida / água máxima); a definição do ISNA veio só de resumo de busca, não abri o artigo **[não conferi]**.

### Ficha 8. Pluviômetros (FUNCEME, INMET, ANA)
- **FUNCEME:** achei só indícios por busca (nenhuma página consegui abrir; erro de certificado da rede deles). Existem: Calendário de Chuvas (https://chuvas.funceme.br/, abriu só o título), Portal Hidrológico do Ceará (http://www.funceme.br/hidro-ce-zend/app/pagina/show/178, com menu "Downloads", segundo a busca), um KML de postos (http://funceme.br/app/kml/postos_pluviometricos.kml) e, numa FAQ antiga, uma página "Download de Séries Históricas" (http://www.funceme.br/?p=843). Notícias citam 527 a 550 pluviômetros (números diferentes entre jornais). **Não confirmei API nem formato; para dados completos o caminho seguro é pedir à FUNCEME.** O repositório https://github.com/thiagozaranza/funceme-api (PHP, sem licença, 1 estrela, 2020) não é cliente da FUNCEME: é um tutorial de API própria, sem endpoints.
- **INMET:** o README de https://github.com/rfsaldanha/bdmepr (R; MIT na página, "NOASSERTION" na API; última atividade 2025-05-27) descreve baixar zips anuais `https://portal.inmet.gov.br/uploads/dadoshistoricos/AAAA.zip` com um CSV por estação, sem login citado. Não consegui testar a URL (host inacessível daqui). O README de https://github.com/ThiagoRBM/API_INMET (R; sem licença; 2 estrelas; última atividade 2022-06-01) diz que a API limita cada pedido a 6 meses; o manual oficial retornou 404 para mim. A página do INMET diz que as estações automáticas têm dados horários e que os dados automáticos "são brutos e sem consistência" (resultado de busca; página do BDMEP lida diz que é atualizada a cada 90 dias).
- **ANA:** https://github.com/wallissoncarvalho/hydrobr (Python; BSD-3-Clause; última atividade 2026-09-16; 59 estrelas) baixa chuva (`ana.prec()`) da ANA por REST (**exige identificador e senha** em variáveis de ambiente; o processo de cadastro não verifiquei) ou pelo serviço antigo ServiceANA; tem limites de taxa (HTTP 429), consultas em blocos, dias sem dado ficam NaN, e a ramificação lida ainda não está no PyPI. Há também https://github.com/hydroversebr/hydrobr (R; GPL-3.0; 2026-11-05) para estações pluvio e fluviométricas da ANA.
- **Como testar:** não como atributo (poucos postos, lacunas). Use para **validar** se o ERA5-Land/POWER erra a chuva nos 184 municípios, e só então decidir. Ganho esperado em previsão de NDVI: baixo, porque CHIRPS (que usa estações) não ajudou.

### Ficha 9. IMERG / MSWEP
- **Fonte lida:** IMERG https://gpm.nasa.gov/data/imerg e https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07 (11 km; 30 min; 1998 em diante; a execução "Final", a recomendada para pesquisa, tem latência de ~2,5 a 3,5 meses; o GEE avisa que não há produtos "permanentes" depois de 30/09/2025; **PPS FTP exige cadastro**). MSWEP: o site (gloh2o.org) não abriu; só tenho o estudo https://doi.org/10.3390/rs10071093 (resumo): compara CHIRPS, CMORPH, MSWEP e SM2RAIN-CCI no Nordeste (1998-2015); mediana de viés do CHIRPS 0,30% no Cerrado; RMSE mediano 12,57 mm do SM2RAIN-CCI na Caatinga (5 dias).
- **Avaliação:** chance baixa pelo mesmo motivo do CHIRPS. Só testar se o item 3 mostrar que resolução espacial da chuva importa.

### Ficha 10. Modelos (ridge, GBM, LSTM, Prophet)
- **Lido:** Gallear 2025: entre random forest, GBM, rede neural, kNN, ridge e regressão linear, o **GBM foi o melhor**; LSTM foi deliberadamente não avaliado ("Occam's razor"). Arxiv 2602.01799 (transformer para NDVI, Landsat 1984-2024, previsão do ano seguinte): R² 0,8412 do modelo proposto contra 0,8088 (LSTM) e 0,7459 (SVM); **não compara persistência nem climatologia e não testa clima**, então não ajuda a decidir.
- **Prophet:** https://github.com/facebook/prophet (MIT; Python e R; 20,5 mil estrelas; versão 1.5.0 em 2026-10-05 segundo o changelog) declara "em modo de manutenção desde a v1.4.0, sem novas funcionalidades". **[opinião]** serve para tendência + sazonalidade de uma série; nosso alvo já é anomalia sem sazonalidade, e o ganho vem de memória e de covariáveis.
- **Conclusão prática:** o XGBoost já empatou ou perdeu para o ridge aqui. Redes profundas com 195 pontos x 24 anos são o pior custo/benefício. Só voltaria a GBM se houver mais atributos (itens 1, 3, 4, 7).
- Busca de repositório "NDVI forecast caatinga" no GitHub: **nenhum resultado**. Repositórios genéricos de previsão de NDVI existem (por exemplo https://github.com/keves1/vegetation-health-monitor, MIT, Jupyter, 2026-10-11, e https://github.com/waldnerf/NDVI_forecasting, sem licença, 2021), mas **não abri** nenhum; não os recomendo.

## 3. Os 3 testes para rodar primeiro

Pré-requisito comum: terminar o `ndvi_16d.parquet` com 195 pontos e confirmar `pers_lags4` (passo já pendente em `04_RETOMADA.md`). Todo teste novo usa o mesmo protocolo: seleção 2010-2021, confirmação 2022-2024 aberta uma vez, placebo, N total contado no Bonferroni, comparação pareada por ano contra `pers_lags4`.

**Teste 1. Habilidade por horizonte e estação (ficha 2).** Custo zero. Responde onde o clima poderia ajudar antes de gastar mais. Se o clima só aparece a +2 ou +3 compostos, os testes 2 e 3 devem usar esse horizonte como alvo principal.

**Teste 2. SMAP como atributo (ficha 1).** Custo zero, dado já coletado, 2 variantes. Limitado a poucos anos (2015+); resultado positivo consistente justifica o teste 3, resultado nulo não prova nada (pouco poder).

**Teste 3. ERA5-Land (chuva + umidade do solo, 0,1 grau, 2001-2024; ficha 3), e na mesma sessão do Earth Engine, extrair as frações do MapBiomas (ficha 4) para o diagnóstico (1) sem custo de variante.** É o único teste novo com série longa o bastante para ter poder e com resolução melhor que a do POWER.

Os itens 5 (oceano) e 6 (SPI/SPEI) vêm depois, e só no horizonte que o Teste 1 apontar.

## 4. Como validar sem overfitting (aplicável aos nossos poucos dados)

- **Validação em blocos é o mínimo:** Roberts et al. (Ecography 2017, lido) concluem que a validação cruzada aleatória subestima seriamente o erro quando há estrutura temporal, espacial ou hierárquica, e recomendam validação em blocos "sempre que existir dependência nos dados". O walk-forward por ano já cumpre isso.
- **A unidade de independência é o ano, não o ponto [inferência].** No mesmo ano, os 195 pontos veem o mesmo clima. Mais pontos melhoram a estimativa do erro, mas pouco o poder do teste. Por isso o Bonferroni com N alto e 12 anos é muito duro (já notado em `05_EXPERIMENTOS.md`). Reduza N: declare famílias (SMAP, ERA5-Land, oceano) com no máximo 2 a 3 variantes cada, em vez de dezenas.
- **Dois pisos, não um:** comparar sempre contra climatologia **e** contra `pers_lags4`. Barrett et al. comparam contra persistência (lido); Gallear só contra média sazonal (lido), o que explica por que os R² altos de lá não são comparáveis aos nossos.
- **Descritivo versus confirmatório:** análises por horizonte, estação e uso do solo ajudam a escolher hipóteses; só as variantes pré-registradas entram no N e na confirmação 2022-2024. Não ajustar nada olhando a confirmação.
- **Placebo e anomalias sem vazamento:** toda climatologia de atributo (SMAP, ERA5-Land, oceano) só com anos < Y, igual ao alvo. Para índices oceânicos (só 24 valores), exigir placebo negativo.
- **Cuidado com o ano mais seco:** os anos de confirmação (2022-2024) são poucos; reportar também o resultado por ano e não só a média.

## 5. Repositórios conferidos

Abri a página de cada um e consultei a API do GitHub em 2026-11-12 (licença, linguagem, última atividade).

| Repositório | Licença | Linguagem | Última atividade | Observação |
|---|---|---|---|---|
| monocongo/climate_indices | BSD-3-Clause | Python | 2026-11-11 | SPI/SPEI/PET; versão 3.2.0 ainda fora do PyPI (publicada: 3.0.0) |
| Ouranosinc/xclim | Apache-2.0 | Python | 2026-11-12 | não confirmei SPI/SPEI no README |
| ropensci/chirps | MIT na página; "NOASSERTION" na API | R | 2026-11-03 | CHC é a fonte padrão (CHIRPS v3 e v2); ClimateSERV só v2 e pode ser removido |
| wallissoncarvalho/hydrobr | BSD-3-Clause | Python | 2026-09-16 | ANA REST com credenciais; serviço antigo sem |
| hydroversebr/hydrobr | GPL-3.0 | R | 2026-11-05 | estações da ANA |
| rfsaldanha/bdmepr | MIT na página; "NOASSERTION" na API | R | 2025-05-27 | zips anuais do INMET |
| ThiagoRBM/API_INMET | nenhuma | R | 2022-06-01 | 2 estrelas; pedidos de 6 meses; desatualizado |
| thiagozaranza/funceme-api | nenhuma | PHP | 2020-10-30 | não é cliente da FUNCEME |
| facebook/prophet | MIT | Python/R | v1.5.0 em 2026-10-05 (changelog) | modo de manutenção |

## 6. Acessos que exigem cadastro (resumo)

- **Earth Engine** (ERA5-Land, MapBiomas, MOD16, SMAP, IMERG, CHIRPS): conta cadastrada; regras de cota não verificadas.
- **GLEAM:** nome + e-mail, senha por e-mail, SFTP (página lida).
- **IMERG (PPS FTP / Giovanni):** cadastro; Giovanni exige conta NASA Earthdata (página lida).
- **ANA via hydrobr (REST):** identificador e senha da ANA (README lido; cadastro não verificado).
- **CDS/Copernicus, MSWEP, FUNCEME, INMET API:** não consegui abrir; não afirmo nada sobre cadastro.
- **Sem cadastro nas páginas lidas:** arquivos TSA (PSL), ATL3 (CPC), CHIRPS no GEE, zips do INMET segundo o README do `bdmepr` (não testado).

## 7. O que esta pesquisa NÃO mostra

- Nenhum estudo lido reporta ganho de umidade do solo, ENSO ou uso do solo especificamente para prever **anomalia de NDVI de 16 dias na Caatinga** com protocolo walk-forward. As evidências são de outras regiões (SMAP em lavouras dos EUA), de outros horizontes (mensal, anual) ou de outro alvo (VHI, VCI). Trate as chances da tabela como hipóteses.
- A versão SSRN 5655758 é preprint sem revisão por pares; o artigo publicado é o NHESS 2025.

## 8. Não consegui conferir (fora de qualquer conclusão)

FUNCEME (certificado inválido; só títulos via busca), API e manual do INMET (404; host inacessível), CDS/Copernicus, gloh2o (MSWEP), NOAA PSL TNA e CPC ONI, texto completo de Le et al. 2024 (403), Meyer et al. 2018 (sem resumo no Crossref), Pereira et al. 2020 (Sci. Total Environ.; sem resumo no Crossref), estudo IMERG no semiárido (Atmosphere 2022), artigos sobre aprendizado profundo com poucos dados, ISNA (Embrapa; só resumo de busca), definição de qual grade de SMAP vocês baixaram.

## 9. Fontes abertas

- Barbosa et al. 2011, Rev. Bras. Geografia Física: https://periodicos.ufpe.br/revistas/rbgfe/article/download/232655/26668/86229
- Barrett et al., arXiv: https://arxiv.org/pdf/1911.10339
- Gallear et al. 2025, NHESS: https://nhess.copernicus.org/articles/25/1521/2025/ ; preprint SSRN: https://repository.rothamsted.ac.uk/id/eprint/33693/1/ssrn-5655758%20%281%29.pdf
- Rebello 2019 (tese UFRJ): https://pantheon.ufrj.br/bitstream/11422/23163/1/938865.pdf
- Le et al. 2024 (resumo, suplemento): https://doi.org/10.1029/2024GL111187
- Erasmi et al. 2014: https://doi.org/10.3390/rs6043041 ; Hounsou-Gbo et al. 2019: https://doi.org/10.3390/atmos10060335
- Rezende et al. 2023: https://www.frontiersin.org/articles/10.3389/frwa.2023.1295286
- Int. J. Climatol. 2020 (autores não conferidos): https://doi.org/10.1002/joc.6723 ; avaliação de chuva no Nordeste: https://doi.org/10.3390/rs10071093
- Roberts et al. 2017: https://www.biometrie.uni-freiburg.de/mitarbeiter/dormann/roberts-et-al-2017-ecography.pdf
- Transformer NDVI: https://arxiv.org/html/2602.01799
- Catálogos de dados (GEE): SMAP SPL4SMGP, ERA5-Land diário, MOD16A2GF, IMERG V07, CHIRPS diário, MOD13Q1, MapBiomas (links nas fichas)
- GLEAM: https://www.gleam.eu/ ; IMERG: https://gpm.nasa.gov/data/imerg
- MapBiomas legenda C10 e ATBD Caatinga: links na ficha 4
