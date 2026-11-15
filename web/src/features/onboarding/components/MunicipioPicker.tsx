import { useId, useState } from "react";
import { CheckCircle, MapPin } from "@phosphor-icons/react";
import { SearchInput } from "@/shared/components/ui/SearchInput";
import { Button } from "@/shared/components/ui/Button";
import { ErrorState, LoadingState } from "@/shared/components/ui/StatusMessage";
import { cn } from "@/shared/lib/cn";
import type { OnboardingViewModel } from "../viewmodels/useOnboardingViewModel";

interface Props {
  vm: OnboardingViewModel;
}

/** Busca de município (combobox acessível) usando o Search Input do Figma. */
export function MunicipioPicker({ vm }: Props) {
  const { busca, sugestoes, carregando, erro } = vm.municipio;
  const escolhido = vm.rascunho.municipio;
  const listaId = useId();
  const [ativo, setAtivo] = useState(0);
  const aberto = !escolhido && !carregando && busca.trim().length > 0;

  if (erro) {
    return (
      <ErrorState
        action={
          <Button variant="brandDark" onClick={vm.tentarDeNovo}>
            Tentar de novo
          </Button>
        }
      >
        Não foi possível carregar os municípios agora.
      </ErrorState>
    );
  }

  return (
    <div className="relative w-full max-w-[419px]">
      <SearchInput
        rotulo="Nome do município"
        icone={
          escolhido ? (
            <CheckCircle weight="fill" size={24} className="shrink-0 text-brand-secondary" />
          ) : undefined
        }
        role="combobox"
        aria-expanded={aberto}
        aria-controls={listaId}
        aria-autocomplete="list"
        aria-activedescendant={aberto && sugestoes[ativo] ? `${listaId}-${ativo}` : undefined}
        autoFocus
        value={busca}
        placeholder="Pesquise seu município"
        onChange={(e) => {
          vm.buscarMunicipio(e.target.value);
          setAtivo(0);
        }}
        onKeyDown={(e) => {
          if (!aberto) return;
          if (e.key === "ArrowDown") setAtivo((i) => Math.min(i + 1, sugestoes.length - 1));
          else if (e.key === "ArrowUp") setAtivo((i) => Math.max(i - 1, 0));
          else if (e.key === "Enter" && sugestoes[ativo]) vm.escolherMunicipio(sugestoes[ativo]);
          else return;
          e.preventDefault();
        }}
      />

      {carregando && (
        <div className="px-2 pt-2">
          <LoadingState>Buscando municípios…</LoadingState>
        </div>
      )}

      {aberto && (
        <ul
          id={listaId}
          role="listbox"
          className="mt-1.5 max-h-48 overflow-y-auto rounded-2xl border border-bg-border bg-white py-1"
        >
          {sugestoes.length === 0 && (
            <li className="px-3 py-2 font-geist text-sm text-text-body">
              Nenhum município encontrado.
            </li>
          )}
          {sugestoes.map((m, i) => (
            <li
              key={m.ponto_id}
              id={`${listaId}-${i}`}
              role="option"
              aria-selected={i === ativo}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => vm.escolherMunicipio(m)}
              onMouseEnter={() => setAtivo(i)}
              className={cn(
                "flex cursor-pointer items-center gap-2 px-3 py-2 font-geist text-sm text-text-subtitle",
                i === ativo && "bg-brand-primary/30",
              )}
            >
              <MapPin className="text-brand-secondary" size={16} /> {m.nome}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
