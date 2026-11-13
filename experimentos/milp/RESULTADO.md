# Programação Linear Inteira Mista (MILP) para a rotação (2026-11-13)

Código: `src/culturas/rotacao_milp.py` (usa `scipy.optimize.milp`, sem dependência nova). Testes: `tests/test_rotacao_milp.py` (16). Comparação: `comparar.py`.

## O que foi feito
- Modelo: x[t,c] binária (cultura c na safra t), safra 1 = cultura atual; transições ligadas por restrições de FLUXO (Alfandari et al., 2011), regras duras opcionais
  (nunca a mesma cultura duas vezes seguidas, mínimo de leguminosas, máximo de repetições) e versão ROBUSTA (CVaR dos 25% piores anos de clima; Rockafellar e Uryasev).
- Correção validada: o ótimo do MILP é igual ao da enumeração exata em 15 casos (3 sementes x 4 conjuntos de regras, mais o robusto).
- Velocidade: a ligação frouxa das transições (z <= x) levava 15 s com 5 safras e mais de 60 s com 6, sem provar o ótimo; o modelo de fluxo resolve 10 safras
  com 16 culturas em ~0,1 s, com ótimo provado.

## O que o MILP mostrou em 4 municípios do Ceará (ZARC ligado, pesos iguais, lacuna = 0,5 neutro)
- O ótimo do MILP (3 safras) foi sempre **cultura atual > Crotalária juncea > Palma forrageira**, e **não coincide** com nenhuma das alternativas do simulador SMAA
  (Quixadá, Crateús, Limoeiro do Norte, Ipaumirim). Com regras duras e com a versão robusta, a mesma sequência. Com 5 safras, alterna crotalária e palma.
- Causa: o MILP maximiza uma soma com pesos fixos, e a palha (dado de poucos estudos; palma 17.100 e crotalária 11.250 kg/ha) domina a nota. O SMAA trata lacunas como
  incerteza e usa só critérios completos no ranking principal. Ou seja: o ótimo depende dos pesos e das lacunas, não de um fato agronômico.

## Conclusão
O MILP **não reduz o empate técnico** (ele devolve um único ótimo para pesos fixos, o que esconde a incerteza que o SMAA mostra) e **não prova** que a sequência é melhor
na prática. Ele ajuda em três usos concretos, nenhum deles é "decidir":
1. **Plano de várias safras com regras duras** (5 ou mais safras, onde enumerar explode; ex.: nunca repetir a cultura em seguida, ao menos 2 leguminosas).
2. **Verificação de viabilidade:** dizer se uma sequência do agricultor ou do SMAA respeita as regras e quanto perde da nota.
3. **Robustez ao clima (CVaR):** responder "qual sequência aguenta melhor os anos ruins". Nos 4 casos, não mudou o resultado.
Recomendação: usar como opção "plano de 5 safras com regras", rotulado como proposta e com o mesmo aviso de empate técnico; não substituir o SMAA.
