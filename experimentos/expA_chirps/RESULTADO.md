# Experimento A: CHIRPS melhora a previsao da anomalia de NDVI? (2026-11-11)

Dados: 13 pontos (`experimentos/dados13/`), CHIRPS diario via ClimateSERV (312/312 arquivos ponto-ano, 0 falhas, 0 NaN; 113.958 linhas).
Concordancia: correlacao diaria POWER x CHIRPS = 0,521; total anual POWER/CHIRPS = 0,991.
Protocolo: walk-forward, decisao so em 2010-2021 (12 anos); 2022-2024 NAO foram olhados. N = 6 variantes (x Ridge/XGBoost); Bonferroni com N=6.
Placebo rodado (`res_placebo.pkl`); reais em `res_real.pkl`; saida completa em `exp.log`. Pareamento por ano contra `persistencia` (Ridge).

## Resultados (selecao 2010-2021, Ridge)
| Variante | Skill vs clim. | IC inf. corrigido | Anos positivos | Dif. vs persistencia | IC inf. da dif. | Placebo skill |
|---|---|---|---|---|---|---|
| persistencia (referencia) | +0,2283 | +0,1581 | 100% | 0 | 0 | -0,0005 |
| pers_power_chirps (pers+POWER+CHIRPS) | +0,2295 | +0,1584 | 100% | +0,0012 | -0,0019 | -0,0006 |
| pers_chirps (CHIRPS no lugar do POWER) | +0,2180 | +0,1482 | 100% | -0,0103 | -0,0117 | -0,0006 |
| base (POWER) | +0,0583 | +0,0285 | 83% | -0,1701 | -0,2221 | -0,0011 |
| base_power_chirps | +0,0600 | +0,0260 | 83% | -0,1683 | -0,2170 | -0,0009 |
| base_chirps | +0,0378 | +0,0074 | 83% | -0,1905 | -0,2418 | -0,0010 |

XGBoost: pers_power_chirps +0,2349 (dif vs persistencia Ridge-pareada: +0,0066, IC inf. -0,0205); persistencia XGBoost +0,2333 (dif +0,0049, IC inf. -0,0199); placebo XGBoost negativo (-0,02). Sem persistencia, base_power_chirps vs base: Ridge +0,0017 (IC inf. -0,0050), XGBoost +0,0124 vs base Ridge (IC inf. -0,0058); base_chirps pior que base (-0,0205, IC inf. -0,0263).

## Veredito
**Negativo.** Nenhuma variante com CHIRPS supera a `persistencia`: o melhor ganho pareado (pers_power_chirps, +0,0012) tem IC inferior corrigido negativo (-0,0019), ou seja, indistinguivel de zero; trocar POWER por CHIRPS piora (-0,0103, IC inf. -0,0117, significativo para pior). Sem persistencia, CHIRPS tambem nao melhora a base. Placebo OK (Ridge ~0 ou negativo; sem vazamento). Como nenhuma variante passou na selecao, a confirmacao selada (2022-2024) NAO foi aberta e nao deve ser usada para CHIRPS. A conclusao e "sem evidencia de ganho" com 12 anos e 13 pontos (poder baixo, Bonferroni conservador); nao e prova de que chuva nao importa. O ganho do modelo continua vindo da memoria do NDVI.
Observacao: nas tabelas do `exp.log` a coluna `dif_vs_base_*` do primeiro bloco e a diferenca contra `persistencia` (parametro base=), nao contra `base`.
