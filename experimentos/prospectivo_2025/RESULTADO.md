# Teste prospectivo 2025+ do modelo de previsao de NDVI (2026-11-13)

Todos os numeros vieram de codigo rodado nesta sessao (`coletar.py`, `prospectivo.py`, `figuras.py`, `extras.py`, nesta pasta; saidas em `resultados.json`, `extras.json` e CSVs).
`src/` nao foi alterado. Nada foi ajustado, escolhido ou retreinado com dados de 2025+. Sem commit/push.

## 1. Dados coletados (so lacunas e fatos observados)
- **NDVI** `data/processed/ndvi_2025plus.parquet` (cache `data/raw/modis_ornl_2025plus/`, 1.950 janelas, funcoes de `src/coleta/modis_ornl.py`): 8.190 linhas = 195 pontos x 42 compostos, **de 2025-01-01 a 2026-10-16**
  (a lista de datas do ORNL termina em A2026289 = 2026-10-16; o composto de 2026-11-01 nao constava em 2026-11-13). Nenhuma linha faltando (no treino faltavam 57 em 2005).
  Confiabilidade: 0 = 4.805; 1 = 1.840; 3 = 1.544; NaN = 1. Aceitas (0 e 1, como no treino): 81,1% (treino 83,2%). NDVI NaN: 1 linha. Nada preenchido.
- **Clima** `data/processed/clima_2025plus.parquet` (cache `data/raw/power_2025plus/`): 195 x 682 dias, 2025-01-01 a 2026-11-13, mas **chuva e tmax so tem valor ate 2026-11-10** (os 3 ultimos dias vem NaN; radiacao NaN nos ultimos 11 dias; radiacao nao e feature). Sem buraco interno. Os dias mais recentes do POWER podem ser provisorios (hipotese, nao verificada).
- Linhas de NDVI valido 2025+: 6.645. Testaveis (anomalia com clima <= 2024 + 2 compostos anteriores consecutivos validos): **5.147** (195 pontos, 42 datas). Perdidas: 893 sem lag1 (composto anterior invalido ou ausente) + 605 com lag1 e sem lag2 = 1.498. Zero perdas por clima ou por slot sem climatologia.
- Validacao do pipeline: o mesmo codigo, aplicado a 2024 (treino < 2024), reproduz `walk_forward` exatamente (n = 2.890; RMSE XGBoost 0,07276; Ridge 0,07512; skill +0,1855 / +0,1591; ingenua +0,0549).
  (`src/modelos/walkforward.py` ja estava modificado na arvore de trabalho antes desta tarefa; o teste usou essa versao.)

## 2. Modelo congelado
XGBoost (parametros do config) e Ridge com as 9 features de producao (chuva 30/60/90 d, tmax 30 d, dias secos, sin/cos da quinzena, `anom_lag1`, `anom_lag2`), treinados em 2001-2024 (70.370 linhas), climatologia do alvo so de 2001-2024
(fixa tambem para 2026). Faixa: ACI por estacao de `conformal_aci.py` (gamma 0,05, 4 faixas), estado de alpha ao fim de 2024 obtido como na producao (aquecimento 2009-2021, anos 2022-2024), residuos de calibracao 2022-2024 (Ridge treinado < 2022), meia-largura aplicada em torno da previsao.
O alpha segue atualizando online com o erro ja observado a cada composto (o desenho do ACI); a variante estatica (alpha congelado) esta abaixo. Observacao: o modelo "de producao" do repositorio usa treino ate 2021 + holdout 2022-24; aqui treinei ate 2024 (o que estaria em uso em jan/2025).

## 3. Resultado: 1 composto a frente (5.147 previsoes)
| | Selecao 2010-21 (media de 12 anos) | Confirmacao selada 2022-24 (media de 3) | **Prospectivo 2025+ (agregado)** | 2025 | 2026 (ate 10-16) |
|---|---|---|---|---|---|
| XGBoost vs climatologia | +0,322 | +0,264 | **+0,254** [IC95 0,187 a 0,311] | +0,207 [0,146; 0,260] | +0,296 [0,175; 0,380] |
| Ridge vs climatologia | +0,309 | +0,2385 | **+0,247** [0,184; 0,303] | +0,192 [0,123; 0,251] | +0,297 [0,188; 0,379] |
| ingenua (repetir ultima anomalia) | +0,239 | +0,146 | **+0,166** [0,087; 0,239] | +0,086 [0,002; 0,163] | +0,241 [0,106; 0,345] |
Nota de comparacao: selecao e confirmacao sao media de skill por ano (modelo refeito a cada ano); o prospectivo agregado e o skill agrupado das 42 datas (RMSE global), com um unico modelo congelado. Por ano, Ridge na confirmacao: +0,365 / +0,194 / +0,172; 2025 (+0,192) cai dentro dessa faixa.
RMSE: climatologia 0,0818; XGBoost 0,0611; Ridge 0,0616; ingenua 0,0683.
IC95 = bootstrap reamostrando compostos (42 datas; 23 em 2025, 19 em 2026; todos os pontos de uma data juntos, 5.000 reamostragens). Reamostrando pontos (195), o IC agregado do XGBoost e [0,225; 0,282].
Diferencas pareadas (bootstrap por composto): XGBoost - ingenua = +0,088 [+0,059; +0,121]; XGBoost - Ridge = +0,007 [-0,011; +0,026] (nao distinguivel).
**Poder baixo**: sao 2 anos (so 1 ano completo); a variacao de um ano para outro e grande (confirmacao 0,16 a 0,36), e compostos vizinhos sao correlacionados, entao o IC por composto provavelmente e otimista.

Por estacao (faixas de 6 slots; XGBoost / Ridge / ingenua): slots 0-5 (jan-abr) +0,104 / +0,093 / -0,011 (n 568); 6-11 +0,270 / +0,268 / +0,196 (n 1.521); 12-17 +0,358 / +0,351 / +0,278 (n 2.146); 18-22 (out-dez) +0,256 / +0,245 / +0,167 (n 912).
Por mes (XGBoost): jan +0,134; **fev -0,014** (n 170); mar +0,258; abr +0,192; mai +0,265; jun +0,313; jul +0,359; ago +0,351; set +0,364; out +0,379; nov +0,291; dez +0,115. O modelo e fraco no inicio da estacao chuvosa (dez-fev), onde a ingenua tambem e ruim (jan -0,002; fev -0,122; dez -0,031). Por que: hipotese (resposta rapida do NDVI a chuvas novas), nao testada.
Por ponto (193 pontos com n >= 10; `skill_por_ponto.csv`): **XGBoost vence a climatologia em 85,5%** dos pontos (Ridge 84,5%); vence a ingenua em 82,4%. Quantis do skill por ponto: min -0,277; p10 -0,073; p25 +0,074; mediana +0,229; p75 +0,351; p90 +0,446; max +0,591. Cada ponto tem so 8 a 42 compostos (mediana 26): skill por ponto e ruidoso.
Por regiao: nao ha base litoral/sertao; uso so tercis de latitude dos 184 pontos do Ceara (cortes -5,50 e -4,12; proxy, nao classificacao): sul +0,254, meio +0,250, norte +0,276 (n 1.783 / 1.619 / 1.429). Sem diferenca relevante.
Vies: anomalia observada media +0,0277, prevista +0,0128; erro medio (obs - prev) +0,0149 pooled; media dos vieses por composto +0,021 [+0,013; +0,031]. O modelo subestima anomalias positivas nos dois anos (2025 +0,010; 2026 +0,021).
Erro por composto (`erro_por_composto.csv`/`.png`): nao ha choque de ano inteiro em 2025 (anomalia media por composto fica em -0,03 a +0,03, exceto jan-fev/2025, ate +0,107). Em 2026 a anomalia observada media fica em +0,04 a +0,07 de maio a outubro e o modelo capta cerca de metade (+0,02 a +0,045); skill por composto 0,28 a 0,49 nesse periodo. Pior composto: 2026-02-02 (-0,389), 2025-01-17 (-0,111), 2025-05-25 (-0,026); todos transicoes de chuva/seca.

## 4. Cobertura da faixa ACI (meta 80% / 90%) em 2025+
| | 80% | 90% |
|---|---|---|
| Faixa em torno do XGBoost (como em producao) | **85,7%** [IC composto 82,9; 88,3] | **93,6%** [91,9; 95,2] |
| Ridge (o modelo em que o ACI foi validado) | 84,4% [81,3; 87,2] | 93,4% [91,7; 94,8] |
| alpha congelado ao fim de 2024 (sem atualizar), XGBoost | 86,3% | 94,0% |
Por estacao (XGBoost, 80/90): 85,6/92,4; 86,7/94,9; 82,5/91,5; 91,6/97,3. Por mes (80%): minimos em jul 73,2% e fev 75,3%; maximo out 96,5%; a faixa de 80% fica abaixo de 80% em jul, fev (e em dez 80,4% no limite); a de 90% fica abaixo em fev (85,3%) e jul (85,9%). Pior composto: 51,7% (80%) / 67,2% (90%).
Meia-largura media: 0,081 (80%) e 0,115 (90%). Resultado: **a faixa sobrecobre** (conservadora) em vez de subcobrir; na confirmacao 2022-24 tinha dado 79,9% / 90,0%. Cobertura global ok, mas ha meses abaixo da meta.

## 5. Horizonte (+h compostos, usando a ultima anomalia observada na origem e so o clima ate a origem; modelos novos do mesmo tipo, treinados <= 2024)
Features: as 9 de producao tomadas na linha da origem + sin/cos da quinzena do composto-alvo; exige h compostos consecutivos. Skill vs climatologia nas mesmas linhas (IC por composto):
| h | n teste | XGBoost | Ridge | ingenua |
|---|---|---|---|---|
| +1 | 5.147 | +0,254 [0,187; 0,311] | +0,247 [0,184; 0,303] | +0,166 [0,087; 0,239] |
| +2 | 4.666 | +0,163 [0,114; 0,210] | +0,160 [0,107; 0,210] | +0,057 [-0,015; 0,123] |
| +3 | 4.238 | +0,110 [0,066; 0,149] | +0,108 [0,060; 0,148] | -0,023 [-0,088; 0,034] |
| +4 | 3.837 | +0,065 [0,032; 0,099] | +0,069 [0,031; 0,103] | -0,082 [-0,143; -0,030] |
O ganho cai ~33 a 41% a cada composto; a +4 (64 dias) resta +0,065 e a ingenua fica pior que a climatologia. Nao ha clima futuro: o modelo usa memoria do NDVI e sazonalidade.

## 6. Retroteste de 5 municipios (`retroteste_5_municipios.png/.csv`, `retroteste_escolhidos.csv`)
Regra (no codigo, antes de ver 2025+): entre os 184 pontos `_ce`, ordenar por (latitude, id) e tomar as posicoes round(q*(n-1)), q = 0, .25, .5, .75, 1; mais o **pior** skill XGBoost entre os `_ce` com n >= 10.
Escolhidos / skill XGB vs clim / ingenua: penaforte_ce (lat -7,78) +0,23 / +0,19; erere_ce +0,24 / -0,10; itapiuna_ce -0,02 / -0,15; tejucuoca_ce +0,29 / +0,32; jijoca_de_jericoacoara_ce (lat -2,88) +0,21 / +0,18; **pior: horizonte_ce -0,25 / -0,82** (n = 21). Nos graficos as linhas ligam compostos consecutivos *testaveis*; os trechos retos longos sao compostos sem previsao (lacuna), nao previsao.

## 7. Veredito
**O modelo se sustenta.** Em dados que nunca viu, o skill do XGBoost contra a climatologia e +0,254 (IC 0,19 a 0,31), perto da confirmacao selada (+0,264), abaixo da selecao (+0,322, dado otimista por ser escolha) e acima da ingenua (+0,088 [0,06; 0,12]). Nao ha piora com a distancia do treino (2026 > 2025).
2025 sozinho (+0,207 XGBoost; +0,192 Ridge) e um pouco menor, mas dentro da variacao entre anos da confirmacao. Contra o Ridge, o XGBoost nao tem vantagem demonstravel (+0,007, IC cruza 0).
Ressalvas: (a) so ~1,8 ano de teste, IC por composto otimista; (b) fraco em dez-fev (fev -0,014); (c) 14,5% dos pontos perdem para a climatologia; (d) vies positivo pequeno (+0,015), modelo subestima anos mais verdes; (e) a faixa sobrecobre (85,7/93,6) e fica abaixo da meta em fev e jul;
(f) o ganho vem da persistencia do NDVI (o modelo so-clima nao passou antes, ver `avaliacao_195/RESULTADO.md`) e cai para ~+0,07 a +4 compostos; (g) composto mais recentes podem ser reprocessados pelo MODIS (hipotese). Previsao de NDVI continua modulo de apoio, nao prova de que uma rotacao rende mais.
