# Status do projeto SULCO

> **Estado em 2026-11-14 (fim do dia):** tudo da rodada está commitado. Resumo do que mudou desde 2026-11-13:
> - **Chat com RAG ligado à DeepSeek** (`src/llm/`): folha de fatos do local (70 fatos com origem), fonte "sobre o Sulco", acervo de 50 PDFs; resposta em **linguagem simples**, sem siglas e sem marcadores [F#]/[n] no texto (as fontes ficam em "De onde veio esta resposta"); verificador de números, promessas, tom e repetição; recusa de pedidos de lucro/escolha de rotação; **trava de gasto** (100 chamadas/dia, 600 tokens de saída, contador em `data/processed/llm_cache/gasto.json`, ignorado pelo git). Testado com a API real: 31 chamadas, ~55 mil tokens de entrada, **~US$ 0,01 a 0,02** (o usuário tem US$ 5). Última rodada: 5 de 5 respostas da IA aprovadas.
> - **Página de teste do chat:** `GET /teste` (HTML puro) e `GET /chat/gasto`. **Limite de taxa** na API (`src/api/limite_taxa.py`).
> - **Docker:** `Dockerfile` multi-stage, `docker-compose.yml`, `.dockerignore`, `requirements-*.txt` separados, `docs/23`. Imagem `sulco:teste` (5 GB) construída; **o contêiner nunca foi subido** para teste e o proxy (Nginx) não foi escrito.
> - **Rotação:** regras duras do agricultor + comparação por dominância, matriz com fonte (34 pares; 55 no experimento da FAO), cartão do município, nomes oficiais (IBGE), FAO em staging (`docs/25`).
> - **Suíte:** a suíte BLOQUEIA rede e usa chave falsa (`tests/conftest.py`). Nenhum teste gasta dinheiro.
> **Segredos:** `.env` NÃO vai ao git. Modelo em `.env.example`. A chave DeepSeek existe só no `.env` da máquina onde foi colocada; em outro computador crie o seu.
> **Por onde continuar, em ordem:** (1) decisões abaixo; (2) ligar os dados de 2025–2026 ao modelo (a previsão do app é para janeiro de 2025); (3) subir o contêiner e conferir API e app dentro dele; (4) Censo Agropecuário por município (dados sociais); (5) validar com técnico local.
> **Decisões suas pendentes:** a faixa de chuva do EcoCrop é anual ou do ciclo? usar o ciclo da FAO-56 (milho 215 → 140 dias) e qual linha da Tabela 11; aceitar ciclo de outras regiões; trocar a senha do Earthdata; voz (adiada, ver 3.11); Censo Agropecuário.

> **Atualização 2026-11-13 (noite):** MVP com erosão, ETo, renda, calor/chuva extrema, mapa por camadas e filtros; API com rotação, ZARC, plano e previsão; LLM integrado sem chave; RAG 88% no teste (25 perguntas).
> **Modelo:** teste prospectivo 2025+ (modelo congelado, dados nunca vistos): skill +0,254 a +1 composto, +0,065 a +4; cobertura ACI 85,7%/93,6%; vence a climatologia em 85,5% dos pontos; fraco de dez a fev. SoilGrids: sem evidência. ERA5/horizonte: incompleto.
> **Desafio:** régua própria 71% (núcleo 91%). Lacunas maiores: nenhum teste com agricultor/técnico; seções novas fora da nota dos 3 caminhos; sem Kc/ETc; sem preço/mercado. **Rotação:** empate técnico em todos os locais; ver `docs/22`.
> Suíte: 395 testes passam (321 + 74 de LLM/RAG; `tests/test_rag.py` leva ~7 min). Pendências: `docs/15`. Retomada: `docs/04`.


> **Estado em 2026-11-13.** Documentos-chave: `docs/04_RETOMADA.md` (continuar em outro PC e por onde começar), `docs/15_PENDENCIAS.md` (o que falta), `docs/18_ARQUITETURA_TECNICA.md` (como funciona),
> `docs/17_PITCH.md` (pitch e avaliação honesta), `docs/19_ALINHAMENTO_AO_DESAFIO.md` (comparação com o desafio da NASA).
>
> **Dados:** 195 pontos (184 municípios do CE + 11 de outros estados). Clima POWER, NDVI MODIS e SMAP completos; relevo SRTM, solo SoilGrids (195 de 195), produção do IBGE (PAM, 2015–2023, com valor da produção) e ZARC do Ceará coletados.
> **Modelo (anomalia de NDVI, holdout 2022–2024 selado):** skill +0,28 (XGBoost), erro (RMSE) 0,072 contra 0,100 da média histórica; sem sinal de overfitting ou underfitting; faixa de incerteza ACI por estação cobre 80,9% / 90,6% (metas 80% / 90%; pior ano 72%).
> O ganho vem da persistência do NDVI; clima, terreno e índices Niño/Atlântico não melhoram a previsão; o NDVI explica só 3% a 10% do rendimento municipal do IBGE, a chuva da quadra explica mais (milho 31%).
> **Produto:** app Streamlit com diagnóstico, chuva da quadra (2b), 3 estratégias, rotação de 3 safras (3b) com plano MILP, solo estimado e cenários de clima; ZARC **ligado por padrão** (culturas sem ZARC usam janela aproximada);
> API FastAPI; camada LLM sem chave; RAG de 31 PDFs (acerto 54%, meta 80%). Alternativas de rotação seguem em **empate técnico**.
> **Alinhamento ao desafio:** ~61% da régua de 46 pontos (núcleo obrigatório 86%). Maiores lacunas: erosão/infiltração, evapotranspiração e balanço hídrico, renda/mercado, calor e chuva extrema, mapa com camadas e linha do tempo, entradas do agricultor (água, equipamento, mercado). Todas estão em `docs/15_PENDENCIAS.md` como pendentes.
> **Testes:** 324 coletados (`pytest --collect-only -q`); RAG e LLM são pesados e rodam à parte. Decisões e histórico abaixo e em `docs/03_SUPOSICOES_E_DECISOES.md`.

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
