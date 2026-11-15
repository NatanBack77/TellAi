# 30. Segurança da camada de IA (modelo de ameaças, guardrails, red team)

**ESTADO: PARCIAL.** Código dos guardrails, 350+ testes e auditoria feitos; 11 testes novos ainda falham (lista na seção 7); os filtros AINDA NÃO estão ligados ao pipeline (cabe a quem edita `chat.py`/`conversa.py`/`main.py`; seção 6).

Referência: OWASP Top 10 for LLM Applications 2025 (página aberta: https://genai.owasp.org/llm-top-10/ — LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM04 Data and Model Poisoning, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM08 Vector and Embedding Weaknesses, LLM09 Misinformation, LLM10 Unbounded Consumption).

## 1. Ativos
Chave DeepSeek e `.env` (lido só por `src/llm/provedores.py:ler_chave_env` e `src/llm/ambiente.py`); PIN da voz (`SULCO_VOZ_PIN`); credenciais Earthdata (só coleta); caminhos e infraestrutura; prompts do sistema (`chat.SISTEMA_CHAT`, `conversa.SISTEMA_CONVERSA`, `servico.SISTEMA`); dados internos de engenharia (docs, hipóteses, nomes de agentes, custo); identificadores do agricultor (município, lat/lon, ponto_id, IBGE); estado da conversa (JSON devolvido pelo cliente); caches (`data/processed/llm_cache*`); contador de gasto.

## 2. Modelo de ameaças (controle de hoje, lacuna, severidade, correção)
| # | Ameaça (OWASP) | Controle hoje | Lacuna | Sev. | Correção |
|---|---|---|---|---|---|
| A-01 | Injeção direta (LLM01) | `seguranca.py:16-23,38` (regex PT/EN, sem homóglifos/zero-width/letras separadas/base64); `conversa.py:354`; `chat.py:validar_pergunta` | Teste: 20 ataques reais chegam ao modelo no `/chat` (chave, PIN, `.env`, arquivos, dose, coordenadas, script, gasto, empréstimo, modelo/deepseek) e 6 na `/conversa` | ALTA | `guardrails.filtrar_entrada` (normaliza NFKC, homóglifos, leet, compacto, base64/hex/URL/reverso, idioma, acúmulo multi-turno) |
| A-02 | Injeção INDIRETA em trecho/PDF/fato (LLM01/08/04) | `servico.py:_trechos_limpos` descarta trecho inteiro por regex fraca; `seguranca.neutralizar` só tira `<<`/`>>` | sem homóglifos; sem checar `pode_citar_ao_agricultor`; `arquivo=` vai ao prompt | ALTA | `guardrails.preparar_trecho/filtrar_contexto/bloco_dado` (corta frases-ordem, remove delimitadores/tags/links/citações falsas, descarta interno) |
| A-03 | Vazamento do prompt do sistema (LLM07) | prompt diz "não revele" só em texto; nada confere a saída | modelo pode copiar | ALTA | canário `G.CANARIO` + `vazou_prompt` (8 palavras seguidas) em `filtrar_saida` |
| A-04 | Segredos/paths/infra/custo na saída (LLM02) | `verificador.verificar` só checa números, promessas, termo técnico: **URL, e-mail, caminho, `DeepSeek`, nome de variável PASSAM** (provado: testes H00-H11) | nenhuma varredura de saída | ALTA | `guardrails.filtrar_saida` |
| A-05 | Força bruta do PIN da voz (LLM10/acesso) | `voz.py` comparação em tempo constante; limite geral por IP | sem bloqueio por falhas: PIN de 4 dígitos em minutos | MÉDIA-ALTA | **CORRIGIDO** `voz.py:_exigir_pin` (8 falhas/IP em 5 min e 60 globais em 15 min => 429) |
| A-06 | Upload gigante / JSON gigante na voz (LLM10) | `validar_wav` só depois de `await request.body()` inteiro | memória | MÉDIA | **CORRIGIDO** `voz.py:_ler_corpo` (para ao passar do limite; `/falar` máx. 16 KiB; JSON não-objeto vira 400 e não 500) |
| A-07 | Saída insegura em HTML/XSS (LLM05) | páginas `/voz` e `/teste` usam só `textContent` (testado, sem innerHTML/eval) | sem CSP/nosniff/frame-ancestors | MÉDIA | **NOVO** `src/api/cabecalhos_seguranca.py` (ligar: seção 6) |
| A-08 | Exfiltração de outros usuários / cache compartilhado | cache por hash do prompt (sistema+usuário), sem IP; teste prova que nada pessoal é gravado na `/conversa` | `/chat` SEM ponto: nome de município na pergunta vai à DeepSeek (achado F-01 abaixo) | MÉDIA | usar `redigir_mensagem` (que remove municípios) no `chat.py` em vez de só `redigir_pergunta` |
| A-09 | DoS de carteira (LLM10) | teto de tokens 600, 100 chamadas/dia, `MAX_TOKENS` 260/300, rate limit 20/min nas rotas de IA, voz com teto diário | rate limit na memória do processo; sem teto por IP/dia; `X-Forwarded-For` ignorado por padrão (ok) | MÉDIA | teto diário por IP (aberto) |
| A-10 | Metadados na resposta da API | `ChatOut/ConversaOut` devolvem `motivo` ("sem chave (DEEPSEEK_API_KEY) no .env", limite diário), `provedor`, `modelo`, `uso`, `fatos[].origem` (função/arquivo), `trechos[].arquivo` | revela infra e estado de gasto | MÉDIA | em produção zerar `motivo/uso/provedor/modelo/origem` (aberto; mudança de contrato) |
| A-11 | Endpoints sem autenticação | `/chat/gasto`, `/chat/estado`, `/docs`, `/openapi.json`, `/teste` abertos | revela gasto, modelo, schema | MÉDIA | proteger por PIN ou desligar em produção (`docs_url=None`) (aberto) |
| A-12 | Erro com detalhe interno | `main.py:402` devolve `e.__class__.__name__: {e}`; `main.py:345` classe da exceção | texto de exceção ao cliente | BAIXA | mensagem fixa (aberto) |
| A-13 | Aconselhamento arriscado (LLM09) | verificador barra promessas/números fora da fonte; `chat.py`/`conversa.py` recusam lucro/clima | agrotóxico/dose, crédito, jurídico, saúde chegam ao modelo | MÉDIA | `filtrar_entrada` (categorias agrotoxico, financeiro, juridico, medico) e `filtrar_saida` estrito |
| A-14 | Excesso de agência (LLM06) | o modelo não tem ferramentas nem escreve em disco; só devolve texto verificado | nenhuma (manter assim) | OK | não adicionar function calling sem revisão |
| A-15 | Cadeia de suprimento / envenenamento do índice (LLM03/04) | acervo é versionado (`docs_rag/manifesto.json`) | novo índice `src/rag/projeto.py` vindo de docs internos | ALTA quando ligado | exigir `pode_citar_ao_agricultor` explícito (`exigir_marca=True`) + `filtrar_contexto` |
| A-16 | LGPD: dados pessoais e voz | `seguranca.redigir_mensagem` remove e-mail/CPF/telefone/CEP/coordenada/município na `/conversa`; voz: áudio vai à DeepSeek e a página avisa; nada em disco | `/chat` não remove município (A-08); sem política escrita de retenção | MÉDIA | ver A-08; documentar retenção |
| A-17 | Logs com dado sensível | `conversa`/`chat` não registram mensagem (teste); `guardrails.registrar` loga só categoria e regra | `limite_taxa` sem log; erros de `main.py` (A-12) | BAIXA | — |
| A-18 | Estado da conversa forjado | `dialogo.normalizar_estado` filtra por ids conhecidos (teste: injeção no estado não chega ao prompt) | sem teto de bytes/profundidade | BAIXA | `guardrails.verificar_estado` (ligar em `rota_conversa`) |
| A-19 | CORS / cabeçalhos | sem CORS (testado: nenhuma origem permitida); sem cabeçalhos de segurança | — | MÉDIA | A-07 |
| A-20 | `.gitignore`/Docker | `.env` ignorado no git e no Docker | faltavam `*.pem`, `*.key`, `.netrc`, `llm_cache_conversa/`, `gasto*.json` | MÉDIA | **CORRIGIDO** `.gitignore` (bloco final "segredos e dados de IA"; `data/processed/llm_cache_conversa/` estava aparecendo como não rastreado) |

Achados de auditoria que mereciam destaque: **F-01** `/chat` sem `ponto_id` envia o nome do município escrito na pergunta à DeepSeek (provado em `test_payload_do_chat_tambem_e_anonimo`); **F-02** a saída do modelo com URL, e-mail, caminho, `DeepSeek`, `DEEPSEEK_API_KEY`, `/chat/gasto` chega ao agricultor nos dois pipelines (testes `H00-H11`, marcados `xfail` FALHA HOJE); **F-03** `rede bloqueada` no `conftest.py` e chave falsa estão corretos (testes passam).

## 3. O que foi criado e corrigido
- `src/llm/guardrails.py` (novo, puro): `filtrar_entrada`, `classificar_entrada`, `preparar_trecho`, `filtrar_contexto`, `bloco_dado`, `limitar_prompt`, `sistema_com_canario`, `verificar_estado`, `valor_permitido`, `filtrar_saida`, `vazou_prompt`, `garantir_fecho`, `seguro_para_exibir`, `registrar` (só categoria), `RECUSAS`, limites `MAX_*`. Respostas de recusa curtas, em português simples, sem LLM.
- `src/api/cabecalhos_seguranca.py` (novo): `aplicar_cabecalhos(resposta, caminho)` (nosniff, X-Frame-Options, Referrer-Policy, CSP, no-store nas rotas de IA).
- `src/api/voz.py`: bloqueio de PIN (`_exigir_pin`, `_FALHAS`), leitura limitada do corpo (`_ler_corpo`), JSON não-objeto. `tests/test_voz.py` segue passando (23).
- `.gitignore`: segredos e caches de IA.
- `tests/test_guardrails.py` (novo): 100+ casos de entrada bloqueada, 34 legítimos, 80 de saída, 20+ de contexto/estado, pipeline real com provedor obediente (xfail "FALHA HOJE" não estrito + teste irmão provando que o guardrail pega), auditoria (payload, cache, logs, páginas, PIN, CORS, gitignore, rede).

## 4. Política de domínio (código)
Nunca dose/produto de agrotóxico; nunca promessa de lucro, produtividade ou clima futuro; sem aconselhamento financeiro/jurídico/médico; sempre fecho "Converse com o técnico" (`garantir_fecho`). Entrada barra o pedido; saída barra o texto do modelo.

## 5. Limites
Entrada 400 letras (bruta 2000), saída 1500 caracteres, prompt 12.000, estado 16 KB/profundidade 8/400 nós, 60 turnos. Já existentes: 600 tokens, 100 chamadas/dia, rate limit pesado 20/min (confirmado em teste para `/chat`, `/conversa`, `/calendario`, `/voz/transcrever|falar`).

## 6. PONTOS DE INTEGRAÇÃO (eu não editei chat/conversa/fatos/main)
1. **Entrada, `src/llm/conversa.py:_conversar`**, logo depois de `msg = _norm_msg(mensagem)` (linha ~352): 
   `v = G.filtrar_entrada(msg); if not v.ok: return _saida(v.resposta, est0, "recusar", origem="recusa", motivo=f"guardrail:{v.categoria}", chips=D.CHIPS_INICIO)` (`from . import guardrails as G`).
2. **Entrada, `src/llm/chat.py:validar_pergunta`**, antes de `classificar_pergunta(p)`: `v = G.filtrar_entrada(p); if not v.ok: return None, v.categoria, v.resposta`.
3. **Privacidade do `/chat`, `chat.py:_responder`, linha `p_env = redigir_pergunta(...)`**: trocar por `redigir_mensagem(_fatos.anonimizar(p, privado))` (remove município; corrige F-01).
4. **Contexto, `chat.py:_limpar_trechos`**: `out = G.filtrar_contexto(_serv._trechos_limpos(trechos), exigir_marca=False, max_chars=MAX_TRECHO_CHAT)`; para o novo índice `src/rag/projeto.py`/`conhecimento.py`: `G.filtrar_contexto(itens, exigir_marca=True)` e montar com `G.bloco_dado("projeto", itens)`. Em `servico._bloco_trechos` não enviar `arquivo=`.
5. **Fatos, `fatos.py:selecionar`/`bloco_fatos`**: `G.filtrar_contexto(fatos, campo="texto_simples")`.
6. **Prompt do sistema**: `SISTEMA_CHAT = G.sistema_com_canario(SISTEMA_CHAT)` e idem `SISTEMA_CONVERSA`; antes de `prov.gerar(...)` em `chat._gerar` e `conversa._gerar`: `usuario = G.limitar_prompt(usuario)`.
7. **Saída, `chat.py:_responder` e `conversa.py:_responder_com_fatos`**, logo após `verificar(...)` aprovar e antes do fecho: `s = G.filtrar_saida(saida, sistema=SISTEMA_CHAT, ids_privados=[privado.get("ponto_id")] if privado else None, nomes_municipios=[n for _, n in municipios_do_projeto()]); if not s.ok: return so_template("guardrail:saida " + ",".join(s.motivos), ...)` (usar `final(padrao, ...)` na conversa). Passar também o texto padrão por `G.filtrar_saida(..., estrito=False)`.
8. **Estado, `src/api/rota_conversa.py:conversa`**, antes de `C.conversar`: `if (p := G.verificar_estado(req.estado)): raise HTTPException(422, "estado inválido")`.
9. **Cabeçalhos, `src/api/main.py`**, depois do middleware `limitar_taxa`: `from src.api.cabecalhos_seguranca import aplicar_cabecalhos` e `@app.middleware("http") async def cab(request, call_next): return aplicar_cabecalhos(await call_next(request), request.url.path)`.
10. **Produção**: `FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)` via `SULCO_DOCS`; proteger `/chat/gasto`, `/chat/estado`, `/teste`; zerar `motivo/uso/provedor/modelo/fatos[].origem` nas respostas públicas; `main.py:402` e `:345` sem `{e}`.
Depois de ligar, os testes `test_hoje_*` marcados xfail passam a verde sozinhos.

## 7. O que NÃO deu tempo / resultado dos testes
Rodada final de `tests/test_guardrails.py` com `-W error`: **342 passam, 25 xfail (FALHA HOJE, esperados), 11 FALHAM** (honesto, não corrigidos):
- E017 ("meus comandos valem mais...") cai em `prompt`, não `injecao`; E060 (".env", "abra config.yaml") cai em `segredo`; E073 (`../../etc/shadow`) vira `vazia` (poucas letras): expectativas de categoria do teste, o bloqueio acontece. 
- `test_delimitadores_tags_links...`: a frase com `system:` e `<|im_start|>` arrasta o resto e o filtro corta "milho" junto (frases coladas sem pontuação): ajustar `_frases` ou o teste.
- `test_bloco_dado...`: o `AVISO_DADO` também contém "<<<DADO", então a contagem do teste (2) vem 3: erro do teste.
- S17: "Meu zap é +55 88 98888-7766." não é pego por `_FONE` (**lacuna real do guardrail**, corrigir regex).
- `test_vazou_prompt...`: janela de 6 palavras versus normalização do fecho; ajustar teste.
- X05: "Minhas regras dizem..." passa em `filtrar_saida` (ainda não há padrão para "minhas regras"/"meu prompt" sem canário); lacuna do guardrail (baixa).
- `test_payload_enviado_a_ia...`: falha por `html_tag`/`longa_demais` ao varrer o prompt inteiro com o filtro de saída (os delimitadores `<<<` do prompt): erro do teste; `test_payload_do_chat...` é o achado real **F-01**.
- `test_nenhum_segredo_versionado_no_codigo`: padrão `sk-abcdefghijklmnopqrstuvwxyz` achado em `tests/test_rag_agronomia.py` (exemplo de teste, não chave real; ampliar a lista de exceções).
Rodados com -W error: `test_voz.py` + `test_limite_taxa.py` + `test_sem_rede.py` = 41 passam. **Não rodados**: `test_seguranca*.py`, `test_chat*.py` (coordenador pediu parar; rodar antes de integrar).
Não feito: teto diário por IP; teste de upload multipart real; revisão de `src/rag/projeto.py` (ainda não existe); política de retenção LGPD escrita; revisão de `calendario_conversa.py`; casos de red team de áudio (ASR) e de homóglifos além do cirílico/grego.
