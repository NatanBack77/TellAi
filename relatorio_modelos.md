# Relatório dos modelos (SULCO)

**Status: ainda sem resultados.** Não há dados reais (POWER, MODIS, SMAP) no repositório; todo o desenvolvimento
usou dados `SINTETICO_*`, cujas métricas não são resultado do projeto e por isso não aparecem aqui.

Quando existirem `data/processed/{clima_diario,ndvi_16d}.parquet`:

```
.venv/Scripts/python -m src.modelos.preditivo      # grava metricas.json e este relatório, já preenchido
```

O relatório gerado traz: métricas por fold (média e desvio) e no holdout temporal, baselines (climatologia e Ridge),
cobertura conformal a 80% e 90%, decisão XGBoost vs. Ridge, explicação (só explicativa) e lacunas.

Critério da decisão XGBoost vs. Ridge aprovado pelo usuário em 2026-11-11 (ver `docs/03_SUPOSICOES_E_DECISOES.md`, D31).
