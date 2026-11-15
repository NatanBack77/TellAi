import { lazy, Suspense } from "react";

// Só entra no bundle de desenvolvimento.
const DevtoolsPanels = import.meta.env.DEV
  ? lazy(async () => {
      const [router, query] = await Promise.all([
        import("@tanstack/react-router-devtools"),
        import("@tanstack/react-query-devtools"),
      ]);
      return {
        default: () => (
          <>
            <router.TanStackRouterDevtools position="bottom-right" />
            <query.ReactQueryDevtools buttonPosition="bottom-left" />
          </>
        ),
      };
    })
  : () => null;

export function Devtools() {
  return (
    <Suspense>
      <DevtoolsPanels />
    </Suspense>
  );
}
