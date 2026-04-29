# {{HOST}} — target brief
created: {{DATE}}

> Fill in the [TODO] blocks before the first hunt. Edits compound — keep this file
> as the single source of truth for scope and intent.

## program
- platform: [TODO hackerone | bugcrowd | intigriti | private | self-host]
- url: [TODO https://hackerone.com/example]
- bounty range: [TODO $low–$high]
- response time: [TODO 1–7d]

## scope (in)
- [TODO list every host/path/wildcard explicitly authorized]

## out of scope (HARD)
- [TODO any subdomain/path that is OUT — list explicitly. If unsure, treat as out.]
- typical: marketing pages, third-party SaaS, *.staging.*, anything ending in -uat

## auth
- accounts: [TODO none | self-register | provided creds]
- credentials: [TODO email:pass — never commit real ones; keep in session.txt instead]
- mfa: [TODO no | totp | webauthn]
- session capture: [TODO populate session.txt with cookies/headers from a logged-in browser]

## prior intel
- known stack: [TODO laravel / rails / next.js / unknown]
- known endpoints: [TODO list any you've already noticed]
- features: [TODO main flows — cart, oauth, file upload, admin panel, etc.]
- existing reports: [TODO links to public reports if any]

## what NOT to test
- destructive: [TODO delete account, password reset, payment]
- noisy: [TODO no aggressive fuzz / no nuclei aggressive / no scanner UA]

## hunting goals (priority order)
1. [TODO e.g. cross-tenant data access]
2. [TODO e.g. account takeover via oauth]
3. [TODO e.g. payment / pricing logic abuse]

## ground rules
- single-target rate limit: max 5 req/sec, back off on 429.
- store every probe in log.jsonl (one json object per request/response).
- write a finding file the moment evidence is repeatable — not before.
- if a request looks scope-adjacent, STOP and ask the operator.
