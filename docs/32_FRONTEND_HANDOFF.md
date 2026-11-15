# 32. Passagem para o front-end (Codex)

Atualizado em 2026-11-15. Este documento diz o que o front-end pode contar do servidor, o que ele não pode fazer e quem edita o quê. Os caminhos abaixo vieram da lista real de rotas do servidor em execução (`/openapi.json`). O formato exato de cada corpo está em `docs/12_API.md` e nos modelos Pydantic de `src/api/` (`rota_conversa.py`, `rota_calendario.py`, `main.py`, `voz.py`); confira lá antes de codificar.

## 1. Como subir o servidor para desenvolver
- API completa + voz (HTTPS, necessário para o microfone do celular): `.venv/bin/uvicorn src.api.voz_app:app --host 0.0.0.0 --port 8443 --ssl-keyfile <chave.pem> --ssl-certfile <cert.pem>` (certificado autoassinado; gerar com `openssl`; **nunca versionar** `.pem`).
- API sem voz, em HTTP: `.venv/bin/uvicorn src.api.main:app --port 8000`.
- Chaves e PIN ficam no `.env` (não versionado). **O front-end nunca recebe nem guarda a chave da IA.** O PIN da voz (`SULCO_VOZ_PIN`) vai no cabeçalho `X-Voz-Pin` das rotas `/voz/*`.

## 2. Rotas disponíveis
| Rota | Método | Para quê |
|---|---|---|
| `/saude` | GET | verificação de vida |
| `/municipios` | GET | lista de municípios do Ceará (nome e id) |
| `/diagnostico/{ponto_id}` | GET | retrato do local: solo descoberto, estresse, estação chuvosa, veranico |
| `/cenarios` | POST | três caminhos de rotação para um local e uma cultura atual |
| `/cenarios/clima` | POST | cenário "e se" (chuva e temperatura) |
| `/rotacao`, `/plano` | POST | sequências de safras e proposta de plano |
| `/zarc/{ponto_id}/{cultura_id}` | GET | janela do zoneamento por decêndio |
| `/solo/{ponto_id}` | GET | solo estimado (mapa global, não análise) |
| `/modelo/previsao/{ponto_id}` | GET | previsão do verde para o próximo composto de 16 dias, com faixa |
| `/evidencias` | GET | trechos dos documentos (com arquivo e página) |
| `/limites` | GET | o que o Sulco não vê |
| `/chat` | POST | pergunta única (sem memória) |
| `/conversa` | POST | **conversa com memória do estado** (a principal): ver seção 3 |
| `/plano-plantio` | POST | **plano de plantio em 10 etapas** para um local e uma cultura (contrato em `docs/34`); `GET /plano-plantio/culturas` e `/plano-plantio/etapas` |
| `/calendario` | POST | cálculo do calendário de plantio do agricultor |
| `/voz/transcrever` | POST | áudio WAV → texto (DeepSeek); cabeçalho `X-Voz-Pin` |
| `/voz/falar` | POST | texto → áudio WAV; JSON `{texto, motor}`; `motor: "kokoro"` (voz da Dora, local) |
| `/voz/estado` | GET | gasto do dia da voz (precisa do PIN) |

Não usar no front de produção: `/chat/gasto`, `/chat/estado` (internas) e `/docs`.

## 3. A conversa (`POST /conversa`)
- **O servidor não guarda a conversa.** O front envia `estado` de volta a cada turno exatamente como recebeu, sem editar.
- Corpo: `{ mensagem, estado | null, ponto_id, cultura_atual, perfil }`.
- Resposta (campos que o front deve usar): `resposta` (texto, sem marcadores de citação), `estado`, `acao` (`responder` | `perguntar` | `confirmar` | `recusar`), `chips` (botões de resposta rápida: `{rotulo, texto}`; ao tocar, enviar `texto` como a próxima mensagem), `pede` (o que está sendo perguntado), `fontes` (para "De onde veio esta resposta"), `origem`, `assistente`, e `calendario` quando houver plantios.
- A assistente se chama **Maíra** e se apresenta como **automática, não pessoa nem técnica**. O front deve mostrar isso de forma visível e não esconder.

## 4. Regras do produto que o front não pode quebrar
1. **Nada de número inventado.** Só mostrar o que veio da API. Lacunas aparecem como lacuna ("sem dado"), nunca preenchidas.
2. **Não prometer** lucro, colheita, rendimento nem clima futuro. A frase "converse com o técnico" fica à vista.
3. **Não dizer qual rotação é melhor.** Os caminhos são **comparados**; quando a API diz "empate técnico", a tela diz isso.
4. **Texto vindo do modelo só entra como texto** (`textContent`, nunca `innerHTML`, `eval` ou `document.write`). Há teste que reprova isso em `src/api/pagina_voz.py`.
5. Nenhuma chave, PIN, caminho de arquivo ou identificador interno em tela, log ou URL. Não guardar mensagens do usuário no navegador além da sessão.
6. Linguagem simples: público de baixa escolaridade e baixa familiaridade digital; botões grandes; uma pergunta por vez.
7. Aviso de privacidade da voz: o áudio de `/voz/transcrever` vai à DeepSeek; a fala da Dora é gerada no servidor.

## 5. Quem edita o quê
- **Codex (front-end):** diretório novo `frontend/` (ou o que for combinado) e, se quiser, `src/api/pagina_voz.py` e `src/api/pagina_teste.py` (páginas de teste servidas pelo próprio servidor), mantendo as regras da seção 4 e os testes `tests/test_voz.py` e `tests/test_pagina_teste.py` verdes.
- **Claude (back-end):** `src/llm/`, `src/culturas/`, `src/rag/`, `src/api/main.py`, `voz.py`, `rota_*.py`, dados e testes dessas partes. Mudança de contrato (campo novo, rota nova) é pedida aqui e eu faço.
- **Ninguém mexe em:** `.env`, `data/`, certificados, `indice/`.

## 6. O que ainda falta no back-end para um front separado (pedidos abertos)
- **CORS:** o servidor ainda **não** libera outro endereço. Antes de um front em outra origem funcionar, será preciso incluir CORS com lista de origens por variável de ambiente (`SULCO_CORS_ORIGENS`). Se o front for servido pelo mesmo servidor/proxy, não precisa.
- **Proxy único** (Nginx) para `/api`, `/voz` e o front: planejado, não feito.
- **Imagem Docker:** não construída ainda; ver `docs/23_REQUISITOS_PRODUCAO_DOCKER.md`.
- **Primeira pergunta de cada município** leva ~25 s (montagem da ficha); o front deve mostrar "estou olhando os dados do seu local" e não travar.
- **Ainda não validado com agricultores nem técnicos.**

## 7. Como testar
`.venv/bin/python -m pytest -q -W error tests/test_voz.py tests/test_pagina_teste.py tests/test_api.py` (a suíte bloqueia a rede e usa chave falsa; **nunca** chamar a DeepSeek em teste).
