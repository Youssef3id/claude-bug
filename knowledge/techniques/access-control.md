# Access control / IDOR / BOLA — playbook

The bread-and-butter of bug-bounty. Most critical bugs in the last 5 years
were access-control issues, not memory corruption.

## when to try
- Always. Every authenticated endpoint that takes an ID, name, slug, or token.
- Especially: `/api/v*/{org_id}/...`, `/users/{id}`, `/files/{uuid}`,
  `/projects/{slug}`, `/admin/...`, multi-tenant SaaS apps.
- Watch for "viewer-vs-editor-vs-admin" role separation in the UI — bugs hide
  in the gaps where the backend trusts the frontend's hidden actions.

## key bug classes
- **IDOR (horizontal)**: replace your-id with another user's id, get their data.
- **BOLA (Broken Object-Level Auth)** = IDOR for APIs.
- **Vertical privilege escalation**: member calls owner-only endpoint succeeds.
- **BFLA (Broken Function-Level Auth)**: the function exists but isn't gated;
  e.g. `POST /api/users/123/promote` returns 200 for non-admins.
- **Forced browsing**: admin pages reachable without UI link (`/admin`, `/internal`, `/_next/`, source-mapped paths).
- **Mass assignment**: `PATCH /users/me {role: "admin"}` — backend doesn't whitelist updatable fields.
- **Indirect ID leak**: response includes `internal_id` that's then accepted as input on another endpoint.

## confirmation flow
1. **Two accounts.** Always. Account A and Account B in the same org (and a third in a *different* org, if multi-tenant).
2. From A: log in, do a normal action (create a thing). Capture A's request.
3. Replay the same request as B (different cookies/JWT). Outcome:
   - 200 with A's data → IDOR confirmed.
   - 200 with B's view → expected (the system rebuilt context from B's session).
   - 403 → good gate.
4. From the `different-org` account: replay → expect 403/404. 200 = cross-tenant.
5. **Method swap**: GET that returns 200 → try PATCH/DELETE. Often only GET is gated.
6. **HTTP verb tampering**: 403 on POST → try `X-HTTP-Method-Override: POST` with a GET, or PUT/PATCH instead.
7. **Header tricks**: add `X-Original-URL: /admin/...`, `X-Rewrite-URL: /admin/...`, `X-Forwarded-For: 127.0.0.1`. Some routers honor these.
8. **Path tricks**: trailing `/`, `;`, `..;`, `%2e%2e`, double-encoding, `;jsessionid=`.

## exploitation snippet
```bash
# IDOR diff — script the two-account replay
A='Cookie: session=A'
B='Cookie: session=B'
URL='https://target/api/v2/users/{ID}/orders'
for id in $(seq 1 50); do
  url="${URL/\{ID\}/$id}"
  ra=$(curl -sk -o /dev/null -w '%{http_code} %{size_download}' -H "$A" "$url")
  rb=$(curl -sk -o /dev/null -w '%{http_code} %{size_download}' -H "$B" "$url")
  [ "$ra" = "$rb" ] && [ "${ra:0:1}" = "2" ] && echo "$id : $ra/$rb"
done
```

Mass-assignment probe:
```bash
curl -sk -X PATCH https://target/api/users/me -H "$A" -H 'Content-Type: application/json' \
  -d '{"role":"admin","email":"a@b.c","is_verified":true,"organization_id":"<other-org>"}' -i | head
```

## caveats
- Test the *destructive* endpoints LAST and only in your own data. DELETE-then-IDOR can wipe a real user's account.
- Some APIs return 200 with empty/redacted data — read the body, not the status.
- "GraphQL" hides everything in one URL — IDOR appears as field-level: `query { user(id:"OTHER") { email } }`. Test every variable.

## provenance
- PortSwigger Access Control labs.
- Public: GitLab arbitrary file read via path traversal in import (CVE-2020-10977),
  Shopify partner IDOR (multiple), Facebook horizontal-priv-esc cases.
