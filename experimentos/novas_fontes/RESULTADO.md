# Novas fontes e limites do escopo (2026-11-13)

Scripts: `features_wf.py`, `ndvi_vs_pam.py`. Dados: SRTM (`terreno.parquet`), SIDRA/PAM (`pam_ce.parquet`), índices NOAA PSL (`data/raw/indices/`).

## 1. Terreno e índices climáticos como features da anomalia de NDVI (walk-forward 2010–2021, base = persistência, 195 pontos)
N de comparações para o Bonferroni = 8. Diferença de skill sobre a base (ganho pareado, ic inferior corrigido):
| Variante | Ridge | XGBoost |
|---|---|---|
| + terreno (altitude, declive médio e p90 em 1 km) | 0,000 (ic −0,000) | −0,001 (ic +0,005) |
| + índices (Niño 3.4, TNA, TSA, dipolo; média dos 3 meses anteriores) | 0,000 (ic −0,005) | −0,001 (ic −0,018) |
| + ambos | 0,000 (ic −0,005) | −0,003 (ic −0,020) |
**Nenhuma melhora.** A persistência já carrega o estado da vegetação; terreno é estático e os índices não agregam ao NDVI. Confirmação selada NÃO rodada
(nenhuma variante passou na seleção).

## 2. Índices do Pacífico e do Atlântico antecipam a chuva de fev–mai? (24 anos, média dos 195 pontos)
Chuva regional fev–mai: média 593 mm, desvio 170 mm (CV 0,29). Índices de out–jan (antes da quadra) e nov–jan: correlação com a chuva
de −0,24 a +0,03 (nenhuma significativa, p ≥ 0,26); regressão linear leave-one-year-out com dipolo (TNA−TSA) e Niño 3.4: RMSE 186 mm contra 178 mm da
climatologia (skill −0,05). **Não há previsibilidade detectável neste lead com 24 anos.** Só duas janelas foram testadas (sem varredura). A literatura
aponta o Atlântico tropical como principal motor do Ceará, mas a previsão sazonal operacional (FUNCEME) usa modelos dinâmicos e estatísticos próprios:
o app deve apontar para ela, não reproduzi-la.

## 3. O NDVI acompanha a produtividade municipal (PAM/IBGE, rendimento kg/ha, 2015–2023)?
Anomalia do rendimento (% do próprio município) contra anomalia do NDVI de pico (jan–jul) e da chuva de fev–mai, pooled município-ano.
| Cultura | n mun. | NDVI: r (R²) | Chuva fev–mai: r (R²) |
|---|---|---|---|
| Milho | 182 | 0,32 (0,10) | **0,56 (0,31)** |
| Feijão | 182 | 0,22 (0,05) | 0,36 (0,13) |
| Mandioca | 168 | 0,29 (0,09) | 0,43 (0,18) |
| Algodão herbáceo | 34 | 0,19 (0,04) | 0,26 (0,07) |
| Arroz | 65 | 0,18 (0,03) | 0,43 (0,19) |
**O NDVI explica pouco da produtividade (R² 0,03–0,10) e a chuva da quadra explica mais** em todas as culturas, exceto melancia. Por isso o NDVI
não deve ser apresentado como indicador de produtividade, e o app deve usar a chuva da estação como indicador de risco. Ressalvas: rendimento do
PAM é estimado por agentes do IBGE (não medido); 1 ponto por município; no máximo 9 anos por município.
