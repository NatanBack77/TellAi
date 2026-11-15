import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";
import searchIcon from "@/assets/icons/search-01.svg";

export interface SearchInputProps extends Omit<ComponentProps<"input">, "size"> {
  /** Texto para leitores de tela (o campo não tem rótulo visível). */
  rotulo: string;
  /** Substitui o ícone de busca (ex.: check quando já escolhido). */
  icone?: ReactNode;
  wrapperClassName?: string;
}

/** "Search Input" do Figma (Components): pílula branca 46px, ícone 24px, Geist 16px. */
export function SearchInput({
  rotulo,
  icone,
  wrapperClassName,
  className,
  placeholder = "Pesquise aqui",
  ...props
}: SearchInputProps) {
  return (
    <label
      className={cn(
        "flex h-[46px] w-full items-center gap-4 rounded-full border border-bg-border bg-white p-2 transition-shadow focus-within:border-brand-primary focus-within:ring-2 focus-within:ring-brand-primary/40",
        wrapperClassName,
      )}
    >
      {icone ?? <img src={searchIcon} alt="" width={24} height={24} className="size-6 shrink-0" />}
      <span className="sr-only">{rotulo}</span>
      <input
        type="search"
        placeholder={placeholder}
        className={cn(
          "min-w-0 flex-1 bg-transparent font-geist text-base text-text-body outline-none placeholder:text-text-body [&::-webkit-search-cancel-button]:hidden",
          className,
        )}
        {...props}
      />
    </label>
  );
}
