# 27. Calendário verificado, solo, semente, mercado e critérios (2026-11-14)

Regras desta nota: todo número vem de arquivo lido ou de código rodado (scripts em `experimentos/calendario_solo/`); lacuna aparece como lacuna; "preço não é lucro"; "custo médio regional, não o seu"; nada daqui entra no padrão do motor. Sem DeepSeek, sem `.env`, sem edição de `src/app` e `src/api`.

## 1. Por que o assistente dizia "isso olha só chuva e calor; não olha solo, semente nem mercado"

**Onde nascia.** Em `src/llm/fatos.py`, `fatos_sugestao`, havia um fato fixo (texto digitado) chamado "limite da viabilidade", com `simples="Isso olha só chuva e calor; não olha solo, semente nem mercado."`. Ele não lia nada do que o motor tinha feito.

**O que era falso nessa frase.** `sugerir_por_foco` (`src/culturas/avaliar_sequencia.py`) chama `avaliacao_local`, que chama `motor.avaliar_local` com `mvp.parametros("sem", 1000)`; esse usa `usar_zarc=ZARC_PADRAO`, e `mvp.py:43` define `ZARC_PADRAO = True`. Logo a viabilidade da sugestão **já aplica as datas do zoneamento do governo (ZARC)**: risco 30, solo "qualquer", `ciclo.notas_ciclo` zera a nota de inícios fora dos decêndios. Conferido rodando `avaliacao_local("quixada_ce")`: milho com 3 decêndios permitidos (recurso `safra_2026_2027`), caupi 7, algodão 6, etc.; sorgo, guandu, crotalária, feijão-de-porco e mucuna recebem a janela APROXIMADA (união das anuais com ZARC; `aproximada: True`).

**O que existe nos dados e o que o motor usa** (ponto = município do CE):

| Dimensão | O que existe | Usado na viabilidade da sugestão? | Onde mais é usado |
|---|---|---|---|
| Clima | `clima_diario.parquet` (2001-2024, temperatura média e chuva diária) | SIM (nota trapezoidal de temperatura e chuva do ciclo, EcoCrop) | tudo |
| ZARC | `zarc_ce.parquet`: 184 municípios, 53 culturas, 4 safras; `dec1..dec36` (0 = sem indicação; 20/30/40 = risco), manejo, tipo de solo 1/2/3 (+ AD1..AD6 só perenes) | SIM, para as 11 culturas mapeadas (`MAPA_CULTURAS`), risco 30, solo "qualquer"; as 5 sem ZARC usam janela aproximada | `calcular_rotacao`: o solo arenoso/médio/argiloso (informado ou estimado pelo SoilGrids) escolhe o solo do ZARC |
| Solo SoilGrids (`solo.parquet`: areia, silte, argila, carbono, pH, 3 camadas, 195 pontos) | textura, pH, carbono | NÃO (antes desta nota). Só: risco de erosão (`risco_solo`: textura + carbono + declive + chuva erosiva), tipo de solo do ZARC e cartão do local | agora há `Parametros.solo_modo='ecocrop'` (opcional, desligado) |
| PAM/IBGE (`pam_ce.parquet`: área, produção, rendimento, valor, 2015-2023) | o que o município realmente colhe | NÃO na viabilidade | só `renda.py` (receita bruta/ha) quando a prioridade é renda |
| Preço | nada no projeto antes; agora staging CONAB (seção 4) | NÃO | nada |
| Semente | nada antes; agora staging SIGEF/CONAB (seção 4) | NÃO | nada |

**Correção.** `avaliar_sequencia.criterios_aplicados(av)` lê das próprias avaliações o que entrou (clima sempre; ZARC "sim/parcial/não" e risco; solo no ZARC; solo EcoCrop; semente, mercado e "o que o município já planta" = não). `fatos.texto_limite_viabilidade(crit)` gera a frase a partir disso; `sugerir_por_foco` devolve `criterios`. Para Quixadá a frase simples passa a ser: "Isso olhou chuva e calor e as datas do zoneamento do governo (nas plantas sem zoneamento, uma data aproximada); ainda não olha o solo, semente, preço e o que o seu município costuma plantar." Se o ZARC não entrar (ponto fora do CE), ela diz "ainda não olha as datas do zoneamento"; se `solo_modo='ecocrop'` entrar, o solo sai da lista de "não olha". Sem `criterios` (avaliação antiga), só afirma o que sempre vale. Testes: `tests/test_calendario.py` (frase gerada, sim/parcial/não, fato real de Quixadá).

Pendência que NÃO mexi (fora do escopo permitido): `motor.RISCOS_FIXOS` ainda tem a linha fixa "Não considera preço, mercado, pragas, doenças, solo nem disponibilidade de semente" (não cita o ZARC); `fatos.py` linhas de `fatos_ciclo` ("pragas e renda") continuam corretas. Testes `-W error` (test_fatos, test_chat_simples, test_conversa*, test_culturas, test_zarc): 468 passam; as mesmas 3 falhas anteriores (`test_contexto_do_cenario_cabe_em_2500_tokens`, `test_texto_simples_de_cada_tema_no_municipio_completo`, `test_texto_padrao_dos_caminhos_uma_linha_por_caminho_na_ordem`) seguem falhando por outros motivos.

## 2. Calendário verificado (15 municípios x 16 culturas)

Municípios: Fortaleza, Aracati, Itapipoca, Camocim (litoral); Quixadá, Quixeramobim, Tauá, Crateús (sertão); Crato, Barbalha (Cariri); Tianguá, Ibiapina (Ibiapaba); Limoeiro do Norte, Russas, Icó (Jaguaribe/Centro-Sul). Script: `experimentos/calendario_solo/calendario.py`. Saídas em `experimentos/calendario_solo/saida/`: `calendario_resumo.csv` (240 linhas), `calendario_zarc_longo.csv` (decêndios por mês, risco 20/30/40 e por solo), `calendario_<município>.csv` (mês x cultura, nº de decêndios 0-3 ao risco 30), `inconsistencias.csv` (261), `sigef_ce_cultura_mes.csv`.

**Leitura de `dec`.** Valores observados em todas as 72.630 linhas de sequeiro: {0, 20, 30, 40} (`leitura_dec.json`). O dicionário oficial do MAPA (baixado: `entrada/dicionario_tabua_risco_2026.pdf`, sha256 2143127c...4917c) diz só "dec1 a dec36: período de plantio no ano separado por decêndios de 1 a 36" e **não define 0/20/30/40**. A leitura "0 = sem indicação; 20/30/40 = nível de risco máximo em que o plantio é indicado" vem das portarias e da observação e é a que o código usa (`decN` permitido ao risco r se 0 < decN <= r; teste de monotonia r20 ⊆ r30 ⊆ r40 passa nos municípios testados). O mapeamento decêndio->mês (3 por mês) é convenção; o dicionário não o define. O dicionário define `Cod_Solo` 1 Arenoso, 2 Textura Média, 3 Argiloso, 11-16 AD1-AD6 (só perenes/olerícolas aparecem com AD) e `Cod_Outros_Manejos` 1 Sequeiro, 2 Irrigado.

**Exemplo (risco 30, qualquer solo)**, Quixadá (sertão central): milho fev-mar; caupi fev-mar-abr; feijão comum (ZARC "Feijão 2ª Safra") fev-mar; milheto fev-mai; mandioca fev-mar; algodão fev-mar; amendoim fev-abr; girassol e mamona fev-abr; gergelim fev-mai; palma jan-mar e dez. Tianguá (Ibiapaba): milho jan-mar, caupi fev-abr, milheto jan-mai. Fortaleza: palma SEM indicação (nenhum decêndio); caupi só mar-abr. Limoeiro do Norte: milho só fev e girassol só mar. Tabelas completas por município nos CSV (aqui não repito os 15).

**Cruzamentos e inconsistências (261 linhas em `inconsistencias.csv`):**

1. **Motor SEM ZARC sugere início fora da janela do ZARC (risco 30): 120 casos viáveis.** Por cultura (de 15 municípios): algodão 15, caupi 15, mamona 15, girassol 13, mandioca 12, milho 12, milheto 10, amendoim 9, feijão comum 9, gergelim 8, palma 2. Ou seja, sozinho o motor de clima põe o plantio em dez-jan (ex.: milho 01/01 em Crato, 11/01 em Tianguá; mamona 27/12 em Quixadá/Limoeiro), antes do início da quadra que o ZARC indica (fev-mar). Esse é o motivo de o app ligar o ZARC. Com ZARC ligado nenhuma sugestão de cultura mapeada cai fora da janela (teste `test_arquivos_do_calendario`).
2. **Culturas sem ZARC no motor: guandu, crotalária, feijão-de-porco, mucuna** (adubos verdes/leguminosas: não aparecem no ZARC do CE) e **sorgo** (mapa ambíguo). Para o sorgo o ZARC EXISTE: "Sorgo Granífero/Forrageiro (e 2ª safra)" em 184 municípios (e nos 15 do recorte), mas o projeto não os mapeou (granífero x forrageiro). Lacuna sanável: ao risco 30 os meses do sorgo no ZARC saem em `zarc_sorgo_nao_mapeado_meses_r30` do resumo (ex.: Crato/Crateús/Icó jan-abr; Russas fev-mai). Mesmo assim o motor dá sorgo INVIÁVEL nos 15 municípios (clima EcoCrop), apesar do PAM de sorgo em Limoeiro do Norte (1.083 ha/ano em 2021-23): inconsistência clima x PAM, aqui o clima do EcoCrop provavelmente é conservador demais para o sorgo; não resolvido.
3. **ZARC indica plantio, PAM sem área registrada: 64 casos** (amendoim, gergelim, girassol, mamona, algodão em vários municípios; PAM vazio não prova ausência: o arquivo transforma traço/reticência/X em NaN e não distingue zero de omitido). Para milho/feijão/mandioca em Fortaleza (urbano) é esperado.
4. **ZARC "sem indicação" (risco 30) mas PAM com área: 1 caso** (feijão comum em Aracati; o PAM junta caupi e comum, então o caupi pode explicar a área). **PAM com área, cultura sem ZARC: 1** (sorgo em Limoeiro do Norte).
5. **Palma em Fortaleza**: ZARC "palma forrageira" sem nenhum decêndio (único dos 15), enquanto o motor sem ZARC propõe 11/01. Em 13 de 15 municípios o início da palma sem ZARC já cai dentro do ZARC.
6. **Culturas sem nenhuma fonte de calendário no projeto:** guandu, crotalária, feijão-de-porco, mucuna (sem ZARC, sem PAM, só o clima do EcoCrop); milheto e palma têm ZARC mas não PAM (o arquivo PAM do projeto, tabela 1612 de lavouras temporárias, não traz milheto nem palma). Para esses, "plantada de fato" é lacuna.
7. **Ciclo**: FAO-56 Tabela 11 (11 culturas, linha da região "Arid" ou mediana; regiões de outros países, ex.: 'Arid Climate (plantio Dec/Jan)', 'Mediterranean', 'Idaho') e EcoCrop (5 culturas: guandu, palma, crotalária, feijão-de-porco, mucuna, ponto médio de GMIN-GMAX); coluna `ciclo_dias` e `ciclo_fonte` no resumo. Não há ciclo medido no semiárido brasileiro.

**O que o ZARC NÃO cobre.** Só risco climático de perda de produtividade (não é nota do EcoCrop); só as culturas listadas (53 no CE; das 16 do Sulco, 11 mapeadas); só sequeiro nesta leitura (existe linha irrigada, não usada); só Ceará neste arquivo; recurso mais recente por cultura (2026/27 > 2025/26 > 2024/25 > perene/olerícola; feijão comum = "Feijão 2ª Safra" é suposição, o "Feijão" 1ª safra no CE é só irrigado); por município, não por talhão; "qualquer solo" é o mais permissivo. O ZARC também ordena crédito e seguro (seção 4f), por isso sair da janela tem custo financeiro além do agronômico.

**"Plantada de fato por período"** — única fonte aberta achada com data de plantio: SIGEF (seção 4a), que são **campos de produção de semente**, não lavoura comercial. No CE (1.553 linhas, 50 municípios, safras 2013-2026): milho 626 campos (pico mar, 203), caupi 203 (abr-set; pico ago), sorgo 273 (jun-set), algodão 126, mamona 34 (dez-abr). Sem registro: girassol, mandioca, milheto, guandu, palma, crotalária, feijão-de-porco, mucuna. É indicação parcial e enviesada (produtores de semente, possivelmente irrigados), e **contradiz o ZARC** para o caupi (campos plantados em jul-set, fora da janela sequeiro fev-abr): provável irrigação/vazante. NÃO usar como calendário do agricultor.

## 3. Solo na viabilidade

**Colunas do EcoCrop (espelho OpenCLIM, commit ea43ecd, sha256 4187e884...d48d106, baixado de novo):** `PHOPMN/PHOPMX/PHMIN/PHMAX` (pH ótimo e absoluto, numéricos), `DEP/DEPR` (profundidade), `TEXT/TEXTR` (textura ótima e faixa: heavy/medium/light/organic/wide), `FER/FERR` (fertilidade), `SAL/SALR` (salinidade), `DRA/DRAR` (drenagem), `TOX/TOXR`. Extraído para `data/culturas/solo_staging.csv` (256 linhas: 16 culturas x 16 atributos; fonte, URL, coluna, trecho, data; 37 lacunas explícitas, p. ex. milho sem textura e sem drenagem). Script: `experimentos/calendario_solo/extrair_solo_staging.py`.

**O que o projeto consegue comparar com o local (SoilGrids, `risco_solo.solo_de_linha`, média 0-30 cm ponderada por 5/10/15 cm):** pH e textura (via argila, <15% arenoso, 15-35% médio, >35% argiloso). Profundidade, fertilidade, salinidade e drenagem existem na base, mas o projeto **não tem dado do local**: ficam LACUNA (não pontuam; aparecem em `sem_dado`). Sem inventar faixa.

**Implementação.** `src/culturas/solo_ecocrop.py`; `Parametros.solo_modo='sem'|'ecocrop'` (padrão `'sem'`). Nota de solo = mínimo(nota pH trapezoidal, nota textura) aplicada como TETO às notas de temperatura e chuva; avisos: "solo estimado de mapa global (250 m), não análise de solo", aviso de pixels válidos <50% ou pixel central sem dado; suposição no texto das suposições do cenário. SUPOSIÇÕES declaradas (sem fonte lida): arenoso=light, médio=medium, argiloso=heavy (o CSV não define essas classes); textura dentro da faixa mas fora da ótima = 0,5; teto pelo mínimo. Testes `tests/test_solo_ecocrop.py` (18 testes com `test_calendario`): staging com trecho que bate com o CSV, notas, lacunas, **padrão não muda** (compara com `baseline_padrao.json`, gerado ANTES da edição, para Quixadá com e sem ZARC), efeito só reduz nota, palma inviável.

**Antes/depois (15 municípios, ZARC ligado como no app; `efeito_solo.py`, `saida/efeito_solo*.csv`):**

| | sem solo | com solo EcoCrop |
|---|---|---|
| culturas viáveis por município, média (dp; min-max) | 14,73 (0,44; 14-15) | 13,13 (1,15; 10-14) |
| conjuntos distintos de culturas viáveis | 4 | 5 |
| distância de Jaccard média entre pares de municípios | 0,034 | 0,094 |
| dp da adequação entre municípios, média por cultura | 0,117 | 0,176 |

24 pares cultura-município deixam de ser viáveis: palma 14, girassol 5, algodão 2, crotalária 2, milheto 1; a adequação cai em 81 de 240 pares; **nenhuma data de início muda** (o teto não desloca o melhor decêndio). Cariri e Ibiapaba (pH 4,9-5,4) perdem mais (Crato: 5 culturas; Barbalha 4); litoral e Jaguaribe perdem só a palma (Fortaleza perde o girassol). Nos 184 pontos do CE: pH 4,8-6,7 (mediana 5,9); textura por argila: **181 "médio" e 3 "argiloso"**, ou seja, a textura quase não distingue municípios; só 2 pontos com <50% de pixels válidos (`nota_solo_184pontos.csv`).

**Resposta honesta: aumenta a diferença entre municípios? Sim, moderadamente, mas pelo motivo errado em parte.** A diferença vem do pH. O resultado depende de faixas do EcoCrop que merecem desconfiança: a palma tem `PHMIN` = 6,5 (e 7 a 7,5 ótimo), então fica com nota 0 em 182 de 184 pontos, **em contradição com o ZARC**, que traz palma com decêndios permitidos em 14 de 15 municípios, e com o uso real da palma no semiárido (não verifiquei fonte agronômica; apenas aponto o conflito dos dois dados abertos). Algodão, girassol e crotalária ficam com nota <1 em 117 pontos (pH ótimo começa em 6 e o SoilGrids dá 4,8-6,7). Textura e pH do SoilGrids são mapa de 250 m (mediana ~2 km), não análise. **Recomendação: manter DESLIGADO**; se ligar, tratar como aviso por cultura ("pH do mapa abaixo da faixa do EcoCrop; confirme com análise"), não como corte; revisar a palma antes de qualquer uso.

## 4. Semente e mercado: o que dá e o que não dá para obter

Arquivos em `data/externos/` (+ `manifesto_externos.json` com URL, data 2026-11-14, sha256 do bruto, licença). Scripts: `baixar_externos.py`, `baixar_siszarc_ce.py`.

### 4a. Semente

| Fonte | Abri? | Resultado | Nível / formato | Licença |
|---|---|---|---|---|
| **RNC / CultivarWeb (MAPA)** https://sistemas.agricultura.gov.br/snpc/cultivarweb/cultivares_registradas.php | sim (HTML 200) | consulta por formulário **com captcha** (securimage) para a lista completa; sem API nem CSV aberto achado | por cultivar/espécie; sem indicação regional no formulário visto | não lida |
| **SISZARC, cultivares indicadas no ZARC** https://dados.agricultura.gov.br/dataset/d68e269e-dbe5-44d9-83ec-1f0871427773 | cabeçalho e primeiras linhas lidos do CSV.gz (~237 MB; título do dataset diz "EM MANUTENÇÃO"); o recorte do CE (`baixar_siszarc_ce.py` -> `data/externos/siszarc_cultivares_ce.csv`) estava em execução ao fechar esta nota: **contagem de cultivares do CE NÃO verificada** | colunas Safra, Cultura, Obtentor/Mantenedor, **Cultivar, UF**, Grupo, Região de Adaptação (só trigo/soja). **Indicação regional por UF existe** | por UF; ver status abaixo | CC BY (CKAN) |
| **SIGEF campos de produção de sementes** https://dados.agricultura.gov.br/dataset/c7784a6e-f0ec-4196-a1ce-1d2d4784a58e | sim, 611.266 linhas -> 1.553 do CE | espécie, categoria, cultivar, **município, data de plantio**, área, produção estimada; 2013-2026 | município; CSV `;` | CC BY (CKAN); dicionário PDF no dataset |
| **CONAB preços** (semente de milho híbrido, CE) | sim | 2 observações (dez/2025 R$ 16,00/kg; mar/2026 R$ 14,50/kg), "preço pago pelo produtor" | UF CE | não lida |
| Embrapa (BRS), EMATERCE, programas de distribuição | NÃO abri | lacuna | | |

Conclusão: dá para saber **quais cultivares são produzidas como semente no CE e onde** (SIGEF: milho 27 cultivares em 17 municípios, caupi 7 em 13, algodão 55 em 19, sorgo 16 em 15) e **quais cultivares o ZARC indica por UF**; **não** dá para saber disponibilidade nem preço de semente por cultura (só milho), nem produtores de mudas/palma. Não houve afirmação de que a semente "está disponível ao agricultor".

### 4b. Mercado, preço e custo

| Dado | Fonte (aberta, sem login) | Nível | Periodicidade | Unidade | Culturas das 16 cobertas | Observação |
|---|---|---|---|---|---|---|
| Preço mensal por UF | CONAB Portal de Informações, `PrecosMensalUF.txt` (https://portaldeinformacoes.conab.gov.br/downloads/arquivos/PrecosMensalUF.txt), 21.349 linhas, sha256 em manifesto | UF e município (`PrecosMensalMunicipio.txt`) | mensal; **só 2025-2026** no arquivo | R$/kg; níveis: preço recebido pelo produtor, atacado, varejo, preço pago pelo produtor | CE: **feijão (caupi e comum cores)**, **milho**, **raiz de mandioca (para farinha)**, **algodão em caroço**, **mamona em baga (1 obs.)**; ausentes: sorgo, milheto, amendoim, girassol, gergelim, guandu, palma, adubos verdes | **PREÇO NÃO É LUCRO.** Exemplos 2026: milho recebido R$ 1,16-1,26/kg; caupi recebido R$ 3,33-4,93/kg; algodão em caroço R$ 2,80-3,20/kg; mandioca R$ 0,45-0,55/kg. Série curta: não dá tendência |
| Custo de produção | CONAB `CustoProducao.txt` (1.542 linhas, 2018-2026) | município-modelo | por painel (março etc.) | R$/ha e R$/unidade (custo variável, fixo, renda de fatores) | NE: **milho 2ª safra Crateús-CE (agricultura empresarial, 2024-2026)**; mandioca e algodão **só na Bahia**; feijão/sorgo/amendoim/girassol/gergelim: nenhum no NE | **Custo médio regional/modelo, não o seu.** Crateús milho: custo variável R$ 1.531-1.653/ha (2024-26, `conab_custos_producao_nordeste.csv`) |
| Preço mínimo/PGPM | CONAB (arquivo `PrecosMinimosVigentes` e `PGPMBrasil` deram 404 nas URLs que testei) | | | | | LACUNA: não achei o arquivo; página oficial não confirmada |
| CEPEA/ESALQ | https://www.cepea.org.br/br/consultas-ao-banco-de-dados-do-site.aspx devolveu **403** ao acesso automatizado; termos não lidos | | | | | BLOQUEADO; alternativa: planilha manual por indicador, com licença |
| CEASA-CE | só boletim diário em PDF/site (https://www.ceasa-ce.com.br/boletim-diario-de-precos/, indicado em resultado de busca; não abri) e Prohort/CONAB | | | | | hortifrúti: não cobre as 16 culturas |
| IBGE PAM (já no projeto) | SIDRA 1612 | município | anual 2015-2023 | ha, t, kg/ha, mil R$ | 10 das 16 (feijão junta caupi e comum; sem milheto, guandu, palma, adubos verdes) | receita bruta/ha em `renda.py`; **não é lucro** |

### 4c. Dados financeiros e de proteção (pedido adicional)

| Dado | O que li | Fonte aberta | Cobre | Estado |
|---|---|---|---|---|
| **Produtividade por município** | rendimento médio (kg/ha) e valor, 2015-2023 | IBGE PAM `pam_ce.parquet` (já temos) | 10 culturas | pronto |
| **Garantia-Safra (semiárido)** | Lido no PDF do IPECE/CE "Avaliação Executiva MAPP 38 - Garantia Safra" (https://www.ipece.ce.gov.br/wp-content/uploads/sites/45/2025/02/Avaliacao-Executiva-MAPP-38-GarantiaSafra.pdf): beneficiário elegível ao Pronaf, **renda de até 1,5 salário mínimo** (sem aposentadoria rural), **área de plantio de 0,6 a 5 ha**, benefício quando a **perda por estiagem é de 50% ou mais**; no texto o benefício citado é de **R$ 850,00** e a divisão da contribuição por benefício de R$ 17 (agricultor), R$ 51 (município), R$ 102 (estado, FECOP) e R$ 340 (União) (soma R$ 510, que o próprio texto questiona frente aos R$ 850). Reportagens (resultado de busca, NÃO li a norma) citam R$ 1.200 desde 2023, adesão de 181 municípios do CE e projeto PL 1.282/2024 para baixar a perda para 40%. | MDA/Sead/Caixa: norma oficial **não aberta** | feijão, milho, arroz, mandioca, algodão (lista a conferir) | valores de safras diferentes; CONFERIR antes de mostrar ao agricultor |
| **Pronaf** | Resultados de busca (não li resolução do CMN nem site do MDA): Plano Safra da Agricultura Familiar 2025/26 com R$ 78,2 bi para Pronaf; custeio com juros de 2% a 8% por faixa de renda; Pronaf B 0,5% a.a. até R$ 20 mil; plano 2026/27 R$ 85,2 bi. Dados conflitantes entre fontes | MDA / CMN / BCB (MCR) | todas as lavouras financiáveis | NÃO LIDO NA FONTE: lacuna; não implementar valores |
| **Proagro** | Resultados de busca: o ZARC condiciona a cobertura (empreendimento fora das condições do ZARC pode ser excluído); a Resolução CMN 5.224/2025 prevê redução de 5 p.p. de cobertura para empreendimentos com 30% de risco no ZARC. Texto oficial **não lido** | BCB, MCR | culturas zoneadas | NÃO LIDO NA FONTE |
| **Seguro rural / EMATERCE / Embrapa (custo e cultivar)** | não abri | | | lacuna |

## 5. O que fecha lacuna, o que continua faltando

Fecha: motivo da frase e frase gerada dos critérios; calendário ZARC por município com leitura de `dec` conferida contra o dicionário; solo do EcoCrop em staging e critério opcional medido; staging aberto de semente (SIGEF, SISZARC), preço, custo; Garantia-Safra lido em fonte do estado (valores de uma safra).

Continua faltando: (i) calendário "plantado de fato" por período (PAM só anual; SIGEF só semente); (ii) ZARC de sorgo não mapeado; (iii) ciclo medido no semiárido; (iv) profundidade, fertilidade, salinidade e drenagem do local; (v) preço de sorgo, milheto, amendoim, girassol, gergelim, guandu, palma e adubos verdes; série de preço >14 meses; (vi) custo de feijão, mandioca, algodão, amendoim etc. no CE; (vii) PGPM/preço mínimo, CEPEA, EMATERCE, Embrapa; (viii) Pronaf/Proagro/Garantia-Safra lidos na norma; (ix) validação com o técnico local de qualquer calendário.

## 6. Financeiro e critérios que o agricultor escolhe (desenho; NADA implementado no motor)

`src/culturas/renda.py` hoje calcula **receita bruta/ha** do PAM (média 2021-2023, valores correntes, sem inflação; mínimo 2 anos; aviso "não é lucro"). Proposta: o agricultor marca 1 a 3 critérios; cada critério só ordena culturas **com dado**; as sem dado aparecem como "sem dado", nunca como nota 0 nem imputação. Rótulos obrigatórios: "preço não é lucro", "custo médio regional, não o seu", fonte visível, "A avaliar com técnico local".

| Critério | Dado que sustenta | Cobertura hoje | Lacuna/risco |
|---|---|---|---|
| Economizar água | `demanda_hidrica_mm_ciclo` (FAO-56) | só onde há dado FAO; sequeiro (a água da irrigação não é calculada) | culturas sem FAO ficam "sem dado" |
| Proteger o solo | palha (kg/ha) e N fixado da tabela; risco de erosão (declive, textura, carbono, chuva erosiva) | parcial | valores de estudos diferentes; solo é mapa global |
| Menor custo de entrada | custo CONAB (R$/ha) e preço de semente CONAB | **sem dado** para quase todas no CE (só milho 2ª safra Crateús; semente só milho) | marcar "sem dado"; não estimar |
| Menor risco de perda | fração de anos viáveis do motor, janela e risco do ZARC (20/30/40), regra do Garantia-Safra | clima: todas; ZARC: 11 | ZARC não é probabilidade de perda do talhão |
| Renda bruta | PAM (valor/área) e preço recebido CONAB (2025-26) | PAM 10 de 16; preço 5 de 16 | **preço não é lucro**; sem custo não há margem |
| Rapidez do ciclo | `ciclo_dias` (FAO/EcoCrop) | 16 de 16 | ciclo de referência de outros países |
| Pouca mão de obra | nenhum dado no projeto (CONAB tem preço de diarista, não horas por cultura) | **sem dado** | |
| Solo compatível (opcional) | pH e textura SoilGrids x EcoCrop | 16 de 16 (textura: 15; milho sem faixa) | ver seção 3; palma suspeita |

## 7. Recomendação (ordem) e decisões para o usuário

1. Manter a frase gerada (feito) e acrescentar ao teste da API/app, quando permitido, a leitura de `criterios`.
2. Mapear o ZARC de sorgo (granífero e forrageiro 2ª safra) com decisão explícita: hoje o motor o trata como sem ZARC embora o ZARC o traga.
3. Mostrar o calendário ZARC (risco 20/30/40) como contexto ao agricultor (meses permitidos) em vez de só um "melhor início".
4. Solo EcoCrop: manter desligado; se ligado, só como aviso de pH/textura; revisar palma e a regra textura->classe antes.
5. Preço/custo: usar CONAB como contexto rotulado só para as culturas cobertas; o resto "sem dado"; nunca somar a ranking sem custo.
6. Ler as normas (Garantia-Safra, Pronaf, Proagro) antes de qualquer número ao agricultor.

Decisões suas: (a) mapear sorgo no ZARC (granífero? forrageiro? ambos); (b) aceitar `solo_modo='ecocrop'` como aviso (não corte)?; (c) quais critérios do agricultor entram primeiro (sugestão: água, solo, risco, ciclo, renda bruta rotulada); (d) incluir o resumo SIGEF no app, com a ressalva "campos de semente", ou não; (e) autorizar ler as fontes oficiais de crédito/seguro e abrir CEPEA com termos de uso; (f) o que fazer com o `motor.RISCOS_FIXOS` (texto fixo sem ZARC).
