# Calendário verificado, solo EcoCrop, semente e mercado (2026-11-14)

Resumo; o texto completo está em `docs/27_CALENDARIO_SOLO_SEMENTE_MERCADO.md`.

## Scripts (rodar com `.venv/bin/python`, um por vez)
- `calendario.py`: ZARC (risco 20/30/40, solo) x motor (sem/com ZARC) x PAM x ciclo, 15 municípios x 16 culturas -> `saida/calendario_*.csv`, `inconsistencias.csv`, `leitura_dec.json`.
- `extrair_solo_staging.py`: colunas de solo do EcoCrop -> `data/culturas/solo_staging.csv` (entrada: `entrada/EcoCrop_DB.csv`, sha256 4187e884...d48d106).
- `efeito_solo.py`: antes/depois de `Parametros.solo_modo='ecocrop'` -> `saida/efeito_solo.json`, `efeito_solo_15municipios.csv`, `nota_solo_184pontos.csv`.
- `baixar_externos.py`, `baixar_siszarc_ce.py`, `sigef_calendario.py`: recortes do CE de CONAB e MAPA para `data/externos/` (+ manifesto), resumo SIGEF.
- `baseline_padrao.json`: resultado do motor ANTES da edição de `ciclo.py`/`parametros.py` (usado em `tests/test_solo_ecocrop.py` para provar que o padrão não mudou).

## Resultados-chave
- Frase "olha só chuva e calor" era texto fixo em `fatos.py`; a viabilidade da sugestão já usava o ZARC (risco 30, solo "qualquer"). Agora é gerada de `avaliar_sequencia.criterios_aplicados`.
- `dec`: valores observados {0,20,30,40}; o dicionário oficial do MAPA não define 0/20/30/40 (leitura vem das portarias).
- Motor sem ZARC sugere início fora do ZARC (risco 30) em 120 casos viáveis (de 15 municípios x 11 culturas mapeadas); com ZARC, em nenhum.
- 75 pares município-cultura sem ZARC (guandu, crotalária, feijão-de-porco, mucuna, sorgo); o sorgo TEM ZARC no MAPA mas não está mapeado no motor.
- Solo EcoCrop (15 municípios): viáveis 14,73 -> 13,13; Jaccard médio entre municípios 0,034 -> 0,094; 24 pares perdem viabilidade (14 palma); nenhuma data de início muda. Palma com `PHMIN` 6,5 do EcoCrop fica nota 0 em 182 de 184 pontos, em conflito com o ZARC: manter desligado.
- Semente: SIGEF (campos de semente, CE, 1.553 linhas) e SISZARC (cultivares indicadas por UF) abertos; RNC com captcha; preço de semente só de milho (2 obs.).
- Mercado: CONAB baixável sem login (preços mensais 2025-2026; custo de produção); CE tem feijão, milho, mandioca, algodão, mamona; custo só milho 2ª safra em Crateús; CEPEA 403; PGPM não achado.
- Preço não é lucro; custo é médio regional/modelo, não o do agricultor.
