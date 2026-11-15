import type { Transition, Variants } from "motion/react";

/** Mola suave e sem "quique": padrão para movimentos de layout. */
export const MOLA_SUAVE: Transition = { type: "spring", stiffness: 260, damping: 32, mass: 0.9 };

/** Easing para fades curtos. */
export const EASE_SUAVE: Transition = { duration: 0.35, ease: [0.22, 1, 0.36, 1] };

/** Troca de passo: entra/sai deslizando na direção da navegação (custom = 1 | -1). */
export const deslizarPasso: Variants = {
  entrar: (direcao: number) => ({ opacity: 0, x: 32 * direcao, filter: "blur(4px)" }),
  centro: {
    opacity: 1,
    x: 0,
    filter: "blur(0px)",
    transition: { ...MOLA_SUAVE, opacity: EASE_SUAVE },
  },
  sair: (direcao: number) => ({
    opacity: 0,
    x: -32 * direcao,
    filter: "blur(4px)",
    transition: { duration: 0.2, ease: [0.4, 0, 1, 1] },
  }),
};

/** Itens que aparecem em sequência (stagger). */
export const surgirEmCascata: Variants = {
  oculto: { opacity: 0, y: 10 },
  visivel: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { ...EASE_SUAVE, delay: 0.06 * i },
  }),
};
