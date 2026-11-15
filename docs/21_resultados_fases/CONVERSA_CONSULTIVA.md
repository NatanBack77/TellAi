# Conversa consultiva (o agricultor não fica preso a uma cultura)

Estado: código e testes prontos (2026-11-14); **falta só ligar no app e na API** (seção 2). Regras de `docs/01_VISAO_GERAL.md` (3, 4 e 6) e de `docs/14_LLM.md` valem sem mudança.

## 1. O que existe

| Peça | Arquivo | Papel |
|---|---|---|
| Extração de intenção (sem IA, sem custo) | `src/llm/intencao.py` | 16 culturas da tabela com sinônimos, flexões e erro de grafia (aproximação); foco (água, solo, renda, nitrogênio, palha, pragas, forragem); tipo de pedido; ordem e nº de safras; restrições ("não quero mandioca"); município. Cultura fora da lista (melancia, abóbora...) **nunca vira id**: volta em `fora_da_lista` |
| Avaliador de ciclo montado | `src/culturas/avaliar_sequencia.py` | 1 a 4 culturas, ordem dita + todas as outras ordens (até 24), mesmos critérios do `rotacao.py`, viabilidade do `motor.avaliar_local`, Pareto (`pareto.py`), empate, lacunas. `sugerir_por_foco`: o que dá no local e quem fica na frente **só pelo dado da tabela** |
| Folha de fatos da conversa | `src/llm/fatos.py` (`montar_folha_conversa`, `selecionar_conversa`) | Fatos [F#] com `texto`, `texto_simples`, `origem`, `lacuna` e `papel` |
| Gerente de diálogo | `src/llm/dialogo.py` | Estado JSON, perguntas, chips, "Entendi: ...", acolhida |
| Orquestração | `src/llm/conversa.py` | `conversar(mensagem, estado, ponto_id=None, perfil=None, provedor=None)` |
| Privacidade | `src/llm/seguranca.py` (`redigir_mensagem`) | Tira e-mail, CPF, telefone, CEP, coordenada, código IBGE, "meu nome é...", nome de qualquer município e ponto_id antes de a mensagem ir à IA |
| Rota pronta | `src/api/rota_conversa.py` | `POST /conversa` (APIRouter para incluir) |

Fluxo de uma rodada: valida (vazio, longo, "você é uma pessoa?", injeção, saudação) → extrai entidades → atualiza o estado → recusa o que o Sulco não faz (lucro, produtividade, previsão do tempo; texto acolhedor, sem IA) → decide: **perguntar** (município / o que pesa / ordem) · **confirmar** ("Entendi: milho, depois feijão-caupi... Está certo?", só com baixa confiança: "feijão" sozinho, grafia corrigida, conflito) · **responder** · **recusar**. Perguntas, confirmações, recusas e saudações são texto fixo (zero IA). A IA só reescreve uma resposta feita de fatos.

Decisões que o código toma sozinho (a IA nunca decide): quais ordens comparar; quem "sai na frente" (dominância de Pareto, sem pesos); empate (mesmas notas nos critérios com dado: "com os dados que temos, A e B ficam empatadas"); o que é lacuna (palha de feijão-caupi, água de crotalária, N fixado de quase todas, pragas, preço e custo; foco "renda" e "forragem" são lacuna declarada). O que a **ordem** muda: só "família diferente entre safras" e "leguminosa antes de outra planta" (a água, a palha e a adequação ao clima são as mesmas para as mesmas culturas, e o fato diz isso).

## 2. Como ligar (o que falta)

### 2.1 API (`src/api/main.py`, dono: outro agente)
Duas linhas, depois da rota `/chat`:
```python
from src.api.rota_conversa import router as rota_conversa
app.include_router(rota_conversa)
```
`POST /conversa` (o limite de taxa do `main` já vale):
```json
{ "mensagem": "se eu montar um ciclo com milho, feijão e crotalária, qual seria a melhor solução?",
  "estado": null,                      // o `estado` devolvido na rodada anterior; null na primeira
  "ponto_id": "quixada_ce",            // o local escolhido no app (fica no servidor; 404 se não existir)
  "cultura_atual": "milho",            // opcional; com um foco, a resposta inclui os caminhos de 3 safras
  "perfil": { "prioridade": "agua" } } // opcional; mesmo formato do `perfil` do /chat (sem município nem cultura_atual); a prioridade vale como foco
```
Resposta (`ConversaOut`): `resposta` (texto limpo; a última linha pode ser a pergunta), `resposta_com_citacoes`, `estado`, `acao` (`responder|perguntar|confirmar|recusar`), `chips[{rotulo, texto}]`, `pergunta`, `pede` (`municipio|foco|ordem|culturas|confirmacao|mensagem`), `origem` (`llm|template|sem_evidencia|recusa`), `entendido`, `verificacao{ok, motivos}`, `fontes[]` e `fatos[]` (id, tema, rotulo, texto, texto_simples, origem, lacuna), `trechos[]`, `uso`, `motivo`, `provedor`, `modelo`, `em_cache`, `assistente`. O servidor **não guarda a conversa**: o cliente devolve o `estado` (só entidades; nunca o texto das mensagens).

### 2.2 App (`src/app/`, dono: outro agente)
1. Uma página/aba "Conversar" com `st.chat_message`. O `estado` fica em `st.session_state["conversa_estado"]` (JSON); a cada mensagem chamar `POST /conversa` (ou `src.llm.conversa.conversar` direto, sem HTTP) com `ponto_id` do local escolhido e o `perfil` do app (`perfil.para_chat(...)`, mais `cultura_atual`).
2. **Rótulo fixo** acima do chat: valor de `assistente` ("Assistente automático do Sulco (não é uma pessoa nem um técnico)").
3. **Chips** (respostas rápidas): se `chips` não for vazio, mostrar um botão por item abaixo da última resposta; ao tocar, enviar `chip.texto` como a próxima `mensagem` (é uma frase normal, a extração já a entende). Streamlit:
```python
cols = st.columns(len(r["chips"]))
for col, c in zip(cols, r["chips"]):
    if col.button(c["rotulo"], key=f"chip_{turno}_{c['rotulo']}"):
        enviar(c["texto"])          # mesma função do st.chat_input
```
Sem chips: campo de texto livre. `acao == "confirmar"` mostra "Sim, está certo" / "Não, quero mudar" (já vêm em `chips`). `pede == "municipio"`: abrir o seletor de município do app (o texto livre "Quixadá" também funciona) e reenviar com `ponto_id`.
4. Mostrar `resposta` em texto simples; o cartão "de onde veio" lista `fontes[*].origem` e as lacunas (`lacuna: true`) para quem quiser conferir. Nunca exibir `resposta_com_citacoes` ao agricultor.
5. Um botão "Nova conversa" zera o `estado` (None).

## 3. IA (DeepSeek) e custo
- `SULCO_LLM_MODO=online` + chave: só entra para reescrever respostas feitas de fatos. Prompt (sistema + usuário) ≤ ~2.800 tokens (medido em teste: cerca de 1.300); `max_tokens` 260; cache por (provedor, modelo, prompt); o teto de chamadas por dia de `provedores.reservar_chamada` continua valendo.
- Reprovado pelo verificador (`verificador.verificar` com `tom=True` + `conversa.verificar_conversa`): número fora dos fatos, "rende mais"/"garanto"/"lucro", citação [F99], termo técnico, "plante/recomendo/deve", "na minha experiência", "como técnico", pergunta feita pela IA, mais de 100 palavras, "melhor" sem dizer o empate → **texto padrão** (mesma estrutura: acolhida curta + fatos + "Converse com o técnico." + pergunta).
- O que vai à IA: mensagem sanitizada (≤ 300 letras), nomes das culturas entendidas, o foco e os fatos em frase simples. Nunca ponto_id, nome do município, IBGE, lat, lon (travado por `FT.vazou`).

## 4. Testes (sem rede, provedor falso)
`tests/test_conversa_intencao.py` (79: 44 frases com erros de grafia, fora da lista, ordem, restrição, confirmação), `tests/test_conversa_avaliar.py` (26: ordens, Pareto, empate, lacunas, fatos), `tests/test_conversa.py` (84: perguntas uma por vez, confirmação, estado ida e volta e adulterado, prompt sem identificadores, verificador, recusas, 5 turnos com e sem IA, tamanho do prompt, "sobre o Sulco"), `tests/test_conversa_rota.py` (3). Comando: `.venv/bin/python -m pytest tests/test_conversa*.py -W error`.

## 5. Limites e lacunas conhecidos
- Falhas que **já existiam** (dependem de mudanças de outros agentes no motor, não desta entrega): `test_chat_simples.py::test_texto_simples_de_cada_tema_no_municipio_completo`, `::test_texto_padrao_dos_caminhos_uma_linha_por_caminho_na_ordem` e `test_fatos.py::test_contexto_do_cenario_cabe_em_2500_tokens` (conferido: falham igual com o `fatos.py` do HEAD).
- A ordem só muda dois critérios (família e leguminosa antes); palha, água e N são lacuna para várias culturas (`tabela_culturas.csv`). Sem dado de pragas, preço, custo ou mercado: o foco "renda" responde com a lacuna.
- Viabilidade = só temperatura e chuva do ciclo (motor); não olha solo, semente nem mercado (dito em um fato).
- `perfil.regras.proibidas` e as restrições da conversa valem em todas as posições do ciclo e na sugestão; `max_seguidas_*` e `obrigatorias` do perfil ainda não entram na conversa.
- "Feijão" sozinho é lido como feijão-caupi (feijão de corda, o mais comum no semiárido) **e confirmado** com a pessoa; `feijao_comum` precisa ser dito ("feijão carioca/comum").
- Sem voz; sem histórico de texto (por desenho). Municípios com nome de palavra comum (Barro, Jardim, Granja...) só são reconhecidos com "em/de/moro em".
- `calcular_rotacao` (caminhos de 3 safras, ~5 s) só roda quando o perfil traz `cultura_atual` e o foco é água, solo ou nenhum.
