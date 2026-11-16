---
name: crop-rotation-recommender
description: Model and evaluate crop rotations and polyculture combinations, calculating Land Equivalent Ratio (LER), water use efficiency, and soil resilience metrics mapped to UN SDGs.
---

# Crop Rotation Recommender Skill

This skill provides methodologies, calculations, and agronomic guidelines to evaluate polyculture consortia and rotation cycles, specifically adapted for semi-arid climates and family farming systems.

## Quick Start: Calculating LER and Resilience Metrics

Run the bundled script to compute Land Equivalent Ratio (LER), water use efficiency (WUE), and soil resilience score:

```bash
# Example with Corn, Cowpea, and Squash
node .ai/skills/crop-rotation-recommender/scripts/calculate_metrics.cjs --crops "milho:1500:1100,caupi:700:550,jerimum:3500:3000" --water 1200
```

### Metrics Explained

1. **Land Equivalent Ratio (LER):**
   $$LER = \sum \frac{Y_{intercrop, i}}{Y_{monoculture, i}}$$
   - $LER > 1.0$: Consortia produces more yield per hectare than separate monocultures.
   - Land savings: $((LER - 1) / LER) \times 100\%$.

2. **Water Use Efficiency (WUE):**
   $$WUE = \frac{\text{Total Biomass Yield (kg)}}{\text{Water Consumed } (m^3)}$$

3. **Soil Resilience Score (0 - 100):**
   Evaluates functional biodiversity: biological nitrogen fixation (+25), living cover/mulch (+20), and crop stratification (+15).

## Regional Agronomy & Soil Matrix

For complete botanical parameters, soil types (Neossolos, Latossolos, Vertissolos), and pH ranges, consult:
- [semiarid_crops.md](references/semiarid_crops.md)

## UN Sustainable Development Goals (SDG) Linkage

- **ODS 2 (Zero Hunger):** Increases total yield per unit area and diversifies nutritional sources for smallholder families.
- **ODS 6 (Clean Water):** Living mulch cuts direct soil evaporation by 40-60%.
- **ODS 12 (Responsible Production):** Biological nitrogen fixation via legumes replaces synthetic Haber-Bosch fertilizers.
- **ODS 13 (Climate Action):** Root diversity sequesters soil organic carbon (SOC) and buffers thermal extremes.
- **ODS 15 (Life on Land):** Rebuilds soil microbiome and halts land degradation and desertification.
