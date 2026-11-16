#!/usr/bin/env node
/**
 * fetch_ibge.cjs - Fetches official municipal agricultural production (PAM) from IBGE SIDRA
 * Usage: node fetch_ibge.cjs [--city <ibge_code>] [--year <YYYY>] [--format json|summary]
 */

const https = require('https');

function parseArgs() {
  const args = process.argv.slice(2);
  const params = {
    city: '2307304', // Default Juazeiro do Norte - CE
    year: '2023',
    format: 'summary'
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--city' && args[i + 1]) params.city = args[++i];
    else if (args[i] === '--year' && args[i + 1]) params.year = args[++i];
    else if (args[i] === '--format' && args[i + 1]) params.format = args[++i];
  }
  return params;
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      if (res.statusCode < 200 || res.statusCode >= 300) {
        return reject(new Error(`HTTP ${res.statusCode} from ${url}`));
      }
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Failed to parse JSON: ${e.message}`));
        }
      });
    }).on('error', reject);
  });
}

async function getCityInfo(cityId) {
  const url = `https://servicodados.ibge.gov.br/api/v1/localidades/municipios/${cityId}`;
  const data = await fetchJson(url);
  return {
    id: data.id,
    name: data.nome,
    microrregiao: data.microrregiao ? data.microrregiao.nome : 'N/A',
    mesorregiao: data.microrregiao && data.microrregiao.mesorregiao ? data.microrregiao.mesorregiao.nome : 'N/A',
    state: data.microrregiao && data.microrregiao.mesorregiao && data.microrregiao.mesorregiao.UF ? data.microrregiao.mesorregiao.UF.sigla : 'CE'
  };
}

async function getAgriculturalData(cityId, year) {
  // Classification 782 crop codes:
  // 40122: Milho, 40112: Feijão, 40119: Mandioca, 83388: Abóbora, 40136: Banana, 40262: Manga, 83395: Gergelim, 40125: Sorgo
  const cropCodes = '40122,40112,40119,83388,40136,40262,83395,40125';
  const variables = '216|214|112|215';
  const url = `https://servicodados.ibge.gov.br/api/v3/agregados/5457/periodos/${year}/variaveis/${variables}?localidades=N6[${cityId}]&classificacao=782[${cropCodes}]`;

  return fetchJson(url);
}

function processPamData(cityInfo, raw, year) {
  const variableMap = {
    '216': 'area_colhida_ha',
    '214': 'quantidade_produzida_t',
    '112': 'rendimento_medio_kg_ha',
    '215': 'valor_producao_mil_reais'
  };

  const crops = {};
  let totalArea = 0;
  let totalValue = 0;

  raw.forEach((varGroup) => {
    const varKey = variableMap[varGroup.id];
    if (!varKey) return;

    (varGroup.resultados || []).forEach((res) => {
      const cat = res.classificacoes && res.classificacoes[0] && res.classificacoes[0].categoria;
      if (!cat) return;
      const cropId = Object.keys(cat)[0];
      const cropName = cat[cropId];

      if (!crops[cropId]) {
        crops[cropId] = {
          crop_id: cropId,
          crop_name: cropName,
          area_colhida_ha: null,
          quantidade_produzida_t: null,
          rendimento_medio_kg_ha: null,
          valor_producao_mil_reais: null
        };
      }

      const valStr = res.series && res.series[0] && res.series[0].serie && res.series[0].serie[year];
      const valNum = (valStr && valStr !== '...' && valStr !== '-') ? parseFloat(valStr) : null;
      crops[cropId][varKey] = valNum;

      if (varKey === 'area_colhida_ha' && valNum) totalArea += valNum;
      if (varKey === 'valor_producao_mil_reais' && valNum) totalValue += valNum;
    });
  });

  const cropList = Object.values(crops).filter(c => c.area_colhida_ha !== null || c.quantidade_produzida_t !== null);

  return {
    municipality: cityInfo,
    year: parseInt(year, 10),
    summary: {
      total_area_colhida_ha: totalArea,
      total_valor_producao_mil_reais: totalValue,
      total_culturas_monitoradas: cropList.length
    },
    crops: cropList
  };
}

async function main() {
  try {
    const params = parseArgs();
    const cityInfo = await getCityInfo(params.city);
    const raw = await getAgriculturalData(params.city, params.year);

    if (params.format === 'json') {
      console.log(JSON.stringify(raw, null, 2));
    } else {
      const summary = processPamData(cityInfo, raw, params.year);
      console.log(JSON.stringify(summary, null, 2));
    }
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

main();
