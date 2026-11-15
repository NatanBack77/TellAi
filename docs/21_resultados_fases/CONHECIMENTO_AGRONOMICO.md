# Conhecimento agronômico buscável (índice 2): ESTADO PARCIAL, retomar depois

Atualizado em 2026-11-14. **Status: código pronto; índice NÃO construído; avaliação, calibração e testes NÃO rodados.** Nada daqui está ligado à conversa. O usuário pediu para deixar esta parte para depois.

## Objetivo
Dar ao assistente, por busca por significado, o **domínio agronômico** para o qual o Sulco foi feito (clima do semiárido, culturas, ciclos, zoneamento, solo, rotação, consórcio, calendário, produção dos municípios e as lacunas de dados), **sem** conhecimento sobre o projeto (arquitetura, voz, custos, agentes, PIN, deploy). Hoje só os 50 documentos da Embrapa/MAPA/FAO (3.203 trechos, `indice/`) são buscáveis por significado, e só no caminho do chat.

## O que existe no repositório
- `src/rag/agronomia.py`: construção idempotente (sha256 por fonte, embeddings reaproveitados por hash do texto), `IndiceAgronomia` e `buscar_agronomia(pergunta, k, municipio, cultura, so_agricultor)`. Reaproveita BM25, tokenizador e o modelo `multilingual-e5-small` de `src/rag/busca.py` (modo HF offline). CLI: `python -m src.rag.agronomia [--forcar] [--sem-embeddings]`.
- `src/rag/projeto.py`: alias (`buscar_projeto = buscar_agronomia`).
- `src/rag/avaliar_agronomia.py` e `tests/dados/perguntas_agronomia.json`: 45 perguntas de domínio (10 só nas pesquisas internas, 5 de lacuna, 4 de pragas e insumos), 4 fora de domínio e 10 sobre o projeto (devem voltar "sem evidência").
- `tests/test_rag_agronomia.py`: sem segredos nem termos proibidos, sem lat/lon, lista branca, filtros, idempotência, citação com fonte e confiança, trecho interno bloqueado, lacunas em top-3, BM25 puro, embeddings só se o modelo estiver em cache. **Ainda não rodou.**
- Manifesto versionado: `data/conhecimento_agronomia_manifesto.json` (sai da construção; ainda não existe).
- `docs/31_LACUNAS_DE_DADOS.md`: entra no índice como fatos do tipo "lacuna" (uma linha de tabela = um fato; a seção 8 é ignorada).

## Lista branca (o que entra)
Docs 07, 22, 25, 13, 29, `ler_trechos`, 27 (calendário/solo/semente/mercado), 27 (época de plantio), 06 e, de `docs/21`: CALENDARIO_PLANTIO, CICLO_FAO_CHUVA_ANUAL, MATRIZ_ROTACAO, SOILGRIDS, ROTACAO_REGRAS_PARETO. Tabelas com fonte (tabela_culturas, fao_staging, solo_staging, ler_staging, matriz_rotacao), um fato por linha. Externos CONAB (preços e custos, "preço não é lucro") e SIGEF ("campo de produção de semente, não lavoura"). Minerados agregados: ZARC, PAM 2023, solo por município, diagnóstico (solo nu, veranico, chuva mensal), só com nome do município, nunca lat/lon.

## O que fica de fora e por quê
Docs 00, 04, 05, 09, 11, 12, 14, 15, 17, 18, 19, 20, 23, 24, 26, 28 e quase todo `docs/21` e `experimentos/**/RESULTADO.md`: narrativa do projeto, não fato do campo. Parquets de clima, NDVI e umidade: não são resultado agregado por município. Filtro por bloco descarta parágrafo, linha de tabela ou título com termo de projeto, infraestrutura ou segredo (docker, deepseek, prompt, agente, PIN, .env, pytest, commit, endpoint, api, llm, chat, app, motor, sulco, parquet, assistente, tela, caminhos `src/` e `docs/`), e regex de segredo e de coordenadas.

## Contagens da geração de registros (antes do último ajuste, que só acrescentou a seção 6b e mais termos proibidos)
8.846 registros: dado_minerado ~7.350, tabela_com_fonte ~1.030, pesquisa_interna 106, estudo_publicado 66, lacuna 27. Por fonte: zarc 4.961, pam 1.353, diagnóstico 576, conab_custos 286, fao 269, matriz 265, solo_staging 256, tabela_culturas 240, solo 194, conab preços 177, sigef 70, ler_staging 60. 255 blocos de documentos descartados pelo filtro e 32 registros bloqueados na varredura final.

## Como retomar (nesta ordem)
1. Com a máquina livre (a construção pede ~1,5 GB e leva alguns minutos; lote de 16): `.venv/bin/python -m src.rag.agronomia --forcar`. Rode **uma vez** depois dos últimos ajustes (a rodada anterior começou antes das linhas de pragas e doses e dos termos "tela" e "assistente"). A segunda rodada reaproveita embeddings por hash.
2. `.venv/bin/python -m src.rag.avaliar_agronomia`: reportar top-1/top-5, fonte correta, "sem evidência" e se as 10 perguntas sobre o projeto devolvem "sem evidência". **Calibrar `LIM_COS` (0,86) e `LIM_COBERTURA` (0,5)** em `agronomia.py`: os valores atuais **não foram medidos**.
3. `.venv/bin/python -m pytest tests/test_rag_agronomia.py -W error` e ajustar a lista de termos proibidos se algum teste reclamar.
4. Adicionar `indice_agronomia/` ao `.gitignore` (ainda não está; `indice/` já está).
5. Só então ligar à conversa: `from src.rag.agronomia import buscar_agronomia`; retorno `{"sem_evidencia","mensagem","modo","trechos":[...]}`; cada trecho traz id, arquivo, seção, texto, fonte, tipo, data, confiança, aviso, município, culturas e `pode_citar_ao_agricultor`. Trecho do tipo "lacuna" significa "diga que não tem o dado e ofereça o que existe no lugar". **Os filtros de segurança (entrada, contexto, saída; ver docs/30) devem estar ligados ANTES desta base entrar no prompt.**

## Riscos
- Pesquisa interna pode conter hipóteses: confiança e aviso viajam com o trecho, e o assistente só pode reescrever.
- Os limiares da busca não foram calibrados: sem isso, a busca pode devolver trecho fraco ou recusar demais.
- Fato de outro município nunca responde por um município pedido (regra implementada, não testada).
