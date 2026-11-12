# Como retomar o trabalho em outro PC

Atualizado em 2026-11-11 (noite). Tudo foi parado de propósito e commitado. Nada está rodando em segundo plano.
Projeto leve: coleta é limitada pela rede; modelos usam < 2 GB de RAM.

## 1. Preparar o ambiente
```
git clone git@github.com:NatanBack77/sulco-nasa.git
cd sulco-nasa
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt          # Windows: .venv/Scripts/python
.venv/bin/python -m pytest -q -W error                       # deve dar 136 passed
```
- Python 3.14 foi o usado; 3.11+ deve servir (se alguma versão fixa não tiver wheel, ajuste e registre).
- `torch` está fixado como `2.15.0` (CPU). Só o RAG usa; sem ele a busca cai para BM25. Para CPU: `--index-url https://download.pytorch.org/whl/cpu`.
- `pdftotext` (poppler) precisa estar no sistema para reconstruir o índice do RAG.
- **`.env` NÃO está no repositório** (de propósito). Crie na raiz, com as credenciais Earthdata (a do SMAP/AppEEARS):
  ```
  EARTHDATA_USERNAME=<usuario>
  EARTHDATA_PASSWORD='<senha>'
  ```
  POWER e MODIS (ORNL) não precisam de login. **A senha foi digitada numa conversa com o assistente; troque-a no site do Earthdata.**
- Cache do SMAP: `data/raw/smap_cache.tar.gz` (61 MB). Para reaproveitar: `tar xzf data/raw/smap_cache.tar.gz -C data/raw`
  (cria `data/raw/smap/granulos/` com 28.524 arquivos). Sem isso a coleta recomeça do zero (~45 min com 16 workers).
- Cache do POWER: `data/raw/power_cache.tar.gz` (27 MB; `tar xzf data/raw/power_cache.tar.gz -C data/raw`). Opcional: `clima_diario.parquet` já está versionado.
- Índice do RAG (`indice/`, ignorado pelo git): reconstruir com `.venv/bin/python -m src.rag.rag_docs`.

## 2. Estado dos dados (2026-11-11, 21h35)
| Dado | Estado | Onde |
|---|---|---|
| Pontos | **195** = 184 municípios do CE (IBGE) + 11 de outros estados; 59 `celula_power` distintas (aproximada, D36) | `config.yaml` (`coleta.pontos`), `data/processed/pontos.csv` |
| Clima POWER 2001–2024 | completo, 1.709.370 linhas, 0 ausentes | `data/processed/clima_diario.parquet` |
| NDVI MODIS (ORNL) | **18.479 de 21.840 janelas (85%)**; 164 de 195 pontos completos | `data/raw/modis_ornl/*.json` (versionado) |
| `ndvi_16d.parquet` | **ainda só os 13 pontos antigos** (7.173 linhas). O de 195 só é gravado quando a coleta termina | `data/processed/` |
| SMAP SPL4SMGP v008 | **coletado**: 694.980 linhas, 195 pontos, 2015-03-31 a 2024-12-31, 0% NaN. **44 granulos falharam com HTTP 502 do servidor** (jan/2022); o dia só vira NaN com < 6 de 8 granulos | `data/processed/umidade_solo.parquet`, cache em `data/raw/smap_cache.tar.gz` |
| CHIRPS (13 pontos) | feito e **descartado** (sem ganho) | `experimentos/expA_chirps/RESULTADO.md` |
| Tabela de culturas | 16 culturas, 53 lacunas | `data/culturas/tabela_culturas.csv` |
| Acervo RAG | 11 PDFs reais, 889 trechos | `docs_rag/` (+ `manifesto.json`) |
| AppEEARS | uma tarefa antiga (`sulco_mod13q1`) terminou (`done`); não foi baixada | conta Earthdata |

## 3. Terminar a coleta do NDVI (≈ 15 min com 64 workers; faltam ~3.360 janelas)
```
.venv/bin/python -m src.coleta.modis_ornl --workers 64
```
- **A primeira fase (listar datas dos 195 pontos) leva ~9 min sem baixar nada e sem log**; é normal. Depois aparece `21840 janelas` e o contador.
- Idempotente: pula janelas em cache, descarta arquivo truncado. Pode interromper e rodar de novo.
- Ritmo medido: 16 workers ~55/min; 32 workers ~190/min; 64 workers ~230/min (o ORNL satura perto disso; mais workers não ajudam).
- Ao final grava `data/processed/ndvi_16d.parquet` com os 195 pontos. Aí faça `git add data && git commit && git push`.
- Ver avanço: `.venv/bin/python -m src.coleta.modis_ornl --status` (leva alguns minutos: consulta datas de cada ponto).

## 4. Refazer as 44 falhas do SMAP (opcional, rápido)
```
.venv/bin/python -m src.coleta.smap        # só baixa o que falta; regrava umidade_solo.parquet
```
Os erros eram `HTTP 502 ... Failed to read the DMR++ from S3` (lado do servidor). Pode ter passado. `workers` está em 16 (`config.yaml`, `coleta.smap.workers`).
Observação: o ritmo do SMAP oscilou entre 57 e 780 arquivos/min; a causa não foi apurada (o agente de diagnóstico foi interrompido).

## 5. Avaliação (a parte principal que falta) — só depois do `ndvi_16d.parquet` completo
Protocolo anti-overfitting: `docs/05_EXPERIMENTOS.md`. Ordem:
```
.venv/bin/python -m src.modelos.walkforward --variantes base,persistencia,so_persistencia
.venv/bin/python -m src.modelos.walkforward --variantes base,persistencia --placebo      # skill deve ser <= 0
.venv/bin/python -m src.modelos.diagnostico
.venv/bin/python -m src.modelos.preditivo
```
1. Rodar seleção (2010–2021) com 195 pontos; **não olhar 2022–2024 até o fim**.
2. `pers_lags4` (veja `experimentos/expC_features/expC.py`): ainda sem confirmação selada.
3. Confirmação selada (2022–2024) UMA vez, para `persistencia` e `pers_lags4`.
4. Testar o **SMAP como feature** (umidade defasada, só dias anteriores) pelo mesmo protocolo, contando o N total de variantes (Bonferroni) e com placebo. Série só desde 2015 (poucos anos de seleção: cuidado com o poder estatístico).
5. Só se passar: levar a persistência para `preditivo.py` e `cenarios.py` (e documentar que cenários de chuva ficam pouco sensíveis).
`experimentos/avaliacao_195/avaliar.py` é um script iniciado por um agente e **não foi executado nem revisado**; leia antes de usar.
Considere que são só 59 células de clima distintas (amostra efetiva); os 136 municípios novos trazem NDVI, não chuva nova.

## 6. Módulos criados nesta rodada (todos com testes; 136 passam)
| Módulo | O que é | Limites conhecidos |
|---|---|---|
| `src/culturas/` | tabela de culturas (validador exige fonte+URL+trecho) e motor de rotação | pesos (0,25 temp, 0,25 chuva, 0,20 N, 0,15 palha, 0,15 família) e lista das 16 culturas são **proposta, sem aprovação**; EcoCrop veio de espelho do GitHub, não da FAO; scores com número de critérios diferentes não são totalmente comparáveis |
| `src/rag/` | busca híbrida (BM25 + multilingual-e5-small), "sem evidência" explícito | acerto top-5 de **54%** (75% só nos docs em PT) numa avaliação de 13 perguntas; meta era 80%. Faltam fontes em PT sobre rotação/palhada (host `infoteca` da Embrapa não resolve DNS no PC usado) |
| `src/app/` | Streamlit: página Cenários e Limites dos dados | Cenários mostra "lacuna" até existir `data/processed/cenarios/*.json` (falta ligar motor + RAG). Rodar: `.venv/bin/streamlit run src/app/app.py` |
| `src/coleta/smap.py` | SPL4SMGP via OPeNDAP (subset por caixa), média diária (≥6/8 granulos) | ver seção 4 |

## 7. Pendências abertas (decisões suas)
- Lista de pontos (S2), pesos e lista de culturas (acima), semântica da `confiabilidade` MODIS (0–3), `celula_power` aproximada (D36).
- Ligar `src/culturas` + `src/rag` + `src/modelos/cenarios.py` gerando os JSON do contrato (seção 7 de `01_VISAO_GERAL.md`) para o app.
- LLM com cache (extra); chaves DeepSeek/Gemini só via `.env`.
- Uso do solo (MapBiomas) e FUNCEME: não testados. EVI/SAVI: sem resultado (cache parcial em `experimentos/expB_indices/`).
- Bug corrigido: `modis.py` agora remove aspas do `.env`.

## 8. Contexto para o assistente (cole no início da sessão)
> Leia `docs/00_STATUS.md`, `docs/03_SUPOSICOES_E_DECISOES.md`, `docs/04_RETOMADA.md` e `docs/05_EXPERIMENTOS.md`.
> Termine a coleta do NDVI (`python -m src.coleta.modis_ornl --workers 64`), valide `ndvi_16d.parquet` (195 pontos) e `umidade_solo.parquet`,
> rode a avaliação pelo protocolo (seleção 2010–2021; confirmação selada 2022–2024 uma única vez; placebo; Bonferroni com N total) e depois
> teste o SMAP como feature. Regras: dado ausente vira lacuna; nenhum número fora de fonte lida ou de código rodado; métricas de SINTETICO nunca
> são resultado; nunca olhar 2022–2024 para escolher variante; não commitar `.env`; relate resultados negativos como estão.
