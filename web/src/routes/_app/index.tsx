import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { IDS_TOPICOS } from "@/features/painel/models/topicos.model";
import { PainelView } from "@/features/painel/views/PainelView";

// ?topico=colheita abre direto na etapa (link compartilhável).
const searchSchema = z.object({ topico: z.enum(IDS_TOPICOS).optional().catch(undefined) });

export const Route = createFileRoute("/_app/")({
  validateSearch: searchSchema,
  component: PainelView,
});
