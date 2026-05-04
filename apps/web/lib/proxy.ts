import { NextRequest, NextResponse } from "next/server";

type ServiceName = "core" | "search" | "chat";

const baseUrls: Record<ServiceName, string> = {
  core: process.env.CORE_SERVICE_BASE_URL ?? "http://localhost:4000",
  search: process.env.SEARCH_SERVICE_BASE_URL ?? "http://localhost:4001",
  chat: process.env.CHAT_SERVICE_BASE_URL ?? "http://localhost:4002"
};

function targetUrl(service: ServiceName, path: string[], search: string): string {
  const cleanPath = path.map(encodeURIComponent).join("/");
  return `${baseUrls[service].replace(/\/$/, "")}/api/${cleanPath}${search}`;
}

export async function proxyApi(request: NextRequest, service: ServiceName, path: string[]): Promise<NextResponse> {
  if (service === "core" && (path[0] === "admin" || path[0] === "test")) {
    return NextResponse.json(
      { data: null, error: { code: "NOT_FOUND", message: "Endpoint is not available through the public web proxy" }, meta: {} },
      { status: 404 }
    );
  }
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const cookie = filteredCookieHeader(request, service);
  if (contentType) headers.set("content-type", contentType);
  if (cookie) headers.set("cookie", cookie);
  if (service === "chat" && process.env.CHAT_SERVICE_INTERNAL_TOKEN) {
    headers.set("x-service-token", process.env.CHAT_SERVICE_INTERNAL_TOKEN);
  }
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();
  const upstream = await fetch(targetUrl(service, path, request.nextUrl.search), {
    method: request.method,
    headers,
    body,
    redirect: "manual"
  });
  const responseBody = await upstream.arrayBuffer();
  const response = new NextResponse(responseBody, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json"
    }
  });
  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) response.headers.set("set-cookie", setCookie);
  return response;
}

function filteredCookieHeader(request: NextRequest, service: ServiceName): string {
  if (service === "search") return "";
  const allowed = service === "chat" ? new Set(["core_session"]) : new Set(["core_session", "core_anonymous_id"]);
  return request.cookies
    .getAll()
    .filter((cookie) => allowed.has(cookie.name))
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
}

export async function proxyImage(request: NextRequest, filename: string): Promise<NextResponse> {
  const upstream = await fetch(`${baseUrls.core.replace(/\/$/, "")}/product-images/${encodeURIComponent(filename)}`, {
    headers: { cookie: request.headers.get("cookie") ?? "" }
  });
  const body = await upstream.arrayBuffer();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "image/jpeg",
      "cache-control": "public, max-age=3600"
    }
  });
}
