const ORIGIN = "https://bomanaupdate.ruikang.wang";

export default {
  async fetch(request) {
    const src = new URL(request.url);
    const p = src.pathname;

    if (!(p === "/healthz" || p.startsWith("/api/"))) {
      return new Response("Not Found", { status: 404 });
    }

    const dst = new URL(p + src.search, ORIGIN);
    const proxied = new Request(dst.toString(), request);
    const resp = await fetch(proxied, { redirect: "follow" });

    const out = new Response(resp.body, resp);
    out.headers.set("Cache-Control", "no-store");
    return out;
  },
};
