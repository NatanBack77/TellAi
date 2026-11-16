import type { ReactNode } from "react";
import { CircleNotch, WarningCircle } from "@phosphor-icons/react";

export function LoadingState({ children = "Carregando…" }: { children?: ReactNode }) {
  return (
    <p role="status" className="flex items-center gap-2 text-muted">
      <CircleNotch className="animate-spin" /> {children}
    </p>
  );
}

export function ErrorState({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 rounded-xl bg-alert/10 p-4 text-alert"
    >
      <WarningCircle size={22} />
      <span className="flex-1">{children}</span>
      {action}
    </div>
  );
}
