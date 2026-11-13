# 20. Plano das próximas fases: como continuar em outro computador

Atualizado em 2026-11-13. **Só documentação**: nada aqui foi implementado. Leia junto: `docs/04_RETOMADA.md` (ambiente e comandos), `docs/15_PENDENCIAS.md` (IDs citados abaixo: A1..A9, C*, M*, L*, R*, AP*, BL*, DU*), `docs/18_ARQUITETURA_TECNICA.md` (como tudo funciona), `docs/19_ALINHAMENTO_AO_DESAFIO.md` (por que esta ordem).
Esforço (pequeno / médio / grande) é estimativa minha, não medida.

## 0. Princípios (valem em todas as fases)
1. **Nenhum número inventado.** Todo valor vem de arquivo, fonte citada ou código rodado; o que falta vira lacuna visível na tela.
2. **O app apoia, não decide.** Todo resultado leva o aviso "a avaliar com técnico local"; nunca prometer que a rotação "rende mais".
3. **Validação sem trapaça** (`docs/05_EXPERIMENTOS.md`): decidir só com 2010–2021, **nunca olhar 2022–2024** para escolher variante, contar o número N de variantes testadas (Bonferroni), rodar placebo antes de aceitar um ganho.
4. **Métricas de dados `SINTETICO_*` nunca são resultado.**
5. **Cada fase termina com**: testes novos passando (`python -m pytest tests/<arquivo> -q -W error`), documento atualizado (`docs/15`, `docs/00_STATUS.md`, `docs/11_MVP.md` se mexeu no app), commit e push.

## 1. Fase 0: preparar o outro computador (antes de tudo)
```
git clone git@github.com:NatanBack77/sulco-nasa.git && cd sulco-nasa
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt        # Linux/Mac: .venv/bin/python
.venv/Scripts/python scripts/verificar_ambiente.py             # só lê; mostra o que falta
```
**Os dados já vêm no repositório (não é preciso minerar de novo):**
| Dado | Onde | Como restaurar |
|---|---|---|
| Tudo o que o app e os modelos leem | `data/processed/*.parquet`, `pontos.csv`, `diagnostico/`, `mvp/`, `cenarios/`, `modelos/` | já está pronto após o clone |
| NDVI bruto do ORNL (21.840 JSON) | `data/raw/modis_ornl/` | já está pronto |
| Índices Niño 3.4, TNA, TSA | `data/raw/indices/` | já está pronto |
| Solo bruto (SoilGrids por camada) | `data/raw/soilgrids/` | já está pronto |
| Clima bruto do POWER | `data/raw/power/` e `data/raw/power_cache.tar.gz` | já está pronto (o tarball é extraído por `scripts/setup.sh`) |
| SMAP bruto | `data/raw/smap_cache.tar.gz` | `bash scripts/setup.sh` extrai |
| ZARC: dicionário de dados | `data/raw/zarc/` | já está pronto (o CSV do ZARC é filtrado do site oficial; o resultado do Ceará já está em `data/processed/zarc_ce.parquet`) |
| **Tiles do relevo (SRTM), 28 arquivos `.hgt`, 709 MB** | `data/raw/srtm_tiles.tar.gz.part-00 .. part-02` (231 MB, divididos porque o GitHub rejeita arquivo > 100 MB) | `cat data/raw/srtm_tiles.tar.gz.part-* \| tar -xz -C data/raw` recria `data/raw/srtm/`. Só é preciso para recalcular terreno com outra janela; o resultado atual já está em `data/processed/terreno.parquet`. |

**Inventário completo e conferido** (o que está no GitHub, o que não está e por quê, e como completar a partir do outro computador): `docs/04_RETOMADA.md`, seção 3b. Itens que existiam só no computador da rodada anterior (`indice/` do RAG, `t1_linhas.pkl`, SMAP bruto) devem ser conferidos lá com `git status`.

**O que NÃO vem (e como refazer):** `.env` (nunca; crie à mão, ver `docs/04`), `.venv/` (recria com o `pip install`), `indice/` do RAG (`python -m src.rag.rag_docs`, precisa de `pdftotext`), `data/processed/sintetico/` (`python -m src.modelos.sintetico`).

**Antes de codar, conferir que o outro PC reproduz o estado:**
```
.venv/Scripts/python -m pytest --collect-only -q | tail -3      # 324 testes coletados em 2026-11-13
.venv/Scripts/python -m pytest -q -W error --ignore=tests/test_rag.py --ignore=tests/test_llm.py   # suíte sem a parte pesada
.venv/Scripts/python -m streamlit run src/app/app.py             # abrir o app e testar um município (a 1ª abertura é mais lenta)
```
Trocar a senha do Earthdata (BL2) antes de usá-la.

## 2. Fase 1: decisões suas (sem código; destrava o resto)
Registre cada decisão em `docs/03_SUPOSICOES_E_DECISOES.md` (novo D-número). Recomendação do assistente entre parênteses; **a decisão é sua**.
| ID | Decidir | Recomendação |
|---|---|---|
| DU7 | nível de risco do ZARC (20/30/40) e solo "qualquer × todos" | manter 30; solo vem do solo estimado ou informado |
| DU6 | ordem de critérios por prioridade (água, solo) | validar com um técnico (BL5); até lá, manter e declarar como suposição |
| DU1/DU4/DU2 | ciclo real das culturas, pesos-base, `risco_max` | manter padrões e declarar; só trocar com fonte |
| DU13 | como usar o valor da produção do IBGE como renda | receita bruta por hectare, média dos últimos 3 anos, com aviso "não é lucro" |
| DU5 | mais culturas | só acrescentar culturas que tenham fonte para ciclo, faixas e família |
| DU8 | `sobral_ce` (coordenada fora do polígono) | corrigir a coordenada e refazer clima, NDVI e ZARC desse ponto |
| DU9/DU10/BL1 | chave DeepSeek e envio de nome do município a API externa | decidir antes da Fase 4 |
| DU15 | plano MILP: manter como "proposta" | manter |

## 3. Fase 2: fechar as lacunas de "saúde do solo" do desafio (maior retorno)
Os dados já estão no repositório. Sugestão de ordem: A1, A2, A3, A4. Esforço: médio cada.

**A1. Risco de erosão e infiltração** (itens 21, 29b, 33 do `docs/19`)
- Entradas: `data/processed/terreno.parquet` (`elev_m`, `declive_medio_1km_pct`, `declive_p90_1km_pct`), `data/processed/solo.parquet` (areia, argila, carbono orgânico, 0–30 cm; função `mvp.solo_estimado`), chuva diária em `clima_diario.parquet`.
- Fazer: um indicador **simples e transparente** (classes baixo/médio/alto) a partir de declive + textura + carbono + intensidade da chuva, com os limiares declarados na tela. **[VERIFICAR]** as faixas de declive e de textura em fonte (Embrapa) antes de fixá-las no código. Modelos como RUSLE exigem fatores (erosividade, erodibilidade) que o projeto não tem; não imitá-los sem fonte.
- Onde: novo módulo `src/culturas/` ou `src/app/` (ex.: `risco_solo.py`), seção nova no app, e opcionalmente critério nas rotações (cobertura/palha reduz erosão).
- Testes: formato, monotonia (mais declive, mais risco), lacuna quando falta solo ou terreno, texto de aviso.
- Pronto quando: a tela mostra a classe, os números de entrada e a fonte dos limiares; `docs/19` itens 21/29b sobem de 0 para pelo menos 0,5.

**A2. Evapotranspiração e balanço hídrico** (itens 12, 20, 23)
- Entradas: Tmax, Tmin, radiação, chuva diárias (POWER). Fazer: ETo por Hargreaves-Samani (precisa da radiação extraterrestre por latitude e dia do ano; **[VERIFICAR]** a forma da fórmula e as constantes na doc FAO antes de implementar) e saldo `chuva − ETo` por quinzena. Se quiser Penman-Monteith (FAO-56), é preciso coletar vento e umidade do POWER (parâmetros novos, a confirmar).
- Aviso obrigatório: ETo não é o consumo da cultura (ETc = Kc × ETo; o Kc não está na tabela de culturas: lacuna declarada).
- Pronto quando: gráfico do saldo hídrico por quinzena no local, termo "balanço hídrico" no glossário, e o glossário deixa de dizer que não calcula ET.

**A3. Renda** (itens 5, 22, 29e)
- Entradas: `data/processed/pam_ce.parquet`, variáveis `valor_producao_mil_reais` e `area_colhida_ha`; mapa de culturas em `rotacao.PAM_PRODUTO` (feijão-caupi e comum não se separam; palma e perenes não existem na tabela 1612: lacuna C8).
- Fazer: receita bruta por hectare = valor ÷ área, média de 2021–2023 (valores correntes, sem correção de inflação: declarar). Entrar como critério na prioridade "renda" (hoje a prioridade não altera nada) e nos critérios do plano. Aviso: receita bruta, **não é lucro**; sem custo nem mercado.
- Testes: renda deixa de ser igual a "sem prioridade", lacuna para cultura sem PAM, aviso presente.

**A4. Calor e chuva extrema** (itens 9, 14)
- Fazer: dias com Tmax acima de um limiar e um índice de chuva extrema (ex.: dias com chuva acima de um limiar, ou percentil alto) por ano, a partir do POWER diário. **Os limiares são decisão sua ou de um técnico** (DU novo): não escolher sozinho.
- Mostrar no diagnóstico do local como tendência por ano.

## 4. Fase 3: mapa, entradas do agricultor e explicações
- **A5 Mapa com camadas e linha do tempo** (esforço médio): colorir os 195 pontos por indicador (solo nu, declive, variabilidade da quadra, risco de erosão do A1) com seletor de camada e controle de ano. Código do mapa: `src/app/app.py` (`mapa_e_local`, pydeck). Hoje o mapa só mostra pontos clicáveis; sem internet fica sem fundo (AP2).
- **A6 Entradas do agricultor** (pequeno): irrigado ou sequeiro (o ZARC já tem `Cod_Outros_Manejos` 2 e 3 em `zarc_ce.parquet`; hoje só o sequeiro é usado em `zarc._indice`), água disponível, equipamento e preferência de mercado como filtros sobre as alternativas.
- **A7 Explicações curtas** (pequeno): glossário com fixadoras de N, adubação verde, raízes profundas, ET e balanço hídrico, com trecho do acervo (PDFs em `docs_rag/`). Em `mvp.GLOSSARIO`.
- **A8 Valor forrageiro** (médio): palma, sorgo e milheto, a partir dos PDFs do MAPA em `docs_rag/`; entra como critério só com fonte e valor lido.
- **A9 Bases NASA não usadas** (pequeno, só texto): registrar em `docs/16_PESQUISA.md` por que ECOSTRESS, GPM, GRACE e GEDI foram usados ou descartados.
- **AP3 corrigir o texto da página "Limites dos dados"** (pequeno, **faça cedo**): ela ainda diz que não há solo nem ZARC, e lê um `relatorio_modelos.md` antigo da raiz (M12).

## 5. Fase 4: camada LLM e RAG
1. **BL1/DU9/DU10**: criar a chave DeepSeek no `.env` (`DEEPSEEK_API_KEY`), confirmar os IDs de modelo na doc oficial (L5) e decidir o que pode ir à API externa (nome do município e pergunta; lat/lon e dados pessoais já são removidos).
2. **L2/L3**: integrar `src/llm/servico.reescrever` ao app e à API, com o template como padrão e **cache de demo pré-gerado** (`data/processed/llm_cache/`); sem cache o modo offline cai no template.
3. **L4**: avaliar com as 20 perguntas estilo agricultor (citações [n] corretas, "sem evidência" quando falta base, JSON válido); medir latência e custo.
4. **R1/R2**: subir o acerto do RAG (hoje 54%, meta 80%): acrescentar documentos em português (Emater, INSA, portarias do ZARC), traduzir a pergunta para documentos em inglês; reconstruir `indice/` (`python -m src.rag.rag_docs`) e regerar `data/processed/mvp/evidencias_rag.json` (`python -m src.app.precalculo evidencias`, ~9 min).
Regra que não muda: o LLM só reescreve JSON e trechos; nunca calcula, escolhe rotação nem prevê clima.

## 6. Fase 5: API e consistência
- A API não expõe rotação, MILP, cenário de clima nem ZARC; `/modelo/previsao` responde 501 (`docs/12_API.md`). Expor o que o app calcula, ou declarar que a API é só leitura.
- `python -m src.coleta.power` apaga a coluna `ibge` de `pontos.csv` (D5): rode `python -m src.coleta.ibge_codigos` depois, ou faça o coletor preservar a coluna.
- A CLI do walk-forward imprime também 2022–2024 (M13): ajustar para não revelar a confirmação.
- Atualizar docs defasados (I5, AP5): `docs/11_MVP.md` seções 6 e 7, `docs/12_API.md`, `docs/13_ZARC.md`.

## 7. Fase 6: validação e demonstração
1. **AP4**: testar o app com um agricultor ou técnico local (nunca foi feito); validar a ordem de critérios por prioridade e o ciclo das culturas (BL5).
2. Ensaiar o roteiro de 2 minutos de `docs/11_MVP.md` no navegador, com internet, abrindo o app antes.
3. Reler `docs/17_PITCH.md` e atualizar o que mudou (ele já diz o que o app entrega hoje).
4. Conferir `docs/19_ALINHAMENTO_AO_DESAFIO.md` item a item e atualizar a pontuação.

## 8. Fase 7 (opcional, só se sobrar tempo): modelagem
Horizonte e estação do preditivo (M1), umidade do solo de longa série (GLDAS/FLDAS, M3; ERA5-Land exige cadastro novo), EVI/SAVI (M6), EnbPI como alternativa ao ACI (M8). Seguir o protocolo do item 3 dos princípios. O ganho esperado é pequeno: o limite está na informação, não no algoritmo (`experimentos/overfit_underfit/RESULTADO.md`).

## 9. Como trabalhar com dois computadores
- **Antes de começar:** `git pull --rebase origin main`. **Ao terminar:** `git add` do que mudou, `git commit` com mensagem clara, `git push origin main`. Faça isso por fase, não só no fim.
- **Nunca commitar:** `.env`, `.venv/`, `indice/`, arquivos acima de 100 MB (o GitHub recusa). Dados novos grandes: compactar e dividir como foi feito com o SRTM (`tar -czf - ... | split -b 90M`).
- Rodar a suíte **por partes** (`docs/04` seção 4); `tests/test_rag.py` leva ~7 minutos e precisa do `indice/`.
- Se tiver duas sessões de assistente em paralelo, dê a cada uma arquivos diferentes para não sobrescreverem o trabalho uma da outra.

## 10. Prompts prontos (colar no início da sessão no outro computador)
**Retomada geral:** "Projeto SULCO (NASA Space Apps 2026): apoio à decisão de rotação de culturas e saúde do solo no semiárido do Ceará. Leia `docs/04_RETOMADA.md`, `docs/20_PLANO_PROXIMAS_FASES.md`, `docs/15_PENDENCIAS.md` e `docs/18_ARQUITETURA_TECNICA.md`. Regras: nenhum número inventado; lacuna visível; o app apoia, não decide; nunca usar 2022–2024 para escolher variantes; contar N de variantes testadas; não commitar `.env`. Confira o ambiente (Fase 0) e **só implemente o que eu pedir**."
**Fase 2 (exemplo A1):** "Implemente o item A1 de `docs/20_PLANO_PROXIMAS_FASES.md` (risco de erosão e infiltração) com testes e a seção no app; confirme em fonte as faixas de declive e textura antes de fixá-las; atualize `docs/15`, `docs/19` e `docs/11`; faça commit e push."
