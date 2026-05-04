import type { ApiEnvelope } from "./types";

export class ApiError extends Error {
  code: string;
  status?: number;

  constructor(code: string, message: string, status?: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        "content-type": "application/json",
        ...(init.headers ?? {})
      }
    });
  } catch (caught) {
    throw new ApiError("NETWORK_ERROR", caught instanceof Error ? caught.message : "Network request failed");
  }
  const payload = await parseEnvelope<T>(response);
  if (!response.ok || payload.error) {
    throw new ApiError(payload.error?.code ?? "HTTP_ERROR", payload.error?.message ?? `Request failed with status ${response.status}`, response.status);
  }
  if (payload.data === null) {
    throw new ApiError("EMPTY_RESPONSE", "API response did not include data", response.status);
  }
  return payload.data;
}

async function parseEnvelope<T>(response: Response): Promise<ApiEnvelope<T>> {
  const text = await response.text();
  if (!text) {
    return { data: null, error: response.ok ? null : { code: "HTTP_ERROR", message: `Request failed with status ${response.status}` }, meta: {} };
  }
  try {
    return JSON.parse(text) as ApiEnvelope<T>;
  } catch {
    return {
      data: null,
      error: { code: "INVALID_RESPONSE", message: response.ok ? "API returned an invalid response" : `Request failed with status ${response.status}` },
      meta: {}
    };
  }
}

export function money(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}
