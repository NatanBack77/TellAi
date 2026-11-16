import { lazy, Suspense, useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowCounterClockwise, CaretLeft, CaretRight, MapPin } from "@phosphor-icons/react";
import { Seo } from "@/shared/components/seo/Seo";
import { Logo, LogoMark } from "@/shared/components/brand/Logo";
import { Button } from "@/shared/components/ui/Button";
import { IconButton } from "@/shared/components/ui/IconButton";
import { EASE_SUAVE } from "@/shared/components/motion/transicoes";
import { cn } from "@/shared/lib/cn";
import { ConteudoEtapa } from "../components/ConteudoEtapa";
import { usePainelViewModel } from "../viewmodels/usePainelViewModel";

// Three.js só baixa quando a tela principal abre.
const Palco3D = lazy(() => import("../components/three/Palco3D"));

/** Tela principal ("3D VIEW" no Figma): informações da IA à esquerda, cena 3D do tópico à direita. */
export function PainelView() {
  const vm = usePainelViewModel();
  const { proximo, anterior } = vm;

  // Setas do teclado trocam o tópico (fora de campos de texto).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, textarea")) return;
      if (e.key === "ArrowRight") proximo();
      if (e.key === "ArrowLeft") anterior();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [proximo, anterior]);

  return (
    <div className="flex min-h-dvh flex-col-reverse gap-2.5 bg-bg-soft p-2.5 lg:h-dvh lg:flex-row">
      <Seo title={vm.topico.titulo} description={vm.topico.resumo} />

      {/* ---------------- Card (esquerda): informações da IA ---------------- */}
      <section className="flex min-h-0 flex-1 flex-col gap-6 rounded-3xl border border-bg-border bg-white/70 p-4 backdrop-blur-md">
        <header className="flex items-center justify-between gap-3">
          <Logo />
          <button
            type="button"
            onClick={vm.falarComMaira}
            className="flex h-[26px] items-center gap-1 rounded-full border border-bg-border bg-bg-soft px-3 font-geist text-[10px] text-text-body transition-colors hover:bg-white"
          >
            <LogoMark className="h-[14px] w-[12px]" />
            Fale com a Maíra
          </button>
        </header>

        {vm.perfil && (
          <div className="flex flex-wrap items-center gap-2 font-geist text-sm text-text-body">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-bg-border bg-white px-3 py-1">
              <MapPin size={16} className="text-brand-secondary" /> {vm.perfil.municipio}
            </span>
            <span className="rounded-full border border-bg-border bg-white px-3 py-1">
              Solo {vm.perfil.solo.toLowerCase()}
            </span>
            <span className="rounded-full border border-bg-border bg-white px-3 py-1">
              Clima {vm.perfil.clima.toLowerCase()}
            </span>
            <button
              type="button"
              onClick={vm.refazerPerguntas}
              className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs hover:text-text-subtitle"
            >
              <ArrowCounterClockwise size={14} /> Refazer perguntas
            </button>
          </div>
        )}

        <div className="flex min-h-0 flex-1 flex-col gap-6 lg:flex-row">
          {/* Sumário: troca a etapa (e o modelo 3D) */}
          <nav
            aria-label="Sumário das etapas do plantio"
            className="shrink-0 lg:w-64 lg:overflow-y-auto"
          >
            <p className="mb-2 px-3 font-geist text-xs font-medium tracking-wide text-text-body uppercase">
              Sumário
            </p>
            <ol className="space-y-0.5">
              {vm.topicos.map((t, i) => {
                const ativo = t.id === vm.topico.id;
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => vm.irPara(t.id)}
                      aria-current={ativo ? "step" : undefined}
                      className={cn(
                        "flex w-full items-start gap-2.5 rounded-xl px-3 py-2 text-left font-geist text-sm transition-colors",
                        ativo
                          ? "bg-bg-soft font-medium text-text-subtitle"
                          : "text-text-body hover:bg-bg-soft/60",
                      )}
                    >
                      <span
                        className={cn(
                          "grid size-5 shrink-0 place-items-center rounded-full text-[11px]",
                          ativo
                            ? "bg-brand-primary text-brand-secondary"
                            : "bg-bg-border/70 text-text-body",
                        )}
                      >
                        {i + 1}
                      </span>
                      <span className="leading-5">{t.titulo}</span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>

          {/* Conteúdo do tópico (a IA vai preencher aqui) */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            <AnimatePresence mode="wait" initial={false}>
              <motion.article
                key={vm.topico.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0, transition: EASE_SUAVE }}
                exit={{ opacity: 0, y: -8, transition: { duration: 0.15 } }}
                className="space-y-4"
              >
                <p className="font-geist text-sm text-text-body">
                  Etapa {vm.indice + 1} de {vm.total}
                </p>
                <h1 className="font-geist text-3xl font-semibold text-text-subtitle">
                  {vm.topico.titulo}
                </h1>
                <p className="max-w-prose font-geist text-lg text-text-body">{vm.topico.resumo}</p>

                <ConteudoEtapa plano={vm.plano} municipio={vm.perfil?.municipio ?? null} />
              </motion.article>
            </AnimatePresence>
          </div>
        </div>

        {/* Navegação entre os tópicos */}
        <nav aria-label="Etapa anterior e próxima">
          <div className="flex justify-center gap-2.5">
            <Button variant="brandDark" onClick={vm.anterior} disabled={!vm.temAnterior}>
              Anterior
            </Button>
            <Button variant="brand" onClick={vm.proximo} disabled={!vm.temProximo}>
              Próximo
            </Button>
          </div>
        </nav>
      </section>

      {/* ---------------- Modelo 3D (direita) ---------------- */}
      <section
        aria-label={`Ilustração 3D: ${vm.topico.titulo}`}
        className="relative h-[52vh] shrink-0 overflow-hidden rounded-3xl lg:h-auto lg:w-[38%]"
      >
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_45%,#ffffff_0%,#f5f7fa_60%,#e9eef3_100%)]" />
        <Suspense
          fallback={
            <div className="absolute inset-0 grid place-items-center font-geist text-sm text-text-body">
              Preparando a cena 3D…
            </div>
          }
        >
          <Palco3D topico={vm.topico.id} />
        </Suspense>

        <div className="pointer-events-none absolute top-3 right-3 left-3 flex items-start justify-between gap-3">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={vm.topico.id}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0, transition: EASE_SUAVE }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.15 } }}
              className="flex items-center gap-2 rounded-full border border-bg-border bg-white/70 py-1.5 pr-4 pl-1.5 font-geist text-sm text-text-subtitle backdrop-blur-md"
            >
              <span className="grid size-7 place-items-center rounded-full bg-brand-primary text-xs font-semibold text-brand-secondary">
                {vm.indice + 1}
              </span>
              {vm.topico.titulo}
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="absolute bottom-3 left-3 flex gap-2">
          <IconButton
            rotulo="Etapa anterior"
            icone={<CaretLeft size={22} />}
            onClick={vm.anterior}
            disabled={!vm.temAnterior}
          />
          <IconButton
            rotulo="Próxima etapa"
            icone={<CaretRight size={22} />}
            onClick={vm.proximo}
            disabled={!vm.temProximo}
          />
        </div>
      </section>
    </div>
  );
}
