import { NextRequest, NextResponse } from "next/server";

interface Envelope<T> {
  data: T | null;
  error: { code: string; message: string } | null;
  meta?: Record<string, unknown>;
}

const coreBaseUrl = process.env.CORE_SERVICE_BASE_URL ?? "http://localhost:4000";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const form = await request.formData();
  const name = String(form.get("name") ?? "");
  const email = String(form.get("email") ?? "");
  const password = String(form.get("password") ?? "");

  const register = await postCore("/api/auth/register", { name, email, password }, request.headers.get("cookie") ?? "");
  if (!register.response.ok || register.payload.error) {
    return redirectWithError(request, "/register", register.payload.error?.message ?? "Unable to create account");
  }

  const login = await postCore("/api/auth/login", { email, password }, request.headers.get("cookie") ?? "");
  if (!login.response.ok || login.payload.error) {
    return redirectWithError(request, "/login", login.payload.error?.message ?? "Account created. Please sign in.");
  }

  const loginCookie = login.response.headers.get("set-cookie") ?? "";
  const mergeCookie = [request.headers.get("cookie") ?? "", cookiePair(loginCookie)].filter(Boolean).join("; ");
  const merge = await postCore("/api/cart/merge", {}, mergeCookie);

  const response = NextResponse.redirect(new URL("/products", request.url), 303);
  appendSetCookie(response, loginCookie);
  appendSetCookie(response, merge.response.headers.get("set-cookie"));
  return response;
}

async function postCore<T>(path: string, body: unknown, cookie: string): Promise<{ response: Response; payload: Envelope<T> }> {
  const headers = new Headers({ "content-type": "application/json" });
  if (cookie) headers.set("cookie", cookie);
  const response = await fetch(`${coreBaseUrl.replace(/\/$/, "")}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    redirect: "manual"
  });
  const text = await response.text();
  const payload = text
    ? (JSON.parse(text) as Envelope<T>)
    : { data: null, error: response.ok ? null : { code: "HTTP_ERROR", message: `Request failed with status ${response.status}` } };
  return { response, payload };
}

function redirectWithError(request: NextRequest, path: string, message: string): NextResponse {
  const url = new URL(path, request.url);
  url.searchParams.set("error", message);
  return NextResponse.redirect(url, 303);
}

function appendSetCookie(response: NextResponse, value: string | null): void {
  if (value) response.headers.append("set-cookie", value);
}

function cookiePair(setCookie: string): string {
  return setCookie.split(";")[0] ?? "";
}
