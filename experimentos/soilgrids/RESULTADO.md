# SoilGrids como feature da anomalia de NDVI (2026-11-13)

Scripts: `auditoria.py` (parte 1), `nucleo.py` + `rodar.py` (walk-forward, guarda previsões), `analisar.py`, `celulas_novas.py`. Saídas: `auditoria.txt`, `auditoria_vizinhos.csv`,
`selecao_resumo.csv`, `selecao_skill_por_ano.csv`, `selecao_por_estacao.csv`, `selecao_vies_por_ano.csv`, `selecao_conformal.csv`, `celulas_novas.csv`, logs. Previsões em `*.pq` (não versionar).
Base = persistência (modelo de produção), 195 pontos, 59 células, walk-forward 1 ano à frente, **só 2010–2021 decide**. 2022–2024 NÃO foram abertos (nenhuma variante passou).
Hiperparâmetros fixos a priori (produção). Tudo reproduzível com `.venv/bin/python experimentos/soilgrids/<script>`.

## Parte 1. Auditoria do solo (sem ajustar nada)
Unidades conferidas na documentação ISRIC (https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html): areia, silte, argila em g/kg (fator 10 -> %); soc em dg/kg (fator 10 -> g/kg); pH em pH x 10 (fator 10).
`ESCALA = 0.1` de `solo.py` está correta para as cinco propriedades. Camadas 0–5, 5–15, 15–30 cm existem na documentação.
- Cobertura: 195/195 com valor (mediana da janela 9x9); 181 com pixel central válido, 14 sem. Fração de pixels válidos da janela < 50% em 10 pontos (petrolina_pe 5%, mossoro_rn 14%, oros_ce 20%, picos_pi 31%, serra_talhada_pe 36%, senhor_do_bonfim_ba 36%, sousa_pb 40%, irece_ba 42%, maracanau_ce 43%, patos_pb 23%).
- Faixas (todas fisicamente plausíveis): areia 38,6–74,1%; silte 8,1–34,0%; argila 11,6–40,0%; soc 5,3–62,2 g/kg; pH 4,8–7,0. Soma areia+silte+argila 98,1–101,4% (medianas por propriedade, não exatamente 100).
- Extremo: camocim_ce soc 0–5 cm = 62,2 g/kg (corte Q3+3 IQR = 48,4); único acima.
- Pontos a < 10 km: 12 pares; |diferença de argila| máx 3,6 pp (mulungu/guaramiranga/pacoti, serra úmida), mediana 2,9. Nenhum par próximo com valores muito diferentes.
- Pouca amplitude entre pontos: argila 0–30 cm de 15,1 a 36,1% (dp 3,7 pp), pH dp 0,3. 59% da variância da argila está DENTRO da célula de clima (então solo não é só um rótulo de célula).
- **Falhas/inconsistências:**
  1. Média simples das 3 camadas em `mvp.solo_estimado` e em `risco_solo._solo_de_linha` (duplicada), mas as camadas têm 5, 10 e 15 cm. Contra a média ponderada pela espessura: argila −1,2 pp em média (até −2,7), areia +1,0, soc +1,6 g/kg (até +5,7). Muda a classe SiBCS de 1 ponto.
  2. `pixel_central_valido` é devolvido por `solo_estimado` e ignorado pelo app; `fracao_pixels_validos` não chega ao app. Pontos com 5% de pixels válidos (petrolina_pe: ~4 pixels) saem com o mesmo aviso dos demais.
  3. Rótulo do app (argila < 15 / 15–35 / > 35): resulta 0 arenoso, 193 médio, 2 argiloso nos 195 pontos. Contra o SiBCS (`risco_solo.classe_textura`) os rótulos coincidem nos 195 (médio=média, argiloso=argilosa); a divergência que `_nota_textura` do app anuncia não ocorre nestes dados. O rótulo "arenoso" nunca será gerado pelo estimado (argila mínima 15,1%, areia média de 55%), então o solo ZARC "arenoso" e o aviso de solo arenoso só aparecem se o agricultor informar. Cortes 15/35: fonte não verificada (nota do próprio app).
  4. SOC 0–5 cm médio de 19 g/kg parece alto para o semiárido, mas não há dado de campo aqui para dizer; é hipótese a validar (D7).
  5. Nenhum valor foi comparado com medida de campo: a auditoria verifica unidade, faixa e coerência, não acurácia.

## Parte 2. Walk-forward 2010–2021 (skill vs climatologia; ganho pareado por ano vs a persistência do MESMO modelo)
Variantes (hiperparâmetros fixos; detalhes em `nucleo.py`): v1 areia, argila, carbono, pH (média 0–30 cm ponderada); v2 água disponível; v3 v1 + interações (chuva 30/60/90 d x argila e x carbono; dias secos x areia);
v4_solo viés médio por ponto previsto pelo solo (Ridge fixo); v4_ref viés médio por ponto observado no treino (controle sem solo).
v2: pedotransferência de Saxton & Rawls (2006), equações 2–5 lidas (com sinais) em Blake & Assi (2019), Trans. ASABE 62(2):289–301, https://doi.org/10.13031/trans.13073; água disponível = (CC33 − PMP1500) x espessura, somada nas 3 camadas.
Suposição não lida em fonte: matéria orgânica = soc/10 x 1,724 (fator de van Bemmelen). Ordem de grandeza checada: CC 0,24 e PMP 0,14 m3/m3 para areia 58/argila 21; água disponível 24–41 mm em 0–30 cm.
**N total para o Bonferroni = 42** (novas_fontes 8 + ensemble 12 + conformal 6 + ACI 6 + estas 5 variantes x 2 modelos = 10); alfa corrigido 0,05/42 = 0,00119. IC = percentil do bootstrap (10 000) sobre os 12 anos.

| Variante | Modelo | Skill média | Ganho vs base | IC inf. corrigido | IC inf. 5% (sem correção) | Anos com ganho > 0 | Placebo: ganho médio (3 sementes) / máx |
|---|---|---|---|---|---|---|---|
| base (persistência) | ridge | 0,2911 | — | — | — | — | — |
| v1_solo | ridge | 0,2913 | +0,0002 | −0,0006 | −0,0003 | 7/12 | −0,0000 / +0,0000 |
| v2_ad | ridge | 0,2912 | +0,0001 | −0,0000 | +0,0000 | 8/12 | +0,0000 / +0,0000 |
| v3_inter | ridge | 0,2915 | +0,0004 | −0,0004 | −0,0001 | 8/12 | −0,0000 / +0,0001 |
| v4_solo | ridge | 0,2914 | +0,0002 | −0,0006 | −0,0002 | 6/12 | −0,0000 / −0,0000 |
| v4_ref (sem solo) | ridge | 0,2922 | +0,0011 | −0,0003 | +0,0003 | 8/12 | — |
| base (persistência) | xgboost | 0,3071 | — | — | — | — | — |
| v1_solo | xgboost | 0,3073 | +0,0003 | −0,0010 | −0,0004 | 6/12 | +0,0002 / +0,0005 |
| v2_ad | xgboost | 0,3081 | +0,0010 | −0,0002 | +0,0004 | 9/12 | +0,0012 / +0,0014 |
| v3_inter | xgboost | 0,3076 | +0,0005 | −0,0012 | −0,0005 | 6/12 | +0,0004 / +0,0008 |
| v4_solo | xgboost | 0,3070 | −0,0000 | −0,0004 | −0,0003 | 6/12 | −0,0000 / +0,0000 |
| v4_ref (sem solo) | xgboost | 0,3071 | +0,0001 | −0,0010 | −0,0005 | 5/12 | — |

Leitura: **nenhum IC corrigido > 0** (nem o v4_ref, que não usa solo). O maior ganho (v2 xgboost, +0,0010) é igual ao do placebo com solo embaralhado (+0,0012): é o piso de ruído (~0,001 de skill), não efeito.
O placebo do xgboost fica acima de 0 em v1, v2 e v3, ou seja, o critério "placebo ≤ 0" também falha onde o ganho real é positivo. Ridge: placebo ≈ 0.

**Pontos fracos (b) e (c), mesma tabela de previsões (`selecao_*.csv`)**
- Viés por ano (resíduo médio por ano; RMS dos 12 anos): ridge base 0,0102, v1 0,0101, v2 0,0102, v3 0,0101, v4_solo 0,0102; xgboost base 0,0096, v1 0,0095, v2 0,0094, v3 0,0097, v4_solo 0,0096. Faixa dos anos (ridge base −0,0156 a +0,0196). **Não reduz.** Esperado: solo é constante no tempo e o choque é de ano inteiro.
- Conformal temporal (k = 3 anos, meta 80%; ridge base): cobertura 80,9%, pior ano 77,9%, largura 0,1458, pior faixa de estação 55,2%; com solo: v1 80,8% / 77,5% / 0,1457 / 55,0%; v3 80,8% / 77,8% / 0,1458 / 54,9%. Diferenças ≤ 0,3 ponto percentual. Idem para meta 90% e para quantil por faixa (`selecao_conformal.csv`). **Não muda cobertura nem largura.**
- Skill por estação (faixas de slot//6; ridge base 0,210 / 0,342 / 0,461 / 0,239): todas as variantes dentro de ±0,005 (xgboost v1 na faixa 0: 0,2375 -> 0,2396, +0,002; v4_ref na faixa 2 do ridge +0,005, sem solo). Sem padrão.
- Células nunca vistas (GroupKFold por célula, 2001–2021, mistura tempo; só exploratório, não decide; `celulas_novas.csv`): ganhos pareados por ano de −0,0001 a +0,0006 (maior: v3 ridge +0,0006, IC 5% sem correção +0,0003, 16/21 anos; placebos −0,0002 a +0,0003). Skill base: ridge 0,2599, xgboost 0,2912. Ganho de 0,0006 de skill é ~0,05% de RMSE; com N = 42 e fora do desenho decisório, não é evidência.

## Parte 3. Veredito
**Sem evidência.** Nenhuma variante passa (IC corrigido > 0: 0 de 10; placebo ≤ 0: falha no xgboost; confirmação selada 2022–2024 NÃO rodada, pois não há finalista). Integração em `src/modelos/`: nada a propor, nada alterado.
Por que era esperado: o alvo é a anomalia em relação à climatologia do PRÓPRIO ponto, e a persistência já carrega o estado local; solo estático varia entre pontos, não entre anos; a amplitude do solo entre os 195 pontos é pequena (argila dp 3,7 pp) e vem de mapa global de ~2 km. (Explicação plausível, não testada separadamente.)
Quanto custaria testar solo melhor (BDiA/Embrapa, D7): o custo de código/computação é pequeno (este experimento roda em ~2 min por rodada de 12 anos; trocar `data/processed/solo.parquet` e reexecutar `rodar.py`/`analisar.py`). O custo real é obter e harmonizar a fonte (cobertura do Nordeste, resolução, camadas, licença): **não medido, não pesquisado nesta tarefa**. Cada fonte nova soma variantes ao N do Bonferroni (hoje 42), o que exige ganho ainda maior para passar. O uso do solo no app (avisos, ZARC) não depende deste resultado: ele continua útil para a decisão, só não melhora a previsão de NDVI.
