# API testing — playbook

## when to try
- Always. Modern apps have a thicker API than UI.

## reconnaissance
- **Find the API** — JS bundles (`grep -oE '/api/v[0-9]+/[a-zA-Z0-9_/-]+'`),
  network tab during normal use, mobile app reverse-engineering, third-party
  partner docs, `/swagger.json`, `/openapi.yaml`, `/openapi.json`,
  `/api/swagger`, `/v2/api-docs`, `/redoc`, `/graphql` (introspection).
- **Versions**: try `/api/v1/`, `/api/v2/`, `/api/internal/`, `/api/admin/`, also
  off-by-one (`/api/v3/` may be unfinished and ungated).
- **Methods**: for every endpoint, try GET/POST/PUT/PATCH/DELETE/OPTIONS.
  `OPTIONS` often reveals the full method list.

## bug classes (the big ones)
- BOLA → see `access-control.md`.
- BFLA → see `access-control.md`.
- Mass assignment → see `access-control.md`.
- Excessive data exposure (response leaks fields the UI hides — `password_hash`, `is_admin`, internal IDs).
- Lack of rate limiting on sensitive ops.
- Improper input validation: type confusion, wrong-type wins (`"1"` vs `1`).
- Injection (SQLi/NoSQL/Command) — same as for any input.
- Server-side parameter pollution — duplicate keys: `?role=user&role=admin`.

## confirmation flow
1. Pull the OpenAPI/Swagger if available. Iterate endpoints with two test accounts.
2. For each endpoint:
   - GET → are you returning more than you should?
   - PATCH/PUT → can you set fields the UI can't?
   - DELETE → does it check ownership?
3. Try the same endpoint without auth. Many endpoints "happen to be public".
4. JWT / session token portability — does an old token work after logout? Across orgs?

## exploitation snippet
Endpoint hunt:
```bash
# Mine a JS bundle
curl -sk 'https://t/_next/static/chunks/main-*.js' | grep -oE '"/(api|v[0-9])/[a-zA-Z0-9_/-]+"' | sort -u

# OPTIONS sweep
for ep in /api/v2/users /api/v2/orders /api/v2/admin; do
  echo "$ep:"; curl -sk -X OPTIONS "https://t$ep" -i | grep -i 'allow:'
done
```

## caveats
- Excessive-data-exposure findings often look like info-disclosure but bounty programs treat them seriously when PII is involved.
- Don't enumerate IDs at scale on prod (50 max for confirmation, then stop).

## provenance
OWASP API Top 10 (2023). PortSwigger API Testing labs.
