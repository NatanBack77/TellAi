# 14. Camada LLM (`src/llm/`)

Atualizado em 2026-11-12; estado da integração e contagens revisados em 2026-11-14. Sem LangChain. Regras 3, 4 e 6 do docs/01: o LLM só reescreve JSON + trechos [n]; nunca calcula, escolhe rotação nem prevê clima; sem trechos => "sem evidência"; nenhum dado sensível a API externa.

## 0. Chat "Pergunte ao Sulco" (2026-11-14)
Núcleo `src/llm/chat.py` (`responder_chat`), rotas `POST /chat` e `GET /chat/estado`, página do app, `src/llm/ambiente.py` (carrega o `.env`), `python -m src.llm.testar_chave`. Detalhes, verificação na doc oficial e riscos: `docs/21_resultados_fases/CHAT_DEEPSEEK.md`. Isto SUPERA os itens "app e API NÃO importam `src.llm`" e "nenhuma integração" da seção 1 abaixo. Trava de gasto: teto de 600 tokens de saída, 100 chamadas reais/dia (`SULCO_LLM_MAX_CHAMADAS_DIA`), contador em `data/processed/llm_cache/gasto.json`.

### 0.1 Folha de fatos do local e fonte "sobre o Sulco" (2026-11-14)
O chat tem TRÊS fontes, todas montadas por código (nenhum texto digitado de memória):
- **Folha de fatos do local** (`src/llm/fatos.py`, ids `[F1]`, `[F2]`...): previsão do NDVI do próximo composto (anomalia, faixa 80/90%, data do composto, último composto observado, fim do clima), skill histórico do modelo (seleção 2010-2021, confirmação selada 2022-2024, prospectivo 2025+, horizonte +1 a +4, cobertura real da faixa; lidos de `metricas.json`, `experimentos/prospectivo_2025/resultados.json` e `RESULTADO.md`), os LIMITES declarados da previsão, diagnóstico do local, os 3 caminhos do motor (faixa, P(top-3), empate técnico, cobertura de critérios, janela de plantio, lacunas e riscos), risco de solo, extremos, ETo e saldo chuva menos ETo, receita bruta por hectare (IBGE; "não é lucro"), ZARC por cultura, solo estimado (SoilGrids) e limites globais. Usa as MESMAS funções do app e da API (`src.api.main.previsao/limites`, `src.app.mvp`, `src.app.secao_*`, `src.culturas.zarc`); só formata (pt-BR, unidade) e declara a ORIGEM de cada fato. Sem dado = fato de LACUNA com o motivo (ex.: previsão ausente por "compostos anteriores não consecutivos"). Não há LLM nem cálculo novo nessa etapa.
- **Trechos do acervo** `[n]` (RAG, como antes) e **"sobre o Sulco"** (`src/llm/sobre_sulco.py`): glossário (`mvp.glossario_atual()` com os trechos de PDF que ele cita), página "Limites dos dados" (`mvp.limites_linhas()`, números lidos de arquivo; a página do app usa a mesma função), prioridades (`mvp.PRIORIDADES`), fluxo do cálculo (docstring de `mvp`) e títulos/docstrings das páginas e seções lidos de `app.py` por `ast`. Rótulo `arquivo = "sobre o Sulco: ..."`. Entra no chat junto com o RAG, em índice léxico próprio (não dentro do índice BM25/embeddings dos PDFs); portão estrito: termo do glossário só vale se todas as suas palavras estão na pergunta; documentos gerais só se a pergunta é sobre o próprio Sulco.
Roteamento (determinístico): pergunta de definição ("o que é...") ou sobre o app => "sobre o Sulco"; pergunta sobre dados do local (palavras-chave por tema em `fatos.PADROES`; palavras comuns como "chuva"/"solo" só contam se a pergunta fala do SEU local) => só os fatos relevantes, até 1.400 tokens (estimativa 3 caracteres por token); senão => RAG; sem nada => "sem evidência" sem chamar a IA. Sem `ponto_id` (usuário só conversa), só acervo e "sobre o Sulco". O LLM só REESCREVE citando `[F#]`/`[n]`; o verificador valida os dois tipos de citação e exige que todo número do texto exista nos fatos/trechos CITADOS (pt-BR tolerado). Pergunta de previsão ("como vai ficar a vegetação nas próximas semanas?") é respondida com os fatos da previsão e seus limites; lucro/rotação a escolher continuam recusados. Texto padrão (IA desligada ou rejeitada pelo verificador) = os próprios fatos em frases, sem JSON nem rótulos técnicos.
Privacidade: os fatos não têm nome do município, `ponto_id`, IBGE, latitude nem longitude (dizem "este local"); o nome na pergunta vira "o seu município"; antes de enviar há uma trava (`fatos.vazou`) e, se algo escapar, não há envio. Custo e tamanho: ver `docs/21_resultados_fases/CHAT_DEEPSEEK.md`.

### 0.2 Respostas simples e texto sem marcadores (2026-11-14, rodada 3)
O público é o agricultor do semiárido: a resposta tem de ser SIMPLES, CURTA e OBJETIVA. `fatos.py`: cada fato tem `texto_simples` (modelo de frase, sem LLM, sem número novo) que vai ao prompt e ao texto padrão; `texto` técnico e `origem` seguem na API para conferência. `chat.py`: prompt `chat-v3` (até ~70 palavras, sem siglas, tabela de tradução, fecho "converse com o técnico"). `verificador.py`: `verificar(..., tom=True)` barra mais de 110 palavras e termos técnicos sem tradução (NDVI, anomalia, composto, faixa de incerteza, skill, RMSE, ACI, sorteios, persistência, empate técnico...), aceita "duas semanas"/"três caminhos" quando o item está nas fontes e "cerca de 600" para número redondo da fonte; `limpar_citacoes` remove [F#]/[n] DEPOIS da verificação: a API devolve `resposta` (limpa) e `resposta_com_citacoes` (verificada). Texto padrão: no máximo 5 linhas. Guia de estilo, tabela termo técnico => palavra simples e exemplos antes/depois: `docs/21_resultados_fases/CHAT_DEEPSEEK.md` (última seção). Testes: `tests/test_chat_simples.py`.

## 1. Estado
**Pronto (sem rede, sem reranker; contagem de testes COLETADOS por `.venv/bin/python -m pytest --collect-only -q` em 2026-11-14: `tests/test_llm.py` 35, `tests/test_llm_integracao.py` 14, `tests/test_rag_lexico.py` 4):**
- `provedores.py`: interface `gerar(sistema, usuario)`; `Stub` (determinístico) e `DeepSeek` (sem chave => `ProvedorIndisponivel`, mensagem clara; erros HTTP mapeados sem vazar a chave; `ultimo_uso` guarda o `usage`).
- `servico.reescrever(cenario_json, trechos)` e `servico.responder(pergunta)`; ambos devolvem `{texto, origem: llm|template|sem_evidencia|recusa, motivos, provedor, em_cache}`.
- `verificador.py`, `seguranca.py`, `cache.py`.
- `integracao.py` (L2/L3, `docs/21_resultados_fases/L_R.md` seção 1): `explicar_cenario(cenario, modo)`, `responder_pergunta(pergunta, modo)` e `rotulo_origem(r)`. Modo por `SULCO_LLM_MODO` = `template` (padrão) | `offline` (lê só o cache de demo; sem cache cai no template) | `online` (provedor real com chave). O template é sempre o padrão; o stub nunca vira texto de tela; qualquer exceção vira template. `pregerar.py` (`python -m src.llm.pregerar`) grava o cache só com chave; sem chave imprime `{"feito": false}` e não chama nada.
- L4 (`tests/l4_perguntas.py`, `python -m src.llm.avaliar_l4`): 15 perguntas positivas e 5 negativas. Medido só com stub + BM25: recuperação@5 47% (7/15), "sem evidência" 5/5; híbrido sem LLM: 73% (11/15). Fonte: `docs/21_resultados_fases/L_R.md` seção 2. Não mede LLM.

**Estado da integração (conferido em 2026-11-14 por busca no código):**
- (SUPERADO pela seção 0: o app e a API importam `src.llm.chat`; o item abaixo vale só para `integracao.explicar_cenario`, que o app ainda não usa.) `src/app/*.py` e `src/api/main.py` NÃO usavam `explicar_cenario`.
- `data/processed/llm_cache/` NÃO existe (depende da chave); portanto o modo `offline` hoje cai sempre no template.
- Nenhuma chamada real ao DeepSeek foi feita (a chave não existe). Só testado com transporte falso. Formato real do corpo de erro NÃO está na doc (a página de erros só lista códigos); o código usa só o código HTTP.
- `responder` usa por padrão `Indice(usar_embeddings=False, rerank=False)` na camada de serviço (BM25 + portão lexical; poupa RAM); com embeddings o portão de cosseno muda de comportamento e não foi reavaliado aqui.
- Latência e custo reais não medidos.

**Faltando:** ligar `integracao` ao app e à API; gerar o cache para o demo (precisa da chave); avaliação das 20 perguntas com LLM real; decisões DU9/DU10 antes de qualquer envio.

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
3. Integrar ao app (NÃO feito): em `src/app` chamar `integracao.explicar_cenario(cenario)` e mostrar `integracao.rotulo_origem(r)`; manter o template como padrão.
4. API: expor `responder` e `reescrever` com o mesmo contrato `{texto, origem, motivos}`.
5. Pré-gerar o cache dos cenários do demo (fase A6) e commitar `data/processed/llm_cache/`.
6. Medir latência/custo reais e registrar aqui.
