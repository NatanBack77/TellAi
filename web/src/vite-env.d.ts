/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Prefixo da API. Padrão: "/api" (proxy do Vite em dev / proxy reverso em produção). */
  readonly VITE_API_BASE_URL?: string;
}
