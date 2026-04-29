# Web cache poisoning — playbook

Cousin of cache deception. Here YOU poison the cache so OTHER users get
malicious content.

## when to try
- App is behind Cloudflare / Fastly / Akamai / Varnish / CloudFront / nginx-cache.
- Any page cached at the CDN that reflects a request value (header or param) into the response.

## the technique
1. Find an **unkeyed input** — a header or param the cache ignores when computing the cache key, but the origin reads.
2. Influence the response via that input.
3. Send a request with the malicious input + the URL of a popular page.
4. Cache stores the bad response under the URL's normal cache key.
5. Next visitor → poisoned.

## common unkeyed inputs
- `X-Forwarded-Host`, `X-Forwarded-Scheme`, `X-Original-URL`, `X-Rewrite-URL`.
- `X-Forwarded-For` (sometimes — for geo-personalized content).
- `Host` (tricky — CDNs usually key on it but some setups don't).
- Custom company headers (`X-Country`, `X-Site`, `X-Internal`).

## bug shapes
- **Reflected XSS via cached header**: response body includes `<link href="https://X-Forwarded-Host..."` → set the header to `attacker.com/x.css">` to break out and inject.
- **Open-redirect via Host**: app generates `Location: https://Host/...` after login → poison redirects every user to attacker.
- **Cookie probing**: response varies based on a request header → cache has 1-of-N variants. Also rare but used to probe.
- **Cache deception combo**: see `web-cache-deception.md`.

## confirmation flow
1. Find an URL with `Cache-Control: public` and `X-Cache: HIT` after second request.
2. Probe: send the URL with `X-Forwarded-Host: example.attacker.com`. Look for the value in the response body.
3. If reflected: send the request once with malicious value, then visit the URL incognito and verify the poisoned response.
4. **Clean up**: send a clean request with the correct host until the cache returns clean (or wait for TTL). Ethical practice.

## exploitation snippet
```bash
# Probe for reflected unkeyed inputs
for h in X-Forwarded-Host X-Forwarded-Scheme X-Original-URL X-Rewrite-URL X-Country; do
  printf "=== %s ===\n" "$h"
  curl -sk -H "$h: cb-$RANDOM.example.com" -i https://t/popular-page | grep -i "cb-"
done
```

## caveats
- Programs may forbid actual poisoning (it affects other users). Test on staging or a per-request `Cache-Control: no-cache` if allowed; report once with one PoC, then stop.
- TTLs of 1h+ mean a real-target test could affect many users. Use Burp's *Param Miner* with --no-poison mode if available.

## provenance
James Kettle "Practical Web Cache Poisoning" 2018. PortSwigger Cache Poisoning labs.
