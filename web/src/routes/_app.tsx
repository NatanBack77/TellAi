import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { perfilStorage } from "@/features/onboarding/services/perfil.storage";

/** Telas do sistema. Sem perfil salvo no navegador → quiz inicial. */
export const Route = createFileRoute("/_app")({
  beforeLoad: () => {
    if (!perfilStorage.existe()) throw redirect({ to: "/boas-vindas", replace: true });
  },
  component: Outlet,
});
