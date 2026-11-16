import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { getRouteApi, useNavigate } from "@tanstack/react-router";
import { perfilStorage } from "@/features/onboarding/services/perfil.storage";
import type { Chip, Estado, Mensagem } from "../models/conversa.model";
import { conversaService } from "../services/conversa.service";
import { entendidoUtil } from "../lib/texto";
import { montarContexto, resumoDoContexto } from "./contexto";

const route = getRouteApi("/_app/maira");

/** Sugestões que a PESSOA escolhe tocar (a Maíra não fala primeiro). */
export const SUGESTOES_INICIAIS: Chip[] = [
  { rotulo: "O que dá para plantar aqui?", texto: "O que dá para plantar aqui?" },
  { rotulo: "Quando devo plantar?", texto: "Quando devo plantar?" },
];

const ASSISTENTE_PADRAO = "Maíra, assistente automática do Sulco (não é uma pessoa nem uma técnica)";

/**
 * ViewModel do chat: o que a pessoa já informou no app (município, solo e clima) vai junto de cada mensagem.
 * Mensagens e `estado` vivem só na memória desta aba; nada é gravado no navegador.
 */
export function useMairaViewModel() {
  const navigate = useNavigate();
  const { de } = route.useSearch();
  const [perfil] = useState(perfilStorage.ler);
  const contexto = perfil ? montarContexto(perfil) : null;

  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [estado, setEstado] = useState<Estado | null>(null);
  const [chips, setChips] = useState<Chip[]>(SUGESTOES_INICIAIS);
  const [assistente, setAssistente] = useState(ASSISTENTE_PADRAO);

  const envio = useMutation({
    mutationFn: (texto: string) => conversaService.enviar(texto, estado, contexto!),
    onSuccess: (r, texto) => {
      setEstado(r.estado);
      setChips(r.chips);
      setAssistente(r.assistente || ASSISTENTE_PADRAO);
      setMensagens((m) => [...m, { papel: "maira", texto: r.resposta, entendido: entendidoUtil(r.entendido, texto), fontes: r.fontes.filter((f) => !f.lacuna) }]);
    },
  });

  const enviar = (texto: string) => {
    const limpo = texto.trim();
    if (!limpo || !contexto || envio.isPending) return;
    setMensagens((m) => [...m, { papel: "usuario", texto: limpo }]);
    envio.mutate(limpo);
  };

  return {
    semPerfil: !perfil,
    sabe: contexto ? resumoDoContexto(contexto) : [],
    mensagens,
    chips,
    assistente,
    enviando: envio.isPending,
    erro: envio.isError,
    // comandos
    enviar,
    voltarAoPlano: () => void navigate({ to: "/", search: de ? { topico: de } : {} }),
    irParaBoasVindas: () => void navigate({ to: "/boas-vindas" }),
  };
}
