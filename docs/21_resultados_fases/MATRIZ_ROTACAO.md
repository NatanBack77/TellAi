# Matriz "cultura anterior -> cultura seguinte" com fonte (melhoria 2 do doc 22)

Data: 2026-11-14. Substitui, como critério OPCIONAL, os proxies de `rotacao.py` ("diversidade de família" e "leguminosa antes de não leguminosa", ambos sem fonte). **Não altera** `motor.py` nem `rotacao.py`.

Arquivos: `data/culturas/matriz_rotacao.csv`, `src/culturas/matriz_rotacao.py` (carrega, valida, `consulta(anterior, seguinte)`, `cobertura()`), `src/culturas/construir_matriz_rotacao.py` (gera o CSV; cada evidência é escrita com arquivo, página e trecho), `tests/test_matriz_rotacao.py`.

## Método (anti-alucinação)

- Fonte: **só o acervo local** (`docs_rag/`, 50 PDFs, texto extraído com `pdftotext`). Nenhuma página externa foi aberta; nada veio de memória.
- Varredura: cada página dos 50 PDFs foi procurada por frases que citam duas ou mais das 16 culturas junto de rotação, sucessão, antecessor, palhada, nematoide, praga/doença, alelopatia ou consórcio, e por "intervalo de retorno" e variantes. As frases candidatas foram lidas na página inteira antes de entrar.
- Cada linha de evidência tem: arquivo, página, **trecho copiado do PDF**, tipo de evidência, região do estudo e ressalva. O teste `test_todo_trecho_esta_na_pagina_citada_do_pdf` reextrai a página com `pdftotext -f p -l p` e exige que o trecho (e o complemento, quando a frase corta entre páginas) esteja nela. Há teste de que um trecho inventado ou página errada é pego.
- O validador também confere que o trecho (+complemento) **menciona as duas culturas** do par (aliases em `ALIASES`), que o arquivo está no manifesto com o mesmo sha256, e que **todos os 240 pares** existem na matriz (par sem evidência = linha `LACUNA`).
- **Intervalo de retorno por família: não existe no acervo.** A busca por "intervalo mínimo / de retorno / pousio de N / a cada N anos" não achou nada de rotação (só adubação e zoneamento). Nenhuma coluna ou valor de intervalo foi criado (há teste).
- Grau: `favoravel`, `neutro`, `desfavoravel`, `LACUNA`. `neutro` só existe com evidência e significa "a fonte cita a sequência como opção/prática, sem efeito descrito" (ou, em tese, mede e não vê diferença). **Falta de dado nunca vira neutro.**
- Consolidação por par (várias evidências): só neutro -> neutro; neutro + um sentido -> esse sentido; favorável **e** desfavorável juntos -> `LACUNA` com `divergente=True` (não decide; mostra as evidências). Sem número, sem peso.

## Cobertura dos 240 pares ordenados (16 x 15, sem a diagonal)

| Resultado | Pares | % |
|---|---|---|
| favorável | 16 | 6,7 |
| neutro (opção/prática citada, sem efeito) | 9 | 3,8 |
| desfavorável | 8 | 3,3 |
| LACUNA divergente (fontes em sentidos opostos) | 1 | 0,4 |
| **com alguma evidência** | **34** | **14,2** |
| **LACUNA sem dado** | **206** | **85,8** |

Pares com evidência (anterior -> seguinte):
- favorável: caupi -> milho, sorgo, milheto (sanidade; sem ordem na fonte, vale nos dois sentidos, então milho/sorgo/milheto -> caupi também; ver divergência abaixo para milho); crotalária-juncea, mucuna, milheto, guandu -> caupi (nematoides); crotalária-juncea, mucuna, feijão-de-porco, guandu, algodão, girassol -> milho (produtividade do milho seguinte); mucuna, feijão-de-porco -> feijão comum.
- desfavorável: caupi <-> feijão comum, amendoim, girassol (fungos de solo polífagos em comum); milho -> sorgo, milho -> milheto (ciclo contínuo de gramíneas). Diagonal fora dos 240: caupi -> caupi (podridão-radicular-seca) e milho -> milho.
- neutro: caupi <-> gergelim, algodão (opção possível); milho <-> girassol, algodão; sorgo -> milho (as 9 contagens já descontam sorgo -> caupi, que consolida como favorável); milheto -> milho/algodão; caupi -> algodão.
- divergente: **milho -> caupi** (rotação com gramínea favorável à sanidade; milho deixa palha pobre em N, o caupi "possivelmente" precisa de mais N). Vira `LACUNA` e `usar_na_nota = False`.

Linhas de evidência não-LACUNA: 59. Tipo mais forte que sustenta o grau mostrado, nos 34 pares: recomendação técnica 26, revisão 6, artigo de campo em outra região 2 (crotalária -> milho, mucuna -> milho), artigo de campo no semiárido **0**. A única linha de campo no semiárido (sorgo -> caupi, Parnaíba-PI) é neutra, só mostra a sequência em uso, e o grau favorável desse par vem da recomendação técnica. Fontes: livro Embrapa Meio-Norte e Embrapa Soja (recomendação), Pesagro-Rio e Embrapa Milho e Sorgo (revisão), Selvíria-MS e Triângulo Mineiro (campo, Cerrado).

## Fontes usadas

| Arquivo (docs_rag/) | Uso |
|---|---|
| `embrapa_meionorte_feijaocaupi_produtor_pergunta.pdf` (p.84, 136, 151, 154, 157, 173, 183) | caupi: gramíneas, fungos polífagos, nematoides, N após milho. Perguntas e respostas, Meio-Norte; recomendação técnica. |
| `embrapa_meionorte_caupi_plantio_direto_semiarido_piaui.pdf` (p.3) | caupi sobre palhada de sorgo, semiárido piauiense (sem comparação de antecessoras). |
| `embrapa_debiasi_diversificacao_especies.pdf` (p.19) | opções de rotação com milho 2ª safra, algodão após caupi/milheto (Centro-Oeste/MT; sistemas com soja). |
| `embrapa_cruz_plantio_direto_sustentabilidade.pdf` (p.4-5) | palhada x produtividade do milho (Ferreira, 1998, Rio Verde-GO, citado); alerta de ciclo de gramíneas (Sul de MG). |
| `embrapa_alvarenga_plantas_cobertura_spd.pdf` (p.3, 5) | milho após mucuna/crotalária (Triângulo Mineiro, sem repetição) e feijão-de-porco (RS, citado). |
| `pab_milho_sucessao_adubos_verdes.pdf` (p.1) | crotalária (sunn hemp) +18,5% no milho, Selvíria-MS. |
| `pesagro_rio_rural_rotacao_culturas.pdf` (p.6, 12) | revisão: feijão-de-porco/mucuna -> milho e feijão (RJ, SP). |

Lidos e sem pares utilizáveis: demais documentos do acervo (ZARC, palma, adubação verde em videira/melão/mangueira, FAO, caprinos etc.). O que tratam não é "cultura comercial X depois de Y" entre as 16 culturas.

## Vieses e limites (ler antes de usar)

1. **Quase tudo é caupi e milho.** 31 dos 34 pares envolvem caupi ou milho; palma, mandioca, mamona, gergelim, amendoim e girassol quase não aparecem como "seguinte". Os 206 pares sem dado incluem rotações comuns no semiárido (milho -> feijão comum, mandioca, palma...).
2. **Região:** nenhum grau vem de campo no semiárido (há 1 linha neutra). Os efeitos medidos em produtividade são Cerrado (MS, MG, GO) e Sul/Sudeste; a Embrapa Meio-Norte (PI/MA) é a fonte mais próxima. Não generalize para o sertão.
3. **Adubo verde não é cultura comercial.** Mucuna, crotalária, feijão-de-porco e guandu aparecem como cobertura/adubação verde (cortados antes da colheita), não como lavoura com grão. A transferência para "plantar e colher" é suposição.
4. **Recomendação técnica não é medida.** A maior parte dos favoráveis/desfavoráveis é "pergunta e resposta" ou lista de opções, sem efeito quantificado. `neutro` mistura "opção possível" e "sequência praticada".
5. **Sanidade, produtividade e N são critérios diferentes.** O campo `criterio` os separa; o grau consolidado só mistura quando todos apontam o mesmo sentido, senão vira divergente. Um par "favorável" pode ser favorável só por sanidade.
6. **Mapeamentos meus**: "gramíneas" da fonte -> milho/sorgo/milheto (Poaceae); "sunn hemp" -> Crotalaria juncea; crotalária sem espécie (Alvarenga) atribuída a juncea pela lista de destaque; "feijão" -> feijão comum. Estão nas ressalvas da linha.
7. **Revisões repassam estudos citados** (Pesagro, Cruz, Alvarenga): o trecho confere no PDF, mas o estudo original não foi aberto.
8. **Direção:** onde a fonte diz "rotação com", a evidência foi registrada nos dois sentidos (`simetrico=sim`); a fonte não diz qual vem primeiro.
9. Texto extraído de PDF antigo tem erros de OCR (ex.: "ocapim-sudão"); os trechos foram copiados como saem do `pdftotext`, não corrigidos.
10. **Nada aqui foi validado por técnico.** Delphi/painel (doc 22, opção 3) continua pendente.

## Como ligar à nota da rotação (para quem editar `rotacao.py`; não foi feito)

Critério opcional `sucessao_fonte`, desligado por padrão, que não substitui `diversidade_familia`/`leguminosa_antes` enquanto a cobertura for 14%:

1. Para cada sequência (c1, c2, c3), consultar as 2 transições com `matriz_rotacao.consulta(a, b)`.
2. Só entra com **ordem**, nunca com valor inventado: `desfavoravel < neutro < favoravel`. Usar SMAA-O (nota ordinal, Lahdelma et al.), ou contar `n_fav` e `n_desf` por sequência. Não atribuir 0 / 0,5 / 1 fixos.
3. **Transição `LACUNA` (inclusive divergente) não pontua**: não é neutra, não é média. A sequência recebe `n_com_dado` (0, 1 ou 2). Se `n_com_dado == 0`, o critério fica `NaN` para essa sequência (a lacuna visível já existente no motor), e a saída mostra "sem base de fonte para este par".
4. **Só ligar o critério quando for discriminante e honesto**: se mais de ~50% das transições das candidatas forem LACUNA, mostrar apenas o aviso "a matriz de sucessão cobre N de M transições" e **não** incluir na nota (hoje: 34/240 pares, ~14%; para a sequência típica o critério ficaria quase todo vazio).
5. Mostrar, por sequência, os pares com dado e a evidência (`consulta(...)["evidencias"]`: arquivo, página, trecho, tipo, região, ressalva) e os pares sem dado como "o que conferir com o técnico".
6. Teste de propriedade sugerido: mudar uma transição de LACUNA para qualquer grau não pode alterar a nota das outras sequências que não a contêm; sequência sem nenhuma transição com dado não pode subir nem cair por causa do critério.

## Como estender

Acrescentar uma `E(...)` em `construir_matriz_rotacao.py` com arquivo do acervo, página e trecho exatos, rodar `python -m src.culturas.construir_matriz_rotacao` e `pytest tests/test_matriz_rotacao.py`. Fontes novas fora do acervo (Embrapa, FAO, MAPA/ZARC) exigem baixar o PDF para `docs_rag/` e incluí-lo no `manifesto.json` (com URL e sha256) para o teste conseguir conferir o trecho.
