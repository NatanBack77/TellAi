import type { z } from "zod";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown; timeoutMs?: number };

/**
 * Faz a requisição e valida a resposta com o schema zod do Model.
 * Se o back-end mudar o contrato, o erro aparece aqui, não no meio da tela.
 */
export async function request<S extends z.ZodType>(
  path: string,
  schema: S,
  { body, timeoutMs = 30_000, headers, signal, ...init }: RequestOptions = {},
): Promise<z.infer<S>> {
  const timeout = AbortSignal.timeout(timeoutMs);
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    headers: {
      Accept: "application/json",
      ...(body !== undefined && { "Content-Type": "application/json" }),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new ApiError(response.status, `Falha ao chamar ${path} (${response.status})`);
  }
  return schema.parse(await response.json());
}

export const http = {
  get: <S extends z.ZodType>(path: string, schema: S, opts?: RequestOptions) =>
    request(path, schema, { ...opts, method: "GET" }),
  post: <S extends z.ZodType>(path: string, schema: S, body: unknown, opts?: RequestOptions) =>
    request(path, schema, { ...opts, method: "POST", body }),
};
