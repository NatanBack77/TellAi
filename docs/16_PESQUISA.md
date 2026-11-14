# 16. Pesquisa: como melhorar a previsão, a incerteza e o escopo (2026-11-13)

Resumo da literatura consultada (buscas em 2026-11-13; ver links) e o que foi testado no projeto. Os números de skill são do protocolo de `docs/05_EXPERIMENTOS.md`.

## A. Origem do ganho: persistência (memória do NDVI) e clima
- Trabalhos de previsão de NDVI/vegetação de zonas áridas usam como preditores a própria vegetação do período anterior, chuva e umidade do solo
  defasadas; a persistência é um baseline forte. Um modelo bayesiano com chuva e umidade defasadas ganhou ~2 semanas de alcance sobre o
  autorregressivo univariado ([NHESS 2022](https://nhess.copernicus.org/articles/22/2703/2022/)). Em regiões com vegetação esparsa um índice ajustado ao solo (SAVI)
  pode ser mais adequado que o NDVI (mesma referência).
- Estudos de caatinga mostram resposta da vegetação à chuva com defasagem de ~2–3 meses ([Meteosat-SEVIRI 2008–2016](https://cab.inta-csic.es/publicaciones/assessment-of-caatinga-response-to-drought-using-meteosat-seviri-normalized-difference-vegetation-index-2008-2016/)).
- **Testado aqui:** janelas de chuva de 120/180 dias, anomalia de chuva, SPI, eventos, déficit hídrico, terreno, Niño 3.4/Atlântico: nenhum melhorou além da
  persistência (`experimentos/expC_features`, `experimentos/novas_fontes`). O clima segue acrescentando pouco sobre a persistência.
- **Não testado ainda:** SAVI/EVI (cache parcial em `experimentos/expB_indices`), umidade do solo de longa série (GLDAS/ERA5-Land), uso do solo (MapBiomas).

## B. Faixa de incerteza: cobertura abaixo da meta
- O split conformal supõe dados intercambiáveis; um ano seco/úmido desloca os resíduos de todos os pontos juntos. **Conformal adaptativo (ACI)**
  atualiza o nível online com α_{t+1} = α_t + γ(α − err_t) e dá cobertura de longo prazo sem suposição sobre a distribuição
  ([Gibbs e Candès, NeurIPS 2021](https://arxiv.org/abs/2106.00170)). **EnbPI** é uma alternativa sem divisão de dados para séries
  ([Xu e Xie, ICML 2021](https://proceedings.mlr.press/v139/xu21h.html)).
- **Testado aqui:** ACI por estação, γ = 0,05 (fixado antes): cobertura 79,8% / 89,9% na seleção (metas 80% / 90%) e **79,9% / 90,0% na confirmação selada**
  (método atual 75,6% / 86,6%); pior estação 77% / 89%. Detalhe em `experimentos/conformal_A1/RESULTADO.md`. EnbPI não testado.

## C. Escopo: NDVI não é produtividade
- A literatura aponta saturação do NDVI em dossel denso, ruído de solo exposto no início do ciclo (SAVI/MSAVI como alternativa) e confusão entre
  estresse hídrico e de nutrientes; solo e saúde do solo aparecem só de forma indireta no índice. Estudos de produtividade combinam NDVI com
  anomalia de umidade do solo e fenologia ([Frontiers Env. Sci. 2024](https://frontiersin.org/journals/environmental-science/articles/10.3389/fenvs.2024.1417199/pdf)).
- Não achei estudo de NDVI contra rendimento municipal no Nordeste que sirva de referência direta (milho/caupi).
- **Testado aqui** (PAM/IBGE 2015–2023, 182 municípios): NDVI de pico explica R² 0,05–0,10 do rendimento de milho/feijão/mandioca; a chuva de fev–mai
  explica mais (milho 0,31). O app não deve usar NDVI como proxy de produtividade (`experimentos/novas_fontes/RESULTADO.md`).

## D. Chuva da quadra e previsão sazonal
- A quadra chuvosa do Ceará (fev–abr/mai) é governada pelo dipolo do Atlântico tropical, com influência do ENSO via Atlântico; modelos estatísticos e
  de redes neurais compõem o sistema operacional ([Sci. Rep. 2023](https://link.springer.com/10.1038/s41598-023-47841-y); [IRD/FUNCEME](https://horizon.documentation.ird.fr/exl-doc/pleins_textes/divers19-07/010076174.pdf)).
- **Testado aqui:** índices de out–jan não anteciparam a chuva de fev–mai (24 anos, skill −0,05). O app deve apontar para a previsão sazonal oficial da FUNCEME.

## E. Fontes de dados
- Chuva: CHIRPS via ClimateSERV ([chirps, rOpenSci](https://docs.ropensci.org/chirps/articles/Overview.html)); pluviômetros FUNCEME (rede de ~500 postos, sem API oficial confirmada).
- Umidade do solo: SMAP SPL4SMGP via AppEEARS, série desde 2015 ([NSIDC](https://nsidc.org/data/SPL4SMGP)).
- Brasil (equivalentes às bases americanas da lista do desafio): solo (SoilGrids, BDiA/Embrapa), uso do solo (MapBiomas), produção (IBGE PAM/SIDRA, **coletado**),
  preço/mercado (CONAB, CEPEA).

## F. Programação linear inteira mista (MILP) para a rotação
- MILP é a abordagem clássica para planejar rotações: restrições de família botânica e de intervalo entre cultivos, diversidade e renda, em vários períodos
  ([modelo de fluxo, Alfandari et al. 2011](https://faculty.essec.edu/en/research/a-mip-flow-model-for-crop-rotation-planning-in-a-context-of-forest-sustainable-development);
  [modelo binário com famílias e intervalos de demanda, SciTePress 2012](https://www.scitepress.org/Papers/2012/37619/37619.pdf);
  [modelos multiobjetivo, renda e diversidade](https://ersearch2.cvtisr.sk/vufind/SummonRecord/FETCH-LOGICAL-c333t-4559c202ac6cd1131b1ee7a6a991ccf97dfb23a09c14198b45881c70b49554443/Details)).
- Versões robustas e estocásticas tratam incerteza de clima e de rendimento ([planejamento robusto, arXiv 2512.10396](https://arxiv.org/pdf/2512.10396);
  [risco, mão de obra e clima, INRAE](https://prodinra.inra.fr/record/275403); [CVaR com APSIM, arXiv 2208.04840](https://pdf.arxiv.org/pdf/2208.04840)).
  Um achado relevante: aversão a risco muda pouco a rotação; restrições de mão de obra mudam mais.
- Em semiárido, rotações com leguminosas retêm mais água do solo que cereal contínuo (campo na Etiópia); não achei MILP multiobjetivo específico de pequenos agricultores do semiárido.
- **Testado aqui:** `src/culturas/rotacao_milp.py`. Resultado e limites em `experimentos/milp/RESULTADO.md`: ajuda em plano de várias safras com regras duras e em checagem de
  viabilidade; não reduz o empate técnico e depende dos pesos e das lacunas.

## G. Bases NASA do desafio: usadas ou descartadas (2026-11-14)
Responde à pendência A9 (`docs/15_PENDENCIAS.md`). Fontes: o que já está documentado no repositório (`docs/18_ARQUITETURA_TECNICA.md` seção de bases, `docs/09`, `docs/19`, `experimentos/*/RESULTADO.md`) e páginas oficiais LIDAS em 2026-11-14 (URLs na tabela; a leitura passou por uma ferramenta que resume a página, então confira o número na fonte antes de citar em público). Onde não consegui verificar, está escrito "não verificado". **Descartada aqui significa "não integrada neste MVP", não "inadequada"**: o motivo de cada uma é de escopo e de custo, e nenhuma foi testada e reprovada, salvo SMAP (testado, sem ganho).

| Base | Situação no SULCO | Resolução e período | Motivo e custo de integração |
|---|---|---|---|
| **NASA POWER** | **Usada** (clima do app e do modelo) | Grade 0,5° x 0,625° (~50 km), 2001-2024 mais 2025+ (`docs/18`); 195 pontos caem em só 59 células | API REST sem login, coleta idempotente. Limite declarado: célula de ~50 km, não vê o talhão. Calor extremo e chuva extrema do app saem daqui (temperatura do ar e chuva diária), por isso o app NÃO pode dizer que usa ECOSTRESS nem GPM |
| **MODIS MOD13Q1 v061** | **Usada** (NDVI, solo nu, estresse, modelo de previsão) | 250 m, composto de 16 dias, 2001-01-01 a 2024-12-18 mais 2025+ (`docs/18`, `PROSPECTIVO_2025.md`) | Via ORNL DAAC, público e sem login (o caminho AppEEARS ficou preso na fila). Limite: semântica de `pixel_reliability` ainda "a conferir" na doc oficial |
| **SRTM** | **Usada** (declive no indicador de erosão; altitude) | Tiles de 1 arco-segundo (~30 m) no bucket público da AWS, sem login (`docs/18`) | Download de ~700 MB; como feature do NDVI não ajudou (`experimentos/novas_fontes`). Limite: relevo do pixel e da vizinhança, não do talhão |
| **SMAP L4 SPL4SMGP v008** | **Coletada, só informativa** (desligada no modelo) | Grade EASE-Grid 2.0, ~9 km (doc do projeto) ou 11 km (catálogo do Earth Engine): **a verificar**; 2015-03-31 a 2024-12-31 (`docs/18`, `docs/09`) | Exige login Earthdata (OPeNDAP via `earthaccess`, 28.524 grânulos). **Testada: ganho de ~+0,006 a +0,007 de skill, poder baixo; série curta (desde 2015).** Item 11 do desafio fica em 0,5 (`docs/19`) |
| **GPM / IMERG** | **Descartada** (não integrada) | Página oficial https://gpm.nasa.gov/data/imerg: meia hora; cerca de 1998 até hoje (TRMM 1998-2015 + GPM 2014+); latência Early ~4 h, Late ~12 a 14 h, Final ~2,5 a 3,5 meses (a própria página dá os dois números). Resolução da grade: a página não informa; o catálogo do Earth Engine (lido em `docs/09` ficha 9) diz 11 km | `docs/09` ficha 9: o acesso pelo PPS FTP exige cadastro e a avaliação foi "chance baixa" de melhorar o modelo. Nunca foi coletada nem testada. Custo de integração: cadastro + pipeline novo (não medido). Ganho esperado: intensidade de chuva em escala de horas, que o app hoje não mostra (usa chuva diária do POWER) |
| **ECOSTRESS** | **Descartada** | Página oficial https://ecostress.jpl.nasa.gov/: 70 m (mapas de ET), temperatura de superfície (LST) e ET horária como produtos; na Estação Espacial desde 2018. Revisita e cobertura sobre o Ceará: **não verificado**; estado operacional atual: **não verificado** | Nunca foi coletada nem testada. Seria a base certa para estresse por calor da superfície (item 9), mas as cenas são irregulares (órbita da ISS), custo de integração não medido; o app usa Tmax do ar do POWER e avisa que NÃO é ECOSTRESS |
| **Landsat** | **Descartada** | Página oficial https://www.usgs.gov/landsat-missions/landsat-8: Landsat 8 com 30 m multiespectral, 15 m pancromático, 100 m nas bandas térmicas, repetição de 16 dias, lançado em 11/02/2013. Landsat 9 e HLS: **não verificado** | Nunca foi coletada. O MODIS de 250 m já cobre a série diária de NDVI desde 2001; Landsat daria 30 m (mais perto do talhão), mas multiplica o volume de dados e exige tratamento de nuvem (custo não medido). É a candidata mais plausível para a escala de campo (item 33 do `docs/19`) |
| **GRACE / GRACE-FO** | **Descartada** | Página oficial https://gracefo.jpl.nasa.gov/mission/: GRACE de 2002 a 2017; GRACE-FO lançado em 22/05/2018. Resolução espacial: a página não informa, **não verificado** | Nunca foi coletada. Mede variação de armazenamento total de água em escala grande (regional); o app trabalha em ponto de município, então a resolução não casa (avaliação do `docs/19`: "baixo retorno em escala de município"). A tendência hídrica do app é Mann-Kendall de chuva e NDVI, sem GRACE (item 16 em 0,5) |
| **GEDI** | **Descartada** | Página oficial https://gedi.umd.edu/instrument/specifications/: pegada média de 25 m, entre 51,6°N e 51,6°S, missão nominal de 2 anos; datas reais de operação: **não verificado** | Nunca foi coletada. Mede altura e estrutura de dossel; em caatinga baixa e em lavouras anuais o retorno é pequeno (avaliação do `docs/19`, não testada) e a amostragem é por faixas, não contínua (isto último: **não verificado**) |

Leitura honesta: das nove bases, **três entram no app** (POWER, MODIS, SRTM), **uma foi coletada e testada sem ganho** (SMAP, só informativa) e **cinco nunca foram baixadas** (GPM, ECOSTRESS, Landsat, GRACE, GEDI), por falta de tempo e de retorno esperado, não por teste negativo. Não afirmar ao júri que o app "usa" ECOSTRESS, GPM, GRACE ou GEDI (regra "O que NÃO dizer" do `docs/19`).
