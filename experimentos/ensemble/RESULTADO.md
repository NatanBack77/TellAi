# Outros algoritmos e ensembles (2026-11-13)

Script: `ensemble_wf.py`. Anomalia de NDVI com persistência (mesmas features de produção), 195 pontos, walk-forward 1 ano à frente.
Hiperparâmetros FIXOS a priori (no script). 12 candidatos (N=12 no Bonferroni): ridge, xgboost, hgb (HistGradientBoosting), rf, et, enet, mlp,
médias simples (e_rx, e_rxh, e_arvores, e_todos) e stack NNLS (pesos calibrados só nos 3 anos de treino anteriores a Y). Mesmas linhas de teste.

## Seleção 2010–2021 (skill sobre a climatologia; base = ridge, skill 0,291)
| Modelo | Skill | Ganho vs ridge | IC inf. corrigido do ganho |
|---|---|---|---|
| e_rxh (ridge+xgb+hgb) | 0,309 | +0,018 | +0,010 |
| xgboost | 0,308 | +0,017 | +0,006 |
| stack_nnls | 0,308 | +0,017 | +0,008 |
| hgb | 0,307 | +0,015 | +0,002 |
| e_todos / e_rx / mlp | 0,306 | +0,015 | +0,004 a +0,010 |
| e_arvores, rf, enet, et | 0,283–0,304 | −0,008 a +0,013 | ≤ 0 (não passam) |

## Confirmação selada 2022–2024 (finalistas fixados antes: e_rxh, e_rx, stack_nnls, xgboost)
| Modelo | Skill | Ganho vs ridge |
|---|---|---|
| ridge | 0,230 | — |
| e_rx | 0,249 | +0,019 |
| e_rxh | 0,253 | +0,024 |
| stack_nnls | 0,258 | +0,028 |
| xgboost | 0,258 | +0,028 |

## Leitura
- Todos os finalistas melhoram o Ridge e confirmam fora da amostra de seleção, mas o ganho é pequeno (RMSE ~3% menor).
- **Nenhum ensemble supera o XGBoost sozinho**: o stack empata (+0,0001) e as médias simples ficam abaixo. A produção já usa XGBoost
  (decisão automática), então ensemble não acrescenta nada útil e custa mais complexidade. Sem evidência para trocar.
- Variabilidade: a skill da confirmação é menor que a da seleção em todos os modelos (anos 2022–2024 mais difíceis); o ranking se mantém.
- Teto: o ganho vem da persistência; algoritmos mais ricos extraem ~+0,02 a +0,03 a mais. Não há salto.
