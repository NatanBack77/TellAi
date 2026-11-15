---
name: nasa-agro-data
description: Fetch, process, and analyze NASA Earth Observation data (NASA POWER agroclimatology, SMAP soil moisture, ECOSTRESS, Landsat) for agricultural decision-making and crop rotation planning.
---

# NASA Agro-Data Skill

This skill provides procedures and utilities to query, parse, and analyze NASA Earth Observation datasets for farm decision-support tools, with emphasis on agroclimatology and soil conditions.

## Quick Start: Fetching Agroclimatology Data

Use the bundled Node.js script to retrieve NASA POWER daily data:

```bash
# Juazeiro do Norte - CE (Default coordinates: -7.21, -39.31)
node .ai/skills/nasa-agro-data/scripts/fetch_power.cjs --lat -7.21 --lon -39.31 --start 20240101 --end 20240131

# Output raw JSON format
node .ai/skills/nasa-agro-data/scripts/fetch_power.cjs --lat -7.21 --lon -39.31 --start 20240401 --end 20240415 --format json
```

### Script Output Fields

The script returns aggregated metrics:
- `precipitation_total_mm`: Total accumulated rainfall.
- `temperature_avg_celsius`: Mean air temperature at 2m.
- `temperature_max_celsius` / `temperature_min_celsius`: Extreme temperature thresholds.
- `relative_humidity_avg_percent`: Mean relative humidity.
- `solar_radiation_allsky_avg_mj_m2_day`: Incident shortwave radiation in all-sky conditions.
- `solar_radiation_clearsky_avg_mj_m2_day`: Radiation in cloud-free conditions ("Campo Nu").
- `clearsky_index`: Ratio of all-sky to clear-sky radiation (1.0 = completely cloud-free).

## Detailed Mission Reference

For in-depth mission specifications, spectral bands, and access methods for SMAP, ECOSTRESS, Landsat, and MODIS, refer to:
- [missions_and_apis.md](references/missions_and_apis.md)

## Integration in Application Code

To query NASA POWER directly from frontend/backend JavaScript:

```javascript
async function getNasaAgroMetrics(lat, lon, startDate, endDate) {
  const params = 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,RH2M';
  const url = `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=${params}&community=AG&longitude=${lon}&latitude=${lat}&start=${startDate}&end=${endDate}&format=JSON`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`NASA API error: ${res.status}`);
  const data = await res.json();
  return data.properties.parameter;
}
```
