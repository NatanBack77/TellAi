import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { EASE_SUAVE } from "@/shared/components/motion/transicoes";

export interface OpcaoVisual<T extends string> {
  valor: T;
  rotulo: string;
  descricao?: string;
  /** Classes do fundo do bloco (gradiente ou cor). */
  fundo?: string;
  /** Foto real cobrindo o bloco inteiro. */
  foto?: string;
  /** Nuvem do Figma, posicionada como no design. */
  nuvem?: string;
  /** Conteúdo central (ex.: ícone de "não sei"). */
  icone?: ReactNode;
}

interface OpcoesVisuaisProps<T extends string> {
  nome: string;
  legenda: string;
  opcoes: readonly OpcaoVisual<T>[];
  valor: T | null;
  onEscolher: (v: T) => void;
}

/**
 * Grupo de blocos visuais (componente "Weather" do Figma): moldura de vidro com blocos lado a
 * lado. Radio group nativo (setas do teclado trocam a opção). A seleção é só um contorno.
 */
export function OpcoesVisuais<T extends string>({
  nome,
  legenda,
  opcoes,
  valor,
  onEscolher,
}: OpcoesVisuaisProps<T>) {
  const escolhida = opcoes.find((o) => o.valor === valor);

  return (
    <fieldset className="w-full">
      <legend className="sr-only">{legenda}</legend>
      <div className="rounded-2xl border border-bg-border bg-bg-soft/60 p-1.5 backdrop-blur-md">
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
          {opcoes.map((o) => {
            const marcado = valor === o.valor;
            return (
              <div key={o.valor} className="relative">
                <label className="group relative block h-28 cursor-pointer overflow-hidden rounded-[10px]">
                  <input
                    type="radio"
                    name={nome}
                    value={o.valor}
                    checked={marcado}
                    onChange={() => onEscolher(o.valor)}
                    className="peer sr-only"
                  />
                  <span className={`absolute inset-0 bg-linear-to-b ${o.fundo ?? ""}`} />
                  {o.foto && (
                    <img src={o.foto} alt="" className="absolute inset-0 size-full object-cover" />
                  )}
                  {o.nuvem && (
                    <img
                      src={o.nuvem}
                      alt=""
                      className="pointer-events-none absolute top-[20px] left-[-4px] h-[78px] w-[calc(100%+8px)] object-cover"
                    />
                  )}
                  {o.icone && (
                    <span className="absolute inset-0 grid place-items-center pb-6 text-text-body">
                      {o.icone}
                    </span>
                  )}
                  <span
                    className={
                      o.icone
                        ? "absolute inset-x-0 bottom-0 px-2.5 py-1.5 font-geist text-sm text-text-body"
                        : "absolute inset-x-0 bottom-0 bg-linear-to-t from-black/65 to-transparent px-2.5 pt-5 pb-1.5 font-geist text-sm text-white"
                    }
                  >
                    {o.rotulo}
                  </span>
                  {/* foco do teclado */}
                  <span className="pointer-events-none absolute inset-0 rounded-[10px] ring-inset peer-focus-visible:ring-2 peer-focus-visible:ring-brand-secondary" />
                </label>

                {/* seleção: só o contorno, sem animação */}
                {marcado && (
                  <span className="pointer-events-none absolute -inset-[3px] rounded-[13px] border-3 border-brand-primary" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-3 min-h-6 text-center" aria-live="polite">
        <AnimatePresence mode="wait" initial={false}>
          {escolhida?.descricao && (
            <motion.p
              key={escolhida.valor}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0, transition: EASE_SUAVE }}
              exit={{ opacity: 0, y: -6, transition: { duration: 0.15 } }}
              className="font-geist text-base text-text-body"
            >
              <strong className="font-medium text-text-subtitle">{escolhida.rotulo}:</strong>{" "}
              {escolhida.descricao}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </fieldset>
  );
}
