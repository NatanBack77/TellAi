---
name: ibge-data-fetcher
description: Fetch and process official Brazilian agricultural statistics and municipal data from IBGE SIDRA PAM (yields, harvested areas, crop economic values).
---

# IBGE Data Fetcher Skill

This skill provides utilities and documentation to query, parse, and analyze official Brazilian municipal agricultural statistics from the IBGE SIDRA API (Produção Agrícola Municipal - PAM).

## Quick Start: Fetching Agricultural Data

Use the bundled Node.js script to query official production, yields (kg/ha), harvested area (ha), and production value (R$ mil):

```bash
# Juazeiro do Norte - CE (Default code: 2307304)
node .ai/skills/ibge-data-fetcher/scripts/fetch_ibge.cjs --city 2307304 --year 2023

# Crato - CE
node .ai/skills/ibge-data-fetcher/scripts/fetch_ibge.cjs --city 2304202 --year 2023

# Barbalha - CE
node .ai/skills/ibge-data-fetcher/scripts/fetch_ibge.cjs --city 2301901 --year 2023
```

### Script Output Fields

The script returns structured JSON:
- `municipality`: Name, IBGE code, Microrregião (e.g. Cariri), Mesorregião, State.
- `summary`: Total harvested area (`total_area_colhida_ha`), total production value (`total_valor_producao_mil_reais`), number of monitored crops.
- `crops`: Array of crops containing:
  - `crop_name`: Botanical / commercial crop name (e.g., Feijão, Milho, Mandioca).
  - `area_colhida_ha`: Harvested area in hectares.
  - `quantidade_produzida_t`: Quantity produced in metric tonnes.
  - `rendimento_medio_kg_ha`: Real average productivity (kg/ha) — baseline for Land Equivalent Ratio (LER).
  - `valor_producao_mil_reais`: Economic value generated.

## Technical References

For detailed table schemas, classification codes, and regional IBGE identifiers:
- [ibge_apis.md](references/ibge_apis.md)
