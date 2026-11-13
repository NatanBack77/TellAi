# Avaliacao com 195 pontos (2026-11-12)

Todos os numeros vieram de codigo rodado nesta sessao (`avaliar.py`, `src.modelos.preditivo`, leitura dos parquets).
`src/modelos/` nao foi alterado. Amostra efetiva: 59 celulas POWER distintas (os 195 pontos trazem NDVI, nao chuva nova).

## 1. Cobertura dos dados
**NDVI (`data/processed/ndvi_16d.parquet`)**: 107.583 linhas, 195 pontos x 552 datas (2001-01-01 a 2024-12-18).
Esperado 107.640; faltam 57 linhas (0,05%) = todas na data 2005-08-29, uma linha por ponto em 57 pontos (nao e coleta parcial:
a data nao veio para esses pontos). NDVI NaN: 10 linhas (arneiroz_ce e itapipoca_ce em 2015-03-22; pedra_branca_ce 2002-03-22;
oros_ce 7 composicoes seguidas de 2004-02-18 a 2004-05-24). Pontos 100% NaN: 0 (minimo de composicoes validas: 545, oros_ce).
Confiabilidade: 0 = 61.921; 1 = 27.637; 3 = 18.015; NaN = 10 (nao ha valor 2). 83,2% das linhas com confiabilidade 0 ou 1.
NDVI: media 0,527; min -0,182; max 1,0. Nada foi preenchido.

**SMAP (`umidade_solo.parquet`)**: 694.980 linhas = 195 pontos x 3.564 dias (2015-03-31 a 2024-12-31), sem dia faltando, 0% NaN
em `sm_superficie` e `sm_raiz`, 0 pontos 100% NaN. Cache: 28.524 granulos, 0 faltando, 0 baixados nesta rodada, 0 falhas.
Dias com granulos > 8 (9, 10 ou 11, 8 datas em 2023-2024) existem; nenhum dia com < 8. Valores: sm_superficie 0,020-0,400;
sm_raiz 0,008-0,402. Os 44 granulos de HTTP 502 de ontem (jan/2022) ja estavam no cache: jan/2022 tem 8 granulos/dia em todos os dias.

Observado x hipotese (ritmo): (obs) a rodada do SMAP terminou em poucos minutos sem baixar nada, entao nao havia ritmo baixo a
investigar nesta rodada; o log so tem o resumo final. (obs) NDVI: fase de listagem ~10 min; logo depois ~57 janelas/min
(18.496 -> 18.553 em 60 s), depois ~190-250/min. (hipotese, sem evidencia) limitacao/oscilacao do servidor ORNL; (hipotese) o 502 era transitorio.

## 2. Protocolo e desvios
- Seleciono 2010-2021; 2022-2024 so na confirmacao selada (cada uma rodada uma vez). Rodei via `experimentos/avaliacao_195/avaliar.py`
  (rascunho revisado) e NAO pela CLI `python -m src.modelos.walkforward`, porque a CLI avalia 2010-2024 de uma vez e imprime a confirmacao
  (violaria "nao olhar 2022-2024"), e porque `carregar_entradas` carrega `umidade_solo.parquet` automaticamente: sem `ent["umidade_solo"]=None`
  todas as variantes ganhariam features de SMAP e perderiam as linhas pre-2015 (confunde NDVI-persistencia com SMAP).
- Correcao no rascunho: `make_sm` falhava (`TypeError` no rename) e foi reescrita; adicionado `sm_confirma`. Nenhuma outra logica alterada.
- Bonferroni: N=4 no bloco NDVI (base, persistencia, so_persistencia, pers_lags4); N=7 no bloco SMAP (+ pers_sm, pers_sm_l14, pers_sm_l30).
  Variantes de expC.py (13 pontos) nao foram recontadas: so pers_lags4 foi reavaliada.
- SMAP so existe desde 2015: selecao SMAP em 2018-2021 (4 anos; treino com >= 3 anos de SMAP). Com 4 anos o IC bootstrap sobre anos
  degenera para ~o minimo dos 4 valores; tem pouco poder e o IC nao e confiavel.

## 3. Selecao 2010-2021 (12 anos, ~2.300-2.950 linhas de teste/ano, mesmas linhas para todas as variantes). Skill vs climatologia, media dos anos
| Variante | Ridge | XGBoost | IC inf. corrigido (Ridge) | Anos positivos | dif. vs persistencia (Ridge), IC inf. |
|---|---|---|---|---|---|
| base | +0,066 | +0,086 | +0,029 | 10/12 (Ridge) | -0,243 |
| persistencia | +0,309 | +0,322 | +0,260 | 12/12 | referencia |
| so_persistencia | +0,295 | +0,287 | +0,248 | 12/12 | -0,013 (IC inf. -0,020) |
| pers_lags4 | +0,311 | +0,322 | +0,262 | 12/12 | +0,0026 (IC inf. +0,00004), melhor em 10/12 anos |
| ingenua (repetir ultima anomalia) | +0,239 | | +0,183 | 12/12 | |

Placebo (features embaralhadas entre anos): todas as variantes Ridge/XGBoost entre -0,0001 e -0,0025; ingenua -0,31. Passou (<= 0).

## 4. Confirmacao selada 2022-2024 (rodada uma vez)
| Variante | Ridge | XGBoost | por ano (Ridge 2022/23/24) |
|---|---|---|---|
| persistencia | +0,2385 | +0,2644 | +0,360 / +0,192 / +0,164 |
| pers_lags4 | +0,2435 | +0,2701 | +0,365 / +0,194 / +0,172 |
| base (controle) | -0,0444 | -0,0170 | +0,073 / -0,085 / -0,121 |
| ingenua | +0,146 | | |

## 5. SMAP como feature (selecao 2018-2021, N=7; controle = persistencia na MESMA amostra, 11.412 linhas)
| Variante | Skill Ridge | dif. vs controle | IC inf. corrigido da dif. |
|---|---|---|---|
| persistencia (sem SMAP) | +0,2216 | | |
| pers_sm (media 15 d, ate t-1; padrao do pacote) | +0,2290 | +0,0074 | +0,0026 (4 anos: IC pouco confiavel) |
| pers_sm_l14 (sm_raiz media 7 d, defasada 14 d) | +0,2225 | +0,0010 | +0,0005 |
| pers_sm_l30 (idem, defasada 30 d) | +0,2232 | +0,0016 | +0,0010 |
XGBoost: pers_sm +0,2274 (dif. vs controle Ridge +0,0058, IC inf. -0,0030); as outras com SMAP defasado ficam abaixo do controle.
Placebo SMAP: todas negativas (Ridge -0,071 a -0,082; XGBoost ~ -0,096 a -0,107). Passou.
Confirmacao selada SMAP (2022-2024, 8.052 linhas, treino 2015+): controle +0,2311 Ridge / +0,2530 XGBoost; pers_sm +0,2374 / +0,2577
(por ano +0,3629/+0,1772/+0,1720 contra +0,3550/+0,1745/+0,1639). Ganho do SMAP ~ +0,006 sobre a persistencia, positivo nos 3 anos.

## 6. `python -m src.modelos.preditivo` (195 pontos, 59 celulas, confianca "media")
Atencao: a CLI inclui as features de SMAP (arquivo existe), logo so ficam 35.937 de 89.558 periodos completos (>= 2015). Escolhe XGBoost.
Esta CLI NAO usa persistencia (so clima + sazonalidade + SMAP). Holdout 2022-2024 (skill vs climatologia): Ridge +0,013; XGBoost +0,045
(RMSE 0,1032 contra 0,1080 da climatologia). CV por celula (GroupKFold, 5 folds): Ridge +0,069; XGBoost +0,121 (otimista: climatologia usa anos do proprio ponto, D22).
Cobertura conformal holdout (metas 80% / 90%): climatologia 74,7% / 86,2%; Ridge 70,8% / 84,0%; XGBoost 70,3% / 83,3% (subcobertura); CV: 78-79% / 89%.
Controle extra (rodado sem SMAP, nao gravado): holdout Ridge -0,013; XGBoost +0,023.
Esta execucao regravou `data/processed/modelos/metricas.json` e `relatorio_modelos.md` (itens gerados, nao versionados individualmente por mim).

## 7. Vereditos
- **persistencia: valida.** Skill +0,31 (selecao), +0,24 (confirmacao) Ridge; 12/12 anos; placebo ok; vence a base por ~+0,24.
- **pers_lags4: ganho marginal.** +0,0026 sobre a persistencia na selecao (IC inf. +0,00004, no limite com N=4); na confirmacao +0,005 (Ridge) / +0,006 (XGBoost). Estatisticamente passa por pouco, praticamente irrelevante.
- **SMAP: ganho muito pequeno** (~+0,006 a +0,007; confirmacao positiva nos 3 anos), IC sobre 4 anos nao e confiavel. Lags de 14/30 d nao ajudam em XGBoost. Nao e evidencia forte.
- **base (so clima) nao passa** na confirmacao (-0,044 Ridge). O clima sozinho nao supera a climatologia fora da amostra; no preditivo atual o ganho XGBoost (+0,045 com SMAP; +0,023 sem) e pequeno e a cobertura conformal fica abaixo da meta.
- Nao integrei a persistencia a `preditivo.py`/`cenarios.py` (decisao sua). Sem commit/push.
- Ressalvas: 59 celulas efetivas; ano de teste = unidade do IC; confirmacao com 3 anos.
