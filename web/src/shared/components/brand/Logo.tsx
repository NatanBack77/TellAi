import { cn } from "@/shared/lib/cn";

// O logo do Figma é composto por 31 camadas SVG sobrepostas (efeito de profundidade).
// Cada camada mantém o recorte (inset) exato do design.
const camadas = import.meta.glob<string>("@/assets/brand/logo/g*.svg", {
  eager: true,
  query: "?url",
  import: "default",
});

const INSETS = [
  "-5.99% -8.34% -5.76% -0.21%",
  "-5.45% -7.87% -5.2% 0.41%",
  "-4.9% -7.39% -4.64% 1.03%",
  "-4.35% -6.92% -4.08% 1.65%",
  "-3.8% -6.46% -3.52% 2.27%",
  "-3.25% -5.99% -2.96% 2.89%",
  "-2.71% -5.5% -2.38% 3.5%",
  "-2.16% -5.04% -1.83% 4.12%",
  "-1.61% -4.57% -1.27% 4.74%",
  "-1.07% -4.09% -0.69% 5.36%",
  "-0.53% -3.62% -0.14% 5.98%",
  "0.02% -3.14% 0.43% 6.59%",
  "0.57% -2.68% 0.99% 7.21%",
  "1.11% -2.2% 1.56% 7.83%",
  "1.66% -1.73% 2.12% 8.45%",
  "2.2% -1.26% 2.68% 9.07%",
  "2.75% -0.79% 3.24% 9.69%",
  "3.3% -0.31% 3.81% 10.31%",
  "3.84% 0.16% 4.37% 10.92%",
  "4.39% 0.63% 4.94% 11.54%",
  "4.94% 1.1% 5.49% 12.16%",
  "5.49% 1.57% 6.05% 12.78%",
  "6.03% 2.04% 6.62% 13.4%",
  "6.58% 2.52% 7.18% 14.02%",
  "7.13% 2.98% 7.74% 14.64%",
  "7.66% 3.47% 8.32% 15.25%",
  "8.21% 3.94% 8.88% 15.87%",
  "8.76% 4.4% 9.44% 16.49%",
  "9.3% 4.88% 10.01% 17.11%",
  "9.85% 5.35% 10.57% 17.73%",
  "10.4% 5.83% 11.14% 18.35%",
];

const urls = Object.keys(camadas)
  .sort()
  .map((k) => camadas[k]!);

/** Símbolo do logo (46×51 no design). */
export function LogoMark({ className }: { className?: string }) {
  return (
    <div className={cn("relative h-[51px] w-[46px] shrink-0", className)} aria-hidden>
      {urls.map((src, i) => (
        <div key={src} className="pointer-events-none absolute" style={{ inset: INSETS[i] }}>
          <img src={src} alt="" className="absolute inset-0 block size-full max-w-none" />
        </div>
      ))}
    </div>
  );
}

/** Símbolo + nome "tell.ai". */
export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <LogoMark />
      <p className="font-geist text-[36px] text-text-subtitle">
        tell.<span className="font-semibold">ai</span>
      </p>
    </div>
  );
}
