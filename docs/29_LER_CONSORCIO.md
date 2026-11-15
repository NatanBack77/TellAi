# 29. LER (uso equivalente da terra) e consórcio: o que dá para usar no SULCO

Data: 2026-11-14. Pesquisa de literatura do semiárido do Nordeste + implementação opcional (desligada por padrão).
Dados: `data/culturas/ler_staging.csv` (STAGING, **não alimenta o motor**). Scripts: `experimentos/ler/`. Código: `src/culturas/consorcio.py`. Testes: `tests/test_consorcio.py`.
Trechos em português simples para o acervo: `docs/ler_trechos.md`.

## 1. Resposta curta

- O LER **existe** para o semiárido, mas é pouco: **8 estudos** entram na faixa (sequeiro, testemunha na mesma área e safra, duas culturas, número lido no texto). Cobrem **12 pares** de culturas. Outros 13 estudos foram lidos e deixados de fora, cada um com o motivo registrado.
- O LER publicado serve como **evidência na alternativa** ("este par já foi estudado em consórcio, com LER observado X a Y, em N experimentos, não é do seu terreno"). **Não** serve para ranquear: o motor não tem produtividade, arranjo, densidade, cultivar nem testemunha do agricultor.
- Implementados (a) rótulo e (b) desempate opcional, ambos **desligados por padrão** (`consorcio_modo='sem'`). (c) entrada no ranking foi descartada (seção 6).
- Em 45 execuções com clima real (15 locais x 3 culturas atuais): 32 de 90 alternativas ganham rótulo de consórcio; o desempate **não mudou nenhuma escolha** e **não reduziu o empate técnico** (100% antes e depois). Detalhe na seção 7.

## 2. O que é o LER e como foi medido nos estudos

LER = soma, sobre as culturas do consórcio, de (produtividade da cultura no consórcio / produtividade dela solteira). Acima de 1: o consórcio produziu mais do que seria produzido em área separada equivalente; abaixo de 1: produziu menos. Todos os artigos abaixo usam a fórmula de Willey (1979) em português como UET ("uso eficiente da terra") ou IEA ("índice de equivalência de área").

## 3. Tabela de estudos que entram na faixa (sequeiro, semiárido, testemunha pareada)

Faixa = menor e maior LER entre os arranjos medidos no estudo. As produtividades solteira e consorciada estão em `ler_staging.csv`.

| Par | Estudo (local, ano) | Arranjo / densidade | LER (total; parciais) | Fonte e tabela |
|---|---|---|---|---|
| milho + caupi | Távora et al. 2007 (Quixadá-CE, 2003, 630 mm) | séries de substituição 75/25, 50/50, 25/75; milho e caupi 0,8x0,2 m | 1,28 (milho 1,02 + caupi 0,26); 1,22 (0,85+0,37); 1,05 (0,43+0,62). Solteiros: milho 2203, caupi 1003 kg/ha | R. Bras. Agrociência 13(3):311-317, Tab. 7 p.315 |
| milho + caupi | Bela Cruz-CE, 2013, 680 mm (Essentia 18(1)) | milho + feijão em fileiras alternadas, 0,5x0,5 m | 1,34 (milho 0,64 + feijão 0,70) | Tab. 7 (PDF p.18) |
| milho + sorgo | Távora et al. 2007 (Quixadá-CE) | 75/25, 50/50, 25/75 | 1,15; 1,00; 0,98 | Tab. 7 p.315 |
| caupi + sorgo | Távora et al. 2007 (Quixadá-CE) | caupi 75% + sorgo 25% ... caupi 25% + sorgo 75% | 0,87; 1,28; 1,35 | Tab. 7 p.315 |
| milho + feijão comum | Barreto e Serpa 1986 (Poço Verde-SE, 1979) | 1 fileira de milho para 3 de feijão, 0 a 300 kg/ha de P2O5 | 0,85 (sem P); 1,27 (100); 1,29 (200); 1,14 (300) | Embrapa-CNPCo Com. Téc. 20, Tab. 1 p.6 |
| mamona + caupi | Pinto et al. 2011 (Quixadá-CE, 2010, 288 mm) | mamona 10.000 pl/ha + caupi na entrelinha | 0,91 | Rev. Verde 6(2):75-85, Tab. 2 p.79 |
| mamona + caupi | Furtado et al. 2012 (Pombal-PB, 2011) | mamona 3 fileiras a 2 m + caupi 40.000 pl/ha | 1,30 (IAC 2028); 1,51 (BRS Nordestina) | Rev. Verde 7(2):156-162, Tab. 5 p.161 |
| mamona + caupi / milho / sorgo | Azevedo et al. 2007 (Monteiro-PB, 1994-95) | adição de populações, fileiras alternadas | caupi 1,13 a 1,50; milho 0,97 a 1,48; sorgo 1,23 a 1,54 (médias marginais) | Rev. bras. ol. fibros. 11(3):145-162, Tab. 4-6 p.152-153 |
| mamona + milho / gergelim / algodão | Pinto et al. 2011 (Quixadá-CE, 2010) | idem | milho 1,10; gergelim 1,03; algodão 0,95 | Tab. 2 p.79 |
| mamona + gergelim | Furtado et al. 2012 (Pombal-PB) | idem | 0,80 (IAC 2028); 1,37 (BRS Nordestina) | Tab. 5 p.161 |
| girassol + caupi | Pinto et al. 2011 (Quixadá-CE, 2009, 929 mm) | séries de substituição | 1,28 (75/25); 1,02 (50/50); 0,59 (25/75) | Rev. Verde 6(2):69-74, Tab. 4 p.72 |
| palma + caupi | Albuquerque e Rao 1997 (Petrolina-PE, 1982-88, 572 mm/ano) | palma 1x1 a 3x1x0,5 m + fileira dupla do consorte | 1,48 (1o triênio); 1,82 (2o); média 1,65 | R. Bras. Zootec. 26(4):645-650, Tab. 3 p.649 |
| palma + sorgo | idem | idem | 1,27; 1,49; média 1,38 | idem |

Faixa por par (pares do motor; N = estudos na faixa):

| Par | N | LER mínimo | LER máximo |
|---|---|---|---|
| milho + caupi | 2 | 1,05 | 1,34 |
| milho + sorgo | 1 | 0,98 | 1,15 |
| caupi + sorgo | 1 | 0,87 | 1,35 |
| milho + feijão comum | 1 | 0,85 | 1,29 |
| mamona + caupi | 3 | 0,91 | 1,51 |
| mamona + milho | 2 | 0,97 | 1,48 |
| mamona + sorgo | 1 | 1,23 | 1,54 |
| gergelim + mamona | 2 | 0,80 | 1,37 |
| algodão + mamona | 1 | 0,95 | 0,95 |
| girassol + caupi | 1 | 0,59 | 1,28 |
| palma + caupi | 1 | 1,48 | 1,82 |
| palma + sorgo | 1 | 1,27 | 1,49 |

Leitura honesta: em **8 dos 12 pares** há pelo menos um arranjo com LER **abaixo de 1** (consórcio rendeu menos do que o plantio separado). As exceções são milho + caupi (mínimo 1,05), mamona + sorgo (1,23), palma + caupi (1,48) e palma + sorgo (1,27), todos com 1 a 2 estudos.

## 4. Lidos e deixados de fora (com motivo)

| Estudo | Motivo |
|---|---|
| Távora e Lopes 1990 (Petrolina-PE, PAB 25(7):1011-1022) | irrigado com déficit imposto; LER 1,00; 1,01; 0,88 (milho + caupi) |
| Morgado e Rao 1985 (Petrolina-PE, PAB 20(1):45-55) | irrigado em linha de aspersores; LER > 1 só com a menor população de milho e lâmina >= 200 mm (cerca de 1,10 a 1,20); nas populações maiores, "sem vantagem". Gráfico não lido |
| Rao e Morgado 1984 (síntese de 34 experimentos no NE: milho + caupi "produziu 41% mais") | **citação secundária**, original não aberto |
| Beltrão et al. 1986 (algodão + caupi, Gurinhém-PB, PAB 21(3)) | LER 1,56 (cv. TVx 1836-013J) e 1,17 (Pitiúba); local é Agreste, semiárido não confirmado; tabelas ilegíveis |
| Távora et al. 1990 (mandioca + caupi/amendoim, Pacajus-CE, Ciência Agronômica 21(1/2)) | semiárido não confirmado (litoral). LER 1,49 e 1,69 no 1o ciclo (9 meses) mas 0,79 e 0,99 no 2o (20 meses, após poda); mandioca + amendoim 1,35 a 1,55 e 0,89 a 1,21 |
| Essentia 2017: milho + mandioca 0,98; feijão + mandioca 0,87; milho + feijão + mandioca 1,98 | mandioca sem raiz colhida no 1o ano (parcial 0,00); o texto do artigo diz "1,28 a 1,54" e o resumo "1,9", a tabela traz 0,87 a 1,98 |
| Diaconia (Alto Sertão SE, Cariri PB), algodão + caupi + gergelim + milho: LER 1,01 a 2,25 e 1,20 a 3,21 | **sem testemunha pareada**: monocultivo = média municipal do IBGE; quatro culturas misturadas; dados de caderno de campo |
| Pereira et al. 2015 (Piauí, gergelim/milho/caupi): LER 1,9 a 2,6 | valores acima de 2 com duas culturas são improváveis; fórmula e produtividades não legíveis no PDF; **não confiável** até conferir |
| Corrêa, Távora e Pitombeira (mamona + caupi/sorgo, Quixadá-CE; LER 1,08 a 1,45) | só **resumo** aberto (a ferramenta devolveu o resumo); arranjos e parciais não lidos |
| Morais et al. 2018 (beterraba + caupi-hortaliça, Mossoró-RN; LER 1,03 a 1,22) | hortaliça irrigada; beterraba não está no motor |
| Albuquerque et al. 1983 (palma + sorgo/caupi, preliminar) | sem LER de produção: sem vantagem em volume da palma e peso de grãos; só 24% (sorgo) e 33% (caupi) em área foliar |
| Silva et al. 2013 (algodão + gergelim/amendoim, Missão Velha-CE) e Pinto et al. 2012-2013 (mamona + girassol, Quixadá-CE) | abertos, **não calculam LER** |
| Diniz 2016 (palma + sorgo, Serra Talhada-PE, UET 1,51) | só trecho de busca; PDF bloqueado pelo site (verificação de navegador) |

## 5. LER do tempo (ATER) e a crítica da literatura

- **ATER** (Hiebsch e McCollum 1987, Agronomy Journal 79(1):15-22; só registro bibliográfico aberto): multiplica cada parcial pelo tempo que a cultura ocupa a terra em relação ao tempo total do consórcio. Corrige o defeito mais citado do LER (ignorar tempo).
- Um único estudo do staging calcula ATER no semiárido do CE: **Pinto et al. 2011 (Quixadá, 2010)**. LER 0,91 a 1,10 mas ATER (chamada REAT) **0,39 a 0,54, abaixo de 1 em todos os pares**: o consórcio "não teve vantagem de terra e tempo". O mesmo artigo calcula o **coeficiente equivalente de terra (LEC/CET)**: 0,15 a 0,29; só o par mamona + milho passa de 0,25 (limiar atribuído por eles a Adetiloye et al. 1983). Esses valores de ATER não foram recalculados por nós.
- **Balasubramanian e Sekayange 1990** (Agronomy Journal; só resumo de repositório): dizem que o LER só considera área e erra em consórcios de várias estações; propõem o AHER (colheitas por área). Os mesmos resumos dizem que o ATER supõe crescimento contínuo e subestima o consórcio. **Mead e Willey 1980** (Experimental Agriculture 16(3):217-228; só resumo): propõem o "LER efetivo", quando as proporções colhidas diferem da necessidade do agricultor.
- Crítica registrada **nos próprios artigos abertos**: (i) Beltrão et al. 1986: o UET "fornece apenas a dimensão física do sistema, sem considerar o valor de cada componente", e a eficiência mostrada "pode ser irreal": no caso do algodão + caupi Pitiúba o LER foi 1,17, mas a renda bruta do consórcio foi menor que a do algodão solteiro. (ii) Morgado e Rao 1985: o LER depende da testemunha: com a população recomendada de milho como solteiro, a vantagem do consórcio de baixa população aparece mais. (iii) Quixadá: o mesmo consórcio dá LER perto de 1 e ATER abaixo de 1 (Pinto 2011). (iv) Palma é perene e o consorte anual: o LER de Albuquerque e Rao não corrige o tempo de ocupação.
- LER não mede preço, mão de obra nem risco de quebra: **o risco não aparece no LER de nenhum dos estudos lidos** (cada um é uma safra, uma localidade; um dos anos teve apenas 288 mm).

## 6. O que o motor pode e não pode fazer com isso

O motor tem rotação entre safras e viabilidade por clima. **Não tem** produtividade, consórcio, arranjo, densidade, cultivar nem testemunha.

**Permite:** mostrar "consórcio estudado no semiárido, LER observado X a Y em N experimentos, não é do seu terreno" quando o par (cultura atual, alternativa) tem estudo no staging.

**Não permite:** calcular o LER do agricultor (faltam as produtividades dele); prever ganho; ranquear por LER (um LER de outro local, ano e cultivar não é medida da sua roça; 8 de 12 pares têm arranjo com LER < 1; só 8 estudos); comparar alternativas por "maior LER" (arranjos, densidades e cultivares mudam de estudo para estudo, e o LER do mesmo par varia de 0,59 a 1,28 dentro de um único estudo).

Três usos, do mais seguro ao mais arriscado:

| Uso | Status | Risco |
|---|---|---|
| (a) evidência/rótulo na alternativa, sem alterar nota | **implementado** (`consorcio_modo='rotulo'`) | baixo: texto com fonte e página; pode induzir a ler "consórcio é bom" se o rótulo for resumido sem o "não é do seu terreno" |
| (b) critério OPCIONAL "consórcio com respaldo" como desempate/secundário, desligado por padrão | **implementado** (`consorcio_modo='desempate'`) | médio: sem estudo vira 0 no desempate, mas ausência de estudo é lacuna, não defeito; só age em empate exato; teste garante que o padrão não muda |
| (c) entrada no ranking (peso, nota, Monte Carlo) | **descartado** | alto: daria nota a um número que não é do usuário e é de 1 a 3 estudos por par |

## 7. Implementação e antes/depois

`src/culturas/consorcio.py`: `consorcios_para(a, b)` (lista de estudos que entram na faixa, com mín/mediana/máx, n de arranjos, n de estudos do par, fonte, URL, página, avisos; lista vazia = sem estudo), `resumo_par` (rótulo), `fora_da_faixa` (o que foi lido e descartado, com motivo), `tem_respaldo`, `criterio_secundario`, `anexar`. Par sem ordem. `Parametros.consorcio_modo` = `'sem'` (padrão) | `'rotulo'` | `'desempate'`; mudança mínima em `parametros.py` e `motor.py` (um `import` tardio, a chave de ordenação e uma chamada final; com `'sem'` o código novo não é executado).

Rodado com clima real (`experimentos/ler/antes_depois.py`; 15 locais: 10 do Ceará já em `data/processed/cenarios` + Crateús, Mossoró, Patos, Petrolina, Serra Talhada; culturas atuais milho, sorgo e caupi; 45 execuções):

| Medida | Resultado |
|---|---|
| alternativas escolhidas | 90 |
| alternativas com rótulo de consórcio | **32** (36%); 58 ficam em lacuna |
| execuções com pelo menos 1 rótulo | 31 de 45 |
| `rotulo` mudou nota, faixa, critério ou alternativa | **0** |
| `desempate` mudou a escolha das alternativas | **0** (nos dados reais não há empate exato no corte) |
| `desempate` mudou `empate_tecnico` | **0** |
| execuções com empate técnico entre as alternativas | 45 de 45 (**100% antes e depois**) |
| execuções em que o critério separaria as duas alternativas (uma com estudo, outra sem) | 30 de 45 |

Declaração: o `desempate` **não reduz o empate técnico** (ele não toca nos intervalos). Os "30 de 45" dizem apenas que, em 30 execuções, uma alternativa tem estudo e a outra não; **isso não torna uma alternativa melhor**. Com clima sintético e uma cultura duplicada (empate exato forçado em teste), o desempate escolhe a que tem estudo e escreve nas lacunas que isso não significa que seja melhor.

Fato 'consórcio' em `src/llm/fatos.py`: **não feito**. O arquivo está com 633 linhas alteradas por outro trabalho e o verificador de "rende mais" teria de ser tocado em `seguranca.py`; fica como pendência para quem estiver editando esses arquivos (o dado já sai com fonte em `cenario['consorcio']['respaldo']`).

## 8. Recomendação

1. Manter `consorcio_modo='sem'` como padrão. Para o pitch, usar `'rotulo'`: o texto "consórcio estudado no semiárido, LER observado X a Y em N experimentos, não é do seu terreno" é verdadeiro, tem fonte e mostra a lacuna ("sem estudo", 58 de 90).
2. Não usar `'desempate'` na demonstração: nos dados reais não muda nada, e explicá-lo custa mais do que vale.
3. Para fechar a lacuna de verdade: abrir os PDFs hoje só com resumo (Corrêa 2008, Diniz 2016, IFCE Iguatu 2025) e as séries completas de Távora (1988, 1989), Rao e Morgado 1984, Santiago 2014; e guardar os PDFs aprovados em `docs_rag/` com sha256 (o RAG só indexa extração fiel de PDF; o resumo em `docs/ler_trechos.md` não passa nessa regra e **não foi indexado**).
4. Se um dia houver produtividade do agricultor (entrada do usuário), o LER passa a ser calculável para ELE, mas continuaria sem tempo, preço e risco. Isso exigiria decisão do usuário e testemunha.

## 9. Limites e pontos de atenção

- Cada estudo é uma safra e uma localidade; faixa entre estudos não é intervalo de confiança.
- Alguns números vieram de tabela em imagem (Azevedo 2007: médias marginais lidas visualmente) ou de OCR (Barreto e Serpa 1986: um parcial inferido pela soma; Albuquerque 1997: OCR com ruído, conferido no resumo e na Tabela 3).
- A conferência automática (`experimentos/ler/saida/conferencia.csv`) achou divergência entre razão de médias e parcial publicado em Pinto 2011 (mamona + gergelim: 0,84 calculado contra 0,80 publicado), provável média de razões por parcela. O total publicado (1,03) bate com a soma dos parciais publicados.
- `semiarido='provavel'` só para Poço Verde-SE (a introdução do estudo fala de regiões semiáridas; enquadramento oficial não conferido). `nao_confirmado`: Pacajus-CE e Gurinhém-PB, ficam fora da faixa; podem ser promovidos mudando a coluna `entra_na_faixa` e rodando o script de novo.
- Nada aqui é preço, renda ou previsão. O texto gerado nunca diz "rende mais".
