# Relatório dos modelos (SULCO)

Alvo: anomalia_ndvi = NDVI - climatologia do slot (climatologia só dos anos de treino).

Treino 2001–2021; holdout [2022, 2023, 2024]; 13 células POWER no treino; 5 folds. Confiança: **baixa** (heurística: 'baixa' com menos de min_celulas_aviso células POWER distintas; não é probabilidade).

> O modelo captura associações históricas entre clima e NDVI; não é causalidade e não prevê o clima futuro nem a produtividade.

## Métricas por fold (GroupKFold por célula)

| Modelo | MAE | RMSE | R² | skill vs. clim. |
|---|---|---|---|---|
| climatologia | 0.034 ± 0.012 | 0.046 ± 0.018 | -0.000 ± 0.000 | 0.000 ± 0.000 |
| ridge | 0.032 ± 0.011 | 0.044 ± 0.016 | 0.063 ± 0.060 | 0.033 ± 0.031 |
| xgboost | 0.033 ± 0.010 | 0.045 ± 0.016 | 0.045 ± 0.084 | 0.023 ± 0.043 |

XGBoost vs. Ridge (skill): -0.009 ± 0.026

### Por fold

| Fold | Células validação | n | RMSE climatologia | RMSE ridge | RMSE xgboost |
|---|---|---|---|---|---|
| 1 | -10_-65, -16_-60, -21_-62 | 1191 | 0.074 | 0.070 | 0.069 |
| 2 | -10_-62, -14_-60, -19_-65 | 1199 | 0.052 | 0.050 | 0.050 |
| 3 | -14_-66, -21_-64, -23_-67 | 1186 | 0.040 | 0.039 | 0.041 |
| 4 | -15_-65, -16_-61 | 857 | 0.035 | 0.033 | 0.034 |
| 5 | -10_-60, -14_-61 | 864 | 0.029 | 0.029 | 0.030 |

## Holdout temporal

| Modelo | MAE | RMSE | R² | skill vs. clim. |
|---|---|---|---|---|
| climatologia | 0.034 | 0.051 | -0.003 | 0.000 |
| ridge | 0.035 | 0.052 | -0.046 | -0.021 |
| xgboost | 0.035 | 0.052 | -0.038 | -0.017 |

## Cobertura da faixa de incerteza (split conformal, calibração em células distintas)

| Modelo | Meta | CV (média ponderada) | Holdout |
|---|---|---|---|
| climatologia | 80% | 0.746 | 0.750 |
| climatologia | 90% | 0.833 | 0.834 |
| ridge | 80% | 0.721 | 0.710 |
| ridge | 90% | 0.818 | 0.812 |
| xgboost | 80% | 0.722 | 0.716 |
| xgboost | 90% | 0.817 | 0.810 |

## Decisão XGBoost vs. Ridge

**Modelo: ridge.** XGBoost não superou o Ridge de forma consistente (media_folds_positiva, maioria_folds_positiva); mantém-se o Ridge, mais simples.

- Critérios: {'media_folds_positiva': False, 'holdout_positivo': True, 'maioria_folds_positiva': False}
- Fração de folds com XGBoost melhor: 0.40
- **Atenção:** O modelo escolhido (ridge) NÃO supera a climatologia no holdout; a previsão de anomalia não agrega valor sobre a média histórica.
- Critério aprovado pelo usuário antes da avaliação com dados reais.

## Explicação (só explicativa, não valida)

- quinzena_sin: 0.0084
- chuva_ac_30d: 0.0066
- chuva_ac_90d: 0.0063
- tmax_media_30d: 0.0045
- quinzena_cos: 0.0044
- chuva_ac_60d: 0.0014
- dias_secos_consecutivos: 0.0009

## Leitura dos resultados (2026-11-11, dados reais POWER 2001–2024 + MODIS MOD13Q1)

1. **Ganho pequeno na validação por célula, nenhum no holdout.** O Ridge reduz o RMSE em ~3% sobre a climatologia na média
   dos folds (0,044 vs. 0,046), mas no holdout temporal (2022–2024) fica 2% *pior* (skill −0,021). O XGBoost segue o mesmo
   padrão e não supera o Ridge. A decisão automática é **Ridge**, e o próprio relatório avisa que ele não supera a climatologia
   no holdout. Conclusão: com estes dados, a previsão de anomalia de NDVI **não agrega valor comprovado** sobre a média histórica.
2. **A faixa de incerteza cobre menos do que promete.** Metas 80% e 90% deram ~72% e ~81% (CV) e 71% e 81% (holdout). A
   calibração em células separadas não transfere bem: o erro varia muito entre células (RMSE de 0,029 a 0,074 por fold).
   Não use essas faixas como se fossem 80/90%; trate-as como subestimadas.
3. **Poucos dados independentes.** 13 células POWER (< 15): o tamanho efetivo da amostra é ~13; o holdout tem só 3 anos.
4. **Sinal climático fraco nas explicações.** As contribuições de chuva acumulada e sazonalidade são pequenas
   (≤ 0,008 de anomalia). Isto descreve o modelo, não prova causalidade.
5. **Cobertura dos dados.** NDVI de 7.173 composições (13 pontos); confiabilidade 0: 65%, 1: 19%, 3 (nuvem): 15%. Senhor do
   Bonfim tem só 14 anos válidos de NDVI (confiança "baixa" no diagnóstico).

**O que isso significa para o SULCO:** o diagnóstico descritivo (sazonalidade, solo nu, veranicos, tendências) é utilizável com
as ressalvas de confiança; o módulo de cenários não deve apresentar o número previsto como resultado confiável.
Próximos passos possíveis: mais pontos em células distintas, umidade do solo (SMAP), conformal por célula/tipo de região,
e revisar o alvo (anomalia de NDVI pode ter ruído de nuvem).

## Walk-forward (2026-11-11) — ver `docs/05_EXPERIMENTOS.md`
Com validação ano a ano (seleção 2010–2021, confirmação selada 2022–2024) nos 13 pontos: a base atual dá skill +0,058 (confirmação −0,021),
enquanto a **persistência da anomalia** dá +0,228 (confirmação +0,105), validada com placebo e correção por variantes. O clima acrescenta
só ~+0,014 sobre um modelo apenas de persistência. Janelas de chuva longas, alvo normalizado e novas features de clima não validaram.
Nota: o holdout fixo de 3 anos acima (−0,021) concorda com a confirmação da base; a base só é positiva em média nos 12 anos de seleção.

## Lacunas

- Apenas 13 células POWER distintas (< 15): o tamanho efetivo da amostra é o número de células, não de pontos; métricas têm pouca força estatística.
- 70 períodos de NDVI sem alguma feature (janela incompleta ou dado ausente); ficam fora do treino, não são preenchidos.
- Umidade do solo (SMAP) ausente: modelo sem features de umidade.
