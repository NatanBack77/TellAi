import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { municipiosQueryOptions } from "@/features/municipios/viewmodels/municipiosQuery";
import { filtrarMunicipios } from "@/features/municipios/viewmodels/filtrarMunicipios";
import { nomeCurto } from "@/features/municipios/models/municipio.model";
import { RASCUNHO_VAZIO, type Clima, type RascunhoPerfil, type Solo } from "../models/perfil.model";
import { perfilStorage } from "../services/perfil.storage";
import { ETAPAS, etapaCompleta, podeIrPara } from "./etapas";

const MAX_SUGESTOES = 8;

export function useOnboardingViewModel() {
  const navigate = useNavigate();
  const [nav, setNav] = useState({ indice: 0, direcao: 1 as 1 | -1 });
  const { indice, direcao } = nav;
  const setIndice = (alvo: number) =>
    setNav((n) => ({ indice: alvo, direcao: alvo >= n.indice ? 1 : -1 }));
  const [rascunho, setRascunho] = useState<RascunhoPerfil>(RASCUNHO_VAZIO);
  const [busca, setBusca] = useState("");

  const etapa = ETAPAS[indice]!;
  const municipiosQuery = useQuery({ ...municipiosQueryOptions(), enabled: indice >= 1 });

  const sugestoes = useMemo(
    () => filtrarMunicipios(municipiosQuery.data ?? [], busca).slice(0, MAX_SUGESTOES),
    [municipiosQuery.data, busca],
  );

  const irPara = (alvo: number) => {
    if (podeIrPara(alvo, rascunho)) setIndice(alvo);
  };

  const concluir = () => {
    const { municipio, solo, clima } = rascunho;
    if (!municipio || !solo || !clima) return;
    perfilStorage.salvar({
      versao: 2,
      municipio,
      solo,
      clima,
      concluidoEm: new Date().toISOString(),
    });
    void navigate({ to: "/", replace: true });
  };

  return {
    // estado
    etapa,
    indice,
    /** 1 = avançando, -1 = voltando (para a direção da animação). */
    direcao,
    rascunho,
    /** Posição no stepper (etapa "boas-vindas" não aparece nele). */
    passoStepper: indice - 1,
    podeVoltar: indice > 0,
    podeAvancar: etapaCompleta(etapa, rascunho),
    municipio: {
      busca,
      sugestoes,
      carregando: municipiosQuery.isPending,
      erro: municipiosQuery.isError,
    },
    // comandos
    voltar: () => setIndice(Math.max(0, indice - 1)),
    avancar: () => (etapa === "fim" ? concluir() : irPara(indice + 1)),
    /** Recebe a posição do stepper (0 = Município). */
    irParaPasso: (passo: number) => irPara(passo + 1),
    podeIrParaPasso: (passo: number) => podeIrPara(passo + 1, rascunho),
    buscarMunicipio: (q: string) => {
      setBusca(q);
      // Mudou o texto depois de escolher: a escolha anterior deixa de valer.
      if (rascunho.municipio) setRascunho((r) => ({ ...r, municipio: null }));
    },
    escolherMunicipio: (m: { ponto_id: string; nome: string }) => {
      const nome = nomeCurto(m);
      setRascunho((r) => ({ ...r, municipio: { ponto_id: m.ponto_id, nome } }));
      setBusca(nome);
    },
    escolherSolo: (solo: Solo) => setRascunho((r) => ({ ...r, solo })),
    escolherClima: (clima: Clima) => setRascunho((r) => ({ ...r, clima })),
    tentarDeNovo: () => municipiosQuery.refetch(),
  };
}

export type OnboardingViewModel = ReturnType<typeof useOnboardingViewModel>;
