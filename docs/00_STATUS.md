> **Atualização 2026-11-13:** rotação em 3 safras (seção 3b do app, `src/culturas/rotacao.py`), indicador da chuva da quadra (seção 2b), ACI por estação integrado ao preditivo (cobertura 80,9% / 90,6%), ZARC opcional, terreno (SRTM) e PAM/IBGE coletados. Terreno e índices Niño/Atlântico não melhoram a previsão do NDVI; NDVI explica pouco do rendimento. Ver `docs/16_PESQUISA.md`, `docs/15_PENDENCIAS.md`, `experimentos/*/RESULTADO.md`. Solo (SoilGrids) bloqueado.
# Status do projeto SULCO

> **Retomada (2026-11-12, 21h20):** tudo parado e commitado. Passo a passo: `docs/04_RETOMADA.md`; o que falta, em ordem: `docs/15_PENDENCIAS.md`.
> **Estado:** 195 pontos (184 municípios do CE + 11 de outros estados). Clima POWER, NDVI MODIS (107.583 linhas) e SMAP (195 × 3.564 dias) completos.
> **Modelo:** a persistência do NDVI é a única melhoria confirmada (skill +0,24 na confirmação selada 2022–2024); o clima sozinho não supera a climatologia;
> CHIRPS e SMAP (+0,007) não ajudam de forma útil; conformal cobre 76% / 87% para metas de 80% / 90%. Detalhes em `experimentos/avaliacao_195/RESULTADO.md` e `docs/05_EXPERIMENTOS.md`.
> **Produto:** MVP Streamlit (`src/app`, `docs/11_MVP.md`), motor de culturas com ciclo e incerteza (`docs/10`), RAG com 31 PDFs, API FastAPI (`docs/12`, 6/7 endpoints),
> camada LLM com verificador testada sem chave (`docs/14`). ZARC não iniciado (`docs/13`). Alternativas de rotação seguem em empate técnico.
> Pesquisas: `docs/07` (viabilidade), `docs/08` (ranking/incerteza), `docs/09` (previsão NDVI). Decisões: `docs/03`. Pesos: `docs/06`.

Atualizado em 2026-11-11. Escopo atual: módulo `src/modelos/` (séries temporais e preditivo).

## Feito
| Passo | Entrega | Testes |
|---|---|---|
| 1 | Esqueleto, `config.yaml`, `requirements.txt` (versões fixas), sementes | |
| 2 | Gerador de dados `SINTETICO_*` (`sintetico.py`), grade MODIS de 23 obs/ano | |
| 3 | Validador de entrada (`entrada.py`): falha explícita se faltar arquivo/coluna | 7 |
| 4 | `diagnostico.py`: STL, climatologia/z-score, solo nu, Theil-Sen + Mann-Kendall, veranicos | +13 |
| 5 | `features.py`: janelas só de dias anteriores, dias secos, sazonalidade, alvo = anomalia | +17 |
| 6 | `preditivo.py`: climatologia, Ridge, XGBoost; GroupKFold por célula + holdout temporal; métricas | +17 |

| 7 | Conformal split: calibração em células distintas, cobertura a 80%/90% (CV e holdout) | |
| 8 | `decidir_modelo`: XGBoost vs. Ridge pelo critério proposto (critério aprovado pelo usuário) | |
| 9 | Explicação via `pred_contribs` do XGBoost (só explicativa) | |
| 10 | `cenarios.py`: fatores de chuva/temperatura, faixa conformal, aviso de extrapolação | |
| 11 | Testes de vazamento entre grupos, reprodutibilidade, ordem das linhas, extrapolação | |
| 12 | `relatorio.py` + `relatorio_modelos.md` (esqueleto; real só com dados reais) | +17 (7–12) |

Total: 71 testes passando (`pytest -q -W error`). Todo o desenvolvimento usou dados sintéticos.

## Walk-forward e melhorias (2026-11-11) — ver `docs/05_EXPERIMENTOS.md`
- Protocolo anti-overfitting implementado (`walkforward.py`, 10 testes): walk-forward, linhas comuns, placebo, Bonferroni, confirmação selada 2022–2024.
- **Persistência** da anomalia de NDVI: skill +0,23 (seleção) / +0,10 (confirmação) contra +0,06 / −0,02 da base. Ganho vem da memória do NDVI; o clima acrescenta ~+0,014.
- `pers_lags4` (4 lags): +0,024 sobre a persistência, **pendente de confirmação selada**.
- Reprovadas: janelas 120/180 d, alvo normalizado, features de clima novas (anomalia de chuva, SPI, eventos, térmica, déficit), XGBoost monotônico.
- CHIRPS e EVI/SAVI: agentes interrompidos, sem resultado.
- Dados: clima 195 pontos completo (184 municípios do CE + 11 de outros estados); NDVI em coleta (21.840 janelas; cache parcial; `ndvi_16d.parquet` ainda com 13).

## Resultado real do preditivo (13 pontos, 2026-11-11)
Ridge escolhido; **não supera a climatologia no holdout** (skill −0,021; CV +0,033). Conformal cobre ~72%/81% para metas 80%/90% (subcobertura). Ver `relatorio_modelos.md`.

## Persistência na produção (2026-11-12, D52)
- `preditivo.py`/`cenarios.py`/`relatorio.py` usam por padrão `anom_lag1/2` (a mesma função validada em `walkforward.py`). Só-clima segue disponível (`usar_persistencia: false` / `--sem-persistencia`); SMAP desligado (`usar_umidade_solo: false` / `--com-smap`).
- `python -m src.modelos.preditivo` com 195 pontos (59 células, confiança "media"; backup antes: `data/processed/modelos/*.bak_pre_D52`). Holdout 2022–2024, skill vs. climatologia (Ridge / XGBoost): **com persistência +0,257 / +0,284** (62.318 linhas de treino, 8.052 de teste); só clima nas mesmas linhas −0,025 / +0,003; só clima em todas as linhas (modelo anterior sem SMAP) −0,013 / +0,023. CV por célula (otimista, D22): +0,278 / +0,309 contra +0,063 / +0,103.
- Reconciliação com `experimentos/avaliacao_195/RESULTADO.md` (persistência confirmação +0,2385 Ridge): o walk-forward na MESMA amostra daquele resultado (linhas comuns com `pers_lags4`) reproduz +0,2385 / +0,2644; com só a persistência (mais linhas) dá +0,2297 / +0,2568 (média dos anos, treino expansivo); o holdout da produção treina uma vez até 2021 e junta os 3 anos (+0,257 / +0,284). 2022 coincide exatamente com o walk-forward (+0,353 Ridge); 2023–2024 diferem porque o walk-forward re-treina com 2022/2023.
- Cobertura conformal real no holdout (metas 80% / 90%): com persistência Ridge 76,0% / 87,2%, XGBoost 75,8% / 86,7% (antes, só clima: 70,1% / 82,6%). **Ainda abaixo da meta**; não ajustada.
- Cenários: variação com persistência ≈ 0,18–0,54 da variação só-clima (Ridge chuva ×0,8: −0,0019 contra −0,0036; tmax +1 °C: −0,0022 contra −0,0091). Em ambos é pequena frente ao RMSE (~0,07). Ver `relatorio_modelos.md`.
- Testes: `tests/test_persistencia.py` (vazamento, ordem, reprodutibilidade, composto ausente, igualdade com o walk-forward, cenários, relatório).

## Falta (módulo `src/modelos/`)
- (Feito em 2026-11-12: NDVI 195 pontos, confirmação selada e integração da persistência; ver acima e `experimentos/avaliacao_195/RESULTADO.md`.) Pendente: decisão sobre `pers_lags4` (ganho marginal, não integrado) e sobre a cobertura conformal abaixo da meta.
- Testar (agentes interrompidos): CHIRPS, EVI/SAVI; ideias: uso do solo (MapBiomas), SMAP, FUNCEME.
- Opcional: instalar `shap` se houver wheel para o Python em uso; hoje a explicação usa `pred_contribs`.

## Coleta (`src/coleta`)
- **POWER: feita (2026-11-11).** 13 pontos propostos (a revisar, S2), 2001–2024, 113.958 linhas, 0 ausentes, 13 células. `python -m src.coleta.power` (cache em `data/raw/power/`, idempotente).
- Com 13 células (< 15) o modelo sai com confiança "baixa" e o aviso de amostra efetiva; ampliar os pontos melhora isso.
- **Clima (2026-11-11): 195 pontos = 184 municípios do CE (IBGE, todos) + 11 de outros estados; 59 `celula_power` aproximadas distintas (vários municípios compartilham célula e contam como UMA amostra efetiva; `celula_power` segue como grupo do GroupKFold); 1.709.370 linhas, 0 ausentes; as linhas dos 59 pontos antigos ficaram idênticas.** **MODIS: coleta reiniciada para os 195 pontos (21.840 janelas, 32 workers, ~180 janelas/min; ver 04_RETOMADA)**; `ndvi_16d.parquet` ainda com os 13 pontos (7.173 composições). (Histórico: AppEEARS (`coleta/modis.py`) ficou preso na fila; usamos o serviço de subset do ORNL DAAC (`coleta/modis_ornl.py`, público, sem login, cache em `data/raw/modis_ornl/`, retomável). Ele confirmou que `data` = início do composto (resolve S5). Com 16 downloads em paralelo o ritmo foi ~100 janelas/min; ver `docs/04_RETOMADA.md`.)
- SMAP (SPL4SMGP): pendente, opcional; exige Earthdata. Sem o `ndvi_16d.parquet` o preditivo real não roda.

## Falta (projeto SULCO fora deste módulo)
Coleta MODIS e SMAP, tabela de culturas e motor de cenários, RAG, LLM com cache,
app Streamlit, página "Limites dos dados". Ver `docs/01_VISAO_GERAL.md`.

## Achados
- Ambiente: Python 3.14.7. A primeira instalação (com `shap`) travou; o resto instalou. `shap` pode não ter wheel
  para 3.14; alternativa: `pred_contribs` do XGBoost (D3).
- Os esqueletos `tabela_culturas.py` e `rag_docs.py` citados no briefing não foram fornecidos.
- O link do desafio (Resources tab) não foi informado.
- Pendentes de confirmar na documentação oficial: nomes de parâmetros POWER, camadas MOD13Q1 v061 e semântica de
  *pixel reliability* (hoje provisório: aceitar 0 e 1), variáveis SPL4SMGP, ID do modelo DeepSeek, `multilingual-e5-small`.
- Pendente com dado real: `data` do MOD13Q1 é o início do composto? (S5)
- O limiar de solo nu por percentil 20 é relativo ao ponto; todo ponto terá "solo nu" por construção (D10).
- `confianca` em todas as saídas é heurística de cobertura de dados, não probabilidade.
- Limite do alvo: no GroupKFold a climatologia do ponto de teste usa os anos do próprio ponto (D22); no holdout temporal
  ela vem só dos anos de treino.
- Poucas células POWER distintas (< 15) reduzem o tamanho efetivo da amostra; o aviso sai nas lacunas.
- Métricas de dados sintéticos nunca são resultado do projeto; a CLI não as imprime.

## Perguntas em aberto
Pontos do demo; contas Earthdata e chaves DeepSeek/Gemini (via `.env`); anos de dados reais esperados;
escala de `confiabilidade` do NDVI; aprovação do critério do passo 8.
