const DEFAULT_ORIGIN = "https://update.example.com";

export default {
  async fetch(request, env) {
    const src = new URL(request.url);
    const p = src.pathname;
    const origin = (env.UPDATE_ORIGIN || DEFAULT_ORIGIN).replace(/\/+$/, "");

    if (!(p === "/healthz" || p.startsWith("/api/") || p.startsWith("/downloads/"))) {
      return new Response("Not Found", { status: 404 });
    }

    const dst = new URL(p + src.search, origin);
    const proxied = new Request(dst.toString(), request);
    const resp = await fetch(proxied, { redirect: "follow" });

    const out = new Response(resp.body, resp);
    out.headers.set("Cache-Control", "no-store");
    return out;
  },
};
