import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

type Variant = "primary" | "ghost" | "brand" | "brandDark";

const variants: Record<Variant, string> = {
  primary: "min-h-11 rounded-xl px-4 font-medium bg-forest text-white hover:bg-forest-deep",
  ghost: "min-h-11 rounded-xl px-4 font-medium bg-transparent text-ink hover:bg-line/60",
  // Botões do Figma (componente "Button"): pílula 150×36, Geist 14px.
  brand:
    "h-9 w-[150px] rounded-full p-3 font-geist text-sm bg-brand-primary text-text-body hover:brightness-95",
  brandDark:
    "h-9 w-[150px] rounded-full p-3 font-geist text-sm bg-brand-secondary text-brand-primary hover:brightness-110",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = "primary", className, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-2 transition disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
