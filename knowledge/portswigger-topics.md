# PortSwigger Web Security Academy — topic coverage

Source: https://portswigger.net/web-security/all-topics (fetched 2026-04-27)

Status legend: ✅ playbook written | 🟡 stub only | ⬜ not started

| Status | Topic | Playbook | Source |
|---|---|---|---|
| ✅ | SQL injection | techniques/sql-injection.md | /web-security/sql-injection |
| ✅ | XML hex-entity WAF bypass for SQLi | techniques/xml-entity-waf-bypass.md | (lab solved 2026-04-26) |
| ✅ | Authentication bypass | techniques/auth-bypass.md | /web-security/authentication |
| ✅ | Path traversal | techniques/path-traversal.md | /web-security/file-path-traversal |
| ✅ | Command injection | techniques/command-injection.md | /web-security/os-command-injection |
| ✅ | Business logic flaws | techniques/business-logic.md | /web-security/logic-flaws |
| ✅ | Information disclosure | techniques/info-disclosure.md | /web-security/information-disclosure |
| ✅ | Access control / IDOR / BOLA | techniques/access-control.md | /web-security/access-control |
| ✅ | File upload vulns | techniques/file-upload.md | /web-security/file-upload |
| ✅ | Race conditions | techniques/race-conditions.md | /web-security/race-conditions |
| ✅ | SSRF | techniques/ssrf.md | /web-security/ssrf |
| ✅ | XXE | techniques/xxe.md | /web-security/xxe |
| ✅ | NoSQL injection | techniques/nosql-injection.md | /web-security/nosql-injection |
| ✅ | API testing | techniques/api-testing.md | /web-security/api-testing |
| ✅ | Web cache deception | techniques/web-cache-deception.md | /web-security/web-cache-deception |
| ✅ | XSS | techniques/xss.md | /web-security/cross-site-scripting |
| ✅ | CSRF | techniques/csrf.md | /web-security/csrf |
| ✅ | CORS | techniques/cors.md | /web-security/cors |
| ✅ | Clickjacking | techniques/clickjacking.md | /web-security/clickjacking |
| ✅ | DOM-based vulns | techniques/dom-based.md | /web-security/dom-based |
| ✅ | WebSockets | techniques/websockets.md | /web-security/websockets |
| ✅ | Insecure deserialization | techniques/deserialization.md | /web-security/deserialization |
| ✅ | Web LLM attacks | techniques/llm-attacks.md | /web-security/llm-attacks |
| ✅ | GraphQL | techniques/graphql.md | /web-security/graphql |
| ✅ | SSTI | techniques/ssti.md | /web-security/server-side-template-injection |
| ✅ | Web cache poisoning | techniques/web-cache-poisoning.md | /web-security/web-cache-poisoning |
| ✅ | HTTP Host header attacks | techniques/host-header.md | /web-security/host-header |
| ✅ | HTTP request smuggling | techniques/request-smuggling.md | /web-security/request-smuggling |
| ✅ | OAuth attacks | techniques/oauth.md | /web-security/oauth |
| ✅ | JWT attacks | techniques/jwt.md | /web-security/jwt |
| ✅ | Prototype pollution | techniques/prototype-pollution.md | /web-security/prototype-pollution |
| ✅ | Essential skills (recon, scoping) | techniques/essential-skills.md | /web-security/essential-skills |

**Total: 32/32 ✅**

## How to extend
- New target's stack is unusual → add `knowledge/by-stack/<stack>.md`.
- Discovered a novel technique mid-hunt → add a new `techniques/<slug>.md`.
- Lab class added by PortSwigger → re-run the topic fetch and write new playbook.

## How playbooks are structured
1. **When to try** — fingerprint signals.
2. **Key bypass tricks / archetypes** — distinct techniques.
3. **Confirmation flow** — minimum requests to confirm vs kill.
4. **Curl / Python snippet** — copy-pasteable.
5. **Caveats** — false positives, scope/safety.
6. **Provenance** — source labs / public reports.
