#!/usr/bin/env node
/**
 * fetch_power.cjs - Fetches agroclimatology data from NASA POWER API
 * Usage: node fetch_power.cjs [--lat <lat>] [--lon <lon>] [--start <YYYYMMDD>] [--end <YYYYMMDD>] [--format json|summary]
 */

const https = require('https');

function parseArgs() {
  const args = process.argv.slice(2);
  const params = {
    lat: -7.21, // Default Juazeiro do Norte - CE
    lon: -39.31,
    start: null,
    end: null,
    format: 'summary'
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--lat' && args[i + 1]) params.lat = parseFloat(args[++i]);
    else if (args[i] === '--lon' && args[i + 1]) params.lon = parseFloat(args[++i]);
    else if (args[i] === '--start' && args[i + 1]) params.start = args[++i];
    else if (args[i] === '--end' && args[i + 1]) params.end = args[++i];
    else if (args[i] === '--format' && args[i + 1]) params.format = args[++i];
  }

  // Default date window: last 14 days up to 3 days ago (NASA POWER lag)
  if (!params.start || !params.end) {
    const now = new Date();
    const endD = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);
    const startD = new Date(now.getTime() - 17 * 24 * 60 * 60 * 1000);
    const formatDate = (d) => d.toISOString().slice(0, 10).replace(/-/g, '');
    params.end = formatDate(endD);
    params.start = formatDate(startD);
  }

  return params;
}

function fetchNasaPower(params) {
  const paramList = 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,RH2M,WS2M';
  const url = `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=${paramList}&community=AG&longitude=${params.lon}&latitude=${params.lat}&start=${params.start}&end=${params.end}&format=JSON`;

  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      if (res.statusCode < 200 || res.statusCode >= 300) {
        return reject(new Error(`NASA POWER API HTTP Error ${res.statusCode}: ${res.statusMessage}`));
      }
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Failed to parse NASA POWER response: ${e.message}`));
        }
      });
    }).on('error', reject);
  });
}

function computeSummary(raw, params) {
  const p = raw.properties && raw.properties.parameter;
  if (!p) throw new Error('No parameter data returned by NASA POWER API');

  const dates = Object.keys(p.T2M || {});
  if (dates.length === 0) throw new Error('Empty date range received');

  let totalRain = 0;
  let tempSum = 0;
  let rhSum = 0;
  let allSkyRadSum = 0;
  let clrSkyRadSum = 0;
  let maxTemp = -Infinity;
  let minTemp = Infinity;

  dates.forEach((d) => {
    const rain = p.PRECTOTCORR[d] || 0;
    const t = p.T2M[d] || 0;
    const tMax = p.T2M_MAX[d] || t;
    const tMin = p.T2M_MIN[d] || t;
    const rh = p.RH2M[d] || 0;
    const allRad = p.ALLSKY_SFC_SW_DWN[d] || 0;
    const clrRad = p.CLRSKY_SFC_SW_DWN[d] || 0;

    if (rain > -90) totalRain += rain;
    if (t > -90) tempSum += t;
    if (rh > -90) rhSum += rh;
    if (allRad > -90) allSkyRadSum += allRad;
    if (clrRad > -90) clrSkyRadSum += clrRad;
    if (tMax > maxTemp && tMax > -90) maxTemp = tMax;
    if (tMin < minTemp && tMin > -90) minTemp = tMin;
  });

  const count = dates.length;
  return {
    location: {
      latitude: params.lat,
      longitude: params.lon,
      label: (params.lat === -7.21 && params.lon === -39.31) ? 'Juazeiro do Norte - CE (Cariri)' : 'Custom Coordinates'
    },
    period: {
      start: params.start,
      end: params.end,
      days: count
    },
    metrics: {
      precipitation_total_mm: parseFloat(totalRain.toFixed(2)),
      precipitation_daily_avg_mm: parseFloat((totalRain / count).toFixed(2)),
      temperature_avg_celsius: parseFloat((tempSum / count).toFixed(2)),
      temperature_max_celsius: parseFloat(maxTemp.toFixed(2)),
      temperature_min_celsius: parseFloat(minTemp.toFixed(2)),
      relative_humidity_avg_percent: parseFloat((rhSum / count).toFixed(2)),
      solar_radiation_allsky_avg_mj_m2_day: parseFloat((allSkyRadSum / count).toFixed(2)),
      solar_radiation_clearsky_avg_mj_m2_day: parseFloat((clrSkyRadSum / count).toFixed(2)),
      clearsky_index: parseFloat((allSkyRadSum / (clrSkyRadSum || 1)).toFixed(3))
    }
  };
}

async function main() {
  try {
    const params = parseArgs();
    const raw = await fetchNasaPower(params);

    if (params.format === 'json') {
      console.log(JSON.stringify(raw, null, 2));
    } else {
      const summary = computeSummary(raw, params);
      console.log(JSON.stringify(summary, null, 2));
    }
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

main();
