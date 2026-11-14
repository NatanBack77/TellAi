# Regras duras do agricultor e "o que separa as alternativas" (2026-11-14)

Melhoria 1 de `docs/22_PESQUISA_ROTACAO.md` (seção 4). Sem dado novo, sem escolher pesos nem ciclo, todos os padrões mantidos.

## O que mudou
Código novo:
- `src/culturas/regras_duras.py`: `RegrasDuras` e `verificar` / `permite` / `separar` / `descrever` / `validar`.
- `src/culturas/pareto.py`: `separar_alternativas`, `de_estrategias` (saída de `rotacao.gerar_rotacoes`), `de_cenarios` (saída de `motor.gerar_cenarios`).

Código existente (só o necessário, parâmetro novo opcional `regras=None`; sem regra o resultado é idêntico, testado):
- `motor.gerar_cenarios(..., regras=)`: tira dos candidatos o caminho [atual, c] que viola; a lacuna geral lista o que saiu e por quê.
- `rotacao.gerar_rotacoes(..., regras=)`: filtra as sequências de 3 safras; devolve `regras_duras` (regras ativas, descartadas por motivo, exemplos, `base_viola`). Se as regras eliminam tudo, `estrategias == []` com lacuna explicando.
- `rotacao_milp.otimizar(..., regras=)`: aceita `RegrasDuras` ou dict; as chaves antigas (`sem_repetir_seguida`, `min_leguminosas`, `max_repeticoes`) continuam valendo. A saída traz `violacoes_regras` (sempre `[]` quando viável). `melhor_por_enumeracao` usa o mesmo verificador.

## Regras (todas opcionais, todas DESLIGADAS por padrão)
| Campo | Significado |
|---|---|
| `proibidas` | não pode ou não quer plantar (safras 2 em diante; a safra 1 é a cultura atual, já plantada) |
| `obrigatorias` | precisa aparecer na sequência (a atual conta) |
| `exigir_alguma_de` | "cobertura": ao menos uma cultura deste grupo; a lista é do agricultor/técnico (a tabela não classifica cobertura) |
| `max_seguidas_cultura` / `max_seguidas_familia` | máximo de safras seguidas da mesma cultura/família. **SUPOSIÇÃO do agricultor**; padrão `None` (sem limite novo). O que o código já fazia continua por fora: `rotacao.py` não gera alternativa que seja monocultura (3 iguais); o motor de 3 caminhos exige cultura diferente da atual. |
| `aceita_pousio` | só registra; **pousio não é modelado como safra** (não há dado para dar nota a ele). Aparece em `nao_modelado`. |

Cultura citada que não existe na tabela dá erro (typo não vira regra ignorada). Família ausente na tabela não conta como repetição (lacuna, não vantagem).

## "O que separa as alternativas" (`pareto.py`)
`separar_alternativas(alternativas, criterios=None, rotulos=None)`: para cada par, dominância de Pareto só nos critérios com dado nos dois lados. Cada par traz: `relacao` (`a_domina`, `b_domina`, `empate_total`, `sem_dominancia`, `sem_criterio_comum`), `a_melhor_em`, `b_melhor_em`, `empatam_em`, `lacuna_nos_dois`, `lacuna_so_em_a`, `lacuna_so_em_b`, `comparacao_incompleta` e `frases` (curtas e literais). Mais `posicao_pareto` por alternativa (`dominada_por`, `domina`, `na_fronteira`), `fronteira` e `criterios_sem_dado_em_todas`. Não usa pesos. Saída em ordem canônica por id (não depende da ordem de entrada).

## Como ligar no app (`src/app` é de outro dono; nada foi editado lá)
1. Formulário opcional (multiseleção "não quero/não posso plantar", "preciso plantar", "cobertura", números "máx. safras seguidas"). Montar `RegrasDuras(proibidas=..., obrigatorias=..., exigir_alguma_de=..., max_seguidas_cultura=..., max_seguidas_familia=...)`.
2. Passar `regras=` a `gerar_cenarios` e a `gerar_rotacoes`. Mostrar `r["regras_duras"]["descartadas_por_motivo"]` ("descartadas e por quê") e, se `base_viola`, o aviso de que a rotação atual dele viola a regra.
3. Para a tela de comparação: `de_estrategias(r["estrategias"], rotulos={...})["pares"]`; mostrar `frases` e `fronteira`. Para o motor de 3 caminhos: `de_cenarios(cenarios)`.
4. O API (`src/api`) precisa repassar o mesmo objeto de regras (também de outro dono).

## Testes (`-W error`)
`tests/test_regras_duras.py` (27) e `tests/test_pareto.py` (≈ 100 casos). Hypothesis NÃO está instalado: as propriedades usam sementes fixas parametrizadas. Rodados junto com `test_culturas`, `test_incerteza`, `test_rotacao`, `test_rotacao_milp`, `test_zarc_motor`, `test_renda`: 230 passaram.
- regra dura nunca violada: 10 sementes de regras aleatórias na rotação, 10 no motor de 3 caminhos, 8 no MILP (ótimo igual à enumeração, `violacoes_regras == []`);
- monotonia: melhorar um critério (com dado) de uma alternativa nunca aumenta quem a domina, nunca reduz o que ela ganha de cada outra (25 sementes);
- mesma entrada, mesma saída; permutar alternativas (e critérios) não muda o resultado do Pareto; permutar a ordem da tabela de culturas não mudou as sequências do motor nem da rotação (um caso, semente fixa);
- lacuna nunca entra em `a_melhor_em`/`b_melhor_em`/`empatam_em`; trocar um valor por lacuna nunca cria vantagem nesse critério.

## Limites
- A monotonia testada é a da posição de **Pareto**. Não vale para o ranking SMAA (nota min-max entre candidatas muda quando uma candidata melhora, e os pesos são sorteados).
- Ao ignorar critério com lacuna em um lado, uma dominância pode surgir por critério NÃO comparado (ex.: A perde em palha, mas palha é lacuna em A). Por isso `comparacao_incompleta` e a frase de aviso; a tela deve mostrá-las.
- Dominância não prova que uma alternativa é melhor na roça; só diz que, nos critérios medidos, a outra não ganha em nenhum.
- A rotação atual (base) nunca é removida, mesmo violando regra: é a realidade dele, marcada como referência.
- Regras eliminando muitas candidatas podem deixar menos de 2 alternativas (a lacuna é dita, nada é inventado).
- Pousio não modelado; "cobertura" depende da lista informada por quem usa.
- Limite de `proibidas` na safra 1: ignorado (já plantada).
- `aceita_pousio` e `exigir_alguma_de` não têm teste de integração no app (app não foi tocado).
