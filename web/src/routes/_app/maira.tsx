import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { IDS_TOPICOS } from "@/features/painel/models/topicos.model";
import { MairaView } from "@/features/maira/views/MairaView";

// ?de=colheita lembra de qual etapa a pessoa veio, para o "Voltar ao plano" levar de volta a ela.
const searchSchema = z.object({ de: z.enum(IDS_TOPICOS).optional().catch(undefined) });

export const Route = createFileRoute("/_app/maira")({
  validateSearch: searchSchema,
  component: MairaView,
});
