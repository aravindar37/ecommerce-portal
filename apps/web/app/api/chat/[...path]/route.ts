import { NextRequest } from "next/server";
import { proxyApi } from "@/lib/proxy";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyApi(request, "chat", (await context.params).path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyApi(request, "chat", (await context.params).path);
}
