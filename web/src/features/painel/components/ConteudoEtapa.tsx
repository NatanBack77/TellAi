import { CaretDown, Info } from "@phosphor-icons/react";
import { LogoMark } from "@/shared/components/brand/Logo";
import { Button } from "@/shared/components/ui/Button";
import { ErrorState } from "@/shared/components/ui/StatusMessage";
import { cn } from "@/shared/lib/cn";
import type { PlanoViewModel } from "@/features/plano/viewmodels/usePlanoViewModel";
import type { LinhaTexto, Selo } from "@/features/plano/viewmodels/textoEtapa";

interface Props {
  plano: PlanoViewModel;
  municipio: string | null;
}

/** Esqueleto de carregamento (o mesmo bloco tracejado que já existia no card). */
function Esqueleto({ municipio }: { municipio: string | null }) {
  return (
    <div className="max-w-prose space-y-3 rounded-2xl border border-dashed border-bg-border bg-white/60 p-4">
      <div className="flex items-center gap-2 font-geist text-sm text-text-body">
        <LogoMark className="h-[18px] w-[16px]" />A Maíra vai explicar esta etapa para {municipio ?? "o seu município"}.
      </div>
      {[92, 78, 85, 60].map((w) => (
        <span key={w} className="block h-3 animate-pulse rounded-full bg-bg-border/80" style={{ width: `${w}%` }} />
      ))}
    </div>
  );
}

/** Selos curtos: o aviso vai colado no valor, sem frase longa. A frase inteira fica na dica. */
function Selos({ selos }: { selos: Selo[] }) {
  if (selos.length === 0) return null;
  return (
    <span className="mt-1.5 flex flex-wrap gap-1">
      {selos.map((s) => (
        <span
          key={s.tipo}
          title={s.dica}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-geist text-[11px] leading-none",
            s.tipo === "tecnico" ? "border-alert/30 bg-alert/10 text-alert" : "border-bg-border bg-bg-soft text-text-body",
          )}
        >
          <Info size={11} weight="bold" aria-hidden /> {s.rotulo}
        </span>
      ))}
    </span>
  );
}

/** Fonte em uma linha pequena; o texto inteiro fica na dica. */
function Fonte({ linha }: { linha: LinhaTexto }) {
  if (!linha.fonte && !linha.origem) return null;
  const texto = [linha.fonte && `Fonte: ${linha.fonte}`, linha.origem].filter(Boolean).join(" · ");
  return (
    <p title={texto} className="mt-1 line-clamp-1 font-geist text-[11px] text-text-body/80">
      {texto}
    </p>
  );
}

/** Resposta objetiva: rótulo curto + valor em destaque. */
function Resposta({ linha }: { linha: LinhaTexto }) {
  return (
    <li className="rounded-2xl border border-bg-border bg-white p-3.5">
      <p className="font-geist text-[11px] font-medium tracking-wide text-text-body uppercase">{linha.rotulo}</p>
      <p className="mt-0.5 font-geist text-[17px] leading-snug font-semibold text-text-subtitle">{linha.valor}</p>
      <Selos selos={linha.selos} />
      <Fonte linha={linha} />
    </li>
  );
}

function Detalhe({ linha }: { linha: LinhaTexto }) {
  return (
    <li className="py-2.5">
      <p className="font-geist text-xs font-medium text-text-subtitle">{linha.rotulo}</p>
      <p className="font-geist text-sm leading-snug text-text-body">{linha.valor}</p>
      <Selos selos={linha.selos} />
      <Fonte linha={linha} />
    </li>
  );
}

/** Texto da etapa (lado esquerdo): resposta objetiva primeiro, detalhes recolhidos, o que falta sempre visível. */
export function ConteudoEtapa({ plano, municipio }: Props) {
  if (plano.semLocal) {
    return <p className="max-w-prose font-geist text-sm text-text-body">Escolha o seu município nas perguntas iniciais para ver o plano.</p>;
  }
  if (plano.carregando) {
    return (
      <Esqueleto municipio={municipio} />
    );
  }
  if (plano.erro || !plano.texto) {
    return (
      <div className="max-w-prose space-y-3">
        <ErrorState action={<Button variant="brandDark" onClick={plano.tentarDeNovo}>Tentar de novo</Button>}>
          Não consegui montar esta etapa agora. Tente de novo em instantes.
        </ErrorState>
      </div>
    );
  }

  // `faltas` (o que não temos) continua no texto gerado, mas NÃO é mostrado ao agricultor: decisão do produto.
  const { destaques, detalhes, naoSeAplica, semDados } = plano.texto;
  return (
    <div className="max-w-prose space-y-4 font-geist text-text-body">
      {plano.culturaNome && (
        <p className="text-sm">
          Plano para <strong className="font-semibold text-text-subtitle">{plano.culturaNome}</strong>
        </p>
      )}

      {naoSeAplica && <p className="rounded-2xl border border-bg-border bg-bg-soft p-3 text-sm">Esta etapa não se aplica a esta cultura.</p>}
      {semDados && !naoSeAplica && (
        <p className="rounded-2xl border border-bg-border bg-bg-soft p-3 text-sm">Para esta etapa, converse com o técnico local.</p>
      )}

      {destaques.length > 0 && (
        <ul aria-label="Resposta objetiva" className="space-y-2">
          {destaques.map((l, i) => (
            <Resposta key={`${l.rotulo}-${i}`} linha={l} />
          ))}
        </ul>
      )}

      {detalhes.length > 0 && (
        <details className="group rounded-2xl border border-bg-border bg-white/60 px-3.5">
          <summary className="flex cursor-pointer list-none items-center justify-between py-2.5 text-sm font-medium text-text-subtitle">
            Mais detalhes ({detalhes.length})
            <CaretDown size={16} className="transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <ul className="divide-y divide-bg-border border-t border-bg-border">
            {detalhes.map((l, i) => (
              <Detalhe key={`${l.rotulo}-${i}`} linha={l} />
            ))}
          </ul>
        </details>
      )}

      {plano.aviso && <p className="text-[11px] leading-snug text-text-body/80">{plano.aviso}</p>}
      {plano.limites.length > 0 && (
        <details className="text-[11px] text-text-body/80">
          <summary className="cursor-pointer">O que este plano não vê</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {plano.limites.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
