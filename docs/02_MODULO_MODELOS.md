# Módulo `src/modelos/` — séries temporais e modelo preditivo

Escopo: **apenas** diagnóstico, preditivo e sensibilidade a cenários. Motor de cenários, RAG e LLM
consomem as saídas deste módulo. Nenhum código acessa a internet em tempo de execução.

## Entradas (Parquet, baixadas por outra etapa)
- `clima_diario.parquet`: ponto_id, celula_power, data, chuva_mm, tmax_c, tmin_c, radiacao (POWER ~50 km)
- `ndvi_16d.parquet`: ponto_id, data, ndvi, confiabilidade (MOD13Q1 250 m, 16 dias)
- `umidade_solo.parquet` (opcional): ponto_id, data, sm_superficie, sm_raiz (SMAP L4 ~9 km)

Se faltar arquivo ou coluna: **parar e pedir**. Não inventar nem preencher em silêncio.

## Módulo 1 — Diagnóstico por local (`diagnostico.py`)
1. STL do NDVI (período = 23 obs/ano); interpolação limitada com marcação; descarte de baixa confiabilidade.
2. Climatologia por quinzena + z-score de NDVI, chuva acumulada e umidade do solo (se houver).
3. Janelas de solo nu: NDVI < limiar configurável (padrão: percentil 20 do ponto; limiar fixo em `config.yaml`);
   saída = quinzenas típicas + frequência (em quantos anos ocorreu).
4. Tendência: Theil-Sen + Mann-Kendall em chuva anual, temperatura e NDVI de pico.
5. Veranicos: maior sequência de dias com chuva < 1 mm por estação chuvosa + distribuição.
6. Toda saída: `n_anos_validos`, `lacunas`, `confianca`.
Proibido: Prophet, ARIMA, LSTM, modelos de fundação.

## Módulo 2 — Preditivo (`features.py`, `preditivo.py`)
- **Alvo:** anomalia de NDVI no período t.
- **Features:** chuva acumulada 30/60/90 d, tmax média, dias secos consecutivos, quinzena e, por padrão (D52),
  **persistência** = anomalia dos 2 compostos anteriores do ponto (`anom_lag1/2`, só se consecutivos ≤ 17 d; a MESMA função
  validada em `walkforward.py`; lag ausente => linha fora, nunca preenchida). Umidade do solo (SMAP) é opção desligada
  (`preditivo.usar_umidade_solo`). Latitude/longitude **não** entram.
- **Opções (config.yaml `preditivo`):** `usar_persistencia` (padrão true; false = só-clima, comportamento anterior),
  `persistencia_max_gap_dias` (17), `usar_umidade_solo` (false). CLI: `--sem-persistencia`, `--com-smap`.
- **Relatório:** traz as duas linhas lado a lado (só clima em todas as linhas, só clima nas mesmas linhas, com persistência),
  skill por ano do holdout e cobertura conformal real. O ganho vem da memória do NDVI, não do clima.
- **Comparação obrigatória:** climatologia (anomalia = 0), Ridge (mesmas features), XGBoost.
  XGBoost só permanece se superar o Ridge de forma consistente; senão usa-se o Ridge e isso é reportado.
- **Validação sem vazamento:** `GroupKFold` por `celula_power` + holdout temporal (treino até N-3, teste nos últimos 3 anos).
  CV aleatória proibida. Hiperparâmetros nunca ajustados olhando o teste.
- **Métricas:** MAE, RMSE, R², skill = 1 − RMSE_modelo/RMSE_baseline; média e desvio por fold.
- **Incerteza:** split conformal (treino/calibração/teste em grupos distintos); cobertura empírica vs. metas 80% e 90%.
- **SHAP:** só explicativo, nunca validação.
- **Aviso:** < ~15 células POWER distintas => amostra efetiva = nº de células.

## Módulo 3 — Sensibilidade a cenários (`cenarios.py`)
- Entrada: fatores (ex.: chuva ×0,8). Saída: anomalia de NDVI prevista + faixa de incerteza.
- Fora da faixa vista no treino: aviso "extrapolação não confiável", sem número.
- Mensagem obrigatória: o modelo captura associações históricas, não causalidade, e não prevê o clima futuro.
- Com persistência (D52): `anom_lag1/2` não mudam sob cenário (são NDVI observado); `limites` declara que o ganho vem da memória
  do NDVI e que cenários de clima reagem pouco; a faixa de `anom_lag*` entra na regra de extrapolação.
  `cenarios.sensibilidade_comparada` mede a variação do cenário com e sem persistência nas mesmas linhas (número de código, no relatório).

## Não fazer
Prever chuva/temperatura futuras; prometer que rotação "rende mais"; tratar NDVI como produtividade;
reportar métricas de dados sintéticos; ajustar hiperparâmetros no teste; CV aleatória; esconder falhas de dados.

## Dados sintéticos
Só para testar formato/fluxo. Arquivo com `SINTETICO` no nome. Métricas deles **nunca** entram como resultado.

## Entregáveis
`src/modelos/{diagnostico,features,preditivo,cenarios}.py`, `config.yaml`, `tests/` (formato das saídas,
ausência de vazamento entre grupos, baseline reproduzível, aviso de extrapolação), `relatorio_modelos.md`
(métricas por fold, baselines, cobertura, lacunas, decisão XGBoost vs. Ridge), sementes fixas, `requirements.txt` com versões.

## Plano de execução (passos pequenos, testes a cada passo)
1. Esqueleto: `config.yaml`, `requirements.txt`, sementes.
2. Gerador `SINTETICO_*` (só formato/fluxo).
3. Validador de entrada (falha explícita).
4. `diagnostico.py` + testes.
5. `features.py` + teste de vazamento temporal.
6. `preditivo.py`: baselines, GroupKFold, holdout, métricas.
7. Conformal + cobertura.
8. XGBoost vs. Ridge e decisão.
9. SHAP.
10. `cenarios.py` + teste de extrapolação.
11. Testes de vazamento entre grupos e reprodutibilidade.
12. `relatorio_modelos.md`.

## Referências a conferir antes de usar
statsmodels STL, scikit-learn GroupKFold, xgboost, scipy.stats.theilslopes, pymannkendall, shap;
POWER daily API; MODIS MOD13Q1; NSIDC SPL4SMGP. Se algo não conferir: avisar e seguir a documentação oficial.
