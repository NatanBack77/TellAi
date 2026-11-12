# Status do projeto SULCO

> **Retomada (2026-11-11, noite):** tudo parado e commitado. Veja `docs/04_RETOMADA.md` (passo a passo) antes de qualquer coisa.
> Resumo: 195 pontos (184 municípios do CE + 11 de outros estados); clima completo; SMAP coletado (694.980 linhas, 44 granulos com HTTP 502);
> NDVI em 85% (18.479/21.840 janelas, 164/195 pontos completos), `ndvi_16d.parquet` ainda com 13 pontos; avaliação com 195 pontos NÃO feita.
> Novos módulos: `src/culturas/` (16 culturas, 53 lacunas), `src/rag/` (acerto top-5 54%, meta 80% não atingida), `src/app/` (Streamlit), `src/coleta/smap.py`.
> CHIRPS testado em 13 pontos: **sem ganho** (`experimentos/expA_chirps/RESULTADO.md`). Suíte: 136 testes passando.

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

## Falta (módulo `src/modelos/`)
- Terminar NDVI dos 195 pontos (coleta em andamento, 32 workers), reavaliar (walk-forward + preditivo + conformal) e fazer a confirmação selada (2022–2024) de `persistencia` e `pers_lags4`; só então levar a persistência para `preditivo.py`/`cenarios.py`.
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
