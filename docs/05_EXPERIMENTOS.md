# Experimentos de melhoria do modelo preditivo (walk-forward)

Atualizado em 2026-11-11. Objetivo: achar melhorias **reais** (não overfitting) na previsão da anomalia de NDVI.

## 1. Protocolo (`src/modelos/walkforward.py`, `tests/test_walkforward.py`)
- **Walk-forward**: ano de teste Y → treino só com anos < Y; climatologia do alvo só com anos < Y.
- **Mesmas linhas de teste** para todas as variantes (interseção); senão uma variante que descarta linhas difíceis parece melhor.
- **Métricas na escala original** da anomalia (alvo normalizado é convertido de volta antes do RMSE).
- **Seleção** (2010–2021) decide; **confirmação selada** (2022–2024) só é olhada no fim, uma vez, para finalistas.
- **Bonferroni**: limite inferior do IC bootstrap (sobre anos) usa alpha/N, N = nº TOTAL de variantes testadas (inclusive as descartadas).
- **Placebo** (`placebo=True`): embaralha as features entre anos dentro de (ponto, slot). A skill tem de ficar ≤ 0; se não, há vazamento.
- **Melhoria válida** = skill vs. climatologia > 0 com IC corrigido > 0, ≥ 60% dos anos positivos, melhor que a base pareado por ano
  (IC corrigido > 0) e skill > 0 na confirmação.
- Skill = 1 − RMSE_modelo / RMSE_climatologia. Hiperparâmetros nunca ajustados olhando o teste.

Rodar: `python -m src.modelos.walkforward --dados <pasta com clima_diario.parquet e ndvi_16d.parquet> --variantes base,persistencia [--placebo]`.
Variantes registradas em `VARIANTES`: `base`, `persistencia`, `so_persistencia`, `janelas_longas`, `alvo_z`, `persistencia_z`.

## 2. Resultados (13 pontos do instantâneo `experimentos/dados13/`, 2001–2024)
Seleção 2010–2021 (12 anos) / confirmação 2022–2024. Skill sobre a climatologia; modelo Ridge salvo indicação.

| Variante | Skill seleção | Confirmação | Veredito |
|---|---|---|---|
| base (features atuais) | +0,058 | −0,021 | não confirma |
| **persistencia** (anomalia dos 2 compostos anteriores) | **+0,228** | **+0,105** | **válida** (positiva em 15/15 anos) |
| so_persistencia (sem clima) | +0,214 | +0,099 | mostra que o clima acrescenta só ~+0,014 |
| janelas_longas (120/180 d) | +0,087 | −0,035 | reprovada na confirmação |
| alvo_z (alvo normalizado) | +0,052 | −0,037 | sem ganho |
| ingênua (repetir última anomalia) | +0,110 | −0,123 | pior que o modelo; negativa nos anos recentes |
| placebo (base e persistencia) | ≈ 0 ou < 0 | — | pipeline não vaza futuro |

**Leitura honesta:** o ganho real vem da *memória* do NDVI (persistência), não da resposta ao clima. Consequência: o módulo de
cenários (fator de chuva) reage pouco com o modelo com persistência. Isso precisa ficar explícito ao usar cenários.

### Agente de features (16 variantes, dados dos 13 pontos, só 2010–2021, N=16)
Scripts: `experimentos/expC_features/`. Só **`pers_lags4`** (lags 1–4 da anomalia, Ridge) passou: +0,024 sobre a persistência
(IC corrigido +0,012; melhor em 12/12 anos; placebo ≈ 0). **Ainda não passou pela confirmação selada.**
Não passaram: anomalia de chuva, SPI simplificado, eventos de chuva, térmica (tmin/radiação), déficit hídrico (Hargreaves-Samani),
interações sazonais, XGBoost monotônico; XGBoost empatou ou perdeu para o Ridge em todas. Sem persistência, `clima_anom`
melhora a base em ~+0,02 (por pouco, só Ridge). O Bonferroni com 16 variantes e 12 anos é muito conservador: ausência de
achados em clima não prova inutilidade.

### Agentes interrompidos (sem resultado)
- **CHIRPS** (`experimentos/expA_chirps/`): ClimateSERV (datatype 0), cache parcial (175 de ~312 arquivos ponto-ano). Nenhum resultado.
- **EVI/SAVI** (`experimentos/expB_indices/`): ORNL DAAC bandas EVI/vermelho/NIR, cache parcial (~980 arquivos). Nenhum resultado.
Ambos foram parados a pedido do usuário. Para retomar: rodar `baixar.py` (idempotente), depois `exp.py` / `montar.py` + `rodar.py`,
seguindo o protocolo (só 2010–2021; N total; placebo; confirmação selada só no fim).

## 3. Dados
| Dado | Estado |
|---|---|
| Clima POWER | **59 pontos / 59 células**, 2001–2024, 517.194 linhas, 0 ausentes (`data/processed/clima_diario.parquet`) |
| NDVI MODIS (ORNL) | cache em `data/raw/modis_ornl/`: **34 de 59 pontos completos**, 1 parcial (jaguaribe_ce, 48/112 janelas), 24 sem nada (3.856 de 6.608 janelas, 58%) |
| `data/processed/ndvi_16d.parquet` | ainda só os **13 pontos antigos** (7.173 linhas); o completo é gravado quando a coleta terminar |
| Pontos do Ceará | 1 município por célula POWER; centroide IBGE (API v1 + malhas v3); arquivos em `experimentos/ceara_selecao/` |
| SMAP | não iniciado |

## 4. Próximos passos (ordem)
1. Terminar o NDVI: `python -m src.coleta.modis_ornl --workers 16` (~35–60 min; retoma do cache). Grava `ndvi_16d.parquet` com os 59 pontos.
2. Reavaliar com 59 células: `python -m src.modelos.walkforward --variantes base,persistencia,so_persistencia` e as variantes de `expC.py` (importar `pers_lags4`).
3. **Confirmação selada** (2022–2024) para finalistas (`pers_lags4`, `persistencia`); o `resumir` já a incorpora.
4. Rodar `src.modelos.preditivo` (conformal etc.) com 59 células; a confiança deixa de ser "baixa" (≥ 15 células).
5. Se valer a pena: CHIRPS, EVI/SAVI, filtro de uso do solo (MapBiomas), SMAP, pluviômetros FUNCEME (sem API oficial confirmada).
6. Passar a persistência para `preditivo.py` e `cenarios.py` (e documentar a limitação dos cenários) só depois da confirmação.

## 5. Ideias pesquisadas (fontes)
Defasagem de 2–3 meses da resposta da caatinga à chuva (estudos com Meteosat-SEVIRI e TRMM); SAVI pode ser melhor que NDVI na caatinga
(estudo na Paraíba); CHIRPS via ClimateSERV (pacote rOpenSci `chirps`); SPL4SMGP v8 pelo AppEEARS (série desde 31/03/2015;
nomes das camadas a conferir); rede de ~500 pluviômetros da FUNCEME (sem documentação oficial de API encontrada).

## 6. Atualização (2026-11-11, noite)
- **CHIRPS: concluído, sem ganho.** 13 pontos, seleção 2010–2021, N=6 variantes, placebo ≈ 0. Melhor variante (`pers_power_chirps`) +0,0012 sobre a persistência
  (IC inferior −0,0019, não passa); trocar POWER por CHIRPS piora (−0,0103). Confirmação selada não aberta. Detalhes: `experimentos/expA_chirps/RESULTADO.md`.
  Conclusão: "sem evidência de ganho" (pouco poder), não prova que a chuva não importa.
- **SMAP coletado** (195 pontos, 2015–2024) mas **ainda não testado como feature**. Série curta (desde 2015): poucos anos de seleção.
- **Avaliação com 195 pontos pendente** (depende do `ndvi_16d.parquet` completo). Ver `docs/04_RETOMADA.md`, seção 5.
- EVI/SAVI segue sem resultado.
