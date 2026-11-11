# Como retomar o trabalho em outro PC (testado para ~8 GB de RAM)

Atualizado em 2026-11-11. Projeto leve: coleta é limitada pela rede; modelos usam < 1 GB (walk-forward ~1–2 GB com 59 pontos).

## 1. Preparar o ambiente
```
git clone git@github.com:NatanBack77/sulco-nasa.git
cd sulco-nasa
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt        # Linux/Mac: .venv/bin/python
.venv/Scripts/python -m pytest -q -W error                      # deve dar 81 passed
```
Python 3.14 foi o usado; 3.11+ deve servir (se alguma versão fixa não tiver wheel, ajuste e registre).
Não é preciso `.env` para POWER nem para MODIS (ORNL). `.env` (Earthdata) só serve para AppEEARS/SMAP e **nunca é commitado**.

## 2. Estado dos dados (2026-11-11)
| Dado | Estado | Onde |
|---|---|---|
| Clima POWER, **59 pontos**, 2001–2024 | completo | `data/processed/clima_diario.parquet`, `pontos.csv` (versionados) |
| NDVI MODIS (ORNL) | **cache de 34/59 pontos completos**, 1 parcial, 24 sem nada (3.856/6.608 janelas) | `data/raw/modis_ornl/*.json` (versionado) |
| `ndvi_16d.parquet` | só os 13 pontos antigos; o completo sai ao fim da coleta | `data/processed/` |
| SMAP | não iniciado | — |
| Instantâneo dos 13 pontos (reprodutibilidade) | completo | `experimentos/dados13/` |

Ver avanço do NDVI: `.venv/Scripts/python -m src.coleta.modis_ornl --status`

## 3. Terminar o NDVI (≈ 35–60 min)
```
.venv/Scripts/python -m src.coleta.modis_ornl --workers 16
```
Idempotente (pula janelas já em cache, descarta arquivo truncado); pode interromper e rodar de novo. Ao final grava
`data/processed/ndvi_16d.parquet` com os 59 pontos. Faça `git add data/raw/modis_ornl data/processed && git commit && git push`
de tempos em tempos. Com poucos downloads (4–8) o ritmo cai para ~8/min; o gargalo é o nº de chamadas simultâneas, não a RAM.

## 4. Depois que o `ndvi_16d.parquet` estiver completo
```
.venv/Scripts/python -m src.modelos.walkforward --variantes base,persistencia,so_persistencia,janelas_longas
.venv/Scripts/python -m src.modelos.walkforward --variantes base,persistencia --placebo       # deve dar skill <= 0
.venv/Scripts/python -m src.modelos.diagnostico
.venv/Scripts/python -m src.modelos.preditivo
```
Depois: **confirmação selada** (2022–2024) de `persistencia` e `pers_lags4` com os 59 pontos (ver `docs/05_EXPERIMENTOS.md`, seção 4),
atualizar `docs/00_STATUS.md`, `README.md` e `relatorio_modelos.md`, e só então levar a persistência para `preditivo.py`/`cenarios.py`.

## 5. Experimentos pendentes
`experimentos/expA_chirps/` (CHIRPS), `experimentos/expB_indices/` (EVI/SAVI), `experimentos/expC_features/` (features; já rodado).
Cada pasta tem scripts e cache parcial; leia `docs/05_EXPERIMENTOS.md` antes (regras: só 2010–2021, contar N, placebo, confirmação selada).

## 6. Contexto para o assistente (cole no início da sessão)
> Leia `docs/00_STATUS.md`, `docs/03_SUPOSICOES_E_DECISOES.md`, `docs/04_RETOMADA.md` e `docs/05_EXPERIMENTOS.md`.
> Termine a coleta do NDVI (`python -m src.coleta.modis_ornl --workers 16`), reavalie com os 59 pontos pelo walk-forward e faça a
> confirmação selada (2022–2024) de `persistencia` e `pers_lags4`. Regras: dado ausente vira lacuna; métricas de SINTETICO nunca são
> resultado; nunca olhar 2022–2024 para escolher variante; contar N de variantes testadas; não commitar `.env`.

## 7. Pendências abertas
Lista de pontos (S2; os 59 atuais são proposta); semântica da reliability (0–3); SMAP (opcional); `celula_power` é aproximada (D36);
cenários com persistência são pouco sensíveis à chuva; CHIRPS/EVI-SAVI sem resultado; uso do solo (MapBiomas) não testado.
