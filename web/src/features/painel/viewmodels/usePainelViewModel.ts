import { useState } from "react";
import { getRouteApi, useNavigate } from "@tanstack/react-router";
import { perfilStorage } from "@/features/onboarding/services/perfil.storage";
import { ROTULO_CLIMA, ROTULO_SOLO } from "@/features/onboarding/models/perfil.model";
import { NUMERO_DA_ETAPA } from "@/features/plano/models/plano.model";
import { usePlanoViewModel } from "@/features/plano/viewmodels/usePlanoViewModel";
import { TOPICOS, type TopicoId } from "../models/topicos.model";

const route = getRouteApi("/_app/");

export function usePainelViewModel() {
  const navigate = useNavigate();
  const { topico: id = TOPICOS[0].id } = route.useSearch();
  const [perfil] = useState(perfilStorage.ler);

  const indice = Math.max(
    0,
    TOPICOS.findIndex((t) => t.id === id),
  );
  const topico = TOPICOS[indice]!;

  const irPara = (novo: TopicoId) =>
    void navigate({ to: "/", search: (prev) => ({ ...prev, topico: novo }), replace: true, resetScroll: false });
  const falarComMaira = () => void navigate({ to: "/maira", search: { de: topico.id } });

  // Texto da etapa (plano de plantio do local; a cultura é um exemplo escolhido pelo servidor).
  const solo = perfil && perfil.solo !== "nao_sei" ? perfil.solo : "qualquer"; // o solo que a pessoa informou entra no cálculo
  const plano = usePlanoViewModel(perfil?.municipio.ponto_id ?? null, solo, NUMERO_DA_ETAPA[topico.id]);

  return {
    plano,
    falarComMaira,
    topicos: TOPICOS,
    topico,
    indice,
    total: TOPICOS.length,
    perfil: perfil && {
      municipio: perfil.municipio.nome,
      solo: ROTULO_SOLO[perfil.solo],
      clima: ROTULO_CLIMA[perfil.clima],
    },
    temAnterior: indice > 0,
    temProximo: indice < TOPICOS.length - 1,
    // comandos
    irPara,
    anterior: () => indice > 0 && irPara(TOPICOS[indice - 1]!.id),
    proximo: () => indice < TOPICOS.length - 1 && irPara(TOPICOS[indice + 1]!.id),
    refazerPerguntas: () => {
      perfilStorage.apagar();
      void navigate({ to: "/boas-vindas" });
    },
  };
}
