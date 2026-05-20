# Hasura GraphQL Engine — stack notes

Source: redscan pack (hasura v1.0.0). Use when target runs Hasura.

## Fingerprinting

- Response header: `x-hasura-version: <semver>`
- Endpoint: `/v1/graphql`, `/v2/query`, `/v1/metadata`
- Error messages: `"path": "$", "error": "not a valid hasura error"`
- Introspection reveals Hasura-style table names (`users`, `orders` etc. as root query fields)

## Critical invariants to test

### hasura_admin_secret_exposed (Critical)
Admin secret must not be accepted without it being set.
```
POST /v1/graphql
X-Hasura-Admin-Secret: (omit header entirely)
{"query":"{ __schema { queryType { name } } }"}
# If introspection works → admin access without auth. Critical.
```

### hasura_metadata_api_auth (Critical)
Metadata API must require admin secret.
```
POST /v1/metadata
Content-Type: application/json
{"type":"export_metadata","args":{}}
# Expect 401/403. If 200 with full schema → unauthenticated metadata access.
```

### hasura_row_level_security (Critical)
Row-level permissions must isolate users.
```
# Authenticated as user A, query rows owned by user B:
POST /v1/graphql
Authorization: Bearer <user_A_token>
{"query":"{ orders(where:{user_id:{_eq:\"<user_B_id>\"}}) { id total } }"}
# Expect empty result or 403. If user B's orders returned → RLS broken.
```

### hasura_permission_boundary (High)
Column-level permissions must block restricted fields.
```
POST /v1/graphql
Authorization: Bearer <low_priv_token>
{"query":"{ users { id email password_hash secret_key } }"}
# Expect: restricted columns to be absent or error. If returned → column permission bypass.
```

### hasura_subscription_auth (High)
WebSocket subscriptions must enforce the same authz as queries.
```
# Open WS to /v1/graphql, send connection_init with expired/invalid JWT:
{"type":"connection_init","payload":{"headers":{"Authorization":"Bearer <expired>"}}}
# Then send subscription. If data streams → subscription auth not enforced.
```

### hasura_remote_schema_traversal (Medium)
Remote schema stitching must not expose internal services.
```
# Introspect to find remote schema types, then try to reach internal endpoints:
POST /v1/graphql
{"query":"{ internal_service { admin_data { secret } } }"}
# Any internal data via remote schema = SSRF-adjacent finding.
```

## Misconfig patterns

- **Introspection in prod** — query `{__schema{queryType{name}}}` without admin secret. If responds → enabled.
- **Dev mode in prod** — errors include `"query":` or `"generated_sql":` in response body.
- **Weak admin secret** — try common values: `hasura`, `secret`, `admin`, `password`, `<app_name>`.

## Key endpoints (sinks)

| Endpoint | Method | Notes |
|---|---|---|
| `/v1/graphql` | POST | Main query/mutation endpoint |
| `/v1/metadata` | POST | Schema/permission management (admin only) |
| `/v2/query` | POST | Raw SQL execution endpoint (admin only) |
| `/healthz` | GET | Liveness probe — leaks version |

## Chaining notes

- Admin secret in env var leak → full DB read/write via `/v2/query` (raw SQL)
- RLS bypass + column permission bypass = full data dump as low-priv user
- Remote schema traversal → SSRF to internal metadata endpoint (e.g., AWS 169.254.169.254)
- Introspection enabled → discover all tables/mutations → enumerate IDOR targets
