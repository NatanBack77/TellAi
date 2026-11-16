import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

const icones = import.meta.glob<string>("@/assets/icons/*.svg", {
  eager: true,
  query: "?url",
  import: "default",
});

/** Ícones do Figma (Components › Icons). */
export type IconeFigma =
  "plus" | "minus" | "home-04" | "chart-ring" | "service" | "help-square" | "gps-01" | "search-01";

export function iconeFigma(nome: IconeFigma) {
  const chave = Object.keys(icones).find((k) => k.endsWith(`/${nome}.svg`));
  return chave ? icones[chave]! : "";
}

export interface IconButtonProps extends ComponentProps<"button"> {
  /** Nome acessível (o botão só tem ícone). */
  rotulo: string;
  icone: IconeFigma | ReactNode;
}

/** "Btn" do Figma: botão redondo de vidro, 46px, ícone 24px. */
export function IconButton({
  rotulo,
  icone,
  className,
  type = "button",
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={rotulo}
      title={rotulo}
      className={cn(
        "grid size-[46px] shrink-0 place-items-center rounded-full border border-bg-border bg-white/60 text-text-body backdrop-blur-md transition-colors hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
      {...props}
    >
      {typeof icone === "string" ? (
        <img
          src={iconeFigma(icone as IconeFigma)}
          alt=""
          width={24}
          height={24}
          className="size-6"
        />
      ) : (
        icone
      )}
    </button>
  );
}
