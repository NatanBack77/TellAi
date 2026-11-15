import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export interface AiCardProps extends Omit<ComponentProps<"article">, "title"> {
  titulo: ReactNode;
  texto?: ReactNode;
  /** Imagem do topo (proporção 973×706 do Figma). Opcional: sem ela o card mostra só os textos. */
  imagem?: { src: string; alt: string };
  /** Conteúdo extra abaixo do texto (selos, fonte…). */
  children?: ReactNode;
}

/** "ai-card" do Figma (página UI): bloco cinza-claro com imagem, título 24px e texto 16px. */
export function AiCard({ titulo, texto, imagem, children, className, ...props }: AiCardProps) {
  return (
    <article
      className={cn("flex flex-col items-start gap-2.5 rounded-2xl bg-bg-soft p-3", className)}
      {...props}
    >
      {imagem && (
        <img
          src={imagem.src}
          alt={imagem.alt}
          className="aspect-[973/706] w-full rounded-xl object-cover"
        />
      )}
      <h3 className="font-geist text-2xl leading-tight text-black">{titulo}</h3>
      {texto && <p className="font-geist text-base text-black">{texto}</p>}
      {children}
    </article>
  );
}
