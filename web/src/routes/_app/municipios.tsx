import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { municipiosQueryOptions } from "@/features/municipios/viewmodels/municipiosQuery";
import { MunicipiosView } from "@/features/municipios/views/MunicipiosView";
import { AppLayout } from "@/shared/components/layout/AppLayout";

// Busca na URL (?q=quixada) validada com zod: compartilhável e sobrevive ao F5.
const searchSchema = z.object({ q: z.string().optional().catch(undefined) });

export const Route = createFileRoute("/_app/municipios")({
  validateSearch: searchSchema,
  // Começa a buscar antes de renderizar (e no hover do link). prefetch não lança erro:
  // se a API falhar, quem mostra o erro é o ViewModel.
  loader: ({ context }) => context.queryClient.prefetchQuery(municipiosQueryOptions()),
  component: () => (
    <AppLayout>
      <MunicipiosView />
    </AppLayout>
  ),
});
