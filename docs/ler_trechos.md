# Trechos sobre consórcio e LER (uso equivalente da terra), em português simples

**Para o acervo do RAG, mas ainda NÃO indexado.** O RAG do projeto (`src/rag/rag_docs.py`) só indexa extração fiel de PDF com manifesto e sha256; este arquivo é um resumo nosso e por isso **não** entra assim. Para indexar de verdade: baixar os PDFs listados abaixo para `docs_rag/`, registrar no manifesto e reconstruir o índice (não feito agora).

Como ler: "LER" é a soma, para cada cultura, de (quanto ela produziu no consórcio / quanto produziu sozinha). Acima de 1: o consórcio produziu mais do que o plantio separado. Abaixo de 1: produziu menos. É o resultado de **um experimento**, num lugar, num ano, com um arranjo; **não é do seu terreno e não prevê ganho**. O LER não mede tempo de ocupação da terra, preço nem risco.

Cada item: o que foi feito, o que deu, onde está (página do artigo), link do PDF aberto.

## Estudos usados na faixa (sequeiro, semiárido)

1. **Milho, sorgo e feijão-caupi em Quixadá-CE (2003).** Os três foram plantados juntos, dois a dois, em proporções de 75/25, 50/50 e 25/75. Milho + caupi: LER 1,28; 1,22; 1,05. Milho + sorgo: 1,15; 1,00; 0,98. Caupi + sorgo: 0,87; 1,28; 1,35. O caupi rendeu bem menos em consórcio (de 1003 para 263 a 625 kg/ha, conforme a proporção). Choveu 630 mm. Fonte: Távora e outros, Revista Brasileira de Agrociência 13(3):311-317, 2007, Tabela 7 (p. 315). https://periodicos.ufpel.edu.br/index.php/CAST/article/view/1378/1362

2. **Milho, feijão-caupi e mandioca em Bela Cruz-CE (2013, 680 mm).** Milho + caupi: LER 1,34. Os valores com mandioca não valem como LER completo porque a raiz ainda não tinha sido colhida no primeiro ano. O texto do artigo e a tabela não batem entre si (o texto diz "1,28 a 1,54", a tabela traz de 0,87 a 1,98). Fonte: revista Essentia (Sobral) 18(1):2-23, 2017, Tabela 7. https://essentia.uvanet.br/index.php/ESSENTIA/article/view/72/92

3. **Milho e feijão comum em Poço Verde-SE (1979).** O LER depende da adubação com fósforo: 0,85 sem fósforo, 1,27 com 100, 1,29 com 200 e 1,14 com 300 kg/ha de P2O5. Fonte: Barreto e Serpa, Embrapa-CNPCo, Comunicado Técnico 20, 1986, Tabela 1 (p. 6). https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/358299/1/CPATCCOM.TEC.2086.pdf

4. **Mamona com gergelim, algodão, milho e caupi em Quixadá-CE (2010).** Ano seco (288 mm de março a junho). LER: com milho 1,10; com gergelim 1,03; com algodão 0,95; com caupi 0,91. A mamona produziu bem menos em todos os consórcios. O "LER do tempo" (ATER) deu abaixo de 1 em todos (0,39 a 0,54) e o coeficiente equivalente de terra, de 0,15 a 0,29. Fonte: Pinto e outros, Revista Verde 6(2):75-85, 2011, Tabelas 2 e 3 (p. 79-80). https://dialnet.unirioja.es/descarga/articulo/7432904.pdf

5. **Girassol e feijão-caupi em Quixadá-CE (2009, 929 mm).** LER 1,28 (75% girassol + 25% caupi), 1,02 (50/50) e 0,59 (25/75). Fonte: Pinto e outros, Revista Verde 6(2):69-74, 2011, Tabela 4 (p. 72). https://dialnet.unirioja.es/descarga/articulo/7432875.pdf

6. **Mamona com caupi e gergelim em Pombal-PB (2011).** Mamona BRS Nordestina + caupi: LER 1,51; + gergelim: 1,37. Mamona IAC 2028 + caupi: 1,30; + gergelim: 0,80. Um só ano, um só local. Fonte: Furtado e outros, Revista Verde 7(2):156-162, 2012, Tabela 5 (p. 161). https://gvaa.com.br/revista/index.php/RVADS/article/download/1376/2261/8291

7. **Mamona com sorgo, milho e caupi em Monteiro-PB (1994 e 1995).** O LER médio por população ficou entre 1,23 e 1,54 (sorgo), 0,97 e 1,48 (milho) e 1,13 e 1,50 (caupi). Subiu quando havia mais plantas de mamona. Fonte: Azevedo e outros, Revista Brasileira de Oleaginosas e Fibrosas 11(3):145-162, 2007, Tabelas 4 a 6 (p. 152-153). https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/277391/1/1132007004rbof1131451622007.pdf

8. **Palma forrageira com caupi e com sorgo em Petrolina-PE (1982 a 1988).** LER médio 1,65 (palma + caupi) e 1,38 (palma + sorgo). A palma é cortada de três em três anos e o caupi e o sorgo são anuais; o LER não corrige essa diferença de tempo. A palma sozinha rendeu mais forragem do que a consorciada no primeiro corte. Fonte: Albuquerque e Rao, Revista Brasileira de Zootecnia 26(4):645-650, 1997, Tabela 3 (p. 649). https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/131391/1/Rev.BrasileiradeZootecniav.26n.4p.6456501997.pdf

## Lidos, mas fora da faixa

9. **Milho e caupi irrigados em Petrolina-PE (1982/83).** Com déficit de água, LER 1,00; 1,01 e, sem déficit, 0,88: sem vantagem. Fonte: Távora e Lopes, Pesquisa Agropecuária Brasileira 25(7):1011-1022, 1990, Tabela 7 (p. 1020). https://apct.sede.embrapa.br/pab/article/download/13547/7691/60300

10. **Milho e caupi irrigados em Petrolina-PE (1983).** O LER só passou de 1 com a menor população de milho (10.000 plantas/ha) e com 200 mm ou mais de água irrigada (cerca de 1,10 a 1,20). Com mais milho, sem vantagem. Fonte: Morgado e Rao, Pesquisa Agropecuária Brasileira 20(1):45-55, 1985, p. 52-53. https://apct.sede.embrapa.br/pab/article/download/14975/8695/66348 O mesmo artigo cita, sem que tenhamos aberto o original, uma síntese de 34 experimentos no Nordeste (Rao e Morgado, 1984) em que milho + caupi "produziu 41% mais" que as culturas isoladas: **citação secundária**.

11. **Mandioca com caupi, soja e amendoim em Pacajus-CE (1987/88).** No primeiro ciclo (9 meses) o LER foi de 1,35 a 1,69; no segundo (20 meses, depois da poda) caiu para 0,78 a 1,21: os autores desaconselham o consórcio no segundo ciclo. Semiárido não confirmado para o local. Fonte: Távora e outros, Ciência Agronômica 21(1/2):1-9, 1990, Tabela 8 (p. 6). https://periodicos.ufc.br/revistacienciaagronomica/article/download/91105/249059/346456

12. **Algodão com caupi em Gurinhém-PB (1983).** LER 1,56 com a cultivar TVx 1836-013J e 1,17 com a Pitiúba; mas a renda bruta do consórcio com a Pitiúba foi menor que a do algodão sozinho. Local no Agreste. Fonte: Beltrão e outros, Pesquisa Agropecuária Brasileira 21(3):271-284, 1986. https://apct.sede.embrapa.br/pab/article/download/14727/8411/65372

13. **Algodão com milho, feijão de corda e gergelim, em fazendas de famílias (Sergipe e Paraíba, 2020).** LER de 1,01 a 3,21. **Fraco:** a comparação é com a média municipal do IBGE, não com uma testemunha na mesma terra, e a produção vem do caderno de campo. Fonte: Diaconia, Cadernos de Agroecologia 17(2), 2022. https://cadernos.aba-agroecologia.org.br/cadernos/article/download/6952/5089/30024 e https://cadernos.aba-agroecologia.org.br/cadernos/article/download/6982/5104/30049

## Lacunas deste acervo

- Sem estudo aberto, no semiárido, para milho + guandu, milho + crotalária, milho + girassol, algodão + gergelim (só relato qualitativo: não foi vantajoso para o algodão em Missão Velha-CE, Revista ACSA 9(3):104-109, 2013).
- Só resumo aberto: Corrêa, Távora e Pitombeira (mamona + caupi e sorgo, Quixadá-CE, LER 1,08 a 1,45); Diniz 2016 (palma + sorgo, Serra Talhada-PE, LER 1,51); estudo do IFCE Iguatu (2025, milho + caupi).
- Não abertos: Rao e Morgado 1984, Távora 1988 e 1989, Santiago 2014.
