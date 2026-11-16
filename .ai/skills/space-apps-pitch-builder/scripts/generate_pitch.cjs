#!/usr/bin/env node
/**
 * generate_pitch.cjs - Generates structured NASA Space Apps Challenge Pitch & Submission Markdown
 * Usage: node generate_pitch.cjs [--title "Project Title"] [--slogan "One liner"]
 */

function parseArgs() {
  const args = process.argv.slice(2);
  const data = {
    title: 'TerraViva: Orbital Agro-Decision System',
    slogan: 'Empowering smallholder resilience through NASA Earth data and regenerative polyculture rotations.'
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--title' && args[i + 1]) data.title = args[++i];
    else if (args[i] === '--slogan' && args[i + 1]) data.slogan = args[++i];
  }
  return data;
}

function generateContent(data) {
  return `# ${data.title}
**${data.slogan}**

---

### 👥 Equipe Big Space Creative (Juazeiro do Norte - CE)
- **Nathanael Ferreira Bueno** (Líder / Coordenação de Projeto)
- **Natanael Marcelino da Silva Vieira** (Pesquisa & Validação Agronômica)
- **Enzo Almino de Lima** (Estratégia ODS & Modelagem de Dados)
- **Arthur de Araujo Neves** (Desenvolvimento & Arquitetura de Software)
- **Antenor Pires de Lima Neto** (Engenharia de Prompt & Inteligência de Sistema)
- Instagram: \`@bigspacecreative\`

### 🎯 Desafio Oficial NASA Space Apps
**Field Shift: Adapting Farms with NASA Data**

---

## 📌 1. Resumo do Projeto (High-Level Summary)
Agricultores familiares do semiárido cearense e de regiões áridas globais enfrentam mudanças drásticas no padrão pluviométrico, picos extremos de calor e acelerada degradação do solo por monoculturas. O **${data.title}** é uma plataforma inteligente de apoio à decisão que cruza observações orbitais da NASA (precipitação, radiação solar e umidade do solo) com características locais de solo (pH, textura e tipo de solo) para prescrever consórcios agrícolas sinérgicos e rotações de culturas resilientes.

Nossa solução comprova que a transição de monoculturas para policulturas planejadas eleva o Land Equivalent Ratio (LER > 1.3), economiza mais de 40% de água e restaura a microbiota do solo, conectando ciência aeroespacial com segurança alimentar comunitária.

---

## 🛰️ 2. Dados e Recursos da NASA Utilizados
- **NASA POWER API (Agroclimatology):** Variáveis \`PRECTOTCORR\` (chuvas), \`T2M\` (temperatura), \`ALLSKY_SFC_SW_DWN\` e \`CLRSKY_SFC_SW_DWN\` (radiação e dias sem nuvens no semiárido).
- **NASA SMAP:** Dados de umidade volumétrica da zona radicular (0-100 cm).
- **NASA ECOSTRESS:** Monitoramento de estresse evapotranspirativo e eficiência hídrica da lavoura.
- **Landsat 8/9 & MODIS:** Índices de vigor de biomassa (NDVI e EVI).

---

## 🎯 3. Impacto Mensurável nos ODS da ONU
- **ODS 2 (Fome Zero - Meta 2.4):** Aumento de até 35% no rendimento alimentar por hectare com menor vulnerabilidade a secas.
- **ODS 6 (Água Potável - Meta 6.4):** Redução drástica da evapotranspiração do solo através de cobertura vegetal permanente.
- **ODS 12 (Produção Responsável - Meta 12.4):** Substituição de adubos sintéticos via fixação biológica de Nitrogênio com leguminosas nativas.
- **ODS 13 (Ação Climática - Meta 13.1):** Aporte contínuo de biomassa radicular, estocando Carbono Orgânico no Solo (SOC).
- **ODS 15 (Vida Terrestre - Meta 15.3):** Contenção da desertificação e proteção da biodiversidade da Caatinga.

---

## ⏱️ 4. Roteiro de Apresentação em Vídeo (Pitch de 4 Minutos / 240 Segundos)

| Tempo | Seção | Conteúdo Chave |
| :--- | :--- | :--- |
| **00:00 - 00:40** | **O Gancho (Hook)** | Mostrar a aridez do solo degradado, seca e o dilema do agricultor familiar que perde a safra com monoculturas. |
| **00:40 - 01:20** | **A Solução** | Apresentar o ${data.title}: como os olhos da NASA no espaço encontram a sabedoria dos consórcios ancestrais. |
| **01:20 - 02:30** | **Demo do Protótipo** | Navegar no sistema: selecionar Juazeiro do Norte, ver dados da NASA POWER em tempo real, inserir solo e receber recomendação com LER. |
| **02:30 - 03:15** | **Impacto & Validação** | Exibir gráficos dos ODS da ONU e dados reais de economia de água e regeneração do solo. |
| **03:15 - 04:00** | **Encerramento & Visão** | Equipe Big Space Creative: da Caatinga cearense para os agricultores de todo o planeta. |
`;
}

const input = parseArgs();
const md = generateContent(input);
console.log(md);
