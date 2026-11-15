# Perfil do agricultor (2026-11-14)

Código: `src/app/perfil.py` (schema, validação, regras, texto sem identificador), `src/app/ligacao_conversa.py` (ponto de ligação com a conversa), `src/app/app.py` (seção "Seu perfil"), `src/app/cartao.py` (bloco "O que você informou"), `src/app/mvp.py` (`regras=` em `calcular`, `calcular_rotacao`, `calcular_plano`, `cenario_clima`; `descartes_caminhos`), `src/api/main.py`. Testes: `tests/test_perfil.py`.

## Desenho (sem fechar o agricultor numa cultura)
Não há cultura padrão. "Culturas que eu planto ou penso em plantar" começa vazio. A **primeira** é a cultura atual (base dos três caminhos); as outras vão em `tambem_considero` (só perfil e chat: os caminhos não partem delas). Sem nenhuma cultura: retrato do local + convite para conversar; nada de caminhos, rotação, cenário, renda, cartão ou chat com cenário. `quer_conversar` só registra "ainda não sei".

## O que tem efeito e o que só registra
| Campo | Efeito |
|---|---|
| primeira cultura (`cultura_atual`), `prioridade` | muda o cálculo (motor dos três caminhos e rotação) |
| `regras.proibidas`, `regras.obrigatorias`, `regras.max_seguidas_cultura` | **regra dura**: alternativa que viola não entra (3 caminhos, rotação de 3 safras, plano MILP). A cultura atual e a rotação atual dele nunca somem; se violarem, há aviso |
| `safra_2`, `safra_3`, `textura`, `materia_organica` | como antes (rotação informada; solo só gera avisos/ZARC por solo) |
| `manejo`, `agua_irrigacao_mm`, `equipamento`, `mercado` | só consulta/marca "atende, não atende, lacuna"; não mudam nota nem ranking |
| `regras.aceita_pousio` | só registra; pousio não é modelado como safra (aviso na tela, na rotação e na API) |
| `tambem_considero`, `quer_conversar` | só registram (perfil, cartão, chat) |
| `informativos.area_ha`, `.mes_plantio`, `.declive`, `.acesso_mercado` | **só registram para o técnico; não mudam o resultado** (testado: mesmas tabelas e pontuações com e sem). O mês é só comparado com a melhor época já calculada ("você costuma plantar em março; para os dados do local a melhor época é fevereiro"), sem recomendar |

Regras inconsistentes (mesma cultura em "não quero" e "preciso") param os caminhos com mensagem; não são ignoradas em silêncio. Se as regras descartam todas as alternativas, a tela diz isso (3 caminhos: só a cultura atual; rotação: só a rotação atual dele). "Máximo de seguidas" é suposição do agricultor; sem padrão.

## JSON do perfil (`sulco.perfil.v1`)
```json
{"schema": "sulco.perfil.v1", "municipio": "quixada_ce", "cultura_atual": "milho", "tambem_considero": ["sorgo"], "quer_conversar": false,
 "prioridade": "sem|agua|solo|renda", "manejo": "sequeiro|irrigado", "agua_irrigacao_mm": 0,
 "equipamento": "<lista de filtros.py>", "mercado": "<lista de filtros.py>",
 "textura": "não sei|arenoso|médio|argiloso", "materia_organica": "não sei|baixa|média|alta", "safra_2": null, "safra_3": null,
 "regras": {"proibidas": [], "obrigatorias": [], "max_seguidas_cultura": null, "aceita_pousio": false},
 "informativos": {"area_ha": null, "mes_plantio": null, "declive": "plano|suave|forte|null", "acesso_mercado": "sim|não|não sei|null"}}
```
Validação campo a campo (`perfil.validar`): chave desconhecida, tipo errado (bool não vale como número), cultura fora da tabela, município fora de `pontos.csv`, número fora da faixa (água 0 a 3000 mm; área > 0 e até 100 mil ha; mês 1 a 12; máx. seguidas 1 a 8), conflito proibida x obrigatória e arquivo > 20 mil bytes são recusados com mensagem em português. Só `json.loads`: nada é executado. Campo ausente = padrão. O arquivo vai e volta pelo navegador (download/upload); nenhum servidor guarda perfil. O JSON baixado contém `municipio` (é o arquivo do próprio agricultor); o que vai ao chat nunca.

## API
- `POST /cenarios` e `POST /rotacao`: `regras` opcional (`{proibidas, obrigatorias, max_seguidas_cultura, aceita_pousio}`, schema estrito, `extra=forbid`); cultura desconhecida, conflito, limite fora da faixa ou tipo errado = **422**. `/cenarios` devolve `regras_duras` (regras ativas, `n_viaveis`, `n_descartadas`, `todas_descartadas`, motivos, `nao_modelado`); `/rotacao` devolve em `detalhes.regras_duras` (inclui `base_viola`) e, com pousio, uma lacuna avisando que não é modelado. Rotação que as regras zeram: `estrategias: []`.
- `POST /chat`: `perfil` opcional (`prioridade, manejo, agua_irrigacao_mm, equipamento, mercado, textura, materia_organica, safra_2, safra_3, tambem_considero, quer_conversar, regras, informativos`). `municipio`, `ponto_id`, `nome`, `lat`, `lon` e `cultura_atual` dentro do perfil = 422. Só tem efeito junto com `ponto_id` e `cultura_atual` (vira um fato "o que o agricultor informou", tema `caminhos`, na folha de fatos; no caminho antigo vai em `contexto.perfil_agricultor`). O teste confere que o prompt não contém nome, ponto_id, IBGE, lat nem lon.
- Limite de taxa: `/cenarios`, `/rotacao` e `/chat` já estão no grupo pesado por prefixo (`limite_taxa.PESADAS`); nada precisou mudar.

## Conversa consultiva (ponto de ligação)
`ligacao_conversa.ligar_conversa(fala, estado, perfil)` chama `src.llm.conversa.responder(fala, estado=, perfil=)` se existir e devolve `{texto, chips, estado}` (ou None; nunca levanta). `estado = {culturas_citadas: [ids], foco: agua|solo|renda|None}`. Em "Pergunte ao Sulco" a seção (chips + texto livre + "Usar isto no meu perfil") só aparece se o módulo existir. `perfil.estado_conversa_para_perfil` filtra o estado (só culturas da tabela, foco conhecido) e o aplica ao perfil quando "Meu local" reabre. Nenhuma lógica de conversa foi implementada aqui.

## Limites e lacunas
- Pousio, área, declive, mês e acesso a mercado não têm efeito: não há dado para modelá-los.
- `tambem_considero` não gera caminhos próprios (a base é só a primeira cultura).
- Os campos de "Meu local" somem do estado ao visitar outra página do Streamlit; o app guarda uma cópia do perfil e a restaura ao voltar.
- Tempo medido (máquina com carga média ~9 por outros processos): a primeira cultura escolhida num município (partida a frio: caminhos, rotação de 3 safras, cenário, cartão) levou ~13 s; depois disso, mudar de município sem cultura levou ~1,6 s, regra nova ~3,6 s e mês de plantio ~1 s. Os testes medem só as seleções depois da partida a frio (< 5 s).
