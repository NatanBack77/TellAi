# A1 — Cobertura do conformal (2026-11-13)

Script: `conformal_wf.py` (`selecao`, `confirma`). Ridge com persistência, 195 pontos, walk-forward 1 ano à frente.
6 métodos testados (N=6). Seleção 2010–2021 decidiu o que confirmar; confirmação 2022–2024 rodada UMA vez.

## Seleção 2010–2021 (cobertura marginal média; meta 80% / 90%)
| Método | 80% | 90% | pior estação (80% / 90%) |
|---|---|---|---|
| cell_split (atual) | 77,5% | 87,7% | 52% / 68% |
| temp_k3 (calibra nos 3 anos recentes) | 77,9% | 88,4% | 52% / 69% |
| temp_k6 | 78,1% | 88,4% | 53% / 70% |
| **temp_k3_estacao** (quantil por faixa de estação) | 77,5% | 88,0% | **76% / 86%** |
| temp_k3_ponto (escore por desvio do ponto) | 77,8% | 88,2% | 54% / 71% |
| temp_k3_ponto_estacao | 77,5% | 88,0% | 61% / 76% |

## Confirmação selada 2022–2024
| Método | 80% | 90% | pior estação (80% / 90%) |
|---|---|---|---|
| cell_split | 76,6% | 87,2% | 53% / 68% |
| temp_k3 | 76,2% | 87,0% | 52% / 68% |
| temp_k3_estacao | 76,1% | 87,3% | **74% / 86%** |

## Leitura
- **Nenhum método fecha a cobertura marginal** (fica ~3–4 pontos abaixo da meta). A diferença entre métodos (1–2 pontos) é menor que a
  variação entre anos: anos secos/úmidos deslocam os resíduos de todos os pontos juntos, então os dados não são intercambiáveis no tempo
  e a garantia do conformal não vale. Mais pontos não resolvem (a unidade independente é o ano).
- **Ganho real do `temp_k3_estacao`:** a faixa deixa de cobrir muito mal uma estação (53% → 74% para meta de 80%; 68% → 86% para 90%).
  A largura média sobe ~3%.
- Escolha do `temp_k3_estacao` como candidato foi feita pela cobertura da pior estação na seleção (critério não pré-registrado; exploratório),
  e a confirmação reproduziu o ganho.
- Produção NÃO foi alterada (`preditivo.py`/`cenarios.py` seguem com `cell_split`). Falta decisão: adotar o quantil por estação.
  Em qualquer caso, apresentar a faixa como "cobre ~76% / ~87% (não 80% / 90%)", e pior estação menor.
