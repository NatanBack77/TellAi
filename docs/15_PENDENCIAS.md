# Pendências do SULCO (ordem de prioridade)

Atualizado em 2026-11-12 (21h20). Marcas: **[DECISÃO SUA]** precisa de você; **[FAZER]** trabalho técnico; **[VERIFICAR]** conferir antes de afirmar.
Princípio: o produto é apoio à decisão do agricultor (marcar a área, cultura atual, prioridade; épocas de solo nu e de estresse; 3 caminhos com lacunas; sem fingir certeza). A previsão do NDVI é módulo de apoio.

## A. Modelos (`src/modelos/`)
1. **[FEITO em parte, 2026-11-13] Cobertura do conformal**: 6 métodos testados, nenhum fecha a marginal (76% / 87% na confirmação; causa: anos deslocam os resíduos juntos). O quantil por estação (`temp_k3_estacao`) sobe a pior estação de 53% para 74% (meta 80%). **[DECISÃO SUA]** adotar na produção? Ver `experimentos/conformal_A1/RESULTADO.md`.
2. **[FAZER] Teste de horizonte e estação** (+1 a +4 compostos; chuvosa/seca) para `base`, `persistencia`, `pers_lags4`, só 2010–2021. Parcial em `experimentos/previsao_doc09/` (scripts `t1_*.py`; o `t1_linhas.pkl` é ignorado pelo git; o placebo foi interrompido). Mostra onde o clima pode ajudar (a literatura lida indica R² 0,69 → 0,35 → 0,16 em 1, 2, 3 meses).
3. **[FAZER] Fonte nova de chuva/umidade com série longa** (ERA5-Land ou GLDAS/FLDAS via Earthdata). Scripts iniciais `experimentos/previsao_doc09/t3_*.py` (download não concluído). Earth Engine e CDS exigem cadastro novo. Testar pelo protocolo (só 2010–2021, N no Bonferroni, placebo, pareado contra `pers_lags4`).
4. **[VERIFICAR] Grade do SMAP**: catálogo do Earth Engine diz 11 km, nossa doc diz 9 km. Conferir nos metadados do arquivo.
5. **[FAZER]** SMAP como feature só vale se houver mais anos (série desde 2015). `pers_lags4` não integrado (ganho +0,005).
5b. **[FEITO 2026-11-13] Outros algoritmos e ensembles**: 12 candidatos; XGBoost (+0,028) e stack NNLS (+0,028) melhoram o Ridge na confirmação, mas ensemble não supera o XGBoost sozinho (já em produção). Ver `experimentos/ensemble/RESULTADO.md`.
5c. **[FEITO 2026-11-13] Overfitting/underfitting**: sem evidência de nenhum; parâmetros de produção no fundo plano da curva; erro restante = choques de ano inteiro. Ver `experimentos/overfit_underfit/RESULTADO.md`.
6. Só 59 células de clima distintas para 195 pontos (amostra efetiva); confirmação com 3 anos.

## B. Motor de culturas (`src/culturas/`)
7. **[DECISÃO SUA]** Ciclo real das culturas e data de início (hoje: ponto médio do EcoCrop; o ciclo pesa mais que o município). 
8. **[DECISÃO SUA]** `risco_max` (hoje 0,30); definição de "empate técnico" e percentis da faixa; pesos-base (hoje ordem 0,25/0,25/0,20/0,15/0,15, sem fonte); lista das 16 culturas (faltam: melancia, abóbora, quiabo, leucena, gliricídia, sisal, cebola, capins etc.); cobertura e comerciais na mesma lista ou separadas.
9. **[DECISÃO SUA]** Mapeamento prioridade → ordem de critérios (água/solo/renda) é SUPOSIÇÃO a validar com técnico (`docs/11_MVP.md`). "Renda" não tem dado de preço/mercado = lacuna.
10. **[FAZER]** 34 lacunas na tabela: demanda hídrica (9 culturas), palha e N de 6 culturas, N fixado de 13. Palma domina a prioridade "solo" nos 194 locais com alternativas (maiores valores de palha/N, estudos diferentes).
11. **[VERIFICAR]** A faixa de chuva do EcoCrop é anual ou por ciclo? Divergências EcoCrop × FAO (girassol, amendoim, algodão, milho) em `docs/06`. EcoCrop veio de espelho do GitHub, não do site da FAO.
12. **[FAZER]** `sensibilidade.py` e `docs/06` ainda descrevem o motor antigo (perfil anual, desempate alfabético). Só entram 23 anos de clima no ciclo (a janela de 2024 passa do fim da série).
13. Petrolina-PE: milho inviável, motor sem alternativas (tela mostra lacuna). Pontuação central pode cair fora de p10–p90 (ex.: Caridade).

## C. ZARC (`docs/13_ZARC.md`) — não iniciado
14. **[FEITO 2026-11-13] ZARC**: baixado (CE, 108.818 linhas), `src/coleta/zarc.py`, `src/culturas/zarc.py`, `Parametros.usar_zarc` (desligado), 7 testes, comparação sem × com em `experimentos/zarc/RESULTADO.md`. **[DECISÃO SUA]** ligar por padrão? nível de risco (20/30/40), solo (qualquer/todos), `feijao_comum`→"Feijão 2ª Safra", sorgo sem ZARC.
15. **[DECISÃO SUA]** `sobral_ce`: a coordenada cai fora do polígono de Sobral (183 códigos IBGE únicos no CE, não 184). Corrigir a coordenada (e o clima associado) ou aceitar o código 2312908?

## D. Back-end (`docs/12_API.md`)
16. **[FAZER]** `GET /modelo/previsao/{ponto_id}` responde 501 (modelo não treinado/cacheado na API; sem clima futuro só dá o último composto).
17. **[FAZER]** `/evidencias` leva ~28 s na 1ª chamada (carrega embeddings e reranker) e ~8 s depois: pré-aquecer/cachear. Cenário de clima alterado ainda só no app, não na API.
18. Nomes oficiais dos municípios: `pontos.csv` só tem o `ponto_id` (sem acento).

## E. Camada LLM (`docs/14_LLM.md`)
19. **[DECISÃO SUA]** Chave: `DEEPSEEK_API_KEY` no `.env`. O agente leu na doc oficial (por ferramenta que resume a página) `deepseek-flash` e `deepseek-v4-pro`: **[VERIFICAR]** os IDs antes de ligar.
20. **[DECISÃO SUA]** Enviar nome do município e pergunta a uma API externa é aceitável? (lat/lon e dados pessoais já são removidos.) Embeddings no `responder` ou só BM25? Recusar "qual rotação devo escolher" é a leitura certa da regra 3? "garante"/"lucro" barrados mesmo em negação.
21. **[FAZER]** Integrar ao app e à API, pré-gerar o cache do demo, avaliar com LLM real (20 perguntas), medir latência e custo. O verificador valida forma e números, não a fidelidade semântica.

## F. RAG
22. **[FAZER]** Perguntas PT sobre documentos EN (FAO): 0%; traduzir a pergunta. Faltam Emater, INSA, portarias do ZARC, EcoCrop paginado, cartilha de palma. Acerto 80% no TESTE (25 perguntas) é frágil; no DEV, 57%. `www.infoteca.cnptia.embrapa.br` resolve; sem `www` não.
23. Trechos mostrados nem sempre confirmam o valor da tabela (43 de 80 pares cultura-critério têm algum trecho); a tela avisa.

## G. App/MVP (`docs/11_MVP.md`)
24. **[FAZER]** Itens de marketing propostos e NÃO construídos: cartão de uma página do município (PDF) e abertura de zoom órbita→município. Mapa sem internet fica sem fundo.
25. Alternativas em empate técnico em 100% dos locais testados (388/388 com milho); mostrar honestamente.

## H. Dados
26. Não feitos: MapBiomas (uso do solo), FUNCEME (certificado/API não confirmados), INMET, EVI/SAVI (cache parcial em `experimentos/expB_indices/`), tarefa AppEEARS antiga (`done`, não baixada).
27. Unidade de independência estatística é o ano; mais pontos melhoram pouco o poder dos testes.

## I. Repositório
28. Segredos: `.env` fora do git; troque a senha do Earthdata (foi digitada em conversa).
29. Pastas pesadas: `experimentos/previsao_doc09/t1_linhas.pkl` (46 MB) é ignorada pelo git; `indice/` também (reconstruir com `python -m src.rag.rag_docs`).
