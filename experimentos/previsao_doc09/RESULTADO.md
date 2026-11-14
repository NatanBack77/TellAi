# Testes de previsão do doc 09: horizonte/estação (M1) e ERA5 (M3): estado em 2026-11-13

**Status: INCOMPLETO. Nenhuma confirmação selada foi aberta (2022–2024 intocados). Os placebos não terminaram. Nada aqui deve ser lido como "o clima ajuda" ou "o ERA5 ajuda".**
Escrito pelo assistente principal a partir dos arquivos que existem em disco (`t1_linhas_resumo.csv`, `t3_rodar.log`, `t3_res.pkl`); o agente que fez os testes foi interrompido a pedido do usuário antes de escrever o relatório. Nada foi completado de memória.
Protocolo: `docs/05_EXPERIMENTOS.md` (só 2010–2021 decide; 2022–2024 selados; placebo; Bonferroni com N total).

## M1: habilidade por horizonte e estação (T1; 195 pontos; seleção 2010–2021)
Script `t1_horizonte.py`, resumo `t1_resumo.py` → `t1_linhas_resumo.csv` (linhas `t1_linhas.pkl`, 46 MB, ignorado pelo git). Skill média por ano contra a climatologia. Estação: chuvosa = fev–mai; resto = jun–jan.

| Horizonte | Estação | base (só clima) | persistência | pers_lags4 | só lags (sem clima) |
|---|---|---|---|---|---|
| +1 | chuvosa | 0,078 | 0,218 | 0,216 | 0,191 |
| +1 | resto | 0,055 | 0,329 | 0,332 | 0,323 |
| +1 | todas | 0,066 | 0,309 | 0,311 | 0,296 |
| +2 | todas | 0,050 | 0,191 | 0,191 | 0,181 |
| +3 | todas | 0,040 | 0,127 | 0,128 | 0,120 |
| +4 | todas | 0,033 | 0,090 | 0,092 | 0,085 |

**O que o clima acrescenta** (pers_lags4 menos só lags; IC 95% bootstrap sobre anos, **sem correção de Bonferroni**):
| Horizonte | Todas | Estação chuvosa | Resto do ano |
|---|---|---|---|
| +1 | +0,015 [0,009; 0,021], 11/12 anos | +0,025 [0,012; 0,039], 11/12 | +0,009 [0,004; 0,015], 9/12 |
| +2 | +0,011 [0,005; 0,018] | +0,018 [0,005; 0,032] | +0,005 [−0,001; 0,011] |
| +3 | +0,008 [0,002; 0,015] | +0,008 [−0,008; 0,022] | +0,004 [−0,003; 0,011] |
| +4 | +0,007 [−0,000; 0,016] | +0,005 [−0,011; 0,022] | +0,003 [−0,005; 0,012] |

Leitura (descritiva): a skill da persistência cai de 0,31 (+1) para 0,09 (+4). O clima acrescenta pouco em qualquer horizonte; o maior acréscimo está na estação chuvosa a +1 e +2 (+0,025 e +0,018), e some (IC inclui zero) a +3/+4. Isso concorda com o teste prospectivo (`experimentos/prospectivo_2025/RESULTADO.md`: +0,254 a +1 e +0,065 a +4).
**Limites:** o placebo de T1 NÃO terminou (`t1_placebo.log` só tem "h 1 118416"); os ICs não têm correção de múltiplas comparações; é descritivo, não uma variante candidata.

## M3: fonte nova de chuva/umidade (T3; ERA5 via Open-Meteo; 30 pontos)
- **Acesso:** API Histórica do Open-Meteo (`https://archive-api.open-meteo.com/v1/archive`), sem chave nem cadastro. Umidade do solo em 3 camadas (0–7, 7–28, 28–100 cm; média diária, m³/m³) do ERA5-Land a 0,1°. Chuva: `models=era5`, `precipitation_sum`, 0,25°. Segundo o comentário do script (a conferir na doc do Open-Meteo, que eu não reabri), o ERA5-Land não fornece precipitação; a chuva é o próprio forçante ERA5.
- **Cota:** plano gratuito 10.000 unidades/dia (script limita a 4.000/h). Gasto nas últimas 24 h: 7.812 unidades (262 chamadas ok, 158 do cache). Cache em `data/raw/era5land/` (420 arquivos, 13 MB; versionado como `data/raw/era5land_cache.tar.gz`, extrair com `tar xzf data/raw/era5land_cache.tar.gz -C data/raw`), blocos de 3 anos entre 2001 e 2021 (14 por ponto).
- **Cobertura:** só **30 pontos** (subconjunto em `t3_pontos_subconjunto.csv`) de 191 células ERA5-Land distintas dos 195 pontos. O teste tem poder baixo.
- **Resultado (seleção 2010–2021, base `pers_lags4_c`, N Bonferroni = 57, SEM placebo):**
| Variante | Modelo | Skill | Ganho vs base | IC inferior do ganho (corrigido) |
|---|---|---|---|---|
| era_chuva_sm12 | xgboost | 0,3226 | +0,0085 | −0,0149 |
| era_chuva_sm12 | ridge | 0,3222 | +0,0081 | −0,0017 |
| era_chuva_sm123 | ridge | 0,3221 | +0,0080 | −0,0016 |
| era_chuva | xgboost | 0,3216 | +0,0075 | −0,0151 |
| era_spi3 | xgboost | 0,3198 | +0,0057 | −0,0144 |
| era_chuva | ridge | 0,3176 | +0,0035 | −0,0024 |
**Nenhuma variante passa** (todos os ICs inferiores corrigidos são ≤ 0). Os ganhos de +0,004 a +0,009 são pequenos.
- **Não feito:** placebo de T3 (`t3_rodar_placebo.log` só tem a linha de cobertura), confirmação selada, extensão a mais pontos. Resultado: **sem evidência**, com poder baixo e sem placebo; não prova ausência de efeito.
- **M6 (EVI/SAVI):** não iniciado.

## Como retomar
```
cd experimentos/previsao_doc09
../../.venv/bin/python t3_baixar.py --n 40 --tipos solo,chuva      # idempotente; respeita a cota (ver t3_ledger.jsonl); aceita --primeiros k
../../.venv/bin/python t3_rodar.py --N 57                           # seleção sem placebo (grava t3_res.pkl)
../../.venv/bin/python t3_rodar.py placebo --N 57                   # placebo: o ganho deve ficar <= 0
../../.venv/bin/python t1_horizonte.py [placebo] [--h 1,2,3,4]      # gera t1_linhas.pkl; depois: python t1_resumo.py t1_linhas.pkl
```
Antes de rodar, conferir os argumentos exatos nos próprios scripts (`argparse` de `t3_baixar.py`, `sys.argv` dos demais). Cada rodada de walk-forward pesa ~1–2 GB de RAM e leva 10–20 min. Arquivos ignorados pelo git: `t1_linhas.pkl` (46 MB), `*.pkl`. O `N` do Bonferroni deve continuar contando as variantes já testadas em `avaliacao_195`, `novas_fontes`, `ensemble`, `conformal_A1` e `soilgrids` (42 no último, mais as 15 de T3 = 57).

## Lacunas e riscos
- Só 30 pontos no ERA5; chuva a 0,25° não é 0,1°; Open-Meteo é serviço de terceiros com cota diária.
- ICs de T1 sem correção de múltiplas comparações e sem placebo.
- Se o resultado de T3 for retomado, só vale com placebo ≤ 0, IC corrigido > 0 e confirmação selada aberta UMA vez.
