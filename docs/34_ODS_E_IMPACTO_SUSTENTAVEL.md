# 34. ODS da ONU e Impacto Sustentável: Onde o SULCO se Conecta à Agenda 2030

Data: 2026-11-15.
Mapeamento sistemático de conformidade entre os módulos computacionais do **SULCO**, os dados orbitais da **NASA** e as metas oficiais dos **Objetivos de Desenvolvimento Sustentável (ODS/SDGs) da ONU**.
Este documento complementa a avaliação de alinhamento ao desafio (`docs/19_ALINHAMENTO_AO_DESAFIO.md`) e fornece o alicerce quantitativo para o pitch (`docs/17_PITCH.md`).

---

## 1. Resumo Executivo: O SULCO como Catalisador dos ODS

No Semiárido brasileiro, onde apenas **8,2% dos estabelecimentos rurais têm assistência técnica regular** (Censo Agropecuário 2017), as monoculturas sucessivas e a exposição do solo nu aceleram a desertificação e a pobreza no campo.

O SULCO atua na intersecção entre **Observação da Terra (NASA)**, **Estatísticas Oficiais (IBGE)** e **Agronomia Regenerativa**, impactando diretamente **5 ODS prioritários** e **5 ODS transversais**:

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 SULCO (Órbita ao Sulco)                │
                  └───────────────────────────┬────────────────────────────┘
                                              │
         ┌───────────────────┬────────────────┼───────────────────┬──────────────────┐
         ▼                   ▼                ▼                   ▼                  ▼
    ODS 2 (Fome)        ODS 6 (Água)     ODS 12 (Consumo)   ODS 13 (Clima)    ODS 15 (Solo)
  • LER > 1 consórcio  • ETo Hargreaves  • Fixação BNF      • Anomalia NDVI   • Risco erosão
  • Rotação 3 safras   • SMAP umidade    • Menos químico    • Cenários chuva  • Cobertura viva
  • Diversificação     • Anti-solo nu    • ZARC oficial     • Faixa ACI 90%   • Salva Caatinga
```

---

## 2. Matriz Detalhada: Metas Oficiais da ONU vs. Módulos do SULCO

| ODS & Meta ONU | Desafio no Semiárido | Implementação no SULCO (Código / Dados) | Variável NASA / IBGE | Avaliação Honesta (O que é vs. Lacuna) |
|---|---|---|---|---|
| **ODS 2 • Meta 2.4**<br>Sistemas sustentáveis e resilientes de produção de alimentos | Monoculturas de milho e feijão quebram com veranicos; risco de fome familiar | `src/culturas/consorcio.py`<br>`data/culturas/ler_staging.csv`<br>`matriz_rotacao.csv` | **NASA MODIS** (NDVI de 16 dias)<br>**IBGE PAM** (rendimento municipal) | **É:** Evidência de LER de 1,05 a 1,82 em 8 estudos pareados no NE; rotação de 3 safras.<br>**Lacuna:** Não prevê produtividade no talhão do agricultor. |
| **ODS 6 • Meta 6.4**<br>Aumento substancial da eficiência no uso da água | Chuvas concentradas (fev-mai) e perda de água por solo nu em meses quentes | `src/app/app.py` (Seções 2 e 5)<br>`src/coleta/power.py`<br>`config.yaml` (`solo_nu`, `veranico`) | **NASA POWER** (`PRECTOTCORR`, `T2M`)<br>**NASA SMAP** (umidade radicular 0-100 cm) | **É:** ETo de referência (Hargreaves-Samani), chuva menos ETo e diagnóstico de campo nu.<br>**Lacuna:** Sem coeficiente de cultivo ($K_c$) específico nem balanço hídrico do talhão. |
| **ODS 12 • Meta 12.4**<br>Manejo ecológico de químicos e redução de resíduos | Dependência de fertilizantes nitrogenados fósseis (ureia) de alto custo | `src/culturas/rotacao.py`<br>`data/culturas/tabela_culturas.csv`<br>`src/culturas/zarc.py` | **ZARC MAPA** (janelas de plantio)<br>**ISRIC SoilGrids** (textura estimada) | **É:** Matriz penaliza repetição da mesma família e prioriza leguminosas com fixação BNF.<br>**Lacuna:** Não calcula dose de adubação nem analisa química do solo local. |
| **ODS 13 • Meta 13.1**<br>Fortalecimento da resiliência a desastres climáticos | Veranicos severos, ondas de calor e variabilidade pluviométrica extrema | `src/modelos/preditivo.py`<br>`src/modelos/cenarios.py`<br>`src/modelos/conformal.py` | **NASA POWER** (temperatura extrema e seca)<br>**MODIS** (persistência vegetal) | **É:** Previsão de anomalia de NDVI com 28% menos erro; incerteza calibrada (ACI 80%/90%); cenários de chuva.<br>**Lacuna:** Não prevê a próxima quadra chuvosa (fonte é a FUNCEME). |
| **ODS 15 • Meta 15.3**<br>Neutralização da degradação da terra e desertificação | Solos rasos (Neossolos) vulneráveis a erosão laminar durante torós | `src/modelos/erosao.py`<br>`src/app/app.py` (Camada no mapa)<br>`src/coleta/srtm.py` | **NASA SRTM** (declividade/relevo)<br>**SoilGrids** (argila, areia, silte) | **É:** Indicador relativo de risco de erosão e escoamento entre os 195 pontos do semiárido.<br>**Lacuna:** Não é modelo RUSLE empírico; não mede taxa em t/ha/ano. |

---

## 3. Os ODS Transversais e de Impacto Social

Além dos 5 pilares agroecológicos, o SULCO responde a metas socioeconômicas e de inovação:

1. **ODS 1 (Erradicação da Pobreza) & ODS 8 (Trabalho Decente e Renda):**
   - *Como atua:* O app incorpora dados de receita bruta por hectare do **IBGE PAM** de Juazeiro do Norte e de 184 municípios do Ceará (`tabela_culturas.csv`), permitindo comparar culturas comerciais (feijão, milho, banana, mandioca) e orientando a rotação de 3 safras para mitigar a volatilidade da renda familiar.
2. **ODS 9 (Indústria, Inovação e Infraestrutura) & ODS 10 (Redução das Desigualdades):**
   - *Como atua:* Democratiza dados aeroespaciais de ponta (satélites de centenas de milhões de dólares) em uma ferramenta acessível por celular e navegadores modestos (`frontend/`), reduzindo o abismo entre grandes latifúndios irrigados e pequenas roças camponesas.
3. **ODS 17 (Parcerias e Meios de Implementação):**
   - *Como atua:* Integração de dados globais abertos da **NASA** (Open Science) com a infraestrutura pública brasileira (**IBGE, MAPA/ZARC, FUNCEME**), servindo como ponte de cooperação científica para a extensão rural comunitária.

---

## 4. O LER (Land Equivalent Ratio) e o ODS 2 no SULCO

Conforme registrado em `docs/29_LER_CONSORCIO.md`, o SULCO trata o **LER** com honestidade exemplar:

- **O que a literatura do Semiárido comprova:** 8 estudos em sequeiro no Ceará, Paraíba e Pernambuco registraram que consórcios como **Milho + Caupi (LER 1,05 a 1,34)** e **Palma + Caupi (LER 1,48 a 1,82)** produzem mais alimento por hectare do que cultivos separados, salvando até 35% de terra de desmatamento.
- **Como o SULCO entrega:** O LER **não inventa notas** no ranking do agricultor, mas é exibido como **rótulo de evidência científica** na tela de recomendações:
  > *"Este par já foi estudado em consórcio no semiárido (LER observado de X a Y em N experimentos; não é a medição do seu terreno)."*

---

## 5. Declaração de Honestidade Científica sobre os ODS (Para a Banca)

Para garantir pontuação máxima nos critérios de **Impacto, Validade e Apresentação** do NASA Space Apps Challenge, a equipe adota as seguintes regras de comunicação:

1. **O SULCO é ferramenta de apoio, não substituto:** Apoia a conversa com o técnico extensionista; não promete produtividade em sacas nem lucro garantido.
2. **Métricas validadas vs. Lacunas explícitas:**
   - O ganho de 28% no erro de NDVI é sobre a climatologia histórica com validação selada (`docs/05_EXPERIMENTOS.md`).
   - A cobertura de solo e o risco de erosão são indicadores relativos orientadores, não ensaios de laboratório de pedologia.
3. **Alinhamento genuíno:** A solução não adicionou os ODS como "etiquetas de marketing", mas derivou suas funcionalidades da necessidade biofísica do Semiárido Cearense de cumprir a Agenda 2030.
