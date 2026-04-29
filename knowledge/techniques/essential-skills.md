# Essential skills — workflow & recon

Not a vuln class. The meta — how to prepare and stay productive.

## scoping discipline
- Read the program brief twice. Note in-scope assets, OOS, severity caps,
  DO-NOT-DO list. Re-read on every session start.
- If unsure, ask the program. Cheaper than getting paused.

## recon checklist (per target — first session, ≤30min)
1. DNS: A/AAAA/CNAME apex + any subdomains in scope.
2. Cert transparency: `crt.sh?q=%25.target.com` → subdomains the company forgot.
3. Wayback: `web.archive.org/web/*/target.com/*` → historic endpoints, deleted features.
4. JS-bundle endpoint mining (see `info-disclosure.md`).
5. `robots.txt`, `sitemap.xml`, `security.txt`, `/.well-known/`.
6. GitHub search: `"target.com" filename:.env`, `"target.com" "AWS_SECRET"`.
7. Public buckets: `target-prod.s3.amazonaws.com`, `target.blob.core.windows.net`.
8. Mobile apps: pull APK, decompile (`apktool`), grep for endpoints/secrets.
9. Stack fingerprint: response headers, source-map presence, framework markers in HTML.
10. List every authenticated feature you can find. Pick 2–3 high-value flows for deep-dive.

## tooling fast-start
- **Burp Suite Pro** (or Caido) — proxy + Repeater + Intruder + extensions.
- Key extensions: HTTP Request Smuggler, Param Miner, Turbo Intruder, Logger++, Autorize, Hackvertor, JWT Editor, InQL.
- **httpx** + **subfinder** + **nuclei** for surface mapping.
- **ffuf** for content discovery.
- **interactsh** / Burp Collaborator for OOB.

## evidence hygiene
- Every confirmed bug → finding file + minimal repro request.
- Use `prowl finding <host> <slug>`.
- Don't paste full bodies — just the diff that proves the bug.

## time discipline
- 90-min timer per goal. If not converging, switch goals or call it.
- One goal per session, not five. Keeps you sharp.

## reporting
- Title: `<vuln class> in <feature> via <vector>`.
- Repro: 1-2-3 numbered steps a triager can copy-paste.
- Impact: concrete, financial / data-scope when possible.
- Fix: specific (e.g. "switch to `mongo-sanitize` 2.x" not "validate input").

## anti-patterns to avoid
- Running automated scanners against a target without explicit allowance.
- Reporting "missing security header" alone — only chain it as part of a real bug.
- Leaving spam in the system: cleanup test users, comments, files.
- Speculative reports — every finding must be reproducible.

## provenance
Distilled from years of public bounty writeups and PortSwigger Essential Skills labs.
