# NASA Earth Observation & Agroclimatology Missions

Este documento serve como referência técnica detalhada para consultas aos dados da NASA voltados para rotação de culturas, saúde do solo e policultura.

---

## 1. NASA POWER API (Agroclimatology)

- **URL Base:** `https://power.larc.nasa.gov/api/temporal/daily/point`
- **Comunidade:** `community=AG`
- **Autenticação:** Aberta, não requer token ou chave de API.
- **Variáveis Principais:**
  - `T2M`: Temperatura média a 2 metros (°C).
  - `T2M_MIN` / `T2M_MAX`: Temperatura mínima e máxima diária.
  - `PRECTOTCORR`: Precipitação corrigida diária (mm).
  - `RH2M`: Umidade relativa a 2 metros (%).
  - `ALLSKY_SFC_SW_DWN`: Radiação de ondas curtas descendente incidente na superfície em céu total ($MJ/m^2/dia$).
  - `CLRSKY_SFC_SW_DWN`: Radiação solar em céu límpido ("Campo Nu" / Clear Sky). A razão entre All-Sky e Clear-Sky expressa o índice de cobertura de nuvens.
  - `WS2M`: Velocidade do vento a 2 metros (m/s).

---

## 2. NASA SMAP (Soil Moisture Active Passive)

- **Missão:** Satélite em órbita polar com radiômetro em banda L (1.4 GHz).
- **Parâmetros:**
  - `Soil Moisture Surface (0-5 cm)`: Umidade volumétrica da camada superficial ($cm^3/cm^3$).
  - `Soil Moisture Root-Zone (0-100 cm)`: Umidade na zona das raízes (fundamental para agricultura familiar e perenes).
- **Acesso:** NASA Earthdata Search (produtos SPL3SMP / SPL4SMAU) ou via OpenDAP.
- **Aplicação:** Provar empiricamente que consórcios agrícolas e cobertura morta preservam a umidade do solo por semanas a mais após o término da quadra chuvosa.

---

## 3. NASA ECOSTRESS (na Estação Espacial Internacional - ISS)

- **Sensor:** Radiômetro térmico multiespectral de alta resolução (70m x 70m).
- **Parâmetros:**
  - `Evapotranspiration (ET)`: Evapotranspiração real de dossel e solo.
  - `Evaporative Stress Index (ESI)`: Detecção precoce de estresse hídrico antes de danos visíveis na biomassa.
  - `Water Use Efficiency (WUE)`: Relação entre carbono fixado e água transpirada.
- **Aplicação:** Identificar estresse térmico em monoculturas vs. microclima amenizado em sistemas consorciados e agroflorestais.

---

## 4. Landsat 8/9 & MODIS (Índices de Vegetação)

- **Resolução:** Landsat (30 metros, revisita a cada 8-16 dias) / MODIS (250m-1km, diário).
- **Cálculo de Índices:**
  - **NDVI:** $(NIR - RED) / (NIR + RED)$
  - **EVI:** $2.5 \times (NIR - RED) / (NIR + 6 \cdot RED - 7.5 \cdot BLUE + 1)$
  - **NDWI:** $(NIR - SWIR) / (NIR + SWIR)$
- **Interpretação:**
  - $NDVI > 0.6$: Vegetação densa e vigorosa.
  - $0.2 < NDVI < 0.4$: Vegetação esparsa ou Caatinga em transição seca.
  - $NDWI < 0$: Solo exposto ou vegetação severamente desidratada.
