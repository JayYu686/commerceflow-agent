import { NextRequest } from "next/server";
export const dynamic = "force-dynamic";
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const url = `${process.env.CF_API_URL || "http://127.0.0.1:8000"}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  for (const key of [
    "content-type",
    "cookie",
    "idempotency-key",
    "x-requested-with",
    "last-event-id",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.text(),
      cache: "no-store",
      signal: request.signal,
    });
    const outgoing = new Headers();
    for (const key of [
      "content-type",
      "cache-control",
      "set-cookie",
      "x-accel-buffering",
    ]) {
      const value = response.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return Response.json(
      {
        code: "api_unavailable",
        message: "后端服务暂不可用，请检查启动状态。",
      },
      { status: 502 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
