import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import type { QueryClient } from "@tanstack/react-query";
import { Devtools } from "@/shared/components/layout/Devtools";
import { NotFoundView } from "@/shared/components/layout/NotFoundView";

export interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: () => (
    <>
      <Outlet />
      <Devtools />
    </>
  ),
  notFoundComponent: NotFoundView,
});
