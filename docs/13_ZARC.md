# 13. ZARC (Tábua de Risco): estado parcial

Etapa B do docs/07. **Só o passo 1 (código IBGE) foi feito.** Download do ZARC, `zarc.py` e integração ao motor
**não foram iniciados** (o tempo acabou); nada foi baixado, então não há versão nem sha256 do ZARC a registrar.

## Pronto
- `src/coleta/ibge_codigos.py` (`python -m src.coleta.ibge_codigos`): lê nomes/códigos da API IBGE localidades v1
  (`/estados/<UF>/municipios`) e confere por coordenada com os polígonos da API de malhas v3. Só aceita o código se o nome
  (ponto_id sem sufixo da UF) casa com exatamente 1 município da UF **e** o ponto cai dentro do polígono.
  Nota: a API devolve gzip mesmo com `Accept-Encoding: identity`; o script trata.
- `data/processed/pontos.csv` ganhou a coluna `ibge` (as demais não mudaram). Resultado: 194 de 195 pontos com código
  (184 CE menos 1; os 11 de outros estados casaram por nome e coordenada).
- `tests/test_zarc.py`: colunas preservadas, códigos CE únicos e começando em 23, 7 dígitos.
- Suíte `test_zarc, test_culturas, test_pipeline, test_sensibilidade, test_incerteza` com `-W error`: 71 passaram (motor intocado).

## Lacuna
- `sobral_ce` (-3.8117, -40.2279): o nome casa com Sobral (2312908), mas a coordenada cai **fora** do polígono de Sobral
  (conferido também com malha de qualidade máxima). Ficou vazio; não adivinhei. Logo são **183 códigos únicos no CE, não 184**.
  O teste registra essa exceção. Decisão do usuário: corrigir a coordenada do ponto (e o clima associado) ou aceitar o código 2312908.

## Faltando (próximos passos, em ordem)
1. Listar recursos do dataset por `https://dados.agricultura.gov.br/api/3/action/package_show?id=6d3d141c-885e-41a4-ab7f-dc8ff323b96f`
   e baixar em streaming (urllib/requests com `stream`, escrever em `data/raw/zarc/`, pular se já existe) os CSV das safras recentes; registrar sha256.
2. Ler o dicionário do dataset para saber como "sem indicação" aparece em `dec1..dec36` (docs/07 seção 7: não verificado).
3. Filtrar `UF == CE` (e manejo sequeiro) em blocos (RAM < 1,5 GB), gravar `data/processed/zarc_ce.parquet`.
4. `src/culturas/zarc.py`: (município, cultura, risco 20/30/40, solo) -> indicação e decêndios; mapear culturas só com nome claro; as demais "sem ZARC".
5. Parâmetro opcional `usar_zarc` (padrão desligado) em `Parametros`/`motor.py`, restringindo `ciclo.indices_inicio` aos decêndios e registrando em suposições/lacunas; comparar ~10 municípios com e sem.

## Decisões pendentes do usuário
Nível de risco (20/30/40), tipo de solo, tratamento de culturas sem ZARC (docs/07 seção 9), e o caso de `sobral_ce`.
