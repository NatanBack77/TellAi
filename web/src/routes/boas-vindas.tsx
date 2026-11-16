import { createFileRoute, redirect } from "@tanstack/react-router";
import { perfilStorage } from "@/features/onboarding/services/perfil.storage";
import { OnboardingView } from "@/features/onboarding/views/OnboardingView";

export const Route = createFileRoute("/boas-vindas")({
  // Quem já respondeu vai direto para o sistema.
  beforeLoad: () => {
    if (perfilStorage.existe()) throw redirect({ to: "/", replace: true });
  },
  component: OnboardingView,
});
