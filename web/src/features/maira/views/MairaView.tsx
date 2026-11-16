import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, PaperPlaneTilt } from "@phosphor-icons/react";
import { Seo } from "@/shared/components/seo/Seo";
import { Logo, LogoMark } from "@/shared/components/brand/Logo";
import { Button } from "@/shared/components/ui/Button";
import { ErrorState } from "@/shared/components/ui/StatusMessage";
import { cn } from "@/shared/lib/cn";
import type { Mensagem } from "../models/conversa.model";
import { dividirNegrito } from "../lib/texto";
import { useMairaViewModel } from "../viewmodels/useMairaViewModel";

/** Texto do servidor entra sempre como texto (só **negrito** vira <strong>; nunca HTML). */
function Texto({ texto }: { texto: string }) {
  return (
    <>
      {dividirNegrito(texto).map((p, i) => (p.negrito ? <strong key={i}>{p.texto}</strong> : <span key={i}>{p.texto}</span>))}
    </>
  );
}

function Balao({ m }: { m: Mensagem }) {
  if (m.papel === "usuario") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-primary px-3.5 py-2.5 font-geist text-[15px] leading-snug whitespace-pre-line text-brand-secondary">
          {m.texto}
        </p>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full border border-bg-border bg-white">
        <LogoMark className="h-[14px] w-[12px]" />
      </span>
      <div className="max-w-[85%] space-y-2">
        <div className="rounded-2xl rounded-tl-md border border-bg-border bg-white px-3.5 py-2.5 font-geist text-[15px] leading-snug whitespace-pre-line text-text-subtitle">
          <Texto texto={m.texto} />
        </div>
        {m.entendido && (
          <p className="inline-flex items-center gap-1 rounded-full bg-bg-soft px-2.5 py-1 font-geist text-[11px] text-text-body">
            <Check size={12} weight="bold" aria-hidden /> Entendi: {m.entendido}
          </p>
        )}
        {m.fontes && m.fontes.length > 0 && (
          <details className="font-geist text-[11px] text-text-body">
            <summary className="cursor-pointer">De onde veio esta resposta</summary>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {m.fontes.map((f) => (
                <li key={f.id}>{f.texto_simples || f.rotulo}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

/** Chat com a Maíra, só em texto: ela já chega sabendo o que a pessoa informou no app. */
export function MairaView() {
  const vm = useMairaViewModel();
  const [texto, setTexto] = useState("");
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [vm.mensagens.length, vm.enviando]);

  const enviar = (t: string) => {
    vm.enviar(t);
    setTexto("");
  };

  if (vm.semPerfil) {
    return (
      <div className="grid min-h-dvh place-items-center bg-bg-soft p-4">
        <div className="max-w-sm space-y-4 text-center font-geist text-text-body">
          <p>Para conversar com a Maíra, responda antes as perguntas iniciais. Assim ela já sabe onde você planta.</p>
          <Button variant="brand" onClick={vm.irParaBoasVindas}>
            Responder as perguntas
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-dvh flex-col bg-bg-soft p-2.5">
      <Seo title="Conversar com a Maíra" description="Converse com a Maíra, assistente automática do Sulco." />
      <section className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col gap-4 rounded-3xl border border-bg-border bg-white/70 p-4 backdrop-blur-md">
        <header className="flex items-center justify-between gap-3">
          <Logo />
          <button
            type="button"
            onClick={vm.voltarAoPlano}
            className="inline-flex h-[30px] items-center gap-1.5 rounded-full border border-bg-border bg-bg-soft px-3 font-geist text-xs text-text-body transition-colors hover:bg-white"
          >
            <ArrowLeft size={14} /> Voltar ao plano
          </button>
        </header>

        <div className="space-y-2 font-geist">
          <p className="text-xs text-text-body">{vm.assistente}</p>
          <ul aria-label="O que a Maíra já sabe" className="flex flex-wrap gap-1.5">
            {vm.sabe.map((s) => (
              <li key={s} className="rounded-full border border-bg-border bg-white px-3 py-1 text-xs text-text-body">
                {s}
              </li>
            ))}
          </ul>
        </div>

        <div role="log" aria-live="polite" className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          {vm.mensagens.length === 0 && (
            <p className="font-geist text-sm text-text-body">Pergunte o que quiser sobre o seu plantio. Você também pode tocar numa sugestão abaixo.</p>
          )}
          {vm.mensagens.map((m, i) => (
            <Balao key={i} m={m} />
          ))}
          {vm.enviando && (
            <p className="flex items-center gap-2 font-geist text-xs text-text-body">
              <span className="inline-flex gap-1" aria-hidden>
                {[0, 1, 2].map((d) => (
                  <span key={d} className="size-1.5 animate-pulse rounded-full bg-text-body/60" style={{ animationDelay: `${d * 150}ms` }} />
                ))}
              </span>
              Só um instante, estou olhando os dados.
            </p>
          )}
          {vm.erro && <ErrorState>Não consegui falar com a Maíra agora. Tente de novo em instantes.</ErrorState>}
          <div ref={fim} />
        </div>

        {vm.chips.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {vm.chips.map((c) => (
              <button
                key={c.rotulo}
                type="button"
                disabled={vm.enviando}
                onClick={() => enviar(c.texto)}
                className={cn(
                  "rounded-full border border-bg-border bg-white px-3 py-1.5 font-geist text-xs text-text-subtitle transition-colors",
                  "hover:border-brand-secondary/40 disabled:opacity-50",
                )}
              >
                {c.rotulo}
              </button>
            ))}
          </div>
        )}

        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            enviar(texto);
          }}
        >
          <label className="sr-only" htmlFor="mensagem-maira">
            Sua mensagem
          </label>
          <input
            id="mensagem-maira"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            maxLength={400}
            autoComplete="off"
            placeholder="Escreva aqui…"
            className="min-w-0 flex-1 rounded-full border border-bg-border bg-white px-4 py-2.5 font-geist text-sm text-text-subtitle"
          />
          <Button type="submit" variant="brand" disabled={vm.enviando || !texto.trim()}>
            <PaperPlaneTilt size={18} aria-hidden /> Enviar
          </Button>
        </form>
      </section>
    </div>
  );
}
