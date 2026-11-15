# Relatório da curadoria (Claude) — etapas 4, 5, 6 e 7

Data: 2026-11-15. Cada linha `verificado` só foi gravada depois de o trecho ser encontrado **literalmente** na página citada (`scripts/curar.py`; controle negativo: trecho inventado, página errada e número alterado são rejeitados). Isso prova que o trecho existe na página; **não** prova que o `valor` o resume bem (conferi cada par), nem que serve ao local do agricultor.

| Etapa | Linhas com fonte | Lacunas | Culturas com dado |
|---|---|---|---|
| 4 | 13 | 9 | 7/16 |
| 5 | 36 | 2 | 14/16 |
| 6 | 35 | 5 | 11/16 |
| 7 | 20 | 5 | 11/16 |

## Limites
- **Fontes**: PDFs da Embrapa. Os de `material_antigravity/` (baixados por outro agente, sem URL registrada: coluna `url` com `file://`), os de `docs_rag/` e os de `fontes_op/` (baixados das URLs reais da coluna `url`).
- Várias fontes são do Meio-Norte (PI/MA) ou dos Tabuleiros Costeiros, ou nacionais, não do Ceará: está no campo `contexto`.
- Linhas marcadas **ATENÇÃO** no contexto (guandu, crotalária) vêm de parcelas de experimento, **não são recomendação**.
- **Kc (etapa 6)**: tabela 12 da FAO-56, para clima sub-úmido; o texto das notas de rodapé não foi baixado (só o número).
- **Adubação (etapa 7)**: valores `_referencia`, com a condição da fonte (análise de solo). Não são prescrição. A decisão D2 é **do usuário e continua em aberto**.
- Sem dose de agrotóxico nem produto comercial.