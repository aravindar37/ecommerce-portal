import { NextRequest } from "next/server";
import { proxyImage } from "@/lib/proxy";

interface RouteContext {
  params: Promise<{ filename: string }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyImage(request, (await context.params).filename);
}
