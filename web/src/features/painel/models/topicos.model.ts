/**
 * Model: as 10 etapas do guia de plantio. Cada uma tem uma cena 3D própria.
 * Os textos aqui são só a abertura do tópico; o conteúdo do local vem da IA (lado esquerdo).
 * Regra do produto: nada de número inventado nem promessa de colheita.
 */
export const TOPICOS = [
  {
    id: "introducao",
    titulo: "Introdução ao Plantio",
    resumo: "Um panorama do que vamos ver: do preparo da terra até guardar a colheita.",
  },
  {
    id: "recomendacao",
    titulo: "Recomendação de Plantação",
    resumo: "Quais culturas combinam com o seu solo, o seu clima e a janela do zoneamento.",
  },
  {
    id: "clima",
    titulo: "Clima e Época de Plantio",
    resumo: "Quando a chuva costuma chegar no seu local e qual a melhor janela para plantar.",
  },
  {
    id: "preparo-solo",
    titulo: "Preparação do Solo",
    resumo: "Como abrir os sulcos e cuidar da terra para guardar água e evitar erosão.",
  },
  {
    id: "semeadura",
    titulo: "Semeadura e Plantio",
    resumo: "Profundidade, espaçamento e o momento certo de colocar a semente na terra.",
  },
  {
    id: "irrigacao",
    titulo: "Irrigação e Cuidados com a Água",
    resumo: "Como aproveitar cada gota: quando molhar e como não desperdiçar água.",
  },
  {
    id: "adubacao",
    titulo: "Adubação e Nutrição",
    resumo: "O que a planta precisa tirar do solo e como devolver esses nutrientes.",
  },
  {
    id: "manutencao",
    titulo: "Desenvolvimento e Manutenção",
    resumo: "Acompanhar o crescimento, controlar o mato e ficar de olho em pragas.",
  },
  {
    id: "colheita",
    titulo: "Colheita",
    resumo: "Os sinais de que está na hora de colher e como colher sem perder produção.",
  },
  {
    id: "pos-colheita",
    titulo: "Pós-colheita e Armazenamento",
    resumo: "Secar, limpar e guardar bem para a colheita durar e não estragar.",
  },
] as const;

export type Topico = (typeof TOPICOS)[number];
export type TopicoId = Topico["id"];

export const IDS_TOPICOS = TOPICOS.map((t) => t.id) as [TopicoId, ...TopicoId[]];
