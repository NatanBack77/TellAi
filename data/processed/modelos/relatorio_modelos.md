# Relatório dos modelos (SULCO)

Configuração: persistência **ligada**; SMAP **desligado (opção documentada, D52)**. Features: chuva_ac_30d, chuva_ac_60d, chuva_ac_90d, tmax_media_30d, dias_secos_consecutivos, quinzena_sin, quinzena_cos, anom_lag1, anom_lag2.

Alvo: anomalia_ndvi = NDVI - climatologia do slot (climatologia só dos anos de treino).

Treino 2001–2021; holdout [2022, 2023, 2024]; 59 células POWER no treino; 5 folds. Confiança: **media** (heurística: 'baixa' com menos de min_celulas_aviso células POWER distintas; não é probabilidade).

> O modelo captura associações históricas entre clima e NDVI; não é causalidade e não prevê o clima futuro nem a produtividade.

## Métricas por fold (GroupKFold por célula)

| Modelo | MAE | RMSE | R² | skill vs. clim. |
|---|---|---|---|---|
| climatologia | 0.064 ± 0.006 | 0.088 ± 0.006 | -0.001 ± 0.001 | 0.000 ± 0.000 |
| ridge | 0.043 ± 0.002 | 0.064 ± 0.004 | 0.478 ± 0.027 | 0.278 ± 0.019 |
| xgboost | 0.041 ± 0.002 | 0.061 ± 0.003 | 0.522 ± 0.030 | 0.309 ± 0.021 |

XGBoost vs. Ridge (skill): 0.043 ± 0.005

### Por fold

| Fold | Células validação | n | RMSE climatologia | RMSE ridge | RMSE xgboost |
|---|---|---|---|---|---|
| 1 | -10_-60, -11_-61, -11_-64, -12_-61, -15_-65, -16_-61, -23_-67, -6_-65, -6_-66, -8_-62, -9_-61, -9_-65 | 12525 | 0.081 | 0.058 | 0.056 |
| 2 | -10_-61, -10_-63, -11_-65, -13_-62, -14_-62, -14_-64, -14_-65, -16_-60, -16_-62, -21_-62, -8_-63, -9_-64 | 12493 | 0.096 | 0.068 | 0.065 |
| 3 | -10_-65, -10_-66, -12_-64, -12_-65, -13_-64, -14_-63, -15_-62, -21_-64, -7_-66, -8_-66, -9_-60, -9_-63 | 12460 | 0.094 | 0.066 | 0.063 |
| 4 | -10_-62, -10_-64, -12_-62, -13_-63, -14_-61, -14_-66, -6_-64, -7_-62, -7_-63, -8_-61, -9_-62 | 12314 | 0.085 | 0.064 | 0.061 |
| 5 | -11_-62, -11_-63, -12_-63, -13_-65, -14_-60, -15_-63, -19_-65, -7_-64, -7_-65, -8_-64, -8_-65, -9_-66 | 12526 | 0.084 | 0.062 | 0.059 |

## Holdout temporal

| Modelo | MAE | RMSE | R² | skill vs. clim. |
|---|---|---|---|---|
| climatologia | 0.073 | 0.100 | -0.258 | 0.000 |
| ridge | 0.050 | 0.075 | 0.306 | 0.257 |
| xgboost | 0.049 | 0.072 | 0.355 | 0.284 |

## Cobertura da faixa de incerteza (split conformal, calibração em células distintas)

| Modelo | Meta | CV (média ponderada) | Holdout |
|---|---|---|---|
| climatologia | 80% | 0.789 | 0.763 |
| climatologia | 90% | 0.896 | 0.875 |
| ridge | 80% | 0.796 | 0.760 |
| ridge | 90% | 0.899 | 0.872 |
| xgboost | 80% | 0.797 | 0.758 |
| xgboost | 90% | 0.899 | 0.867 |

## Só clima × com persistência (lado a lado, holdout temporal)

so_clima_mesmas_linhas = modelo sem persistência avaliado nas MESMAS linhas do modelo com persistência (comparação justa); so_clima_todas_as_linhas = o modelo anterior, que mantém linhas sem composto anterior consecutivo. Cada skill é relativa à climatologia das PRÓPRIAS linhas.

| Configuração | n treino | n teste | RMSE clim. | RMSE Ridge | skill Ridge | RMSE XGB | skill XGB | skill CV Ridge | skill CV XGB |
|---|---|---|---|---|---|---|---|---|---|
| só clima (modelo anterior, todas as linhas) | 78015 | 10738 | 0.1080 | 0.1094 | -0.013 | 0.1055 | 0.023 | 0.063 | 0.103 |
| só clima (mesmas linhas da persistência) | 62318 | 8052 | 0.1004 | 0.1029 | -0.025 | 0.1001 | 0.003 | 0.066 | 0.101 |
| com persistência (produção) | 62318 | 8052 | 0.1004 | 0.0746 | 0.257 | 0.0719 | 0.284 | 0.278 | 0.309 |

Skill por ano do holdout (vs. climatologia do próprio conjunto):

| Configuração | Modelo | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| só clima (modelo anterior, todas as linhas) | ridge | 0.062 | -0.052 | -0.097 |
| só clima (modelo anterior, todas as linhas) | xgboost | 0.139 | -0.031 | -0.103 |
| só clima (mesmas linhas da persistência) | ridge | 0.071 | -0.075 | -0.112 |
| só clima (mesmas linhas da persistência) | xgboost | 0.134 | -0.054 | -0.120 |
| com persistência (produção) | ridge | 0.353 | 0.193 | 0.185 |
| com persistência (produção) | xgboost | 0.386 | 0.214 | 0.210 |

Cobertura conformal real no holdout (recalibrada por células como antes; **não ajustada**):

| Configuração | Modelo | 80% (real) | 90% (real) | CV 80% | CV 90% |
|---|---|---|---|---|---|
| só clima (modelo anterior, todas as linhas) | climatologia | 0.748 | 0.865 | 0.789 | 0.893 |
| só clima (modelo anterior, todas as linhas) | ridge | 0.701 | 0.826 | 0.792 | 0.894 |
| só clima (modelo anterior, todas as linhas) | xgboost | 0.701 | 0.826 | 0.794 | 0.893 |
| só clima (mesmas linhas da persistência) | climatologia | 0.763 | 0.875 | 0.789 | 0.896 |
| só clima (mesmas linhas da persistência) | ridge | 0.710 | 0.833 | 0.788 | 0.893 |
| só clima (mesmas linhas da persistência) | xgboost | 0.706 | 0.832 | 0.787 | 0.892 |
| com persistência (produção) | climatologia | 0.763 | 0.875 | 0.789 | 0.896 |
| com persistência (produção) | ridge | 0.760 | 0.872 | 0.796 | 0.899 |
| com persistência (produção) | xgboost | 0.758 | 0.867 | 0.797 | 0.899 |

## Decisão XGBoost vs. Ridge

**Modelo: xgboost.** XGBoost superou o Ridge nos três testes do critério.

- Critérios: {'media_folds_positiva': True, 'holdout_positivo': True, 'maioria_folds_positiva': True}
- Fração de folds com XGBoost melhor: 1.00
- Critério aprovado pelo usuário antes da avaliação com dados reais.

## Explicação (só explicativa, não valida)

- anom_lag1: 0.0386
- anom_lag2: 0.0122
- quinzena_sin: 0.0116
- chuva_ac_30d: 0.0110
- dias_secos_consecutivos: 0.0051
- chuva_ac_90d: 0.0037
- tmax_media_30d: 0.0030
- quinzena_cos: 0.0015
- chuva_ac_60d: 0.0011

## Sensibilidade a cenários, com e sem persistência (medida)

Base: períodos de treino (anos 2001–2021) com 2 compostos anteriores consecutivos. variacao = previsão sob cenário - previsão neutra (média das linhas-base, anomalia de NDVI). razão = variação com persistência / variação só-clima. Associação histórica, não causalidade.

As features de persistência não mudam sob cenário de chuva/temperatura: o ganho vem da memória do NDVI; cenários de clima reagem pouco.

| Modelo | Cenário (chuva x, tmax +°C) | linhas usadas / fora da faixa | variação com persistência | variação só clima | razão |
|---|---|---|---|---|---|
| ridge | x0.8, +0 | 62317 / 1 | -0.00192 | -0.00356 | 0.54 |
| ridge | x1.2, +0 | 62256 / 62 | 0.00191 | 0.00354 | 0.54 |
| ridge | x1, +1 | 61644 / 674 | -0.00223 | -0.00907 | 0.25 |
| xgboost | x0.8, +0 | 62317 / 1 | -0.00139 | -0.00447 | 0.31 |
| xgboost | x1.2, +0 | 62256 / 62 | 0.00124 | 0.00364 | 0.34 |
| xgboost | x1, +1 | 61644 / 674 | -0.00141 | -0.00805 | 0.18 |

## Lacunas

- 799 períodos de NDVI sem alguma feature (janela incompleta ou dado ausente); ficam fora do treino, não são preenchidos.
- Umidade do solo (SMAP) fora do modelo (desligada por padrão em `preditivo.usar_umidade_solo`, D52, ou ausente): modelo sem features de umidade.
- Cobertura conformal do holdout abaixo da meta em ridge: 80% (real 76.0%); 90% (real 87.2%). A faixa é calibrada em células do período de treino e não reproduz a cobertura nominal em outro período: NÃO deve ser lida como garantia nominal (não foi ajustada para 'bater' a meta).
- Cobertura conformal do holdout abaixo da meta em xgboost: 80% (real 75.8%); 90% (real 86.7%). A faixa é calibrada em células do período de treino e não reproduz a cobertura nominal em outro período: NÃO deve ser lida como garantia nominal (não foi ajustada para 'bater' a meta).
- Persistência: o ganho vem da memória do NDVI (autocorrelação), não do clima; cenários de chuva/temperatura reagem pouco. Linhas sem 2 compostos anteriores consecutivos (≤ 17 d) ficam fora do treino e do teste (não são preenchidas).
