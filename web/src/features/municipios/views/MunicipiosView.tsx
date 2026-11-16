import { lazy, Suspense, useMemo } from "react";
import { MagnifyingGlass, MapPin } from "@phosphor-icons/react";
import { Seo } from "@/shared/components/seo/Seo";
import { Button } from "@/shared/components/ui/Button";
import { ErrorState, LoadingState } from "@/shared/components/ui/StatusMessage";
import { cn } from "@/shared/lib/cn";
import { nomeCurto, ufDoMunicipio } from "../models/municipio.model";
import { useMunicipiosViewModel } from "../viewmodels/useMunicipiosViewModel";

// Three.js é pesado: só baixa quando a tela de municípios abre.
const MapaPontos3D = lazy(() => import("../components/MapaPontos3D"));

/** View: só desenha o que o ViewModel entrega e repassa eventos. Sem fetch, sem regra. */
export function MunicipiosView() {
  const vm = useMunicipiosViewModel();
  const destacados = useMemo(
    () => new Set(vm.busca ? vm.filtrados.map((m) => m.ponto_id) : []),
    [vm.busca, vm.filtrados],
  );

  return (
    <section className="space-y-6">
      <Seo title="Municípios" description="Pontos do Ceará acompanhados pelo Sulco." />

      <header className="space-y-1">
        <h1 className="text-3xl font-semibold">Municípios</h1>
        {!vm.carregando && !vm.erro && <p className="text-muted">{vm.total} pontos com dados</p>}
      </header>

      <label className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:border-leaf">
        <MagnifyingGlass className="text-muted" />
        <span className="sr-only">Buscar município</span>
        <input
          value={vm.busca}
          onChange={(e) => vm.buscar(e.target.value)}
          placeholder="Digite o nome do município"
          className="min-h-12 flex-1 bg-transparent outline-none"
        />
      </label>

      {vm.carregando && <LoadingState>Buscando municípios…</LoadingState>}
      {vm.erro && (
        <ErrorState action={<Button onClick={vm.tentarDeNovo}>Tentar de novo</Button>}>
          Não foi possível carregar os municípios agora.
        </ErrorState>
      )}

      {!vm.carregando && !vm.erro && (
        <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <ul className="max-h-[28rem] space-y-1 overflow-y-auto rounded-xl border border-line bg-surface p-2">
            {vm.filtrados.length === 0 && (
              <li className="p-3 text-muted">Nenhum município encontrado.</li>
            )}
            {vm.filtrados.map((m) => (
              <li key={m.ponto_id}>
                <button
                  type="button"
                  onClick={() => vm.selecionar(m.ponto_id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-paper",
                    vm.selecionado?.ponto_id === m.ponto_id && "bg-lime/50",
                  )}
                >
                  <MapPin className="text-leaf" />
                  <span className="flex-1">{nomeCurto(m)}</span>
                  <span className="text-sm text-muted">{ufDoMunicipio(m)}</span>
                </button>
              </li>
            ))}
          </ul>

          <div className="h-[28rem] overflow-hidden rounded-xl border border-line">
            <Suspense
              fallback={
                <div className="grid h-full place-items-center bg-forest-deep text-white/70">
                  Carregando mapa 3D…
                </div>
              }
            >
              <MapaPontos3D
                todos={vm.todos}
                destacados={destacados}
                selecionadoId={vm.selecionado?.ponto_id ?? null}
                onSelecionar={vm.selecionar}
              />
            </Suspense>
          </div>
        </div>
      )}

      {vm.selecionado && (
        <p className="rounded-xl bg-surface p-4">
          Selecionado: <strong>{nomeCurto(vm.selecionado)}</strong>
          {vm.selecionado.ibge === null && (
            <span className="text-muted"> · código IBGE sem dado</span>
          )}
        </p>
      )}
    </section>
  );
}
