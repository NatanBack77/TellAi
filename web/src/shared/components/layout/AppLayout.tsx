import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { MapPin, Plant } from "@phosphor-icons/react";

const navLinkClass =
  "flex items-center gap-2 rounded-lg px-3 py-2 text-ink-soft hover:bg-line/60 data-[status=active]:bg-forest data-[status=active]:text-white";

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-line bg-surface">
        <nav className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
          <Link
            to="/"
            className="mr-auto flex items-center gap-2 text-lg font-semibold text-forest"
          >
            <Plant weight="fill" size={26} /> Sulco
          </Link>
          <Link to="/municipios" className={navLinkClass}>
            <MapPin /> Municípios
          </Link>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
    </div>
  );
}
