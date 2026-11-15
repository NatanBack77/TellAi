import { createRouter } from "@tanstack/react-router";
import { queryClient } from "@/app/providers/queryClient";
import { routeTree } from "@/routeTree.gen";

export const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
  // Com React Query cuidando do cache, o loader do router não precisa cachear de novo.
  defaultPreloadStaleTime: 0,
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
