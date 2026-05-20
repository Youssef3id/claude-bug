# Auth0 — stack notes

Source: redscan pack (auth0 v1.0.0). Use when target uses Auth0 for identity.

## Fingerprinting

- OIDC config URL contains `auth0.com` in issuer
- Response headers: `x-auth0-requestid`
- Tokens: JWT `iss` field = `https://<tenant>.auth0.com/`

## Critical invariants to test

### auth0_wildcard_callback (Critical)
Callback URLs must not use wildcards or overly broad patterns.
```
# Register app callback to https://attacker.com and attempt authorization
GET /authorize?response_type=code&client_id=<id>&redirect_uri=https://attacker.com&scope=openid
# Expect: 400 redirect_uri mismatch. If 302 → redirect_uri open redirect = ATO.
```

### auth0_mfa_bypass (Critical)
MFA enrollment verification must not be skippable via API manipulation.
```
POST /oauth/token
{"grant_type":"http://auth0.com/oauth/grant-type/mfa-otp","client_id":"...","mfa_token":"invalid_token","otp":"000000"}
# Watch for error message disclosure, fallback to password-only, or token issued without MFA.
```

### auth0_tenant_isolation (Critical)
Users from Tenant A must not read Tenant B data.
```
GET /api/v2/users/<tenant_B_user_id>  (with Tenant A M2M token)
# Expect 403. If 200 → cross-tenant IDOR.
```

### auth0_pkce_required (High)
SPA/mobile apps must not support implicit flow.
```
GET /authorize?response_type=token&client_id=<spa_client_id>&redirect_uri=<uri>&scope=openid
# Expect: error=unsupported_response_type. If access_token in fragment → implicit enabled → token theft risk.
```

### auth0_refresh_token_rotation (High)
Refresh token reuse must trigger family invalidation.
```
POST /oauth/token  {"grant_type":"refresh_token","refresh_token":"<old_token>"}
# Use the same refresh token a second time after rotation.
# Expect: 400 invalid_grant. If new tokens issued → reuse not detected.
```

### auth0_management_api_scope (High)
M2M tokens must be scoped — test scope creep.
```
# Get M2M token with narrow scope (e.g., read:users)
POST /api/v2/users/<id>  PATCH  (requires update:users scope)
# Expect 403. If 200 → over-privileged M2M token.
```

## Key endpoints (sinks)

| Endpoint | Method | Key params |
|---|---|---|
| `/oauth/token` | POST | grant_type, client_id, client_secret, code, redirect_uri, refresh_token |
| `/authorize` | GET | response_type, client_id, redirect_uri, scope, state, nonce |
| `/api/v2/users` | GET | q, search_engine, include_totals, fields |

## Misconfig patterns

- **Client secret in SPA** — find the JS bundle, grep for `clientSecret`. Secret in public client = critical.
- **Brute-force protection disabled** — POST /oauth/token 10x with wrong password → no lockout = missing protection.
- **Log retention < 30 days** — info from tenant settings; affects incident response capability.

## Chaining notes

- Wildcard callback + PKCE disabled = account takeover without user interaction (chain: open redirect → token theft)
- Tenant isolation bug + M2M token = cross-org data dump
- MFA bypass + refresh token reuse = persistent session after forced logout
