import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { HelmetProvider } from "react-helmet-async";
import { IconContext } from "@phosphor-icons/react";
import { MotionConfig } from "motion/react";
import { queryClient } from "./queryClient";

const iconDefaults = { size: 20, weight: "regular" as const, mirrored: false };

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <IconContext.Provider value={iconDefaults}>
          {/* Respeita "reduzir movimento" do sistema operacional em todas as animações. */}
          <MotionConfig reducedMotion="user">{children}</MotionConfig>
        </IconContext.Provider>
      </QueryClientProvider>
    </HelmetProvider>
  );
}
