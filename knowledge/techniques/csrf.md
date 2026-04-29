# CSRF — playbook

## when to try
- Any state-changing endpoint (POST/PUT/PATCH/DELETE) that uses cookie-based auth.
- "Update email", "change password" (legacy ones not requiring current password), "buy", "transfer", "invite".

## defenses to bypass
- **Token absent** → trivial CSRF.
- **Token present but not validated** → drop the token, request still succeeds.
- **Token tied to user A but submitted with B's session** → cross-user token reuse.
- **Token sent in custom header only when present** → if absent, server falls back to "OK".
- **Origin/Referer check**:
  - Strict allowlist → bypass via subdomain takeover, open-redirect on the same origin, or whitelisted CDN.
  - `Origin: null` accepted → use sandbox iframe (`<iframe sandbox=allow-forms ...>`) which sends `null`.
  - Substring match: server checks `Referer` contains `target.com` → host on `target.com.attacker.com`.
- **SameSite=Lax** (modern default) — defeats most CSRF for `POST` but NOT for top-level GETs. So `GET-based state change` is back on the table.
- **CORS preflighted** non-simple requests can't be CSRF'd from a different origin BUT `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain` are simple → still possible if backend accepts them.
- **Content-Type sniffing**: backend accepts `text/plain` containing JSON → simple POST → CSRF.

## extra angles
- **CSRF + XSS** on same origin → trivially game-over (use XSS to read token).
- **JSON CSRF** via Flash/HTML form trick: form with two equal-sign tricks → builds JSON body. Mostly historical (Flash dead).
- **GET-state-change** + `<img src=https://t/api/transfer?...>`.
- **Login CSRF**: log victim into attacker's account → they save a credit card → attacker uses it. (HackerOne report family.)

## confirmation flow
1. Build a minimal HTML PoC that submits the request from `attacker.com`.
2. Open in browser logged into target → verify state changed.
3. Document SameSite caveat: Chrome's default treats fresh sessions differently; if SameSite=Lax-by-default, GET-state-change is the path.

## exploitation snippet
PoC HTML:
```html
<form action="https://target/api/email" method="POST" enctype="text/plain">
  <input name='{"email":"attacker@x","x":"' value='"}'>
</form>
<script>document.forms[0].submit()</script>
```

## caveats
- Real bounties for CSRF have collapsed since SameSite-Lax-default. Always check actual cookie attributes.
- Account-deletion CSRF often accepted as Medium even with token — argue "no current password" angle.

## provenance
PortSwigger CSRF labs.
