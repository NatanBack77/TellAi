# 14. Camada LLM (`src/llm/`)

Atualizado em 2026-11-12. Sem LangChain. Regras 3, 4 e 6 do docs/01: o LLM só reescreve JSON + trechos [n]; nunca calcula, escolhe rotação nem prevê clima; sem trechos => "sem evidência"; nenhum dado sensível a API externa.

## 1. Estado
**Pronto (35 testes em `tests/test_llm.py`, sem rede, sem reranker):**
- `provedores.py`: interface `gerar(sistema, usuario)`; `Stub` (determinístico) e `DeepSeek` (sem chave => `ProvedorIndisponivel`, mensagem clara; erros HTTP mapeados sem vazar a chave).
- `servico.reescrever(cenario_json, trechos)` e `servico.responder(pergunta)`; ambos devolvem `{texto, origem: llm|template|sem_evidencia|recusa, motivos, provedor, em_cache}`.
- `verificador.py`, `seguranca.py`, `cache.py`.

**Parcial:**
- DeepSeek só testado com transporte falso (nenhuma chamada real: a chave não existe). Formato real do corpo de erro NÃO está na doc (a página de erros só lista códigos); o código usa só o código HTTP.
- `responder` usa por padrão `Indice(usar_embeddings=False, rerank=False)` (BM25 + portão lexical; poupa RAM). Com embeddings o portão de cosseno muda de comportamento: não foi reavaliado aqui.
- Não rodei `responder` contra o índice real (só com busca simulada).
- Latência e custo reais não medidos.

**Faltando:** integração ao app (src/app não foi tocado) e à API; geração de cache para o demo; avaliação das 20 perguntas com LLM real.

## 2. DeepSeek: o que foi verificado
Lido em 2026-11-12 (via ferramenta de leitura de páginas, que resume o conteúdo):
- https://api-docs.deepseek.com/ : base_url OpenAI `https://api.deepseek.com`; endpoint `POST /chat/completions`; `Authorization: Bearer <chave>`; modelos `deepseek-flash` (DeepSeek-V4.1-Flash-1017) e `deepseek-v4-pro`; nomes antigos `deepseek-v4-flash` ainda aceitos (servidos pelo Flash).
- https://api-docs.deepseek.com/quick_start/error_codes : 400, 401, 402 (saldo), 422, 429, 500, 503. Formato do corpo de erro: não mostrado.
- https://api-docs.deepseek.com/api/create-chat-completion : `temperature` 0–2 (sem efeito em modo thinking), `max_tokens` 1–393216, `thinking.type` enabled|disabled, `response_format` text|json_object, `usage` com prompt/completion/total_tokens.
- https://api-docs.deepseek.com/quick_start/pricing : contexto 1M, saída máx. 384K; preço por 1M tokens, deepseek-flash: entrada cache miss US$0,15 (fora do pico) / 0,30 (pico), cache hit 0,003 / 0,006, saída 0,60 / 1,20. Pico: 01-04 e 06-10 UTC, seg-sex, exceto feriados chineses.
- Latência: a doc lida não informa números. Não afirmo nenhum.
Uso no código: modelo `deepseek-flash` (troque com `DEEPSEEK_MODEL`), `temperature=0`, `thinking: disabled`, `max_tokens=900`. Confirme os IDs na doc antes de ligar: a leitura foi resumida por ferramenta e os IDs mudam.

Custo estimado (cálculo meu, não da doc): uma chamada de ~2.000 tokens de entrada e ~400 de saída no Flash, em pico e sem cache, = 2000×0,30/1e6 + 400×1,20/1e6 = US$0,00108. Os tamanhos de token são suposição.

## 3. Como ligar a chave
1. Crie a chave em platform.deepseek.com/api_keys.
2. Acrescente ao `.env` (já no .gitignore, nunca commitar): `DEEPSEEK_API_KEY=...`
3. `SULCO_LLM=deepseek` (ou `provedores.obter("deepseek")`). Sem chave, o serviço usa o template (`origem: "template"`, motivo explica).
4. Para demo offline: gere o cache online com `Cache()` (pasta `data/processed/llm_cache/`) e rode com `offline=True`: só lê o cache; falha de cache => template. O stub não grava cache.

## 4. Como o verificador barra violações (`verificador.py`, sem LLM)
Falhou qualquer item => saída descartada, devolve template (`src.app.logica.explicar`) com os motivos em `motivos`:
- todo número do texto (fora dos [n]) aparece no JSON enviado ou nos trechos; tolera `0,35`/`0.35`/`1.234,5`; com casas decimais aceita arredondamento da fonte (ex.: 0,4 para 0,35); inteiro tem de ser exato; porcentagem derivada (35% de 0,35) é barrada;
- números por extenso (dois, dez, mil...) só se a palavra estiver na fonte;
- todo [n] existe entre os trechos enviados; exige ao menos uma citação quando há trechos;
- promessas proibidas (rende mais, garante, lucro, aumenta a renda, dobra, com certeza, 100%...), inclusive em negação (conservador);
- aviso "a avaliar com técnico local" presente; limite de 3.000 caracteres.
Limitação: verifica forma e números, não a verdade semântica de uma frase (um modelo pode citar [1] para algo que o trecho não diz). Por isso o prompt é restrito e o template é o padrão seguro.

## 5. Injeção e dados sensíveis
- Prompt de sistema fixo (`servico.SISTEMA`); trechos e pergunta entram em blocos delimitados como dados; `<<<`/`>>>` removidos do texto.
- Pergunta com padrão de injeção ("ignore as regras", "invente", "prompt do sistema", "finja") => recusa sem chamar o LLM. Pedido de previsão do clima/escolha de rotação => recusa e remete ao app.
- Trecho do PDF com padrão de injeção não vai ao modelo.
- Antes de enviar: remove coordenadas e identificação do JSON (lat, lon, agricultor, cpf, telefone...); pergunta tem e-mail/CPF/telefone redigidos. O nome do município e o texto da pergunta ainda vão à API: decisão sua.
- Os padrões são regex em português/inglês: um ataque reformulado pode passar da triagem, mas ainda terá de passar pelo verificador.

## 6. Decisões pendentes do usuário
1. Enviar nome do município e a pergunta à DeepSeek (API externa, servidores fora do Brasil) é aceitável? Se não, mantenha o stub/template.
2. Embeddings no `responder` (mais recall, ~RAM do e5) ou só BM25?
3. Refusar "qual rotação devo escolher" é a leitura da regra 3; confirme.
4. Aceitar rejeição conservadora de "garante"/"lucro" mesmo em negação.

## 7. Próximos passos (em ordem)
1. Criar a chave, pôr no `.env`, rodar 5 cenários reais com `deepseek` e ver quantos são rejeitados (`motivos`).
2. Rodar as 20 perguntas estilo agricultor com `responder` + índice real; medir citações corretas.
3. Integrar ao app: em `src/app` chamar `servico.reescrever(cenario, provedor=obter(), cache=Cache(), offline=True)` e mostrar `origem`; manter o template como padrão.
4. API: expor `responder` e `reescrever` com o mesmo contrato `{texto, origem, motivos}`.
5. Pré-gerar o cache dos cenários do demo (fase A6) e commitar `data/processed/llm_cache/`.
6. Medir latência/custo reais e registrar aqui.
