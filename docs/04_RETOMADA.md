# Como retomar o trabalho em outro PC (testado para ~8 GB de RAM)

Atualizado em 2026-11-11. O projeto é leve: coleta usa rede (não RAM) e os modelos usam < 1 GB.

## 1. Preparar o ambiente
```
git clone git@github.com:NatanBack77/sulco-nasa.git
cd sulco-nasa
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt        # Linux/Mac: .venv/bin/python
.venv/Scripts/python -m pytest -q                               # deve dar 71 passed
```
Python 3.14 foi o usado; 3.11+ deve servir (requirements fixam versões; se alguma não tiver wheel, ajuste e registre).

## 2. Onde parou (2026-11-11)
| Dado | Estado | Onde |
|---|---|---|
| Clima NASA POWER, 13 pontos, 2001–2024 | **completo** | `data/processed/clima_diario.parquet` (versionado) |
| NDVI MODIS MOD13Q1 via ORNL DAAC | **parcial** (cache de janelas) | `data/raw/modis_ornl/*.json` (versionado) |
| SMAP (umidade do solo) | não iniciado (opcional, exige Earthdata) | — |

Ver o avanço do NDVI: `.venv/Scripts/python -m src.coleta.modis_ornl --status`

## 3. Continuar a coleta do NDVI
```
.venv/Scripts/python -m src.coleta.modis_ornl
```
- Idempotente: pula janelas já em cache; descarta arquivo truncado. Pode interromper (Ctrl+C) e rodar de novo.
- Ritmo observado: ~7–9 janelas/min (servidor lento; mais paralelismo não ajudou). Total 1.456 janelas, ~3 h no total.
- Termina gravando `data/processed/ndvi_16d.parquet`. Faça `git add data/raw/modis_ornl data/processed && git commit && git push` de tempos em tempos para não perder o cache.
- Não precisa de login. O `.env` (Earthdata) só serve para AppEEARS/SMAP e **nunca é commitado**: crie o seu com
  `EARTHDATA_USERNAME=...` e `EARTHDATA_PASSWORD=...` se for usar `src/coleta/modis.py` (AppEEARS, tarefa antiga ficou na fila e é redundante).

## 4. Quando o `ndvi_16d.parquet` existir
```
.venv/Scripts/python -m src.modelos.diagnostico            # diagnóstico por ponto
.venv/Scripts/python -m src.modelos.preditivo              # métricas, conformal, decisão e relatorio_modelos.md
.venv/Scripts/python -m pytest -q -W error
```
Depois: conferir os valores reais de `confiabilidade` (0–3) contra `ndvi.confiabilidade_aceita` em `config.yaml`
(hoje provisório [0, 1]), atualizar `docs/00_STATUS.md` e `README.md`, e reportar métricas reais, cobertura, decisão e lacunas.

## 5. Contexto para o assistente (cole no início da sessão)
> Leia `docs/00_STATUS.md`, `docs/03_SUPOSICOES_E_DECISOES.md` e `docs/04_RETOMADA.md`. Continue a coleta do NDVI
> (`python -m src.coleta.modis_ornl`), e ao terminar rode diagnóstico e preditivo com dados reais e gere o relatório.
> Regras: dado ausente vira lacuna; métricas de SINTETICO nunca são resultado; não commitar `.env`.

## 6. Pendências abertas
Lista de pontos do demo (S2, os 13 atuais são proposta); confirmar semântica da reliability; SMAP (opcional);
`celula_power` é aproximada (D36); com 13 células (< 15) a confiança sai "baixa".
