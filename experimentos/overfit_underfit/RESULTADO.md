# Diagnóstico de overfitting e underfitting (2026-11-13)

Script: `diagnostico.py`. Só anos de seleção (2010–2021); 2022–2024 intocados. Modelo: anomalia de NDVI com persistência, 195 pontos.
CSVs: `t1_lacuna.csv`, `t2_curva_aprendizado.csv`, `t3_complexidade.csv`, `t4_residuos_por_ano.csv`, `t5_espacial.csv`.

1. **Lacuna treino × teste (walk-forward, média 2010–2021):** ridge treino 0,0620 / teste 0,0710 (razão 1,15); xgboost 0,0579 / 0,0693 (1,20);
   climatologia no teste 0,1013. Lacuna pequena. Ressalva: a anomalia do treino usa climatologia com os próprios anos (otimista).
2. **Curva de aprendizado (teste 2018 e 2021):** RMSE de teste estável de 4 a 20 anos de treino (ridge 0,067–0,074; xgb 0,067–0,073). Platô: mais dados não ajudam.
3. **Complexidade do XGBoost (média de 2012, 2015, 2018, 2021):** mínimo de teste 0,0667 (400 árvores, profundidade 3); produção (200, 3) = 0,0671.
   Subajuste: profundidade 1 com 25 árvores → treino 0,0728 / teste 0,0851. Superajuste: profundidade 6 com 800 árvores → treino 0,0453 / teste 0,0685.
   **Ridge:** teste 0,0684 para alpha de 0,001 a 100 (regularização irrelevante); 0,0709 só com alpha 10⁴ (subajuste).
4. **Resíduos (XGBoost, 2012–2021):** viés médio −0,0022; autocorrelação lag-1 por ponto 0,019 (≈ 0). Viés por ano de −0,016 (2012) a +0,013 (2020):
   choques de ano inteiro não capturados (mesma causa da cobertura do conformal abaixo da meta). R² por faixa de estação: 0,41 / 0,56 / 0,68 / 0,43.
5. **Células nunca vistas (GroupKFold por célula, 2001–2021; mistura tempo, otimista):** skill ridge +0,279; xgboost +0,310.

**Conclusão:** sem evidência de overfitting ou underfitting relevantes; os parâmetros de produção estão no fundo plano da curva; o erro restante é de
choques climáticos de ano inteiro. Só informação nova (solo, chuva melhor, indicador de seca) deveria reduzi-lo. Nenhuma mudança no modelo.
