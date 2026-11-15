#!/usr/bin/env node
/**
 * calculate_metrics.cjs - Calculates Land Equivalent Ratio (LER), WUE, and Soil Resilience
 * Usage:
 *   node calculate_metrics.cjs --crops "milho:1200:900,caupi:600:500,jerimum:3000:2600" --water 1500
 * Format: --crops "<name>:<mono_yield_kg>:<intercrop_yield_kg>,..." --water <cubic_meters>
 */

function parseArgs() {
  const args = process.argv.slice(2);
  let cropsInput = 'milho:1200:900,caupi:600:500,jerimum:3000:2600';
  let waterM3 = 1500;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--crops' && args[i + 1]) cropsInput = args[++i];
    else if (args[i] === '--water' && args[i + 1]) waterM3 = parseFloat(args[++i]);
  }

  const crops = cropsInput.split(',').map((item) => {
    const [name, mono, inter] = item.split(':');
    return {
      name: name.trim(),
      monoYield: parseFloat(mono) || 1,
      interYield: parseFloat(inter) || 1
    };
  });

  return { crops, waterM3 };
}

function calculateMetrics({ crops, waterM3 }) {
  let totalLER = 0;
  let totalInterYield = 0;
  const breakdown = [];

  crops.forEach((c) => {
    const partialLER = c.interYield / c.monoYield;
    totalLER += partialLER;
    totalInterYield += c.interYield;
    breakdown.push({
      crop: c.name,
      mono_yield_kg_ha: c.monoYield,
      intercrop_yield_kg_ha: c.interYield,
      partial_ler: parseFloat(partialLER.toFixed(3))
    });
  });

  const landSavingsPercent = totalLER > 1 ? ((totalLER - 1) / totalLER) * 100 : 0;
  const wue = waterM3 > 0 ? totalInterYield / waterM3 : null;

  // Ecological and Soil Resilience Score (0 - 100)
  const hasLegume = crops.some(c => ['caupi', 'feijao', 'guandu', 'crotalaria', 'soja'].some(l => c.name.toLowerCase().includes(l)));
  const hasCover = crops.some(c => ['abobora', 'jerimum', 'melancia', 'palma'].some(cov => c.name.toLowerCase().includes(cov)));
  const cropCount = crops.length;

  let soilScore = 40; // baseline
  if (hasLegume) soilScore += 25; // biological N-fixation
  if (hasCover) soilScore += 20;  // living mulch & moisture retention
  if (cropCount >= 3) soilScore += 15; // stratification & biodiversity
  soilScore = Math.min(soilScore, 100);

  return {
    summary: {
      total_ler: parseFloat(totalLER.toFixed(3)),
      advantage: totalLER > 1.0 ? 'Produtividade Consorciada Superior' : 'Monocultura Mais Eficiente',
      land_savings_percent: parseFloat(landSavingsPercent.toFixed(1)),
      total_biomass_yield_kg_ha: totalInterYield,
      water_use_efficiency_kg_m3: wue ? parseFloat(wue.toFixed(3)) : null,
      soil_health_resilience_score: soilScore
    },
    crops_breakdown: breakdown,
    sdg_alignment: {
      sdg_2_zero_hunger: `LER de ${totalLER.toFixed(2)} indica ${landSavingsPercent.toFixed(0)}% mais terra necessária se cultivado isolado, ampliando a segurança alimentar.`,
      sdg_6_clean_water: `WUE de ${wue ? wue.toFixed(2) : 'N/A'} kg/m³ com redução da evapotranspiração do solo.`,
      sdg_12_responsible_production: hasLegume ? 'Fixação biológica de Nitrogênio reduz adubos químicos fósseis.' : 'Recomenda-se adicionar leguminosa.',
      sdg_13_climate_action: 'Aumento do Carbono Orgânico do Solo (SOC) e microclima atenuado.',
      sdg_15_life_on_land: 'Preservação de microbiota do solo e polinizadores.'
    }
  };
}

try {
  const input = parseArgs();
  const result = calculateMetrics(input);
  console.log(JSON.stringify(result, null, 2));
} catch (err) {
  console.error(`Error: ${err.message}`);
  process.exit(1);
}
