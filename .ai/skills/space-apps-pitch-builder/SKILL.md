---
name: space-apps-pitch-builder
description: Generate structured NASA Space Apps Challenge hackathon submissions, 4-minute video pitch scripts, and slide decks aligned with the 5 official judging criteria.
---

# Space Apps Pitch Builder Skill

This skill provides step-by-step procedures and generators to craft winning submission packages and high-impact pitch scripts for the NASA Space Apps Challenge.

## Quick Start: Generating Pitch & Submission Content

Run the bundled script to generate the complete project submission document and 240-second video pitch script:

```bash
node .ai/skills/space-apps-pitch-builder/scripts/generate_pitch.cjs --title "TerraViva: Orbital Agro-Decision System" --slogan "Empowering smallholder resilience through NASA Earth data and regenerative rotations"
```

## Pitch Structure (4 Minutes / 240 Seconds Rule)

1. **0:00 - 0:40 | The Hook:** The vulnerability of smallholders to climate shifts and soil depletion in semi-arid regions.
2. **0:40 - 1:20 | The Revelation:** How space observations meet traditional polyculture wisdom.
3. **1:20 - 2:30 | Prototype Walkthrough:** Live demonstration of the platform querying NASA POWER data, receiving local soil inputs, and calculating LER.
4. **2:30 - 3:15 | Impact & UN SDG Proof:** Quantifiable metrics (LER > 1.3, 40% water savings, carbon sequestration).
5. **3:15 - 4:00 | Call to Action:** Team Big Space Creative's vision to scale the solution from Cariri to global drylands.

## Official Judging Rubrics Reference

To review details on maximizing points across Impact, Creativity, Validity, Relevance, and Presentation, see:
- [judging_rubrics.md](references/judging_rubrics.md)
