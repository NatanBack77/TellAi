import { cn } from "@/shared/lib/cn";

export interface StepperProps {
  passos: readonly string[];
  /** Índice do passo atual (0-based). */
  atual: number;
  /** Diz se o usuário pode pular para o passo `i` (ex.: já respondido). */
  podeIrPara?: (i: number) => boolean;
  onIrPara?: (i: number) => void;
  className?: string;
}

/** Stepper em barras segmentadas: uma barra por passo, preenchida conforme o progresso. */
export function Stepper({ passos, atual, podeIrPara, onIrPara, className }: StepperProps) {
  return (
    <nav aria-label="Progresso" className={cn("w-full", className)}>
      <ol className="flex gap-1.5">
        {passos.map((rotulo, i) => {
          const feito = i < atual;
          const ativo = i === atual;
          const clicavel = !ativo && !!onIrPara && (podeIrPara?.(i) ?? false);
          return (
            <li key={rotulo} className="flex-1">
              <button
                type="button"
                disabled={!clicavel}
                onClick={() => onIrPara?.(i)}
                aria-current={ativo ? "step" : undefined}
                aria-label={`${rotulo}${feito ? " (respondido)" : ""}`}
                className="group flex w-full flex-col gap-1.5 text-center disabled:cursor-default"
              >
                <span className="relative block h-1.5 w-full overflow-hidden rounded-full bg-bg-border">
                  <span
                    className={cn(
                      "absolute inset-y-0 left-0 rounded-full transition-[width,background-color] duration-700 ease-[cubic-bezier(.22,1,.36,1)]",
                      feito && "w-full bg-brand-secondary",
                      ativo && "w-full bg-brand-primary",
                      !feito && !ativo && "w-0",
                      clicavel && "group-hover:brightness-125",
                    )}
                  />
                </span>
                <span
                  className={cn(
                    "truncate font-geist text-xs transition-colors",
                    ativo ? "font-medium text-text-subtitle" : "text-text-body",
                    !feito && !ativo && "opacity-60",
                  )}
                >
                  {rotulo}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
