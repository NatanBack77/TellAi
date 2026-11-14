# 21. Fase 4: camada LLM (L2/L3/L4) e RAG (R1/R2) — resultados de 2026-11-13

Nenhuma chamada a API externa foi feita; `.env` não foi tocado; `src/app/app.py`, `mvp.py` e `logica.py` não foram editados. Sem chave DeepSeek, tudo foi validado com provedor stub e provedores falsos de teste.

## 1. L2/L3: integração ao app e cache de demo
Arquivos novos: `src/llm/integracao.py`, `src/llm/pregerar.py`, `tests/test_llm_integracao.py` (14 testes, sem rede). Alteração mínima em `src/llm/provedores.py`: `DeepSeek.ultimo_uso` guarda o campo `usage` da resposta (para medir custo no L4).

**Regra:** o template (`src.app.logica.explicar`) é sempre o padrão. O LLM só entra em dois casos: (a) modo `online` com provedor real e chave; (b) modo `offline`, que lê SÓ o cache de demo (`data/processed/llm_cache/`) e, se não houver, cai no template. Todo texto do LLM passa pelo verificador (números, [n], promessas, aviso); falhou ⇒ template com o motivo em `motivos`. O stub nunca vira texto de tela (`permitir_stub=False`). Qualquer exceção da camada vira template.

**Como o app deve chamar** (a integração no app é do outro agente):
```python
from src.llm import integracao as li
r = li.explicar_cenario(cenario)            # modo = SULCO_LLM_MODO (template|offline|online); padrão template
st.write(r["texto"]); st.caption(li.rotulo_origem(r))     # r["origem"] in {"template","llm"}; r["motivos"] explica a queda
r = li.responder_pergunta(pergunta)         # RAG: sem LLM devolve os trechos [n]; sem trecho => "sem evidência"
```
- Demo offline: `SULCO_LLM_MODO=offline` (o cache precisa ter sido gerado antes, com a mesma versão do prompt, provedor e modelo; mudar o cenário ou o prompt muda o hash e cai no template).
- `python -m src.llm.pregerar` (`--max N`): COM `DEEPSEEK_API_KEY` chama o provedor para cada cenário de `data/processed/cenarios/` e grava o cache; SEM chave imprime `{"feito": false, ...}` e não chama nada (verificado: nenhum arquivo criado).
- O cache guarda a saída bruta; o verificador roda de novo na leitura. Depois de gerar, commitar `data/processed/llm_cache/` (ainda NÃO existe: depende da chave).
- Pendente (não feito aqui): API (`src/api`) não foi tocada; basta chamar as mesmas duas funções.

## 2. L4: 20 perguntas estilo agricultor
`tests/l4_perguntas.py`: 15 positivas (cada uma com arquivo, página e frase literal conferidas por `pdftotext -f p -l p` contra o PDF; todas nos documentos novos: portarias ZARC, cartilhas Propaga Palma e dia de campo Embrapa) e 5 negativas (preço da saca, aftosa, mastite, cotação do feijão, queijo de coalho; a ausência foi checada por regex em `indice/trechos.jsonl`: 0 ocorrências). Escritas antes de ajustar a busca; **não usadas para calibrar nada**.
`python -m src.llm.avaliar_l4 [--provedor deepseek] [--indice bm25|hibrido]` mede: recuperação@5 (trecho esperado entre os devolvidos), citação [n] correta (todo [n] aponta para o arquivo+página esperados), "sem evidência" nas negativas, JSON do contrato válido e, só com chave, latência e custo (tokens do `usage` × tabela de preços do `docs/14` seção 2, faixa fora-do-pico..pico, é cálculo nosso).

Rodado com **stub + índice BM25** (valida o encanamento; NÃO mede LLM): recuperação@5 47% (7/15); citação correta 33% (5/15; o stub cita sempre o 1º trecho, então este número é do stub, não do DeepSeek); "sem evidência" nas negativas 100% (5/5); JSON válido 100%; latência média 0,01 s (sem rede, irrelevante). Recuperação híbrida (embeddings + reranker, sem LLM) nas 15 positivas: **73% (11/15)**; falhas: temperatura do caupi, fase da falta de água do caupi, "zoneamento considera praga e doença", controle de praga do algodão.
Com chave: rodar `python -m src.llm.avaliar_l4 --provedor deepseek --indice hibrido` e colar o JSON aqui. Latência e custo reais continuam **não medidos**.

## 3. R1/R2: RAG
**Documentos novos (19 PDFs reais em português, 31 → 50 no manifesto; `indice/` passou a 3.203 trechos):** 13 portarias ZARC do Ceará do MAPA (milho 1ª safra, milho consorciado com braquiária, algodão, feijão irrigado, feijão 2ª safra sequeiro, feijão-caupi, sorgo granífero, sorgo forrageiro, amendoim, girassol, mamona, palma forrageira, mandioca; de gov.br/agricultura, página "safra vigente" do Ceará); 1 publicação Embrapa Semiárido (dia de campo/unidades demonstrativas, via `www.infoteca.cnptia.embrapa.br`); 5 cartilhas do Projeto Propaga Palma/UFV-PDHC (palma forrageira). Manifesto: URL, data 2026-11-13, sha256 e título copiado da primeira página do próprio PDF (backup do manifesto antigo fora do repositório).
**Não conseguido:** Emater (nenhum PDF verificado), INSA (a cartilha em `gc.aksaam.ufv.br` não respondeu), EcoCrop paginado (só HTML), capítulo Embrapa "culturas anuais" (infoteca doc/1118488: PDF sem camada de texto, `pdftotext` devolve 0 palavras; sem OCR não entra).  As portarias contêm listas de municípios (tabelas numéricas descartadas pelo filtro de letras).
O teste de substring por página passa (ver seção 4).

**PT→EN sem LLM:** `src/rag/lexico_pt_en.py` (≈130 entradas de vocabulário agronômico geral, nenhuma com número ou fato) + uso em `busca.Indice(traduzir=True)` (padrão ligado): a tradução entra como consulta extra (BM25 e embedding, peso 0,5) e como portão lexical adicional (≥60% dos termos EN, mínimo 3 termos, só se ≥50% das palavras da pergunta têm tradução). Montado olhando só o DEV.

**Acerto top-5 (híbrido + reranker; conjuntos separados em `tests/rag_perguntas.py`)**
| Conjunto | Antes (índice novo, sem tradução) | Depois (com tradução) |
|---|---|---|
| DEV (21; usado para ajustar) | 57% (12/21) | 67% (14/21) |
| TESTE (25; não usado para ajustar) | 80% (20/25) | **88% (22/25)** |
| TESTE em português (22) | 91% | 91% |
| TESTE com documento em inglês (3) | 0% (0/3) | 67% (2/3) |
| DEV com documento em inglês (5) | 20% (1/5) | 60% (3/5) |
| L4 positivas (15, só avaliação) | 73% | 73% |
Honestidade: (a) o TESTE tem só 3 perguntas em inglês: 0/3→2/3 é indício, não prova; (b) vi o TESTE antes da tradução (baseline) e uma vez depois, sem iterar; (c) os documentos novos não mudaram o TESTE (80%→80% com o índice antigo vs novo; o índice antigo foi medido na rodada anterior): as portarias só são exercitadas pelas perguntas do L4, que são novas; (d) a meta de 80% no conjunto de 13 originais NÃO foi atingida: 69% (9/13); (e) falhas do DEV que continuam: "rotação segundo a FAO" (menos de 3 termos traduzíveis), "pragas e doenças pela rotação", "falta de água na floração", "pilares do plantio direto", "coquetel vegetal ... Vertissolo", "quantidade de palha", "zoneamento no seguro rural".
Só BM25 (sem embeddings) na L4: 47%; o híbrido é necessário.

## 4. Testes
`tests/test_llm.py`, `test_llm_integracao.py`, `test_rag_lexico.py`: 53 passam (`-W error`). `tests/test_rag.py`: 21 passam em 6 min 54 s (inclui substring de todo trecho na página do PDF, manifesto com sha256, 8 perguntas fora do acervo ⇒ "sem evidência"; só-BM25 no TESTE: 60%).

## 5. Pendências
- `data/processed/mvp/evidencias_rag.json` NÃO foi regenerado (o índice mudou: 3.203 trechos e tradução ligada). Há backup `evidencias_rag.json.bak`. Regenerar com `python -m src.app.precalculo evidencias` (~9 min) após aprovação.
- Chave DeepSeek: pré-gerar cache (`python -m src.llm.pregerar`), rodar `avaliar_l4 --provedor deepseek`, registrar latência/custo.
- Conferir os IDs de modelo (L5) e decidir DU9/DU10 antes de qualquer envio.
- `indice/` não é versionado (R5); `docs_rag/` cresceu (~PDFs novos) e o manifesto deve ir ao commit.
