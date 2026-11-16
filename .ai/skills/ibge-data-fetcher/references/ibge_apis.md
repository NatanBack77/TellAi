# Guia de APIs e Dados Agropecuários do IBGE

Este documento fornece as especificações e mapeamento de consultas para a API de Serviços de Dados do IBGE e API SIDRA (Sistema IBGE de Recuperação Automática).

---

## 1. API de Localidades (Municípios e Regiões)

- **Endpoint de Município por Código IBGE:**
  `https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{id}`
- **Códigos Relevantes da Região do Cariri (CE):**
  - **Juazeiro do Norte:** `2307304`
  - **Crato:** `2304202`
  - **Barbalha:** `2301901`
  - **Missão Velha:** `2308401`
  - **Brejo Santo:** `2302503`

---

## 2. API SIDRA - Tabela 5457 (Produção Agrícola Municipal - PAM)

- **URL Base:**
  `https://servicodados.ibge.gov.br/api/v3/agregados/5457/periodos/{ano}/variaveis/{variaveis}?localidades=N6[{codigo_municipio}]&classificacao=782[{codigos_culturas}]`
- **Variáveis Oficiais da Tabela 5457:**
  - `8331`: Área plantada ou destinada à colheita (Hectares)
  - `216`: Área colhida (Hectares)
  - `214`: Quantidade produzida (Toneladas)
  - `112`: Rendimento médio da produção (Quilos por Hectare - kg/ha)
  - `215`: Valor da produção (Mil Reais)
- **Classificação 782 (Produtos das Lavouras Temporárias e Permanentes):**
  - `40122`: Milho (em grão)
  - `40112`: Feijão (em grão)
  - `40119`: Mandioca
  - `83388`: Abóbora
  - `40136`: Banana (cacho)
  - `40262`: Manga
  - `83395`: Gergelim
  - `40125`: Sorgo (em grão)
  - `40120`: Melancia
  - `40330`: Caju / Castanha de Caju (`40143`)

---

## 3. Aplicação no Desafio Field Shift

Os dados do IBGE representam o **cenário basal de monocultura real** dos agricultores de cada localidade:
- **Baseline de Rendimento ($Y_{mono}$):** O rendimento monocultural oficial (ex: Milho ~626 kg/ha, Feijão ~275 kg/ha) serve de denominador para o cálculo do **Land Equivalent Ratio (LER)**.
- **Risco Econômico:** Ao calcular o valor da produção por hectare, o sistema alerta o agricultor sobre o risco de monoculturas em anos secos e propõe consórcios com maior estabilidade de renda.
