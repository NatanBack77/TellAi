import { Seo } from "@/shared/components/seo/Seo";
import { Logo } from "@/shared/components/brand/Logo";
import { Button } from "@/shared/components/ui/Button";
import { Stepper } from "@/shared/components/ui/Stepper";
import campo from "@/assets/onboarding/campo.webp";
import nuvemDia from "@/assets/onboarding/nuvem-dia.webp";
import nuvemTarde from "@/assets/onboarding/nuvem-tarde.webp";
import nuvemNoite from "@/assets/onboarding/nuvem-noite.webp";
import soloArenoso from "@/assets/solos/arenoso.webp";
import soloMedio from "@/assets/solos/medio.webp";
import soloArgiloso from "@/assets/solos/argiloso.webp";
import { CloudSun, MapPin, Plant, Question } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { AlturaSuave } from "@/shared/components/motion/AlturaSuave";
import { deslizarPasso, MOLA_SUAVE, surgirEmCascata } from "@/shared/components/motion/transicoes";
import {
  CLIMAS,
  DESCRICAO_CLIMA,
  DESCRICAO_SOLO,
  ROTULO_CLIMA,
  ROTULO_SOLO,
  SOLOS,
  type Clima,
  type Solo,
} from "../models/perfil.model";
import { MunicipioPicker } from "../components/MunicipioPicker";
import { OpcoesVisuais, type OpcaoVisual } from "../components/OpcoesVisuais";
import { PASSOS_STEPPER, type Etapa } from "../viewmodels/etapas";
import { useOnboardingViewModel } from "../viewmodels/useOnboardingViewModel";

/** Uma frase por passo, sem título. A de boas-vindas fica pequena, como no Figma. */
const PERGUNTA: Record<Etapa, string> = {
  "boas-vindas":
    "Seja bem-vindo(a) ao nosso sistema. Iremos realizar algumas perguntas para melhores resultados.",
  municipio: "Em qual município fica a sua roça? Digite o nome e escolha na lista.",
  solo: "Como é a terra onde você planta? Aperte um punhado de terra úmida na mão e escolha a foto mais parecida.",
  clima:
    "Como costuma ser o clima na sua região ao longo do ano: quanto chove e por quanto tempo fica seco?",
  fim: "Agradecemos pelo compartilhamento das informações. Agora você pode prosseguir para o sistema.",
};

// Clima: gradientes e nuvens do Figma (Day / tarde / Night) + um tom quente para "Quente".
const VISUAL_CLIMA: Record<Clima, Pick<OpcaoVisual<Clima>, "fundo" | "nuvem" | "icone">> = {
  semiarido: { fundo: "from-[#7b718b] via-[#c98a67] via-70% to-[#f99e4d]", nuvem: nuvemTarde },
  tropical: { fundo: "from-[#6bc6fd] via-[#2dacfb] via-70% to-[#5fb4e3]", nuvem: nuvemDia },
  quente: { fundo: "from-[#fbbf24] via-[#f59e0b] via-70% to-[#ea580c]", nuvem: nuvemDia },
  nao_sei: { fundo: "from-[#565656] via-[#676767] via-70% to-[#333]", nuvem: nuvemNoite },
};

// Solo: fotos reais (créditos em src/assets/solos/CREDITOS.md).
const VISUAL_SOLO: Record<Solo, Pick<OpcaoVisual<Solo>, "fundo" | "foto" | "icone">> = {
  arenoso: { foto: soloArenoso },
  medio: { foto: soloMedio },
  argiloso: { foto: soloArgiloso },
  nao_sei: { fundo: "from-white to-bg-soft", icone: <Question size={34} /> },
};

const climas = CLIMAS.map((valor) => ({
  valor,
  rotulo: ROTULO_CLIMA[valor],
  descricao: DESCRICAO_CLIMA[valor],
  ...VISUAL_CLIMA[valor],
}));
const solos = SOLOS.map((valor) => ({
  valor,
  rotulo: ROTULO_SOLO[valor],
  descricao: DESCRICAO_SOLO[valor],
  ...VISUAL_SOLO[valor],
}));

export function OnboardingView() {
  const vm = useOnboardingViewModel();

  return (
    <div className="flex min-h-dvh">
      <Seo title="Primeiros passos" />
      <main className="relative flex flex-1 items-center justify-center overflow-hidden p-2.5">
        <img
          src={campo}
          alt=""
          className="pointer-events-none absolute inset-0 size-full object-cover"
        />

        <motion.form
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={MOLA_SUAVE}
          onSubmit={(e) => {
            e.preventDefault();
            if (vm.podeAvancar) vm.avancar();
          }}
          className="relative flex w-full max-w-[680px] flex-col items-end gap-6 rounded-3xl border border-bg-border bg-white/70 p-5 backdrop-blur-md sm:p-6"
        >
          <Logo className="w-full" />

          {vm.passoStepper >= 0 && (
            <Stepper
              passos={PASSOS_STEPPER}
              atual={vm.passoStepper}
              podeIrPara={vm.podeIrParaPasso}
              onIrPara={vm.irParaPasso}
            />
          )}

          <AlturaSuave className="w-full">
            <AnimatePresence mode="wait" initial={false} custom={vm.direcao}>
              <motion.div
                key={vm.etapa}
                custom={vm.direcao}
                variants={deslizarPasso}
                initial="entrar"
                animate="centro"
                exit="sair"
                className="flex w-full flex-col items-center gap-5 px-1 py-1"
              >
                <p
                  aria-live="polite"
                  className={
                    vm.etapa === "boas-vindas" || vm.etapa === "fim"
                      ? "w-full font-geist text-base text-text-body"
                      : "w-full font-geist text-xl leading-snug text-text-subtitle"
                  }
                >
                  {PERGUNTA[vm.etapa]}
                </p>

                {vm.etapa === "municipio" && <MunicipioPicker vm={vm} />}
                {vm.etapa === "solo" && (
                  <OpcoesVisuais
                    nome="solo"
                    legenda="Tipo de solo"
                    opcoes={solos}
                    valor={vm.rascunho.solo}
                    onEscolher={vm.escolherSolo}
                  />
                )}
                {vm.etapa === "clima" && (
                  <OpcoesVisuais
                    nome="clima"
                    legenda="Clima da região"
                    opcoes={climas}
                    valor={vm.rascunho.clima}
                    onEscolher={vm.escolherClima}
                  />
                )}
                {vm.etapa === "fim" && <Resumo vm={vm} />}
              </motion.div>
            </AnimatePresence>
          </AlturaSuave>

          <div className="flex w-full justify-center gap-2.5">
            <Button variant="brandDark" onClick={vm.voltar} disabled={!vm.podeVoltar}>
              Voltar
            </Button>
            <Button variant="brand" type="submit" disabled={!vm.podeAvancar}>
              Próximo
            </Button>
          </div>
        </motion.form>
      </main>
    </div>
  );
}

const RESUMO = [
  { chave: "municipio", rotulo: "Município", Icone: MapPin },
  { chave: "solo", rotulo: "Solo", Icone: Plant },
  { chave: "clima", rotulo: "Clima", Icone: CloudSun },
] as const;

function Resumo({ vm }: { vm: ReturnType<typeof useOnboardingViewModel> }) {
  const { municipio, solo, clima } = vm.rascunho;
  const valores = {
    municipio: municipio?.nome ?? "—",
    solo: solo ? ROTULO_SOLO[solo] : "—",
    clima: clima ? ROTULO_CLIMA[clima] : "—",
  };
  return (
    <ul className="grid w-full gap-2 sm:grid-cols-3">
      {RESUMO.map(({ chave, rotulo, Icone }, i) => (
        <motion.li
          key={chave}
          variants={surgirEmCascata}
          initial="oculto"
          animate="visivel"
          custom={i + 1}
          className="flex items-center gap-3 rounded-2xl border border-bg-border bg-white/80 p-3"
        >
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-brand-primary/40 text-brand-secondary">
            <Icone size={22} />
          </span>
          <span className="min-w-0">
            <span className="block font-geist text-xs text-text-body">{rotulo}</span>
            <span className="block truncate font-geist text-base font-medium text-text-subtitle">
              {valores[chave]}
            </span>
          </span>
        </motion.li>
      ))}
    </ul>
  );
}
