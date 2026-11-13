export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const BACKEND_HOST = "seatsurge-7mp2.onrender.com";
    const BACKEND_ORIGIN = `https://${BACKEND_HOST}`;
    const BACKEND_WS = `wss://${BACKEND_HOST}`;

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Session-ID, Idempotency-Key, X-Admission-Token, X-Internal-Token",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    // 1. WebSocket routing: /ws/*
    if (url.pathname.startsWith("/ws")) {
      const targetWsUrl = `${BACKEND_WS}${url.pathname}${url.search}`;
      const wsHeaders = new Headers(request.headers);
      wsHeaders.set("Host", BACKEND_HOST);

      return fetch(targetWsUrl, {
        method: request.method,
        headers: wsHeaders,
      });
    }

    // 2. API routing: /api/*, /health, /docs, /openapi.json
    if (
      url.pathname.startsWith("/api/") ||
      url.pathname === "/health" ||
      url.pathname.startsWith("/docs") ||
      url.pathname === "/openapi.json"
    ) {
      const targetApiUrl = `${BACKEND_ORIGIN}${url.pathname}${url.search}`;
      const apiHeaders = new Headers(request.headers);
      apiHeaders.set("Host", BACKEND_HOST);

      const response = await fetch(targetApiUrl, {
        method: request.method,
        headers: apiHeaders,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "follow",
      });

      const responseHeaders = new Headers(response.headers);
      responseHeaders.set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
      responseHeaders.set("Access-Control-Allow-Origin", "*");
      responseHeaders.set("Access-Control-Allow-Headers", "*");

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders,
      });
    }

    // 3. Static Assets & SPA routing
    return env.ASSETS.fetch(request);
  },
};
