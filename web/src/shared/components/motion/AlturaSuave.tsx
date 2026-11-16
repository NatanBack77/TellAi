import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { motion } from "motion/react";
import { MOLA_SUAVE } from "./transicoes";

/** Anima a altura quando o conteúdo muda de tamanho (sem distorcer texto, ao contrário de `layout`). */
export function AlturaSuave({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [altura, setAltura] = useState<number | "auto">("auto");

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => e && setAltura(e.contentRect.height));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <motion.div
      className={className}
      style={{ overflow: "hidden" }}
      initial={false}
      animate={{ height: altura }}
      transition={MOLA_SUAVE}
    >
      <div ref={ref}>{children}</div>
    </motion.div>
  );
}
