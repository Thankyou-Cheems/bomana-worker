const ORIGIN = "https://bomanaupdate.ruikang.wang";

export default {
  async fetch(request) {
    const src = new URL(request.url);
    const p = src.pathname;

    // 只代理统计相关接口，其他路径直接拒绝
    if (!(p === "/healthz" || p.startsWith("/api/"))) {
      return new Response("Not Found", { status: 404 });
    }

    const dst = new URL(p + src.search, ORIGIN);
    const proxiedReq = new Request(dst.toString(), request);
    const resp = await fetch(proxiedReq, { redirect: "follow" });

    // 接口不缓存
    const out = new Response(resp.body, resp);
    out.headers.set("Cache-Control", "no-store");
    return out;
  },
};
