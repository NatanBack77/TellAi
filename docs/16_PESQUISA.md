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
