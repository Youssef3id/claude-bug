# HTTP request smuggling — playbook

## when to try
- Front-end + back-end pair (CDN/LB/proxy + origin app server). Both must
  parse HTTP slightly differently for smuggling to work.
- Tells: CDN headers (`CF-RAY`, `X-Akamai-Edgescape`, `X-Amzn-Trace-Id`),
  `Server: cloudflare`/`nginx`/`varnish` vs the origin language.
- HTTP/2 → HTTP/1.1 downgrade is the modern boom-zone (h2c smuggling, h2.cl/h2.te).

## the variants
- **CL.TE**: front-end uses `Content-Length`, back-end uses `Transfer-Encoding: chunked`.
- **TE.CL**: opposite.
- **TE.TE**: both use TE but one is fooled by obfuscated header (`Transfer-encoding : chunked`, `Transfer-Encoding\x0bchunked`, `transfer-encoding: identity`).
- **H2.CL/H2.TE** (HTTP/2 downgrade smuggling): inject `Content-Length` or `Transfer-Encoding` via H2 pseudo-headers → back-end sees H1 ambiguity.
- **H2.0** (CL=0 smuggling): H2 implicit content-length = 0; back-end H1 parses extra bytes as next request.
- **H2 request line injection**: inject `\r\n` into pseudo headers → smuggle a fake request.

## impact
- Bypass front-end auth: smuggled request reaches back-end without going through ACL.
- Cache poisoning: smuggled request poisons the response delivered to next user.
- XSS via stolen requests: smuggled prefix forces back-end to respond to NEXT user's request with attacker-chosen body.

## confirmation flow (Burp Repeater Turbo Intruder is fastest)
- Use the Smuggler / HTTP Request Smuggler Burp extension. It has timing-based probes.
- For H2 downgrade: Turbo Intruder template `http2-tunneller.py`.
- For TE.CL/CL.TE: `Smuggler.py` Python tool.

CL.TE probe (timing):
```
POST / HTTP/1.1
Host: t
Content-Length: 4
Transfer-Encoding: chunked

1
A
X
```
If front-end honors CL=4, it forwards `1\r\nA\r\nX`. Back-end sees TE chunked, reads `1\r\nA\r\n`, then waits for next chunk → 30s timeout = positive signal.

## exploitation snippet
After confirming TE.CL, smuggle a request that hijacks the next user's response:
```
POST / HTTP/1.1
Host: t
Content-Length: 4
Transfer-Encoding: chunked

5c
GPOST /admin HTTP/1.1
Host: t
Cookie: ?

0

```

## caveats
- This is **dangerous on real targets**. A confirmed smuggle can break legit users' requests. Some programs explicitly forbid live smuggling tests.
- Use timing-only probes for confirmation; report immediately with H1 raw and stop.

## provenance
James Kettle "HTTP Desync Attacks" 2019, "Browser Powered Desync" 2022, "HTTP/2 Request Smuggling" 2021. PortSwigger Smuggling labs.
